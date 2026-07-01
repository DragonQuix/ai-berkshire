"""Report Audit Tool for AI Berkshire.

数据抽检工具：从研究报告中抽取15%的财务数据点，与可靠信源比对，
通过则准出，不通过则打回并说明原因。

Zero external dependencies — uses only Python stdlib.
Requires Python >= 3.7.

工作流程（三步）：
  Step 1 — 提取数据点，随机抽样15%：
    python3 tools/report_audit.py extract --report reports/xxx.md

  Step 2 — Claude 对抽检清单中的每个数据点，从可靠信源（macrotrends/
            stockanalysis/aastocks/eastmoney）取数，填入 fetched_value

  Step 3 — 输入核验结果，输出准出/打回判决：
    python3 tools/report_audit.py verdict --results '[...]'

  一步完成（仅提取+打印抽检清单，不做网络验证）：
    python3 tools/report_audit.py extract --report reports/xxx.md --dry-run
"""

import argparse
import json
import math
import os
import re
import sys
from decimal import Decimal, Context, ROUND_HALF_EVEN
from random import Random

_CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)


def _configure_utf8_stdio():
    """Ensure CLI output works in Windows shells with legacy code pages."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (TypeError, ValueError, OSError):
            pass


# ---------------------------------------------------------------------------
# 数据点提取：从 Markdown 报告中识别财务数字
# ---------------------------------------------------------------------------

# 匹配模式：数字 + 单位，前面有上下文标签
# 例：收入：1,239亿元、PE 18.8x、毛利率 56%、市值 ~$5,670亿
_SIGNED_NUM = r'[+\-]?[\d,，\.]+'
_PATTERNS = [
    # 百分比
    (rf'({_SIGNED_NUM})\s*%',                        '%',    'percent'),
    # 亿元/亿美元/亿港元
    (rf'({_SIGNED_NUM})\s*亿(元|美元|港元|RMB|USD|HKD)?', '亿',    'hundred_million'),
    # 倍数 PE/PB/PS
    (rf'({_SIGNED_NUM})\s*[xX倍]',                   'x',    'multiple'),
    # 万亿
    (rf'({_SIGNED_NUM})\s*万亿',                      '万亿', 'trillion'),
    # 美元绝对值（B/T）
    (rf'\$\s*({_SIGNED_NUM})\s*([BMT亿])',             '$',    'usd_abs'),
    # 纯整数（如市值、收入、用户数等，出现在表格 | 里）
    (rf'\|\s*[~约]?\$?({_SIGNED_NUM})\s*\|',          '',     'table_num'),
]

_LABEL_RE = re.compile(
    rf'(?P<label>[^\|\n：:]{{2,25}})[：:\s]+[~约]?\$?(?P<num>{_SIGNED_NUM})\s*(?P<unit>亿[元美港]?元?|万亿|[xX倍]|%|[BMT])?'
)

_TABLE_ROW_RE = re.compile(
    rf'\|\s*(?P<label>[^|]{{1,40}})\s*\|\s*[~约]?\$?(?P<num>{_SIGNED_NUM})\s*(?P<unit>亿[元美港]?元?|万亿|[xX倍]|%|[BMT])?\s*\|'
)


def _clean_num(s: str) -> float:
    """把带逗号、中文逗号的数字字符串转为 float。"""
    s = s.replace(',', '').replace('，', '').strip()
    try:
        return float(s)
    except ValueError:
        return None


def _is_valid_label(label: str) -> bool:
    """判断标签是否是有意义的财务字段名，过滤噪声。"""
    label = label.strip()
    # 太短
    if len(label) < 2:
        return False
    # 纯数字或纯年份
    if re.fullmatch(r'[\d\s年季度Q]+', label):
        return False
    # 以符号/markdown标记开头
    if re.match(r'^[+\-\*#\|~\$>_`]', label):
        return False
    # 含有 markdown 粗体/代码标记
    if '**' in label or '`' in label or '__' in label:
        return False
    # 标签含有纯增速符号（如 +56%、-13% 单独作标签）
    if re.fullmatch(r'[+\-]?\d+(\.\d+)?%', label):
        return False
    # 常见无意义标签
    _SKIP = {'来源', 'sources', 'source', '说明', '注意', '备注', '数据来源',
             'n/a', '—', '-', '/', '合计', 'total', '单位', '趋势'}
    if label.lower() in _SKIP:
        return False
    return True


# 两列表格行：| 标签 | 数值 unit |（专为财务报告的 KV 表设计）
_KV_TABLE_RE = re.compile(
    rf'^\|\s*(?P<label>[^|*\n]{{2,40}}?)\s*\|\s*[~约]?\$?(?P<num>{_SIGNED_NUM})\s*'
    r'(?P<unit>亿[元美港]?元?|万亿|[xX倍]|%|[BMT亿])?\s*[\|（\(]'
)

# 带标签的 KV 行：标签：数值 单位
_KV_LABEL_RE = re.compile(
    r'(?P<label>[\u4e00-\u9fa5A-Za-z][^\|\n：:*]{1,30})[：:]\s*[~约]?\$?'
    rf'(?P<num>{_SIGNED_NUM})\s*(?P<unit>亿[元美港]?元?|万亿|[xX倍]|%|[BMT])?'
)

_CORE_TABLE_KEYWORD_RE = re.compile(
    r'(PE|PB|PS|ROE|ROA|EPS|BVPS|EV/NBV|NBV|内含价值|新业务价值|'
    r'营收|营业收入|收入|收益|归母|净利润|市值|估值|毛利率|净利率|'
    r'现金流|自由现金流|股息率|股息|股利|利润|资产总计|总资产|'
    r'负债合计|总负债|资产负债率)',
    re.I,
)
_NON_CORE_TABLE_HEADER_RE = re.compile(r'(触发条件|自查|修正动作|应对|情景|路径|概率|偏误|压力测试)', re.I)
_NON_AUDITABLE_TABLE_HEADER_RE = re.compile(r'(触发条件|自查项|修正动作|应对|路径|概率)', re.I)
_CALIBER_HEADER_RE = re.compile(r'(口径|来源|source|caliber)', re.I)


def _split_table_cells(line: str) -> list:
    return [
        c.strip().strip('*_').strip()
        for c in line.strip().strip('|').split('|')
    ]


def _table_has_core_metric(headers: list, row_lines: list) -> bool:
    header_text = ' '.join(headers)
    if _NON_CORE_TABLE_HEADER_RE.search(header_text):
        return False
    haystack = ' '.join(headers + row_lines)
    return bool(_CORE_TABLE_KEYWORD_RE.search(haystack))


def _table_has_caliber_header(headers: list) -> bool:
    return any(_CALIBER_HEADER_RE.search(h) for h in headers)


def _table_should_skip_extraction(headers: list) -> bool:
    header_text = ' '.join(headers)
    return bool(_NON_AUDITABLE_TABLE_HEADER_RE.search(header_text))


def _caliber_warning_ranges(lines: list) -> list:
    ranges = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        is_header = '|' in line and not re.match(r'^\|[\-\s\|:]+\|$', line)
        has_sep = i + 1 < len(lines) and re.match(r'^\|[\-\s\|:]+\|$', lines[i + 1].strip())
        if not (is_header and has_sep):
            i += 1
            continue
        headers = [h for h in _split_table_cells(line) if h]
        row_lines = []
        j = i + 2
        while j < len(lines):
            dline = lines[j].strip()
            if not dline or not dline.startswith('|'):
                break
            row_lines.append(dline)
            j += 1
        if _table_has_core_metric(headers, row_lines) and not _table_has_caliber_header(headers):
            ranges.append({
                'start': i + 3,
                'end': j,
                'note': '核心数据表缺少口径/来源列，请补充字段口径、数据来源、币种或单位',
            })
        i = j
    return ranges


def _caliber_warning_for_line(lineno: int, ranges: list):
    for item in ranges:
        if item['start'] <= lineno <= item['end']:
            return item['note']
    return None


def _parse_md_tables(lines: list) -> list:
    """解析 Markdown 中所有表格，返回 (row_label, col_header, value, unit, lineno, raw) 列表。"""
    results = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 检测表头行（含 | 且不是分隔行）
        if '|' in line and not re.match(r'^\|[\-\s\|:]+\|$', line):
            headers_raw = _split_table_cells(line)
            if not headers_raw or any(not h for h in headers_raw):
                i += 1
                continue
            # 下一行应是分隔行
            if i + 1 < len(lines) and re.match(r'^\|[\-\s\|:]+\|$', lines[i+1].strip()):
                skip_table = _table_should_skip_extraction(headers_raw)
                i += 2  # 跳过分隔行
                # 读数据行
                while i < len(lines):
                    dline = lines[i].strip()
                    if not dline or not dline.startswith('|'):
                        break
                    cells = _split_table_cells(dline)
                    if skip_table or len(cells) != len(headers_raw) or len(cells) < 2:
                        i += 1
                        continue
                    row_label = cells[0]
                    for col_idx, cell in enumerate(cells[1:], start=1):
                        col_header = headers_raw[col_idx] if col_idx < len(headers_raw) else f'列{col_idx}'
                        # 提取 cell 中的数字+单位
                        m = re.search(
                            rf'[~约]?\$?({_SIGNED_NUM})\s*(亿[元美港]?元?|万亿|[xX倍]|%|[BMT])?',
                            cell
                        )
                        if m:
                            val = _clean_num(m.group(1))
                            unit = (m.group(2) or '').strip()
                            if val and val != 0 and abs(val) < 1e15:
                                results.append((row_label, col_header, val, unit, i + 1, dline))
                    i += 1
                continue
        i += 1
    return results


def extract_data_points(md_text: str) -> list:
    """从 Markdown 报告中提取所有可识别的财务数据点。

    覆盖三类结构：
      1. 多列 Markdown 表格（最主要的来源）：(行标签 + 列标题) → 数值
      2. 带冒号的 KV 行：标签：数值 单位
      3. 加粗数字行：**数值** 单位

    返回 list of dict：
      {id, label, reported_value, unit, raw_text, line_number}
    """
    points = []
    seen = set()
    lines = md_text.split('\n')
    caliber_ranges = _caliber_warning_ranges(lines)

    def _add(label, val, unit, lineno, raw, caliber_note=None):
        label = re.sub(r'[\*_`]+', '', label).strip()
        if not _is_valid_label(label):
            return
        if val is None or val == 0 or abs(val) > 1e15:
            return
        # 过滤纯年份/季度
        if re.fullmatch(r'(20\d{2}|Q[1-4]|\d{4}\s*Q[1-4])', label.strip()):
            return
        key = f"{label}|{round(val,4)}|{unit}"
        if key in seen:
            return
        seen.add(key)
        point = {
            'id': len(points) + 1,
            'label': label,
            'reported_value': val,
            'unit': unit,
            'raw_text': raw[:120],
            'line_number': lineno,
        }
        if caliber_note:
            point['caliber_column_warning'] = True
            point['caliber_column_note'] = caliber_note
        points.append(point)

    in_code = False

    # --- 1. 多列表格 ---
    for row_label, col_header, val, unit, lineno, raw in _parse_md_tables(lines):
        # 跳过无意义行标签
        if not _is_valid_label(row_label):
            continue
        # 跳过无意义列标题（YoY增速列单独标注，不作为待核验数据）
        if col_header.upper() in ('YOY', 'YOY增速', '增速', '同比', '变化', '趋势', '说明', '备注'):
            continue
        # label = "行标签 · 列标题"（若列标题是行标签的补充）
        if col_header and col_header != row_label:
            label = f"{row_label} · {col_header}"
        else:
            label = row_label
        _add(label, val, unit, lineno, raw, _caliber_warning_for_line(lineno, caliber_ranges))

    # --- 2. KV 冒号行 ---
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code = not in_code
            continue
        if in_code or stripped.startswith('> ') or re.match(r'^#{1,6}\s', stripped):
            continue
        if '|' in stripped:
            continue  # 表格已在上面处理

        for m in _KV_LABEL_RE.finditer(stripped):
            label = m.group('label')
            val = _clean_num(m.group('num'))
            unit = (m.group('unit') or '').strip()
            _add(label, val, unit, lineno, stripped)

    return points


def sample_points(points: list, ratio: float = 0.15, seed: int = None) -> list:
    """随机抽取 ratio 比例的数据点，最少 3 个，最多 30 个。"""
    n = max(3, min(30, math.ceil(len(points) * ratio)))
    n = min(n, len(points))
    rng = Random(seed)
    sampled = rng.sample(points, n)
    # 按行号排序，方便人工比对
    return sorted(sampled, key=lambda p: p['line_number'])


# ---------------------------------------------------------------------------
# 准出/打回判决
# ---------------------------------------------------------------------------

_TOLERANCE = 0.02   # 2% 容差（与 financial-data.md / plan-skill-enhancement §4.3 一致）


def _write_json_output(path: str, payload) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _to_numeric(value):
    """安全转为 float；日期、文本、评级等非数值返回 None。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(',', '').replace('，', '').strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _unit_scale(unit: str):
    """返回数量单位相对 1 的倍率；未知单位返回 None。"""
    text = str(unit or "").strip().lower()
    text = text.replace(" ", "").replace("（", "").replace("）", "")
    if not text:
        return None
    scales = {
        "%": 1.0,
        "x": 1.0,
        "倍": 1.0,
        "万": 1e4,
        "千万": 1e7,
        "亿": 1e8,
        "亿元": 1e8,
        "亿人民币": 1e8,
        "亿港元": 1e8,
        "亿港币": 1e8,
        "亿美元": 1e8,
        "亿美金": 1e8,
        "百万": 1e6,
        "百万元": 1e6,
        "百万港元": 1e6,
        "百万美元": 1e6,
        "million": 1e6,
        "mn": 1e6,
        "m": 1e6,
        "十亿": 1e9,
        "billion": 1e9,
        "bn": 1e9,
        "b": 1e9,
        "千亿": 1e11,
        "万亿": 1e12,
        "trillion": 1e12,
        "tn": 1e12,
        "t": 1e12,
    }
    return scales.get(text)


