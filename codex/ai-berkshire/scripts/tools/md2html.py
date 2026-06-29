# -*- coding: utf-8 -*-
"""md2html.py — Markdown 报告转自包含 HTML（暗色模式 + 导航栏 + 表格可视化）

将 ai-berkshire 的 Markdown 投研报告转为单文件 HTML，提升传播性与阅读体验。

特性：
    - 暗色/浅色双主题，一键切换（localStorage 记忆，默认暗色）
    - 左侧导航栏，由 H1-H3 标题自动生成，可折叠
    - 表格可视化：数值列渲染为内嵌 CSS 条形图（正绿负红），一眼看出量级差异
    - 纯 Python 标准库，零外部依赖
    - 纯渲染层（parse → AST → render）与 CLI 拼装层分离，全部可 mock 测试
    - 输出完全自包含，无外链，可离线传播

用法:
    python tools/md2html.py reports/腾讯/腾讯-research-20260408.md
    python tools/md2html.py input.md -o output.html       # 指定输出路径
    python tools/md2html.py input.md --no-sidebar          # 关闭导航栏
    python tools/md2html.py input.md --light               # 默认浅色主题
    python tools/md2html.py --stdin < input.md > output.html  # stdin/stdout

退出码: 0 = 成功；1 = 参数/IO 错误。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union

__all__ = [
    "parse_markdown",
    "render_html",
    "convert_md_to_html",
]


# ============================================================
# 一、Markdown 解析层：源文本 → AST 节点列表
# ============================================================

# 节点类型：
#   {"type": "heading", "level": int, "text": str}
#   {"type": "table", "headers": [str], "rows": [[str], ...], "aligns": [str|None]}
#   {"type": "code", "lang": str, "text": str}
#   {"type": "list", "ordered": bool, "items": [AST]}
#   {"type": "blockquote", "children": AST}
#   {"type": "hr"}
#   {"type": "para", "text": str}


def _strip_md_inline(text: str) -> str:
    """剥离 Markdown 行内格式标记，保留纯文本（用于表格条形图标签与导航文本）。"""
    # 去图片 ![alt](url) → alt
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    # 去链接 [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # 去粗体/斜体
    text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # 去 `code`
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)(.*)$")


def _is_numeric_cell(cell: str) -> Optional[float]:
    """判断单元格是否为纯数值（含中文量级单位），返回 float 或 None。"""
    stripped = _strip_md_inline(cell).strip()
    if not stripped or stripped in ("—", "-", "–"):
        return None
    cleaned = (
        stripped.replace(",", "")
        .replace("%", "")
        .replace("亿", "")
        .replace("万", "")
        .replace("+", "")
        .replace("¥", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("HKD", "")
        .replace("RMB", "")
        .replace("USD", "")
        .replace("x", "")
        .replace("X", "")
        .strip()
    )
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_table_aligns(sep_line: str) -> List[Optional[str]]:
    """从分隔行解析列对齐方式，返回 ['left'|'right'|'center'|None, ...]。"""
    cells = [c.strip() for c in sep_line.strip("|").split("|")]
    aligns = []
    for c in cells:
        c = c.strip()
        if not c:
            aligns.append(None)
            continue
        left = c.startswith(":")
        right = c.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append(None)
    return aligns


def _split_table_row(line: str) -> List[str]:
    """拆分表格行，处理转义管道符。"""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _parse_list(lines: List[str], start: int) -> Tuple[AST, int]:
    """解析列表块，返回 (list 节点, 下一行索引)。

    支持有序/无序列表，支持嵌套（缩进），支持列表项内含多行段落。
    """
    if start >= len(lines):
        return [], start

    first = lines[start]
    bullet_re = re.compile(r"^(\s*)(\d+\.|[-*+])\s+(.*)$")
    m0 = bullet_re.match(first)
    if not m0:
        return [], start
    base_indent = len(m0.group(1))
    ordered = bool(re.match(r"^\s*\d+\.\s", first))

    items: List[Dict] = []
    i = start
    current_item: Optional[Dict] = None

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            # 空行：检查是否列表结束
            if i + 1 < len(lines) and bullet_re.match(lines[i + 1]):
                i += 1
                continue
            else:
                break
        m = bullet_re.match(line)
        if m:
            indent = len(m.group(1))
            content = m.group(3)
            if indent == base_indent:
                current_item = {"text": content, "children": []}
                items.append(current_item)
                i += 1
                continue
            elif indent > base_indent:
                # 嵌套：截取缩进更深的连续行，递归解析子列表
                sub_lines = []
                j = i
                while j < len(lines):
                    l2 = lines[j]
                    if not l2.strip():
                        # 空行：若下一行仍属子列表则保留
                        if j + 1 < len(lines):
                            m3 = bullet_re.match(lines[j + 1])
                            if m3 and len(m3.group(1)) > base_indent:
                                sub_lines.append(l2)
                                j += 1
                                continue
                        break
                    m2 = bullet_re.match(l2)
                    if m2 and len(m2.group(1)) > base_indent:
                        sub_lines.append(l2)
                        j += 1
                    else:
                        break
                sub_list, _ = _parse_list(sub_lines, 0)
                if current_item is not None:
                    current_item["children"].append(sub_list)
                i = j
                continue
            else:
                break
        # 非列表行且非空 → 列表结束
        break

    # 构建 AST
    node = {"type": "list", "ordered": ordered, "items": items}
    return [node], i


def parse_markdown(md: str) -> AST:
    """解析 Markdown 文本为 AST 节点列表。

    支持的语法：标题、表格、围栏代码块、列表、引用、分隔线、段落。
    不支持完整的 CommonMark（项目内报告子集足够）。
    """
    lines = md.split("\n")
    nodes: AST = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # 空行
        if not line.strip():
            i += 1
            continue

        # 围栏代码块
        m = _FENCE_RE.match(line)
        if m:
            lang = m.group(2).strip()
            i += 1
            code_lines = []
            while i < n:
                if _FENCE_RE.match(lines[i]):
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1
            nodes.append({"type": "code", "lang": lang, "text": "\n".join(code_lines)})
            continue

        # 标题
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            nodes.append({"type": "heading", "level": level, "text": text})
            i += 1
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", line.strip()):
            nodes.append({"type": "hr"})
            i += 1
            continue

        # 引用块
        if line.strip().startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                stripped = re.sub(r"^\s*>\s?", "", lines[i])
                quote_lines.append(stripped)
                i += 1
            children = parse_markdown("\n".join(quote_lines))
            nodes.append({"type": "blockquote", "children": children})
            continue

        # 表格（需 lookahead：当前行有管道符 + 下一行是分隔行）
        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            headers = _split_table_row(lines[i])
            aligns = _parse_table_aligns(lines[i + 1].strip())
            i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(_split_table_row(lines[i]))
                i += 1
            nodes.append({"type": "table", "headers": headers, "rows": rows, "aligns": aligns})
            continue

        # 列表
        if re.match(r"^\s*(\d+\.|[-*+])\s", line):
            list_nodes, i = _parse_list(lines, i)
            nodes.extend(list_nodes)
            continue

        # 普通段落
        para_lines = [line]
        i += 1
        while i < n and lines[i].strip() and not _HEADING_RE.match(lines[i]) \
                and not _FENCE_RE.match(lines[i]) \
                and not lines[i].strip().startswith(">") \
                and "|" not in lines[i] \
                and not re.match(r"^\s*(\d+\.|[-*+])\s", lines[i]) \
                and not re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", lines[i].strip()):
            para_lines.append(lines[i])
            i += 1
        nodes.append({"type": "para", "text": "\n".join(para_lines)})

    return nodes


# ============================================================
# 二、HTML 渲染层：AST → HTML 字符串
# ============================================================

_INLINE_MAP: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1", ""),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">', "</a>"),
    (re.compile(r"\*\*\*([^*]+)\*\*\*"), r"<strong><em>\1</em></strong>", ""),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>", ""),
    (re.compile(r"\*([^*]+)\*"), r"<em>\1</em>", ""),
    (re.compile(r"__([^_]+)__"), r"<strong>\1</strong>", ""),
    (re.compile(r"_([^_]+)_"), r"<em>\1</em>", ""),
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>", ""),
]


def _render_inline(text: str) -> str:
    """渲染 Markdown 行内格式（粗体、斜体、链接、代码、图片）为 HTML。"""
    # 先 HTML 转义
    out = html.escape(text, quote=False)
    # 图片
    out = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r'<img src="\2" alt="\1">',
        out,
    )
    # 链接
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', out)
    # 代码块标记需在转义后但注意避免冲突
    out = re.sub(r"```", "", out)
    # 粗体+斜体
    out = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<strong><em>\1</em></strong>", out)
    # 粗体
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    # 斜体
    out = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", out)
    # 下划线粗/斜
    out = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", out)
    # 行内代码
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


_CATEGORY_ATTR_RE = re.compile(r"^\|?\s*\*?\*?([^[|\*\s]+)")

_TABLE_HEADER_BARS = "data-bar"
_TABLE_NUM_CLASS = "data-num"


def _is_percentage(cell: str) -> bool:
    s = _strip_md_inline(cell).strip()
    return s.endswith("%")


def _render_table_bar(
    value: float,
    max_abs: float,
    col_index: int,
    is_pct: bool,
) -> str:
    """为数值单元格渲染 CSS 条形图。"""
    if max_abs == 0:
        return ""
    pct = min(abs(value) / max_abs, 1.0) * 100
    if is_pct:
        # 百分比：0 为中点，正绿负红
        mid = 0
        if value >= 0:
            left = 50
            width = pct / 2
            color = "#3fb950"
        else:
            left = 50 - pct / 2
            width = pct / 2
            color = "#f85149"
    else:
        # 普通数值：左对齐填充
        left = 0
        width = pct
        color = "#3fb950" if value >= 0 else "#f85149"

    return (
        f'<span class="cell-bar" style="left:{left:.1f}%;width:{width:.1f}%;'
        f'background:{color};"></span>'
    )


def _render_table(node: Dict) -> str:
    headers = node["headers"]
    rows = node["rows"]
    aligns = node.get("aligns") or [None] * len(headers)

    # 检测数值列
    num_cols = set()
    max_abs_per_col: Dict[int, float] = {}
    pct_cols = set()
    for ci in range(len(headers)):
        values = []
        all_pct = True
        for row in rows:
            if ci < len(row):
                v = _is_numeric_cell(row[ci])
                if v is not None:
                    values.append(v)
                    if not _is_percentage(row[ci]):
                        all_pct = False
                else:
                    all_pct = False
        if values and len(values) >= max(2, len(rows) // 2):
            num_cols.add(ci)
            max_abs_per_col[ci] = max(abs(v) for v in values)
            if all_pct:
                pct_cols.add(ci)

    parts: List[str] = []
    parts.append('<div class="table-wrap">')
    parts.append("<table>")

    # 表头
    parts.append("<thead><tr>")
    for ci, h in enumerate(headers):
        align = aligns[ci] if ci < len(aligns) and aligns[ci] else (
            "right" if ci in num_cols else "left"
        )
        cls = f' class="num-col"' if ci in num_cols else ""
        parts.append(f'<th style="text-align:{align}"{cls}>{_render_inline(h)}</th>')
    parts.append("</tr></thead>")

    # 表体
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>")
        for ci in range(len(headers)):
            cell = row[ci] if ci < len(row) else ""
            align = aligns[ci] if ci < len(aligns) and aligns[ci] else (
                "right" if ci in num_cols else "left"
            )
            if ci in num_cols:
                v = _is_numeric_cell(cell)
                bar = ""
                if v is not None and ci in max_abs_per_col:
                    is_pct = ci in pct_cols
                    bar = _render_table_bar(v, max_abs_per_col[ci], ci, is_pct)
                parts.append(
                    f'<td style="text-align:{align}" class="num-cell">'
                    f'{bar}<span class="cell-val">{_render_inline(cell)}</span></td>'
                )
            else:
                parts.append(f'<td style="text-align:{align}">{_render_inline(cell)}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</div>")
    return "\n".join(parts)


def _render_list(node: Dict) -> str:
    items = node["items"]
    if not items:
        return ""
    tag = "ol" if node.get("ordered") else "ul"
    parts = [f"<{tag}>"]
    for item in items:
        item_parts = ["<li>"]
        item_parts.append(_render_inline(item.get("text", "")))
        children = item.get("children") or []
        if children:
            for child in children:
                if isinstance(child, dict) and child.get("type") == "list":
                    item_parts.append(_render_list(child))
        item_parts.append("</li>")
        parts.append("".join(item_parts))
    parts.append(f"</{tag}>")
    return "\n".join(parts)


def _render_node(node: Dict, heading_counter: List[int]) -> str:
    t = node["type"]
    if t == "heading":
        level = node["level"]
        text = node["text"]
        heading_counter[0] += 1
        hid = f"h-{heading_counter[0]}"
        return f'<h{level} id="{hid}">{_render_inline(text)}</h{level}>'
    if t == "table":
        return _render_table(node)
    if t == "code":
        lang = html.escape(node.get("lang", ""))
        code = html.escape(node["text"], quote=False)
        lang_class = f' class="language-{lang}"' if lang else ""
        return (
            f'<div class="code-block"><pre><code{lang_class}>{code}</code></pre></div>'
        )
    if t == "blockquote":
        inner = "".join(
            _render_node(c, heading_counter) for c in node.get("children", [])
        )
        return f'<blockquote>{inner}</blockquote>'
    if t == "list":
        return _render_list(node)
    if t == "hr":
        return "<hr>"
    if t == "para":
        return f"<p>{_render_inline(node['text'])}</p>"
    return ""


def _build_sidebar(nodes: AST) -> str:
    """从 AST 提取 H1-H3 标题构建导航 HTML。"""
    items: List[str] = []
    counter = [0]
    for node in nodes:
        if node.get("type") == "heading":
            level = node["level"]
            if level > 3:
                continue
            counter[0] += 1
            hid = f"h-{counter[0]}"
            text = html.escape(_strip_md_inline(node["text"]))
            indent = (level - 1) * 16
            items.append(
                f'<a href="#{hid}" class="nav-l{level}" '
                f'style="padding-left:{indent}px">{text}</a>'
            )
    if not items:
        return ""
    return f'<nav class="sidebar" id="sidebar">\n' + "\n".join(items) + "\n</nav>"


_CSS = """\
:root[data-theme="dark"]{--bg:#0d1117;--surface:#161b22;--border:#30363d;--text:#c9d1d9;
--text-strong:#f0f6fc;--text-muted:#8b949e;--accent:#58a6ff;--accent-bg:rgba(88,166,255,.12);
--code-bg:#1f2428;--bar-pos:#3fb950;--bar-neg:#f85149;--table-stripe:#11161b;
--table-hover:#1c2128;--nav-active:rgba(88,166,255,.15)}
:root[data-theme="light"]{--bg:#ffffff;--surface:#f6f8fa;--border:#d0d7de;--text:#1f2328;
--text-strong:#24292f;--text-muted:#656d76;--accent:#0969da;--accent-bg:rgba(9,105,218,.08);
--code-bg:#eff1f3;--bar-pos:#1a7f37;--bar-neg:#cf222e;--table-stripe:#f6f8fa;
--table-hover:#eaeef2;--nav-active:rgba(9,105,218,.1)}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--text);line-height:1.7;-webkit-font-smoothing:antialiased;transition:background .2s,color .2s}
.layout{display:flex;min-height:100vh}
.sidebar{width:260px;flex-shrink:0;position:fixed;top:0;left:0;height:100vh;overflow-y:auto;
border-right:1px solid var(--border);padding:16px 0;background:var(--surface);transition:transform .25s;z-index:100}
.sidebar a{display:block;padding:6px 16px;color:var(--text-muted);text-decoration:none;font-size:13px;
border-left:3px solid transparent;transition:all .15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sidebar a:hover{color:var(--accent);background:var(--accent-bg);border-left-color:var(--accent)}
.sidebar a.active{color:var(--accent);background:var(--nav-active);border-left-color:var(--accent)}
.sidebar a.nav-l1{font-weight:600;font-size:14px;color:var(--text-strong);margin-top:8px}
.sidebar a.nav-l2{font-size:13px}
.sidebar a.nav-l3{font-size:12px;color:var(--text-muted)}
.content{flex:1;margin-left:260px;max-width:960px;padding:32px 40px 80px;transition:margin-left .25s}
.content.no-sidebar{margin-left:0}
h1{font-size:28px;font-weight:700;margin:24px 0 16px;color:var(--text-strong);padding-bottom:8px;border-bottom:1px solid var(--border)}
h2{font-size:22px;font-weight:600;margin:28px 0 12px;color:var(--text-strong);padding-bottom:6px;border-bottom:1px solid var(--border)}
h3{font-size:18px;font-weight:600;margin:24px 0 8px;color:var(--text-strong)}
h4{font-size:16px;font-weight:600;margin:20px 0 8px;color:var(--text-strong)}
h5{font-size:15px;font-weight:600;margin:16px 0 8px}
h6{font-size:14px;font-weight:600;margin:16px 0 8px;color:var(--text-muted)}
p{margin:8px 0}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:var(--code-bg);padding:2px 6px;border-radius:4px;font-family:"SF Mono",Consolas,"Liberation Mono",monospace;font-size:.9em}
pre code{background:none;padding:0}
.code-block{background:var(--code-bg);border:1px solid var(--border);border-radius:6px;margin:12px 0}
.code-block pre{margin:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
table-wrap{display:block;overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px;position:relative}
th,td{padding:8px 12px;border:1px solid var(--border);text-align:left}
th{background:var(--surface);font-weight:600;color:var(--text-strong)}
tbody tr:nth-child(even){background:var(--table-stripe)}
tbody tr:hover{background:var(--table-hover)}
td.num-cell{position:relative;min-width:80px}
td.num-cell .cell-bar{position:absolute;bottom:2px;left:0;height:3px;border-radius:1.5px;opacity:.55;z-index:0}
td.num-cell .cell-val{position:relative;z-index:1}
blockquote{border-left:4px solid var(--accent);margin:12px 0;padding:8px 16px;background:var(--accent-bg);border-radius:0 4px 4px 0;color:var(--text-muted)}
blockquote p{margin:4px 0}
hr{border:none;border-top:1px solid var(--border);margin:24px 0}
img{max-width:100%;border-radius:6px}
.toggle-btn{position:fixed;top:16px;right:16px;width:36px;height:36px;border-radius:50%;
border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font-size:16px;z-index:200;transition:all .2s}
.toggle-btn:hover{border-color:var(--accent);color:var(--accent)}
.menu-btn{display:none;position:fixed;top:16px;left:16px;width:36px;height:36px;border-radius:50%;
border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer;font-size:16px;z-index:200}
.footer{margin-top:48px;padding-top:16px;border-top:1px solid var(--border);color:var(--text-muted);font-size:12px;text-align:center}
@media(max-width:768px){
.sidebar{transform:translateX(-100%)}
.sidebar.open{transform:translateX(0)}
.content{margin-left:0;padding:20px}}
"""

_JS = """\
(function(){
var root=document.documentElement;
var btn=document.querySelector('.toggle-btn');
var saved=localStorage.getItem('md2html-theme')||'dark';
root.setAttribute('data-theme',saved);
btn&&btn.addEventListener('click',function(){
var cur=root.getAttribute('data-theme');
var next=cur==='dark'?'light':'dark';
root.setAttribute('data-theme',next);
localStorage.setItem('md2html-theme',next);
});
// 导航高亮
var links=document.querySelectorAll('.sidebar a');
var sections=[];
links.forEach(function(a){var id=a.getAttribute('href').slice(1);var el=document.getElementById(id);if(el)sections.push({el:el,link:a})});
if(sections.length){
function onScroll(){
var scrollY=window.scrollY;
var active=sections[0];
for(var i=0;i<sections.length;i++){if(sections[i].el.offsetTop<=scrollY+60)active=sections[i]}
active.link.classList.add('active');
links.forEach(function(a){if(a!==active.link)a.classList.remove('active')})
}
window.addEventListener('scroll',onScroll,{passive:true});
onScroll();
}
// 移动端菜单
var menu=document.querySelector('.menu-btn');
var sidebar=document.querySelector('.sidebar');
menu&&menu.addEventListener('click',function(){sidebar.classList.toggle('open')});
})();
"""


def render_html(
    nodes: AST,
    title: str = "报告",
    sidebar: bool = True,
    default_theme: str = "dark",
) -> str:
    """把 AST 渲染为自包含 HTML 字符串。"""
    counter = [0]
    body_parts: List[str] = []
    for node in nodes:
        body_parts.append(_render_node(node, counter))

    sidebar_html = _build_sidebar(nodes) if sidebar else ""
    content_cls = "content no-sidebar" if not sidebar else "content"
    theme_attr = html.escape(default_theme)

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="{theme_attr}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<button class="toggle-btn" title="切换主题">🌓</button>
<button class="menu-btn" title="导航">☰</button>
<div class="layout">
{sidebar_html}
<main class="{content_cls}">
{''.join(body_parts)}
<div class="footer">由 ai-berkshire md2html.py 生成</div>
</main>
</div>
<script>
{_JS}
</script>
</body>
</html>
"""


def convert_md_to_html(
    md: str,
    title: Optional[str] = None,
    sidebar: bool = True,
    default_theme: str = "dark",
) -> str:
    """一站式：Markdown 文本 → HTML 字符串。便于测试直接调用。"""
    nodes = parse_markdown(md)
    if title is None:
        # 取第一个 H1 作标题
        for node in nodes:
            if node.get("type") == "heading" and node["level"] == 1:
                title = _strip_md_inline(node["text"])
                break
        else:
            title = "报告"
    return render_html(nodes, title=title, sidebar=sidebar, default_theme=default_theme)


# ============================================================
# 三、CLI 拼装层
# ============================================================


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="md2html.py",
        description="Markdown 报告转自包含 HTML（暗色模式 + 导航栏 + 表格可视化）",
    )
    parser.add_argument("input", nargs="?", help="Markdown 输入文件路径（省略则读 stdin）")
    parser.add_argument("-o", "--output", help="HTML 输出路径（默认同名 .html）")
    parser.add_argument("--no-sidebar", action="store_true", help="关闭左侧导航栏")
    parser.add_argument("--light", action="store_true", help="默认浅色主题")
    parser.add_argument("--stdin", action="store_true", help="从 stdin 读入，stdout 输出")
    args = parser.parse_args(argv)

    if args.stdin or args.input is None:
        md = sys.stdin.read()
        title = "报告"
        out_path = Path("output.html")
    else:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"错误：文件不存在 {in_path}", file=sys.stderr)
            return 1
        md = in_path.read_text(encoding="utf-8")
        title = in_path.stem
        if args.output:
            out_path = Path(args.output)
        else:
            out_path = in_path.with_suffix(".html")

    html_str = convert_md_to_html(
        md,
        title=title,
        sidebar=not args.no_sidebar,
        default_theme="light" if args.light else "dark",
    )

    if args.stdin or args.input is None:
        sys.stdout.write(html_str)
    else:
        out_path.write_text(html_str, encoding="utf-8")
        print(f"已生成：{out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(_main())