# -*- coding: utf-8 -*-
"""verify_channel_capability.py
渠道能力与 `_source` 规范校验。

校验两类不变式：

A) `/quality-screen` 精确复核层（full 模式，需理杏仁 token / 网络）
   运行 `python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet`，
   解析其 JSON 输出并做**有效值断言**（非仅 key 存在）：
     - 顶层 `_source` 存在且为 `lixinger`
     - `checks` 含 7 项 key（见 EXPECTED_CHECK_KEYS）
     - `share_dilution_5y` 非 missing 且 `value` 为有效数值（int/float，非 None/非字符串 "missing"）
     - 顶层 `result` 与 `status` 为 `pass`

B) 增强 Skill 的 `_source` 标注覆盖 + 根/Codex reference 同步（`--quick` 即执行，纯静态）
     - skills/news-pulse.md | earnings-review.md | bottleneck-hunter.md
     - 必含 `_source: mx-search`（三者均要求）；news-pulse / earnings-review 另要求 `_source: mx-data`
     - 18 个 root skills 与 codex/ai-berkshire/references/skills/*.md 副本 SHA256 一致

C) 权限安全多 Agent 静态校验（`--quick` 即执行，纯静态）
     - 调用 tools/verify_multi_agent_permissions.py
     - 扫描后台 Agent 自行联网、取数、命令执行和写文件等旧句式

用法:
    python tools/verify_channel_capability.py --quick     # 仅 B/C 类静态校验，不联网
    python tools/verify_channel_capability.py             # A+B+C 全部校验（需 quality-metrics 子命令与网络）

退出码: 0 = 全部通过；非 0 = 有失败项。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / "skills").is_dir()
            and (candidate / "codex" / "ai-berkshire" / "references" / "skills").is_dir()
        ):
            return candidate
    return Path(__file__).resolve().parent.parent


REPO = _find_repo_root(Path(__file__).resolve())
LXR = REPO / "tools" / "lxr_data.py"
EXPECTED_SKILL_COUNT = 18

# /quality-screen 的 7 条去劣指标（与 skills/quality-screen.md 一致）
EXPECTED_CHECK_KEYS = [
    "roe_10y_avg",        # 1. 10年平均ROE
    "fcf_5y_cumulative",  # 2. 5年累计自由现金流
    "interest_coverage",  # 3. 利息覆盖倍数
    "gross_margin_avg",   # 4. 长期毛利率
    "ocf_ni_5y_avg",      # 5. 经营现金流/净利润 5年均值
    "net_margin_avg",     # 6. 长期净利率
    "share_dilution_5y",  # 7. 5年总股本膨胀
]

# (root 相对路径, codex reference 相对路径, 必需的 _source / 渠道标记)
SOURCE_MARKER_TARGETS: list[tuple[str, str, list[str]]] = [
    (
        "skills/news-pulse.md",
        "codex/ai-berkshire/references/skills/news-pulse.md",
        ["_source: mx-search", "_source: mx-data", "mx-search", "mx-data"],
    ),
    (
        "skills/earnings-review.md",
        "codex/ai-berkshire/references/skills/earnings-review.md",
        ["_source: mx-search", "_source: mx-data", "mx-search", "mx-data"],
    ),
    (
        "skills/bottleneck-hunter.md",
        "codex/ai-berkshire/references/skills/bottleneck-hunter.md",
        ["_source: mx-search", "mx-search"],
    ),
]

BAD_SOURCE_MARKERS = [
    "_source: " + "理杏仁",
    "`" + "理杏仁" + "`（结构化",
    "标注 `_source: " + "理杏仁`",
]

WINDOWS_BLOCKERS = [
    "~/" + "ai-berkshire",
    "/" + "tmp",
    "/usr/bin",
    "wsl.exe",
    "/mnt/c",
    "/home/dragonquix",
]

_MISSING_TOKENS = (None, "missing", "MISSING", "N/A", "n/a", "null", "")


def _pass(msg: str) -> None:
    print(f"PASS: {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")


# ---------------------------------------------------------------------------
# A) quality-metrics JSON 有效值断言
# ---------------------------------------------------------------------------

def _is_valid_number(v) -> bool:
    """有效数值：int/float 且非 bool、非 None。"""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _run_quality_metrics(code: str = "600132", years: int = 5) -> dict:
    cmd = [sys.executable, str(LXR), "quality-metrics", code,
           "--years", str(years), "--quiet"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"quality-metrics 子命令执行失败 (exit={proc.returncode})\n"
            f"stderr: {proc.stderr.strip()[:400]}\n"
            f"hint: 确认 lxr_data.py 已含 quality-metrics 子命令且理杏仁 token 可用"
        )
    # lxr_data.py 末尾 print(json.dumps(...))，取 stdout 末段首个 JSON 对象
    out = proc.stdout.strip()
    start = out.find("{")
    if start < 0:
        raise RuntimeError(f"quality-metrics stdout 未找到 JSON: {out[:200]}")
    return json.loads(out[start:])


def check_quality_metrics_json() -> int:
    """解析 quality-metrics JSON 并做有效值断言。"""
    print("\n-- A) quality-metrics JSON 有效值断言 --")
    try:
        data = _run_quality_metrics()
    except Exception as e:
        _fail(f"无法获取 quality-metrics JSON: {e}")
        return 1

    rc = 0

    # 1. 顶层 _source
    src = data.get("_source")
    if src == "lixinger":
        _pass(f"顶层 _source = {src!r}")
    else:
        _fail(f"顶层 _source 期望 'lixinger'，实际 {src!r}")
        rc |= 1

    # 2. 7 项 checks key
    checks = data.get("checks")
    if not isinstance(checks, dict):
        _fail(f"checks 不是 dict: {type(checks).__name__}")
        return rc | 1
    present = set(checks.keys())
    expected = set(EXPECTED_CHECK_KEYS)
    missing = expected - present
    if missing:
        _fail(f"checks 缺少 key: {sorted(missing)} (实际 keys: {sorted(present)})")
        rc |= 1
    else:
        _pass(f"checks 7 项 key 齐全: {sorted(expected)}")
    # 额外断言：checks 至少 7 项（防止退化为只查 key 存在而内容空）
    if len(checks) < 7:
        _fail(f"checks 项数 {len(checks)} < 7")
        rc |= 1

    # 3. share_dilution_5y 非 missing 且 value 为有效数值（核心有效值断言）
    sd = checks.get("share_dilution_5y")
    if not isinstance(sd, dict):
        _fail(f"share_dilution_5y 不是 dict: {sd!r}")
        rc |= 1
    else:
        sd_status = sd.get("status")
        sd_value = sd.get("value")
        if sd_status in _MISSING_TOKENS or str(sd_status).lower() == "missing":
            _fail(f"share_dilution_5y status=missing (status={sd_status!r})")
            rc |= 1
        elif not _is_valid_number(sd_value):
            _fail(f"share_dilution_5y.value 非有效数值: {sd_value!r}")
            rc |= 1
        else:
            _pass(f"share_dilution_5y 有效: value={sd_value!r}, status={sd_status!r}")

    # 4. 顶层 result / status
    result = data.get("result")
    status = data.get("status", result)
    if result == "pass" and status == "pass":
        _pass(f"顶层 result={result!r}, status={status!r}")
    else:
        _fail(f"顶层 result={result!r}, status={status!r} (期望均 'pass')")
        rc |= 1

    return rc


# ---------------------------------------------------------------------------
# B) Skill _source 覆盖 + 根/Codex 同步
# ---------------------------------------------------------------------------

def check_source_coverage(rel: str, markers: list[str]) -> int:
    p = REPO / rel
    if not p.exists():
        _fail(f"{rel} 不存在")
        return 1
    text = p.read_text(encoding="utf-8")
    missing = [m for m in markers if m not in text]
    if missing:
        _fail(f"{rel} 缺少标记: {missing}")
        return 1
    _pass(f"{rel} _source 渠道标注覆盖完整 ({len(markers)} markers)")
    return 0


def check_sync(root_rel: str, codex_rel: str) -> int:
    a = REPO / root_rel
    b = REPO / codex_rel
    if not a.exists() or not b.exists():
        _fail(f"同步校验跳过：{root_rel} 或 {codex_rel} 不存在")
        return 1
    ha = hashlib.sha256(a.read_bytes()).hexdigest()
    hb = hashlib.sha256(b.read_bytes()).hexdigest()
    if ha == hb:
        _pass(f"{root_rel} ↔ {codex_rel} 同步一致 (sha256={ha[:16]})")
        return 0
    _fail(f"{root_rel} ↔ {codex_rel} 不一致 (root={ha[:16]} codex={hb[:16]})")
    return 1


def check_skills_source_and_sync() -> int:
    print("\n-- B1) 增强 Skill _source 覆盖 --")
    rc = 0
    for root_rel, codex_rel, markers in SOURCE_MARKER_TARGETS:
        print(f"\n>> {root_rel}")
        rc |= check_source_coverage(root_rel, markers)
        rc |= check_source_coverage(codex_rel, markers)
    return rc


def check_all_skill_sync() -> int:
    print("\n-- B2) 18 个 Skill 根/Codex reference SHA256 同步 --")
    rc = 0
    root_dir = REPO / "skills"
    codex_dir = REPO / "codex" / "ai-berkshire" / "references" / "skills"
    root_files = {p.name: p for p in sorted(root_dir.glob("*.md"))}
    codex_files = {p.name: p for p in sorted(codex_dir.glob("*.md"))}

    if len(root_files) != EXPECTED_SKILL_COUNT:
        _fail(f"skills/*.md 数量期望 {EXPECTED_SKILL_COUNT}，实际 {len(root_files)}")
        rc |= 1
    if len(codex_files) != EXPECTED_SKILL_COUNT:
        _fail(
            "codex/ai-berkshire/references/skills/*.md "
            f"数量期望 {EXPECTED_SKILL_COUNT}，实际 {len(codex_files)}"
        )
        rc |= 1

    missing_in_codex = sorted(set(root_files) - set(codex_files))
    extra_in_codex = sorted(set(codex_files) - set(root_files))
    if missing_in_codex:
        _fail(f"Codex reference 缺少 skill: {missing_in_codex}")
        rc |= 1
    if extra_in_codex:
        _fail(f"Codex reference 存在 root 未配对 skill: {extra_in_codex}")
        rc |= 1

    common = sorted(set(root_files) & set(codex_files))
    for name in common:
        root_rel = f"skills/{name}"
        codex_rel = f"codex/ai-berkshire/references/skills/{name}"
        rc |= check_sync(root_rel, codex_rel)
    if rc == 0:
        _pass(f"18 个 Skill 同步一致 ({len(common)} pairs)")
    return rc


def check_multi_agent_permissions() -> int:
    print("\n-- D) 高风险后台 Agent 旧句式扫描 --")
    try:
        from verify_multi_agent_permissions import check_permissions
    except Exception as e:
        _fail(f"无法导入 verify_multi_agent_permissions.py: {e}")
        return 1
    return check_permissions(repo=REPO, verbose=True)


def check_global_static_markers() -> int:
    print("\n-- C) 全量静态规范检查 --")
    rc = 0
    roots = [REPO / "skills", REPO / "codex" / "ai-berkshire" / "references" / "skills"]
    for root in roots:
        for path in sorted(root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(REPO).as_posix()
            for marker in BAD_SOURCE_MARKERS:
                if marker in text:
                    _fail(f"{rel} 含非规范 _source 标记: {marker}")
                    rc |= 1
            for marker in WINDOWS_BLOCKERS:
                if marker in text:
                    _fail(f"{rel} 含 Windows 阻塞路径: {marker}")
                    rc |= 1
    if rc == 0:
        _pass("全量 skill 静态规范检查通过")
    return rc


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="渠道能力与 _source 规范校验")
    ap.add_argument("--quick", action="store_true",
                    help="仅静态校验 Skill _source 覆盖与根/Codex 同步，不联网、不调用 quality-metrics")
    args = ap.parse_args()

    mode = "quick (offline)" if args.quick else "full (A+B+C)"
    print(f"== verify_channel_capability.py ({mode}, repo={REPO}) ==")
    rc = 0
    rc |= check_skills_source_and_sync()
    rc |= check_all_skill_sync()
    rc |= check_global_static_markers()
    rc |= check_multi_agent_permissions()
    if not args.quick:
        rc |= check_quality_metrics_json()

    print(f"\n== 结果: {'全部通过' if rc == 0 else '存在失败'} (exit={rc}) ==")
    return rc


if __name__ == "__main__":
    sys.exit(main())