def _normalize_fetched_unit(value: float, fetched_unit: str, report_unit: str):
    """把 fetched_value 从 fetched_unit 换算到 report_unit。"""
    fetched_scale = _unit_scale(fetched_unit)
    report_scale = _unit_scale(report_unit)
    if fetched_scale is None or report_scale is None:
        return value, ""
    if fetched_scale == report_scale:
        return value, ""
    normalized = value * fetched_scale / report_scale
    note = f"单位换算: {value:.2f} {fetched_unit} → {normalized:.2f} {report_unit}"
    return normalized, note


def _magnitude_ratio(a: float, b: float):
    values = [abs(x) for x in (a, b) if x is not None and abs(x) > 0]
    if len(values) < 2:
        return None
    return max(values) / min(values)


def _unit_gap_warning(reported: float, fetched: float, report_unit: str, fetched_unit: str) -> bool:
    if not report_unit or fetched_unit:
        return False
    ratio = _magnitude_ratio(reported, fetched)
    return ratio is not None and ratio > 50


def _pct_diff(reported: float, fetched: float, compare_mode: str = "") -> float:
    """相对偏差 (absolute)。"""
    if compare_mode == "absolute_magnitude":
        reported = abs(reported)
        fetched = abs(fetched)
    if reported == 0:
        return 0.0 if fetched == 0 else float('inf')
    return abs(reported - fetched) / abs(reported)


