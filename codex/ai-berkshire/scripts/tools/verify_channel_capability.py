#!/usr/bin/env python3
"""E0 渠道能力最小复验脚本（Windows / PowerShell 友好）。

用法:
    python tools/verify_channel_capability.py
    python tools/verify_channel_capability.py --quick
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
LXR = ROOT / "tools" / "lxr_data.py"
RIGOR = ROOT / "tools" / "financial_rigor.py"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _check(name: str, cmd: list[str], predicate) -> bool:
    code, out = _run(cmd)
    ok = code == 0 and predicate(out)
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    if not ok:
        print(out[:800])
    return ok


def _quality_metrics_ok(out: str) -> bool:
    """quality-metrics 须含 7 项 checks，且 share_dilution_5y 有有效数值（非 missing）。"""
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return False
    if data.get("_source") != "lixinger":
        return False
    checks = data.get("checks") or {}
    required = (
        "roe_10y_avg", "fcf_5y_cumulative", "interest_coverage",
        "gross_margin_avg", "ocf_ni_5y_avg", "net_margin_avg", "share_dilution_5y",
    )
    if not all(k in checks for k in required):
        return False
    dil = checks["share_dilution_5y"]
    if dil.get("status") == "missing" or dil.get("value") is None:
        return False
    if dil.get("status") not in ("pass", "fail"):
        return False
    summary = data.get("summary") or {}
    return summary.get("share_dilution_5y_pct") is not None


def main():
    parser = argparse.ArgumentParser(description="复验 E0 关键渠道能力")
    parser.add_argument("--quick", action="store_true", help="跳过 mx-xuangu（省日限额）")
    args = parser.parse_args()

    results = []

    results.append(_check(
        "insurance EV/NBV industry-deep 601336",
        [PY, str(LXR), "industry-deep", "601336", "--years", "3", "--quiet"],
        lambda o: "ev" in o and "nbv" in o and '"_source": "lixinger"' in o,
    ))

    results.append(_check(
        "datapack --no-mx _source=lixinger",
        [PY, str(LXR), "datapack", "600519", "--years", "5", "--no-mx", "--quiet"],
        lambda o: '"_source": "lixinger"' in o and "mx_quote" not in o,
    ))

    results.append(_check(
        "quality-metrics 7 indicators + share_dilution_5y",
        [PY, str(LXR), "quality-metrics", "600132", "--years", "5", "--fcf-years", "5", "--quiet"],
        _quality_metrics_ok,
    ))

    results.append(_check(
        "verify-valuation dividend yield ~4%",
        [PY, str(RIGOR), "verify-valuation", "600519", "--source", "lixinger"],
        lambda o: "股息率" in o and ("4.0" in o or "4.1" in o) and "0.04%" not in o,
    ))

    results.append(_check(
        "HK governance 00700",
        [PY, str(LXR), "governance", "00700", "--years", "2", "--quiet"],
        lambda o: '"_source": "lixinger"' in o,
    ))

    if not args.quick:
        results.append(_check(
            "mx-xuangu screen",
            [PY, str(LXR), "mx-xuangu",
             "ROE大于15%，市盈率小于30的消费股，返回前10只", "--quiet"],
            lambda o: '"_source": "mx-xuangu"' in o or "raw" in o,
        ))

    passed = sum(results)
    total = len(results)
    print(f"\n合计: {passed}/{total} PASS")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
