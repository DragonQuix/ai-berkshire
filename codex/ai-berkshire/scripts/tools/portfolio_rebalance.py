#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


TOP1_LIMIT = 0.40
MIN_CASH = 0.03
TARGET_CASH = 0.10
MAX_CASH = 0.35


def _weight_by_name(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {row["name"]: row["weight"] for row in rows}


def _largest_security(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    securities = [row for row in rows if not row.get("is_cash")]
    if not securities:
        return None
    return max(securities, key=lambda row: row["weight"])


def _weighted_cash_drag(item: dict[str, Any], cash_hurdle: float) -> float:
    return item["weight"] * max(0.0, cash_hurdle - item["risk_adjusted_return"])


def _item(
    action: str,
    target: str,
    priority: str,
    reason: str,
    current_weight: float | None = None,
    suggested_weight: float | None = None,
) -> dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "priority": priority,
        "reason": reason,
        "current_weight": current_weight,
        "suggested_weight": suggested_weight,
    }


def _primary_action(items: list[dict[str, Any]]) -> str:
    if not items:
        return "维持观察"
    first = items[0]
    target = first["target"]
    labels = {
        "reduce_or_exit": f"减仓/清仓 {target}",
        "trim_to_target": f"下调 {target} 至目标仓位/上限",
        "add_to_target": f"提高 {target} 至目标仓位/下限",
        "trim_to_limit": f"下调 {target} 至集中度上限",
        "raise_cash": "提高现金仓位",
        "deploy_cash_review": f"研究现金用途：{target}",
        "fill_inputs": f"补齐 {target} 预期收益输入",
        "review_exposure": f"复核 {target} 单一暴露",
        "review_valuation_tension": f"复核 {target} 估值水位张力",
    }
    return labels.get(first["action"], f"复核 {target}")


def _high_valuation_tension_names(valuation_sanity: dict[str, Any] | None) -> set[str]:
    if not valuation_sanity:
        return set()
    return {
        item["name"]
        for item in valuation_sanity.get("tensions", [])
        if item.get("tension_type") == "high_valuation_high_return"
    }


def _low_valuation_tension_names(valuation_sanity: dict[str, Any] | None) -> set[str]:
    if not valuation_sanity:
        return set()
    return {
        item["name"]
        for item in valuation_sanity.get("tensions", [])
        if item.get("tension_type") == "low_valuation_low_return"
    }


def _append_below_cash(
    items: list[dict[str, Any]],
    opportunity_cost: dict[str, Any],
    low_valuation_tension_names: set[str],
) -> None:
    cash_hurdle = opportunity_cost["cash_hurdle"]
    below_cash = sorted(
        opportunity_cost["below_cash_hurdle"],
        key=lambda item: (-_weighted_cash_drag(item, cash_hurdle), item["name"]),
    )
    for row in below_cash:
        if row["name"] in low_valuation_tension_names:
            items.append(
                _item(
                    "review_valuation_tension",
                    row["name"],
                    "medium",
                    "风险调整后收益低于现金门槛，但存在低估低预期张力，应先复核估值水位与 expected_return。",
                    row["weight"],
                    None,
                )
            )
            continue
        items.append(
            _item(
                "reduce_or_exit",
                row["name"],
                "high",
                "风险调整后预期收益低于现金门槛，继续持有需要额外论文支撑。",
                row["weight"],
                0.0,
            )
        )


def _append_concentration(
    items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    concentration: dict[str, Any],
) -> None:
    largest = _largest_security(rows)
    seen_targets = {item["target"] for item in items}
    if not largest or concentration["top1_weight"] <= TOP1_LIMIT:
        return
    if largest["name"] in seen_targets:
        return
    items.append(
        _item(
            "trim_to_limit",
            largest["name"],
            "high",
            f"第一大持仓超过 {TOP1_LIMIT:.0%} 集中度上限。",
            largest["weight"],
            TOP1_LIMIT,
        )
    )


def _target_or_limit(item: dict[str, Any], status: str) -> float | None:
    target = item.get("target_weight")
    min_weight = item.get("min_weight")
    max_weight = item.get("max_weight")
    if status == "overweight":
        candidates = [value for value in (target, max_weight) if value is not None]
        return min(candidates) if candidates else None
    candidates = [value for value in (target, min_weight) if value is not None]
    return max(candidates) if candidates else None


def _append_allocation_drift(
    items: list[dict[str, Any]],
    allocation_drift: dict[str, Any] | None,
    missing_input_names: set[str],
    high_valuation_tension_names: set[str],
) -> None:
    if not allocation_drift:
        return
    seen_targets = {item["target"] for item in items}
    for row in allocation_drift["needs_attention"]:
        if row["name"] in seen_targets:
            continue
        if row["status"] == "underweight" and row["name"] in missing_input_names:
            continue
        if row["status"] == "overweight":
            items.append(
                _item(
                    "trim_to_target",
                    row["name"],
                    "high",
                    "当前仓位高于目标仓位或上限，应先回到目标约束内。",
                    row["current_weight"],
                    _target_or_limit(row, "overweight"),
                )
            )
        elif row["status"] == "underweight":
            if row["name"] in high_valuation_tension_names:
                items.append(
                    _item(
                        "review_valuation_tension",
                        row["name"],
                        "medium",
                        "当前低配但存在高估高预期张力，应先复核 PE 分位与 expected_return，再决定是否补足。",
                        row["current_weight"],
                        None,
                    )
                )
                seen_targets.add(row["name"])
                continue
            items.append(
                _item(
                    "add_to_target",
                    row["name"],
                    "medium",
                    "当前仓位低于目标仓位或下限，若个股论文仍成立，可优先补足。",
                    row["current_weight"],
                    _target_or_limit(row, "underweight"),
                )
            )
        seen_targets.add(row["name"])


def _append_cash_buffer(
    items: list[dict[str, Any]],
    concentration: dict[str, Any],
    opportunity_cost: dict[str, Any],
    high_valuation_tension_names: set[str],
) -> None:
    cash_weight = concentration["cash_weight"]
    if cash_weight < MIN_CASH:
        items.append(
            _item(
                "raise_cash",
                "现金",
                "medium",
                f"现金低于 {MIN_CASH:.0%}，组合抗冲击缓冲不足。",
                cash_weight,
                TARGET_CASH,
            )
        )
    elif cash_weight > MAX_CASH and opportunity_cost["ranked_holdings"]:
        eligible = [
            row
            for row in opportunity_cost["ranked_holdings"]
            if row["name"] not in high_valuation_tension_names
        ]
        if not eligible:
            target = opportunity_cost["ranked_holdings"][0]
            items.append(
                _item(
                    "review_valuation_tension",
                    target["name"],
                    "medium",
                    "现金偏高但最高收益候选存在高估高预期张力，应先复核估值水位再部署现金。",
                    target["weight"],
                    None,
                )
            )
            return
        target = eligible[0]["name"]
        items.append(
            _item(
                "deploy_cash_review",
                target,
                "medium",
                "现金占比偏高，可优先研究风险调整后收益最高的已有持仓。",
                cash_weight,
                MAX_CASH,
            )
        )


def _append_missing_inputs(
    items: list[dict[str, Any]],
    weights: dict[str, float],
    opportunity_cost: dict[str, Any],
) -> None:
    seen_targets = {item["target"] for item in items}
    for name in opportunity_cost["missing_inputs"]:
        if name in seen_targets:
            continue
        items.append(
            _item(
                "fill_inputs",
                name,
                "medium",
                "缺少 expected_return，无法纳入机会成本排序。",
                weights.get(name),
                None,
            )
        )


def _append_exposure_review(items: list[dict[str, Any]], risk_flags: list[dict[str, Any]]) -> None:
    if items or not risk_flags:
        return
    level_order = {"high": 0, "medium": 1, "low": 2}
    flag = min(
        risk_flags,
        key=lambda item: (level_order.get(item["level"], 9), -item["weight"], item["name"]),
    )
    reason = flag.get("message", "存在单一暴露偏高")
    items.append(
        _item(
            "review_exposure",
            flag["name"],
            flag["level"] if flag["level"] in {"high", "medium", "low"} else "low",
            f"{reason}，需结合个股论文判断是否降权。",
            flag["weight"],
            None,
        )
    )


def build_rebalance_suggestions(
    rows: list[dict[str, Any]],
    concentration: dict[str, Any],
    risk_flags: list[dict[str, Any]],
    opportunity_cost: dict[str, Any],
    allocation_drift: dict[str, Any] | None = None,
    valuation_sanity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    missing_input_names = set(opportunity_cost["missing_inputs"])
    high_valuation_names = _high_valuation_tension_names(valuation_sanity)
    low_valuation_names = _low_valuation_tension_names(valuation_sanity)
    _append_below_cash(items, opportunity_cost, low_valuation_names)
    _append_allocation_drift(
        items, allocation_drift, missing_input_names, high_valuation_names
    )
    _append_concentration(items, rows, concentration)
    _append_cash_buffer(items, concentration, opportunity_cost, high_valuation_names)
    _append_missing_inputs(items, _weight_by_name(rows), opportunity_cost)
    _append_exposure_review(items, risk_flags)
    return {
        "primary_action": _primary_action(items),
        "items": items,
        "method": "基于机会成本、目标仓位偏离、集中度、估值水位张力、现金缓冲和单一暴露的机械建议；不替代个股研究。",
    }
