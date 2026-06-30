#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


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
    }


def build_allocation_drift(
    rows: list[dict[str, Any]],
    tolerance: float = 0.03,
) -> dict[str, Any]:
    items = [_build_item(row, tolerance) for row in rows if _has_targets(row)]
    attention = [item for item in items if item["status"] != "within_band"]
    primary = None
    if attention:
        primary = max(
            attention,
            key=lambda item: abs(item["drift_to_target"] or 0.0),
        )
    return {
        "has_targets": bool(items),
        "tolerance": tolerance,
        "items": items,
        "needs_attention": attention,
        "primary_drift": primary,
    }
