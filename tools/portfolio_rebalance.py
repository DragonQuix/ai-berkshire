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
        "trim_to_limit": f"下调 {target} 至集中度上限",
        "raise_cash": "提高现金仓位",
        "deploy_cash_review": f"研究现金用途：{target}",
        "fill_inputs": f"补齐 {target} 预期收益输入",
    }
    return labels.get(first["action"], f"复核 {target}")


def _append_below_cash(items: list[dict[str, Any]], opportunity_cost: dict[str, Any]) -> None:
    cash_hurdle = opportunity_cost["cash_hurdle"]
    below_cash = sorted(
        opportunity_cost["below_cash_hurdle"],
        key=lambda item: (-_weighted_cash_drag(item, cash_hurdle), item["name"]),
    )
    for row in below_cash:
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


def _append_cash_buffer(
    items: list[dict[str, Any]],
    concentration: dict[str, Any],
    opportunity_cost: dict[str, Any],
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
        target = opportunity_cost["ranked_holdings"][0]["name"]
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
    for name in opportunity_cost["missing_inputs"]:
        items.append(
            _item(
                "fill_inputs",
                name,
                "medium",
                "缺少 expected_return 或 conviction，无法纳入机会成本排序。",
                weights.get(name),
                None,
            )
        )


def _append_exposure_review(items: list[dict[str, Any]], risk_flags: list[dict[str, Any]]) -> None:
    if items or not risk_flags:
        return
    flag = risk_flags[0]
    items.append(
        _item(
            "review_exposure",
            flag["name"],
            "low",
            "存在单一暴露偏高，需结合个股论文判断是否降权。",
            flag["weight"],
            None,
        )
    )


def build_rebalance_suggestions(
    rows: list[dict[str, Any]],
    concentration: dict[str, Any],
    risk_flags: list[dict[str, Any]],
    opportunity_cost: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    _append_below_cash(items, opportunity_cost)
    _append_concentration(items, rows, concentration)
    _append_cash_buffer(items, concentration, opportunity_cost)
    _append_missing_inputs(items, _weight_by_name(rows), opportunity_cost)
    _append_exposure_review(items, risk_flags)
    return {
        "primary_action": _primary_action(items),
        "items": items,
        "method": "基于机会成本、集中度和现金缓冲的机械建议；不替代个股研究。",
    }
