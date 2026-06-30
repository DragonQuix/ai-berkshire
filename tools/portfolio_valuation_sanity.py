#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


HIGH_VALUATION_THRESHOLD = 0.8
LOW_VALUATION_THRESHOLD = 0.2
HIGH_RETURN_THRESHOLD = 0.15
LOW_RETURN_THRESHOLD = 0.04

_TENSION_LABELS = {
    "high_valuation_high_return": "高估高预期",
    "low_valuation_low_return": "低估低预期",
}

_TENSION_MESSAGES = {
    "high_valuation_high_return": "PE 处于历史 {pct:.0%} 分位（高估区）与 {ret:.0%} 预期年化存在张力：高估值通常压缩未来回报",
    "low_valuation_low_return": "PE 处于历史 {pct:.0%} 分位（低估区）与 {ret:.0%} 预期年化存在张力：低估值可能隐含错杀机会，预期过低或未识别价值",
}


def tension_label(tension_type: str) -> str:
    return _TENSION_LABELS.get(tension_type, tension_type)


def _classify(pe_percentile: float, expected_return: float) -> str | None:
    if pe_percentile >= HIGH_VALUATION_THRESHOLD and expected_return >= HIGH_RETURN_THRESHOLD:
        return "high_valuation_high_return"
    if pe_percentile <= LOW_VALUATION_THRESHOLD and expected_return <= LOW_RETURN_THRESHOLD:
        return "low_valuation_low_return"
    return None


def build_valuation_sanity(
    rows: list[dict[str, Any]],
    opportunity_cost: dict[str, Any],
) -> dict[str, Any]:
    expected_by_name = {
        item["name"]: item["expected_return"]
        for item in opportunity_cost.get("ranked_holdings", [])
    }
    tensions: list[dict[str, Any]] = []
    for row in rows:
        if row.get("is_cash"):
            continue
        pe_percentile = row.get("pe_percentile")
        if pe_percentile is None:
            continue
        expected_return = expected_by_name.get(row["name"])
        if expected_return is None:
            continue
        tension_type = _classify(pe_percentile, expected_return)
        if tension_type is None:
            continue
        tensions.append(
            {
                "name": row["name"],
                "tension_type": tension_type,
                "pe_percentile": pe_percentile,
                "expected_return": expected_return,
                "message": _TENSION_MESSAGES[tension_type].format(
                    pct=pe_percentile, ret=expected_return
                ),
            }
        )
    return {
        "tensions": tensions,
        "tension_count": len(tensions),
    }