#!/usr/bin/env python3
"""Cycle PE trap detector for cyclical industries.

离线判断周期股“低 PE 是否可能来自盈利周期顶部”，供投研报告估值节引用。
不联网、不依赖第三方包；输入必须来自年报、理杏仁或手工整理后的可信数据。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from typing import Any


CYCLICAL_BUCKETS = {
    "oil_gas": {
        "label": "油气",
        "keywords": ("油气", "石油", "天然气", "能源", "oil", "gas", "petroleum"),
        "commodity": "oil_price",
        "high_price": 80.0,
        "low_price": 50.0,
    },
    "coal": {
        "label": "煤炭",
        "keywords": ("煤炭", "煤", "coal"),
        "commodity": "coal_price",
        "high_price": 120.0,
        "low_price": 70.0,
    },
    "steel": {
        "label": "钢铁",
        "keywords": ("钢铁", "钢", "steel"),
        "commodity": "steel_price",
        "high_price": 5500.0,
        "low_price": 3500.0,
    },
    "shipping": {
        "label": "航运",
        "keywords": ("航运", "海运", "集运", "shipping", "freight"),
        "commodity": "freight_index",
        "high_price": 3000.0,
        "low_price": 1000.0,
    },
    "brokerage": {
        "label": "券商",
        "keywords": ("券商", "证券", "brokerage", "securities"),
        "commodity": "market_turnover_index",
        "high_price": 1.5,
        "low_price": 0.7,
    },
}


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (TypeError, ValueError, OSError):
            pass


def _to_float_list(values: list[Any]) -> list[float]:
    result = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"series contains non-numeric value: {value!r}") from exc
    return result


def _parse_series(raw: str | None, field_name: str) -> list[float]:
    if raw is None or raw == "":
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = [item.strip() for item in raw.split(",") if item.strip()]
    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must be a JSON array or comma-separated list")
    return _to_float_list(parsed)


def _detect_bucket(industry: str) -> str | None:
    text = industry.lower()
    for name, cfg in CYCLICAL_BUCKETS.items():
        if any(keyword.lower() in text for keyword in cfg["keywords"]):
            return name
    return None


def _near_peak(values: list[float], tolerance: float = 0.05) -> bool:
    if len(values) < 2:
        return False
    peak = max(values)
    return peak > 0 and values[-1] >= peak * (1 - tolerance)


def _near_trough(values: list[float], tolerance: float = 0.05) -> bool:
    if len(values) < 2:
        return False
    trough = min(values)
    if trough <= 0:
        return values[-1] <= trough * (1 + tolerance)
    return values[-1] <= trough * (1 + tolerance)


def _expanded_vs_history(values: list[float]) -> bool:
    if len(values) < 3:
        return False
    baseline = statistics.median(values[:-1])
    return baseline > 0 and values[-1] >= baseline * 1.25


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def analyze_cycle_pe_trap(
    industry: str,
    pe_percentile: float,
    net_profit: list[Any],
    revenue: list[Any] | None = None,
    commodity_price: float | None = None,
) -> dict:
    """Analyze whether a cyclical stock's low PE is a cycle-top trap."""
    bucket = _detect_bucket(industry)
    if bucket is None:
        return {
            "is_cyclical": False,
            "industry_bucket": None,
            "cycle_position": "non_cyclical",
            "risk_level": "not_applicable",
            "risk_score": 0,
            "signals": [],
            "explanation": ["行业未命中油气/煤炭/钢铁/航运/券商周期股规则，跳过周期 PE 陷阱判断。"],
        }

    profits = _to_float_list(net_profit)
    revenues = _to_float_list(revenue or [])
    if len(profits) < 3:
        raise ValueError("net_profit needs at least 3 annual values")

    cfg = CYCLICAL_BUCKETS[bucket]
    signals: list[str] = []
    explanation: list[str] = []
    score = 10

    low_mid_pe = pe_percentile <= 50
    if low_mid_pe:
        score += 25
        signals.append("low_mid_pe_at_peak")
        explanation.append(f"PE 历史分位 {pe_percentile:.1f}% 不高，低估值可能来自高盈利基数。")
    elif pe_percentile >= 75:
        signals.append("high_pe_percentile")

    if _near_peak(profits) or _expanded_vs_history(profits):
        score += 30
        signals.append("earnings_near_peak")
        explanation.append("最新净利润接近或显著高于历史区间，盈利可能处于周期高位。")
    elif _near_trough(profits):
        score -= 15
        signals.append("earnings_near_trough")

    if revenues and _near_peak(revenues):
        score += 10
        signals.append("revenue_near_peak")
        explanation.append("最新营收接近历史高位，收入端也显示周期高位特征。")

    if commodity_price is not None:
        price = float(commodity_price)
        if price >= float(cfg["high_price"]):
            score += 25
            signals.append("commodity_price_high")
            explanation.append(f"{cfg['label']}景气指标 {price:g} 高于高位阈值 {cfg['high_price']:g}。")
        elif price <= float(cfg["low_price"]):
            score -= 15
            signals.append("commodity_price_low")

    score = max(0, min(100, int(score)))
    if "earnings_near_trough" in signals and "commodity_price_low" in signals:
        position = "bottom"
    elif score >= 60 and "earnings_near_peak" in signals:
        position = "top"
    else:
        position = "mid"

    return {
        "is_cyclical": True,
        "industry_bucket": bucket,
        "industry_label": cfg["label"],
        "cycle_position": position,
        "risk_level": _risk_level(score),
        "risk_score": score,
        "signals": signals,
        "explanation": explanation,
        "inputs": {
            "industry": industry,
            "pe_percentile": float(pe_percentile),
            "net_profit": profits,
            "revenue": revenues,
            "commodity_price": commodity_price,
        },
    }


def _print_text(result: dict) -> None:
    print("=" * 60)
    print("周期 PE 陷阱检测")
    print("=" * 60)
    if not result["is_cyclical"]:
        print("行业类型: 非内置周期行业")
        print("结论: 不适用")
        return
    print(f"行业类型: {result['industry_label']} ({result['industry_bucket']})")
    print(f"周期位置: {result['cycle_position']}")
    print(f"风险等级: {result['risk_level']}")
    print(f"风险评分: {result['risk_score']}/100")
    print(f"信号: {', '.join(result['signals']) if result['signals'] else 'none'}")
    for item in result["explanation"]:
        print(f"- {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检测周期股低 PE 是否可能是周期顶部陷阱",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--industry", required=True, help="行业描述，如 油气/煤炭/钢铁/航运/券商")
    parser.add_argument("--pe-percentile", required=True, type=float, help="PE 历史分位点百分数，如 47.4")
    parser.add_argument("--net-profit", required=True, help="近年净利润序列，JSON 数组或逗号分隔")
    parser.add_argument("--revenue", default="", help="近年营收序列，JSON 数组或逗号分隔")
    parser.add_argument("--commodity-price", type=float, default=None, help="商品价格或景气指标")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = analyze_cycle_pe_trap(
            industry=args.industry,
            pe_percentile=args.pe_percentile,
            net_profit=_parse_series(args.net_profit, "net_profit"),
            revenue=_parse_series(args.revenue, "revenue"),
            commodity_price=args.commodity_price,
        )
    except ValueError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
