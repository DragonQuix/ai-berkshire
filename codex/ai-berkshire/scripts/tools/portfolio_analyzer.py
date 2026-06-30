#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

from portfolio_allocation import build_allocation_drift
from portfolio_input import UNKNOWN, as_ratio, normalize_holdings
from portfolio_opportunity import DEFAULT_CASH_HURDLE, build_opportunity_cost
from portfolio_rebalance import build_rebalance_suggestions
from portfolio_render import render_markdown
from portfolio_stress import build_stress_tests


EXPOSURE_LIMIT = 0.50

def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def _sorted_weights(mapping: dict[str, float]) -> dict[str, float]:
    return dict(sorted(mapping.items(), key=lambda item: (-item[1], item[0])))

def _group_weights(rows: list[dict[str, Any]], field: str) -> dict[str, float]:
    groups: dict[str, float] = {}
    for row in rows:
        name = str(row.get(field) or UNKNOWN)
        groups[name] = groups.get(name, 0.0) + row["weight"]
    return _sorted_weights(groups)

def _theme_weights(rows: list[dict[str, Any]]) -> dict[str, float]:
    groups: dict[str, float] = {}
    for row in rows:
        if row["is_cash"]:
            continue
        for theme in row["themes"]:
            groups[theme] = groups.get(theme, 0.0) + row["weight"]
    return _sorted_weights(groups)

def _assess_concentration(top1: float, top3: float, count: int, cash: float) -> str:
    if count < 3 or top1 > 0.50 or top3 > 0.90:
        return "问题严重"
    if top1 > 0.40 or top3 > 0.80 or count > 15:
        return "需要调整"
    if cash < 0.03 or cash > 0.35:
        return "需要调整"
    if 3 <= count <= 10 and 0.50 <= top3 <= 0.80:
        return "良好"
    return "可接受"

def _build_concentration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    securities = [row for row in rows if not row["is_cash"]]
    security_weights = sorted((row["weight"] for row in securities), reverse=True)
    all_weights = [row["weight"] for row in rows]
    top1 = security_weights[0] if security_weights else 0.0
    top3 = sum(security_weights[:3])
    cash = sum(row["weight"] for row in rows if row["is_cash"])
    hhi = sum(weight * weight for weight in all_weights)
    effective_count = 1 / hhi if hhi else 0.0
    return {
        "holding_count": len(securities),
        "cash_weight": cash,
        "top1_weight": top1,
        "top3_weight": top3,
        "hhi": hhi,
        "effective_holding_count": effective_count,
        "assessment": _assess_concentration(top1, top3, len(securities), cash),
    }

def _build_exposures(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        "industry": _group_weights(rows, "industry"),
        "region": _group_weights(rows, "region"),
        "currency": _group_weights(rows, "currency"),
        "theme": _theme_weights(rows),
    }