def render_verdict(results: list, report_name: str = "") -> dict:
    """
    根据核验结果输出准出/打回判决。

    results: list of dict，每项包含：
      - id, label, reported_value, unit, fetched_value, fetched_source
      - (可选) fetched_value2, fetched_source2   ← 第二来源

    返回：
      {
        'verdict': 'PASS' | 'FAIL',
        'pass_count': int,
        'fail_count': int,
        'total': int,
        'fail_items': [...],
        'summary': str,
      }
    """
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

    print('=' * 70)
    print(f'{BOLD}报告数据抽检 — 准出/打回判决{RESET}')
    if report_name:
        print(f'报告：{report_name}')
    print('=' * 70)
    print()

    fail_items = []
    warn_items = []
    caliber_ack_items = []
    metadata_warn_items = []
    compared_count = 0

    for item in results:
        label = item.get('label', '?')
        if item.get('caliber_column_warning'):
            metadata_warn_items.append({
                'id': item.get('id'),
                'label': label,
                'line_number': item.get('line_number', 0),
                'note': str(item.get('caliber_column_note') or '核心数据表缺少口径/来源列').strip(),
            })
        reported = _to_numeric(item.get('reported_value', 0))
        if reported is None:
            print(f'  ⬜ [{item["id"]:>2}] {label[:35]:35s}  →  [报告值非数值，跳过]')
            continue
        unit = item.get('unit', '')
        report_unit = item.get('report_unit', unit)
        fetched = item.get('fetched_value')
        source = item.get('fetched_source', '?')
        fetched2 = item.get('fetched_value2')
        source2 = item.get('fetched_source2', '')
        fetched_unit = item.get('fetched_unit', '')
        fetched_unit2 = item.get('fetched_unit2', item.get('fetched2_unit', ''))
        compare_mode = item.get('compare_mode', '')
        caliber_ack = bool(item.get('caliber_ack'))
        caliber_note = str(item.get('caliber_note') or '').strip()
        caliber_ack_valid = caliber_ack and bool(caliber_note)

        # --- 主来源比对 ---
        if fetched is None:
            # 没有提供核验值 → 跳过（不计入通过/失败）
            print(f'  ⬜ [{item["id"]:>2}] {label[:35]:35s} {reported:>12.2f} {unit}  →  [未提供核验值，跳过]')
            continue

        fetched_raw = _to_numeric(fetched)
        if fetched_raw is None:
            print(f'  ⬜ [{item["id"]:>2}] {label[:35]:35s} {reported:>12.2f} {unit}  →  [{source} 非数值核验值，跳过]')
            continue
        compared_count += 1
        fetched, unit_note1 = _normalize_fetched_unit(fetched_raw, fetched_unit, report_unit)
        diff1 = _pct_diff(reported, fetched, compare_mode)
        unit_warning1 = (diff1 > _TOLERANCE) and _unit_gap_warning(
            reported, fetched_raw, report_unit, fetched_unit
        )

        # --- 第二来源比对（如有）---
        diff2 = None
        fetched2_raw = None
        unit_note2 = ""
        unit_warning2 = False
        if fetched2 is not None:
            fetched2_raw = _to_numeric(fetched2)
            if fetched2_raw is not None:
                fetched2, unit_note2 = _normalize_fetched_unit(
                    fetched2_raw, fetched_unit2, report_unit
                )
                diff2 = _pct_diff(reported, fetched2, compare_mode)
                unit_warning2 = (diff2 > _TOLERANCE) and _unit_gap_warning(
                    reported, fetched2_raw, report_unit, fetched_unit2
                )

        # 判断
        pass1 = diff1 <= _TOLERANCE
        pass2 = None if diff2 is None else diff2 <= _TOLERANCE
        soft_warn1 = (not pass1) and unit_warning1
        soft_warn2 = False if diff2 is None else ((not pass2) and unit_warning2)

        def _detail(src, value, original, src_unit, diff, note, unit_warning):
            if note:
                detail_text = f'{src}: {original:.2f} {src_unit} → {value:.2f} {unit} (偏差 {diff*100:.2f}%; {note})'
            else:
                detail_text = f'{src}: {value:.2f} (偏差 {diff*100:.2f}%)'
            if unit_warning:
                detail_text += '；疑似单位不一致，请补 fetched_unit'
            return detail_text

        if pass1 and (pass2 is None or pass2):
            status = f'{GREEN}✅ 通过{RESET}'
            detail = _detail(source, fetched, fetched_raw, fetched_unit, diff1, unit_note1, unit_warning1)
            if diff2 is not None:
                detail += '  |  ' + _detail(source2, fetched2, fetched2_raw, fetched_unit2, diff2, unit_note2, unit_warning2)
        elif caliber_ack_valid:
            status = f'{YELLOW}📝 口径认可{RESET}'
            detail = _detail(source, fetched, fetched_raw, fetched_unit, diff1, unit_note1, unit_warning1)
            if diff2 is not None:
                detail += '  |  ' + _detail(source2, fetched2, fetched2_raw, fetched_unit2, diff2, unit_note2, unit_warning2)
            detail += f'；口径说明：{caliber_note}'
            caliber_ack_items.append({
                'id': item['id'],
                'label': label,
                'reported': reported,
                'unit': unit,
                'diff1_pct': round(diff1 * 100, 2),
                'diff2_pct': round(diff2 * 100, 2) if diff2 is not None else None,
                'caliber_note': caliber_note,
            })
        elif not pass1 and not soft_warn1 and (pass2 is None or (not pass2 and not soft_warn2)):
            status = f'{RED}❌ 不通过{RESET}'
            detail = _detail(source, fetched, fetched_raw, fetched_unit, diff1, unit_note1, unit_warning1)
            if diff2 is not None:
                detail += '  |  ' + _detail(source2, fetched2, fetched2_raw, fetched_unit2, diff2, unit_note2, unit_warning2)
            fail_items.append({
                'id': item['id'],
                'label': label,
                'reported': reported,
                'unit': unit,
                'fetched': fetched,
                'source': source,
                'fetched2': fetched2,
                'source2': source2,
                'diff1_pct': round(diff1 * 100, 2),
                'diff2_pct': round(diff2 * 100, 2) if diff2 is not None else None,
                'raw_text': item.get('raw_text', ''),
                'line_number': item.get('line_number', 0),
            })
        else:
            # 一个来源通过，一个不通过 → 警告，不计入失败
            status = f'{YELLOW}⚠️  警告{RESET}'
            detail = _detail(source, fetched, fetched_raw, fetched_unit, diff1, unit_note1, unit_warning1)
            if diff2 is not None:
                detail += '  |  ' + _detail(source2, fetched2, fetched2_raw, fetched_unit2, diff2, unit_note2, unit_warning2)
            warn_items.append({
                'id': item['id'], 'label': label,
                'reported': reported, 'unit': unit,
                'diff1_pct': round(diff1 * 100, 2),
                'diff2_pct': round(diff2 * 100, 2) if diff2 is not None else None,
                'unit_warning': unit_warning1 or unit_warning2,
            })

        print(f'  {status} [{item["id"]:>2}] {label[:35]:35s}  报告: {reported:>12.2f} {unit}')
        print(f'              {" " * 38}{detail}')

    print()
    print('-' * 70)

    total = compared_count
    fail_count = len(fail_items)
    warn_count = len(warn_items)
    caliber_ack_count = len(caliber_ack_items)
    metadata_warn_count = len(metadata_warn_items)
    pass_count = total - fail_count - warn_count - caliber_ack_count

    print(
        f'  抽检总数: {total}  |  通过: {GREEN}{pass_count}{RESET}'
        f'  |  口径认可: {YELLOW}{caliber_ack_count}{RESET}'
        f'  |  警告: {YELLOW}{warn_count}{RESET}'
        f'  |  元数据警告: {YELLOW}{metadata_warn_count}{RESET}'
        f'  |  不通过: {RED}{fail_count}{RESET}'
    )
    print()

    if fail_count == 0:
        print(f'{BOLD}{GREEN}【准出】所有抽检数据通过，报告可发布。{RESET}')
        verdict = 'PASS'
    else:
        print(f'{BOLD}{RED}【打回】{fail_count} 个数据点核验不通过，报告需修正后重审。{RESET}')
        print()
        print(f'{BOLD}打回原因：{RESET}')
        for fi in fail_items:
            print(f'  ❌ 第 {fi["line_number"]} 行 | {fi["label"]}')
            print(f'     报告值：{fi["reported"]} {fi["unit"]}')
            print(f'     {fi["source"]}：{fi["fetched"]}  （偏差 {fi["diff1_pct"]}%）')
            if fi.get('fetched2') is not None:
                print(f'     {fi["source2"]}：{fi["fetched2"]}  （偏差 {fi["diff2_pct"]}%）')
            print(f'     原文：{fi["raw_text"][:80]}')
            print()
        verdict = 'FAIL'

    if caliber_ack_count > 0:
        print(f'{YELLOW}口径认可：{caliber_ack_count} 个数据点提供了 caliber_note，不占用警告或失败额度。{RESET}')
        for ci in caliber_ack_items:
            print(f'  📝 {ci["label"]}  报告:{ci["reported"]} {ci["unit"]}  偏差: {ci["diff1_pct"]}% / {ci["diff2_pct"]}%')
            print(f'     说明：{ci["caliber_note"]}')

    if metadata_warn_count > 0:
        print(f'{YELLOW}元数据警告：{metadata_warn_count} 个抽检点来自缺少口径/来源列的核心数据表，不阻塞准出但需补表头。{RESET}')
        for mi in metadata_warn_items:
            print(f'  ⚠️  第 {mi["line_number"]} 行 | {mi["label"]} | {mi["note"]}')

    if warn_count > 0:
        print(f'{YELLOW}注意：{warn_count} 个数据点两来源结果不一致（超过2%），可能是口径差异（GAAP/Non-GAAP或汇率），请人工复核。{RESET}')
        for wi in warn_items:
            print(f'  ⚠️  {wi["label"]}  报告:{wi["reported"]} {wi["unit"]}  偏差: {wi["diff1_pct"]}% / {wi["diff2_pct"]}%')

    print('=' * 70)

    return {
        'verdict': verdict,
        'pass_count': pass_count,
        'caliber_ack_count': caliber_ack_count,
        'warn_count': warn_count,
        'metadata_warn_count': metadata_warn_count,
        'fail_count': fail_count,
        'total': total,
        'fail_items': fail_items,
        'caliber_ack_items': caliber_ack_items,
        'warn_items': warn_items,
        'metadata_warn_items': metadata_warn_items,
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    _configure_utf8_stdio()

    parser = argparse.ArgumentParser(
        description='Report Audit Tool — 研究报告数据抽检工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流程：

  Step 1 — 提取数据点并随机抽样 15%，输出抽检清单：
    python3 tools/report_audit.py extract --report reports/腾讯/腾讯-research-20260408.md

  Step 2 — Claude 对清单中每个数据点，从可靠信源取数，
            填入 fetched_value / fetched_source / fetched_value2 / fetched_source2

  Step 3 — 输入核验结果，输出准出/打回判决：
    python3 tools/report_audit.py verdict --results '[
      {"id":1,"label":"营业收入","reported_value":7518,"unit":"亿","fetched_value":7518,"fetched_source":"macrotrends","fetched_value2":7500,"fetched_source2":"stockanalysis"},
      ...
    ]'
    python3 tools/report_audit.py verdict --results '[...]' -o _tmp_verdict.json

  一步预览（只打印抽检清单，不核验）：
    python3 tools/report_audit.py extract --report reports/xxx.md --dry-run

  指定抽样比例（默认0.15）：
    python3 tools/report_audit.py extract --report reports/xxx.md --ratio 0.20

  固定随机种子（复现同一批样本）：
    python3 tools/report_audit.py extract --report reports/xxx.md --seed 42
        """)

    sub = parser.add_subparsers(dest='command')

    # extract
    ext = sub.add_parser('extract', help='从报告提取数据点并随机抽样')
    ext.add_argument('--report', required=True, help='报告文件路径（Markdown）')
    ext.add_argument('--ratio', type=float, default=0.15, help='抽样比例，默认 0.15')
    ext.add_argument('--seed', type=int, default=None, help='随机种子（可选，用于复现）')
    ext.add_argument('--dry-run', action='store_true', help='只打印，不输出 JSON')
    ext.add_argument('-o', '--output', help='将抽检清单 JSON 写入文件')

    # verdict
    vrd = sub.add_parser('verdict', help='根据核验结果输出准出/打回判决')
    vrd.add_argument('--results', required=True, help='JSON 数组，含 fetched_value 等字段')
    vrd.add_argument('--report', default='', help='报告名称（可选，用于显示）')
    vrd.add_argument('-o', '--output', help='将判决结果 JSON 写入文件')
    vrd.add_argument('--output-json', action='store_true', help='将判决结果以 JSON 输出到 stdout')

    args = parser.parse_args()

    if args.command == 'extract':
        if not os.path.exists(args.report):
            print(f'❌ 文件不存在: {args.report}', file=sys.stderr)
            sys.exit(1)

        with open(args.report, 'r', encoding='utf-8') as f:
            text = f.read()

        all_points = extract_data_points(text)
        sampled = sample_points(all_points, ratio=args.ratio, seed=args.seed)

        print('=' * 70)
        print(f'报告数据抽检清单')
        print(f'文件：{args.report}')
        print(f'总提取数据点：{len(all_points)}  |  抽样比例：{args.ratio:.0%}  |  抽检数量：{len(sampled)}')
        if args.seed is not None:
            print(f'随机种子：{args.seed}（可用于复现同一批样本）')
        print('=' * 70)
        print()
        print(f'{"ID":>3}  {"行号":>5}  {"数据标签":<35}  {"报告值":>12}  {"单位"}')
        print(f'{"─"*3}  {"─"*5}  {"─"*35}  {"─"*12}  {"─"*6}')
        for p in sampled:
            print(f'{p["id"]:>3}  {p["line_number"]:>5}  {p["label"][:35]:<35}  {p["reported_value"]:>12.2f}  {p["unit"]}')
        print()
        print('↑ 请对上述每个数据点，从以下信源取数，填入 fetched_value：')
        print('  美股：macrotrends.net（主）+ stockanalysis.com（副）')
        print('  港股：aastocks.com（主）+ macrotrends ADR（副）')
        print('  A股： eastmoney.com（主）+ cninfo.com.cn（副）')
        print()

        if not args.dry_run:
            # 输出可填写的 JSON 模板
            template = []
            for p in sampled:
                row = {
                    'id': p['id'],
                    'label': p['label'],
                    'reported_value': p['reported_value'],
                    'unit': p['unit'],
                    'report_unit': p['unit'],
                    'line_number': p['line_number'],
                    'raw_text': p['raw_text'],
                    'fetched_value': None,       # ← 填入主来源核验值
                    'fetched_unit': None,        # ← 填入主来源核验值单位，默认应与 report_unit 一致
                    'fetched_source': '',        # ← 填入主来源名称
                    'fetched_value2': None,      # ← 填入副来源核验值（可选）
                    'fetched_unit2': None,       # ← 填入副来源核验值单位（可选）
                    'fetched_source2': '',       # ← 填入副来源名称（可选）
                    'caliber_ack': False,        # ← 已知口径差异且报告已脚注时设为 true
                    'caliber_note': '',          # ← caliber_ack 为 true 时必填口径说明
                }
                if p.get('caliber_column_warning'):
                    row['caliber_column_warning'] = True
                    row['caliber_column_note'] = p.get('caliber_column_note', '')
                template.append(row)
            if args.output:
                _write_json_output(args.output, template)
                print(f'抽检清单 JSON 已写入: {args.output}', file=sys.stderr)
            else:
                print('抽检清单 JSON（填入 fetched_value 后，传给 verdict 命令）：')
                print()
                print(json.dumps(template, ensure_ascii=False, indent=2))

    elif args.command == 'verdict':
        try:
            results = json.loads(args.results)
        except json.JSONDecodeError as e:
            print(f'❌ JSON 解析失败: {e}', file=sys.stderr)
            sys.exit(1)

        report_name = args.report or ''
        outcome = render_verdict(results, report_name=report_name)

        if args.output:
            _write_json_output(args.output, outcome)
            print(f'判决 JSON 已写入: {args.output}', file=sys.stderr)

        if args.output_json:
            print(json.dumps(outcome, ensure_ascii=False, indent=2))

        # 非零退出码表示打回，方便 CI/脚本判断
        sys.exit(0 if outcome['verdict'] == 'PASS' else 1)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
