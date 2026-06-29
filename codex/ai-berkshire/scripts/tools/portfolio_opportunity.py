#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


DEFAULT_CASH_HURDLE = 0.04


def _ratio(value: Any) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    if number < 0:
        raise ValueError("expected_return 和 conviction 不可为负数")
    return number / 100.0 if number > 1 else number


def build_opportunity_cost(
    rows: list[dict[str, Any]],
    cash_hurdle: float = DEFAULT_CASH_HURDLE,
) -> dict[str, Any]:
    ranked = []
    missing = []
    for row in rows:
        if row.get("is_cash"):
            continue
        expected_return = _ratio(row.get("expected_return"))
        conviction = _ratio(row.get("conviction")) or 1.0
        if expected_return is None:
            missing.append(row["name"])
            continue
        risk_adjusted = expected_return * conviction
        ranked.append(
            {
                "name": row["name"],
                "weight": row["weight"],
                "expected_return": expected_return,
                "conviction": conviction,
                "risk_adjusted_return": risk_adjusted,
                "spread_to_cash": risk_adjusted - cash_hurdle,
            }
        )

    ranked.sort(key=lambda item: (-item["risk_adjusted_return"], item["name"]))
    below_cash = [item for item in ranked if item["risk_adjusted_return"] < cash_hurdle]
    return {
        "cash_hurdle": cash_hurdle,
        "ranked_holdings": ranked,
        "below_cash_hurdle": below_cash,
        "weakest_holding": ranked[-1] if ranked else None,
        "missing_inputs": missing,
    }