def _build_risk_flags(exposures: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for category, groups in exposures.items():
        for name, weight in groups.items():
            if name in {"现金", UNKNOWN, "未分类"} or weight < EXPOSURE_LIMIT:
                continue
            level = "high" if weight >= 0.70 else "medium"
            flags.append(
                {
                    "category": category,
                    "name": name,
                    "weight": weight,
                    "level": level,
                    "message": f"{name} 暴露达到 {weight:.1%}",
                }
            )
    return flags

def _pair_drivers(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    drivers: list[str] = []
    if left["industry"] == right["industry"] != UNKNOWN:
        drivers.append("same_industry")
    if left["region"] == right["region"] != UNKNOWN:
        drivers.append("same_region")
    if left["currency"] == right["currency"] != UNKNOWN:
        drivers.append("same_currency")
    shared_themes = sorted(set(left["themes"]) & set(right["themes"]))
    drivers.extend(f"shared_theme:{theme}" for theme in shared_themes)
    return drivers

def _risk_level(drivers: list[str], combined_weight: float) -> str:
    if len(drivers) >= 3 or (len(drivers) >= 2 and combined_weight >= 0.50):
        return "high"
    return "medium"

def _build_correlation_risks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    securities = [row for row in rows if not row["is_cash"]]
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(securities, 2):
        drivers = _pair_drivers(left, right)
        if len(drivers) < 2:
            continue
        combined = left["weight"] + right["weight"]
        pairs.append(
            {
                "names": [left["name"], right["name"]],
                "combined_weight": combined,
                "drivers": drivers,
                "risk_level": _risk_level(drivers, combined),
            }
        )
    order = {"high": 0, "medium": 1}
    return sorted(pairs, key=lambda p: (order[p["risk_level"]], -p["combined_weight"]))

def _overall_health(
    concentration: dict[str, Any],
    flags: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    stress_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    high_flags = [flag for flag in flags if flag["level"] == "high"]
    severe_stress = [item for item in stress_tests if item["risk_level"] == "severe"]
    if high_flags or severe_stress or concentration["assessment"] == "问题严重":
        rating = "问题严重"
    elif flags or pairs or concentration["assessment"] == "需要调整":
        rating = "需要调整"
    else:
        rating = concentration["assessment"]
    drivers = [f"严重压力测试：{item['assumption']}" for item in severe_stress]
    drivers.extend(f"单一暴露：{flag['name']} {flag['weight']:.1%}" for flag in flags[:3])
    drivers.extend(
        f"相关性风险：{' / '.join(pair['names'])} {pair['combined_weight']:.1%}"
        for pair in pairs[:3]
    )
    if concentration["assessment"] in {"问题严重", "需要调整"}:
        drivers.append(f"集中度判断：{concentration['assessment']}")
    return {
        "rating": rating,
        "summary": "；".join(drivers) if drivers else "未发现触发降级的结构性风险。",
        "primary_driver": drivers[0] if drivers else "未发现触发降级的结构性风险。",
        "drivers": drivers,
    }

def analyze_portfolio(
    holdings: list[dict[str, Any]],
    cash_hurdle: float = DEFAULT_CASH_HURDLE,
) -> dict[str, Any]:
    rows = normalize_holdings(holdings)
    concentration = _build_concentration(rows)
    exposures = _build_exposures(rows)
    flags = _build_risk_flags(exposures)
    pairs = _build_correlation_risks(rows)
    stress_tests = build_stress_tests(rows)
    allocation_drift = build_allocation_drift(rows)
    opportunity_cost = build_opportunity_cost(rows, cash_hurdle=cash_hurdle)
    rebalance = build_rebalance_suggestions(
        rows,
        concentration,
        flags,
        opportunity_cost,
        allocation_drift,
    )
    return {
        "_source": "portfolio_analyzer",
        "holdings": rows,
        "concentration": concentration,
        "exposures": exposures,
        "risk_flags": flags,
        "correlation_risks": pairs,
        "stress_tests": stress_tests,
        "allocation_drift": allocation_drift,
        "opportunity_cost": opportunity_cost,
        "rebalance_suggestions": rebalance,
        "overall_health": _overall_health(concentration, flags, pairs, stress_tests),
    }

def _load_holdings(path: Path) -> list[dict[str, Any]]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise ValueError(f"无法读取输入文件 {path}: {reason}") from exc
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"输入 JSON 解析失败 {path}: 第 {exc.lineno} 行第 {exc.colno} 列") from exc
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("holdings"), list):
        return payload["holdings"]
    raise ValueError(f"输入 JSON 结构错误 {path}: 必须是持仓数组，或包含 holdings 数组的对象")

def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(description="组合级集中度与相关性离线分析工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="分析 JSON 持仓文件")
    analyze.add_argument("input", type=Path, help="JSON 文件路径")
    analyze.add_argument("--format", choices=["markdown", "json"], default="markdown")
    analyze.add_argument(
        "--cash-hurdle",
        type=float,
        default=DEFAULT_CASH_HURDLE,
        help="现金门槛/无风险收益率，可用小数 0.06 或百分数 6",
    )
    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            cash_hurdle = as_ratio(args.cash_hurdle, "--cash-hurdle")
        except ValueError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 2
        try:
            holdings = _load_holdings(args.input)
        except ValueError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 2
        try:
            analysis = analyze_portfolio(holdings, cash_hurdle=cash_hurdle)
        except ValueError as exc:
            print(f"错误: 输入持仓字段错误 {args.input}: {exc}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        else:
            print(render_markdown(analysis), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
