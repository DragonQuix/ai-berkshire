#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


SCENARIOS = [
    ("global_recession", "全球衰退：权益资产盈利和估值同步下修"),
    ("china_geopolitical", "中美/地缘风险升级：中国与台湾资产折价扩大"),
    ("rate_shock", "利率飙升：长久期成长资产估值压缩"),
    ("ai_capex_downcycle", "AI Capex 下行：AI算力与半导体链条回撤"),
]


def _text(row: dict[str, Any]) -> str:
    return " ".join(
        [
            str(row.get("industry", "")),
            str(row.get("region", "")),
            str(row.get("currency", "")),
            " ".join(str(item) for item in row.get("themes", [])),
        ]
    )


def _has_any(row: dict[str, Any], keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in _text(row).lower() for keyword in keywords)


def _shock(row: dict[str, Any], scenario: str) -> float:
    if row.get("is_cash"):
        return 0.0
    text = _text(row)
    if scenario == "global_recession":
        return -0.25
    if scenario == "china_geopolitical":
        if "中国" in text or "HKD" in text or "CNY" in text:
            return -0.40
        if "台湾" in text:
            return -0.30
        if "美国" in text or "USD" in text:
            return -0.10
        return -0.15
    if scenario == "rate_shock":
        if _has_any(row, ("科技", "互联网", "半导体", "AI", "云计算")):
            return -0.30
        return -0.15
    if scenario == "ai_capex_downcycle" and _has_any(row, ("AI", "半导体", "算力")):
        return -0.35
    return 0.0


def _risk_level(impact: float) -> str:
    if impact <= -0.30:
        return "severe"
    if impact <= -0.20:
        return "high"
    if impact <= -0.10:
        return "medium"
    return "low"


def build_stress_tests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tests = []
    for scenario, assumption in SCENARIOS:
        impacts = []
        for row in rows:
            shock = _shock(row, scenario)
            impacts.append(
                {
                    "name": row["name"],
                    "weight": row["weight"],
                    "shock": shock,
                    "contribution": row["weight"] * shock,
                }
            )
        impact = sum(item["contribution"] for item in impacts)
        tests.append(
            {
                "scenario": scenario,
                "assumption": assumption,
                "portfolio_impact": impact,
                "risk_level": _risk_level(impact),
                "largest_impacts": sorted(impacts, key=lambda item: item["contribution"])[:3],
            }
        )
    return tests
