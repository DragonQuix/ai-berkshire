#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


UNKNOWN = "未知"
CASH_NAMES = {"现金", "cash", "CASH"}


def _as_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc
    if number <= 0:
        raise ValueError(f"{field} 必须大于 0")
    return number


def _as_non_negative_float(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是数字") from exc
    if number < 0:
        raise ValueError(f"{field} 不可为负数")
    return number


def _as_weight(value: Any, field: str) -> float:
    number = _as_float(value, field)
    if number > 100:
        raise ValueError(f"{field} 不能超过 100%")
    return number


def as_ratio(value: Any, field: str) -> float:
    number = _as_non_negative_float(value, field)
    ratio = number / 100.0 if number > 1 else number
    if ratio > 1:
        raise ValueError(f"{field} 不能超过 100%")
    return ratio


def _optional_ratio(value: Any, field: str) -> float | None:
    if value is None or value == "":
        return None
    return as_ratio(value, field)


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


def _validate_allocation_constraints(row: dict[str, Any]) -> None:
    name = row["name"]
    target = row["target_weight"]
    min_weight = row["min_weight"]
    max_weight = row["max_weight"]
    if min_weight is not None and max_weight is not None and min_weight > max_weight:
        raise ValueError(f"{name}.min_weight 不能大于 max_weight")
    if target is not None and min_weight is not None and target < min_weight:
        raise ValueError(f"{name}.target_weight 不能低于 min_weight")
    if target is not None and max_weight is not None and target > max_weight:
        raise ValueError(f"{name}.target_weight 不能高于 max_weight")


def _build_row(raw: dict[str, Any], name: str) -> dict[str, Any]:
    row = {
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
    _validate_allocation_constraints(row)
    return row


def _ensure_unique_names(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        name = row["name"]
        if name in seen:
            raise ValueError(f"持仓名称重复：{name}")
        seen.add(name)


def _ensure_unique_codes(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        code = row["code"]
        if not code:
            continue
        key = code.upper()
        if key in seen:
            raise ValueError(f"持仓代码重复：{code}")
        seen.add(key)


def normalize_holdings(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        raw_weights.append(_as_weight(raw.get("weight"), f"{name}.weight"))
        rows.append(_build_row(raw, name))
    _ensure_unique_names(rows)
    _ensure_unique_codes(rows)

    divisor = 100.0 if sum(raw_weights) > 1.5 else 1.0
    scaled = [weight / divisor for weight in raw_weights]
    total = sum(scaled)
    for row, weight in zip(rows, scaled):
        row["weight"] = weight / total
    return rows
