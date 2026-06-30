#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

from portfolio_allocation import build_allocation_drift
from portfolio_opportunity import DEFAULT_CASH_HURDLE, build_opportunity_cost
from portfolio_rebalance import build_rebalance_suggestions
from portfolio_render import render_markdown
from portfolio_stress import build_stress_tests


UNKNOWN = "未知"
CASH_NAMES = {"现金", "cash", "CASH"}
EXPOSURE_LIMIT = 0.50

def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def _as_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc
    if number <= 0:
        raise ValueError(f"{field} 必须大于 0")
    return number

def _as_ratio(value: Any, field: str) -> float:
    number = _as_float(value, field)
    return number / 100.0 if number > 1 else number

def _optional_ratio(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    return _as_ratio(value, field)

def _as_themes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("themes 必须是字符串或字符串数组")

def _is_cash(raw: dict[str, Any]) -> bool:
    asset_type = str(raw.get("asset_type", "")).lower()
    name = str(raw.get("name", "")).strip()
    code = str(raw.get("code", "")).strip()
    return asset_type == "cash" or name in CASH_NAMES or code in CASH_NAMES

def _normalize_holdings(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(holdings, list) or not holdings:
        raise ValueError("holdings 必须是非空数组")

    rows: list[dict[str, Any]] = []
    raw_weights: list[float] = []
    for idx, raw in enumerate(holdings, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"第 {idx} 个持仓必须是对象")
        name = str(raw.get("name") or raw.get("code") or "").strip()
        if not name:
            raise ValueError(f"第 {idx} 个持仓缺少 name 或 code")
        raw_weights.append(_as_float(raw.get("weight"), f"{name}.weight"))
        rows.append(
            {
                "name": name,
                "code": str(raw.get("code", "")).strip(),
                "weight": 0.0,
                "industry": str(raw.get("industry") or UNKNOWN).strip(),
                "region": str(raw.get("region") or UNKNOWN).strip(),
                "currency": str(raw.get("currency") or UNKNOWN).strip(),
                "themes": _as_themes(raw.get("themes")),
                "is_cash": _is_cash(raw),
                "expected_return": raw.get("expected_return"),
                "conviction": raw.get("conviction"),
                "target_weight": _optional_ratio(raw.get("target_weight"), f"{name}.target_weight"),
                "min_weight": _optional_ratio(raw.get("min_weight"), f"{name}.min_weight"),
                "max_weight": _optional_ratio(raw.get("max_weight"), f"{name}.max_weight"),
            }
        )

    divisor = 100.0 if sum(raw_weights) > 1.5 else 1.0
    scaled = [weight / divisor for weight in raw_weights]
    total = sum(scaled)
    for row, weight in zip(rows, scaled):
        row["weight"] = weight / total
    return rows

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
) -> dict[str, str]:
    high_flags = [flag for flag in flags if flag["level"] == "high"]
    if high_flags or concentration["assessment"] == "问题严重":
        rating = "问题严重"
    elif flags or pairs or concentration["assessment"] == "需要调整":
        rating = "需要调整"
    else:
        rating = concentration["assessment"]
    return {
        "rating": rating,
        "summary": "工具只做组合结构诊断，最终调仓仍需结合个股论文和估值水位。",
    }

def analyze_portfolio(
    holdings: list[dict[str, Any]],
    cash_hurdle: float = DEFAULT_CASH_HURDLE,
) -> dict[str, Any]:
    rows = _normalize_holdings(holdings)
    concentration = _build_concentration(rows)
    exposures = _build_exposures(rows)
    flags = _build_risk_flags(exposures)
    pairs = _build_correlation_risks(rows)
    stress_tests = build_stress_tests(rows)
    allocation_drift = build_allocation_drift(rows)
    opportunity_cost = build_opportunity_cost(rows, cash_hurdle=cash_hurdle)
    rebalance = build_rebalance_suggestions(rows, concentration, flags, opportunity_cost)
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
        "overall_health": _overall_health(concentration, flags, pairs),
    }

def _load_holdings(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("holdings"), list):
        return payload["holdings"]
    raise ValueError("输入 JSON 必须是持仓数组，或包含 holdings 数组的对象")

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
        analysis = analyze_portfolio(
            _load_holdings(args.input),
            cash_hurdle=_as_ratio(args.cash_hurdle, "--cash-hurdle"),
        )
        if args.format == "json":
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        else:
            print(render_markdown(analysis), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
