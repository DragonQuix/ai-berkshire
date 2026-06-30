#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


DEFAULT_CASH_HURDLE = 0.04


def _as_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc


def _as_non_negative_ratio(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    number = _as_float(value, field)
    if number < 0:
        raise ValueError(f"{field} 不可为负数")
    return number / 100.0 if number > 1 else number


def _as_signed_ratio(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    number = _as_float(value, field)
    return number / 100.0 if abs(number) > 1 else number


def _as_confidence_ratio(value: Any, field: str) -> float | None:
    ratio = _as_non_negative_ratio(value, field)
    if ratio is not None and ratio > 1:
        raise ValueError(f"{field} 不能超过 100%")
    return ratio


def build_opportunity_cost(
    rows: list[dict[str, Any]],
    cash_hurdle: float = DEFAULT_CASH_HURDLE,
) -> dict[str, Any]:
    ranked = []
    missing = []
    for row in rows:
        if row.get("is_cash"):
            continue
        expected_return = _as_signed_ratio(
            row.get("expected_return"),
            f"{row['name']}.expected_return",
        )
        conviction = _as_confidence_ratio(row.get("conviction"), f"{row['name']}.conviction")
        if conviction is None:
            conviction = 1.0
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
                "pe_percentile": row.get("pe_percentile"),
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
