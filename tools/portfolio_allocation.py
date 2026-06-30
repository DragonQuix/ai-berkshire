#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


FULL_ALLOCATION_TOLERANCE = 0.005


def _has_targets(row: dict[str, Any]) -> bool:
    return any(row.get(field) is not None for field in ("target_weight", "min_weight", "max_weight"))


def _status(row: dict[str, Any], drift: float | None, tolerance: float) -> str:
    weight = row["weight"]
    min_weight = row.get("min_weight")
    max_weight = row.get("max_weight")
    if min_weight is not None and weight < min_weight:
        return "underweight"
    if max_weight is not None and weight > max_weight:
        return "overweight"
    if drift is not None and abs(drift) > tolerance:
        return "overweight" if drift > 0 else "underweight"
    return "within_band"


def _adjustment_to_band(row: dict[str, Any], drift: float | None, tolerance: float) -> float:
    weight = row["weight"]
    min_weight = row.get("min_weight")
    max_weight = row.get("max_weight")
    target = row.get("target_weight")
    if min_weight is not None and weight < min_weight:
        return min_weight - weight
    if max_weight is not None and weight > max_weight:
        return max_weight - weight
    if target is None or drift is None:
        return 0.0
    if drift > tolerance:
        return target + tolerance - weight
    if drift < -tolerance:
        return target - tolerance - weight
    return 0.0


def _build_item(row: dict[str, Any], tolerance: float) -> dict[str, Any]:
    target = row.get("target_weight")
    drift = None if target is None else row["weight"] - target
    return {
        "name": row["name"],
        "current_weight": row["weight"],
        "target_weight": target,
        "min_weight": row.get("min_weight"),
        "max_weight": row.get("max_weight"),
        "drift_to_target": drift,
        "status": _status(row, drift, tolerance),
        "adjustment_to_band": _adjustment_to_band(row, drift, tolerance),
    }


def _sum_positive_drifts(items: list[dict[str, Any]]) -> float:
    return sum(max(item["drift_to_target"] or 0.0, 0.0) for item in items)


def _sum_negative_drifts(items: list[dict[str, Any]]) -> float:
    return sum(abs(min(item["drift_to_target"] or 0.0, 0.0)) for item in items)


def _target_weight_sum(items: list[dict[str, Any]]) -> float:
    return sum(item["target_weight"] or 0.0 for item in items)


def _targeted_current_weight(items: list[dict[str, Any]]) -> float:
    return sum(item["current_weight"] for item in items if item["target_weight"] is not None)


def _target_allocation_status(items: list[dict[str, Any]], target_sum: float) -> str:
    if not items:
        return "not_configured"
    gap = 1.0 - target_sum
    if abs(gap) <= FULL_ALLOCATION_TOLERANCE:
        return "fully_allocated"
    return "under_allocated" if gap > 0 else "over_allocated"


def _sum_positive_adjustments(items: list[dict[str, Any]]) -> float:
    return sum(max(item["adjustment_to_band"], 0.0) for item in items)


def _sum_negative_adjustments(items: list[dict[str, Any]]) -> float:
    return sum(abs(min(item["adjustment_to_band"], 0.0)) for item in items)


def build_allocation_drift(
    rows: list[dict[str, Any]],
    tolerance: float = 0.03,
) -> dict[str, Any]:
    items = [_build_item(row, tolerance) for row in rows if _has_targets(row)]
    attention = [item for item in items if item["status"] != "within_band"]
    sell_to_target = _sum_positive_drifts(items)
    buy_to_target = _sum_negative_drifts(items)
    sell_to_band = _sum_negative_adjustments(items)
    buy_to_band = _sum_positive_adjustments(items)
    target_sum = _target_weight_sum(items)
    targeted_current = _targeted_current_weight(items)
    primary = None
    if attention:
        primary = max(
            attention,
            key=lambda item: max(
                abs(item["drift_to_target"] or 0.0),
                abs(item["adjustment_to_band"]),
            ),
        )
    return {
        "has_targets": bool(items),
        "tolerance": tolerance,
        "items": items,
        "needs_attention": attention,
        "primary_drift": primary,
        "sell_to_target": sell_to_target,
        "buy_to_target": buy_to_target,
        "turnover_to_target": max(sell_to_target, buy_to_target),
        "unmatched_cash_delta": sell_to_target - buy_to_target,
        "sell_to_band": sell_to_band,
        "buy_to_band": buy_to_band,
        "turnover_to_band": max(sell_to_band, buy_to_band),
        "unmatched_band_cash_delta": sell_to_band - buy_to_band,
        "target_weight_sum": target_sum,
        "target_allocation_status": _target_allocation_status(items, target_sum),
        "target_gap_to_full_allocation": 1.0 - target_sum,
        "targeted_current_weight": targeted_current,
        "untargeted_current_weight": 1.0 - targeted_current,
    }
