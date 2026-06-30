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


def _below_cash_text(row: dict[str, Any], cash_hurdle: float) -> str:
    return f"风险调整后 {row['risk_adjusted_return']:.1%} 低于现金门槛 {cash_hurdle:.1%}"


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


def _weight_text(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


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


def _tensions_by_type(
    valuation_sanity: dict[str, Any] | None,
    tension_type: str,
) -> dict[str, dict[str, Any]]:
    if not valuation_sanity:
        return {}
    return {
        item["name"]: item
        for item in valuation_sanity.get("tensions", [])
        if item.get("tension_type") == tension_type
    }


def _tension_message(tensions_by_name: dict[str, dict[str, Any]], name: str, fallback: str) -> str:
    tension = tensions_by_name.get(name)
    if not tension:
        return fallback
    labels = {
        "high_valuation_high_return": "高估高预期",
        "low_valuation_low_return": "低估低预期",
    }
    label = labels.get(tension.get("tension_type"), "估值水位张力")
    return f"{label}：{tension.get('message', fallback)}"


def _append_below_cash(
    items: list[dict[str, Any]],
    opportunity_cost: dict[str, Any],
    low_valuation_tensions: dict[str, dict[str, Any]],
) -> None:
    cash_hurdle = opportunity_cost["cash_hurdle"]
    below_cash = sorted(
        opportunity_cost["below_cash_hurdle"],
        key=lambda item: (-_weighted_cash_drag(item, cash_hurdle), item["name"]),
    )
    for row in below_cash:
        below_cash_reason = _below_cash_text(row, cash_hurdle)
        if row["name"] in low_valuation_tensions:
            tension = _tension_message(low_valuation_tensions, row["name"], "存在低估低预期张力")
            items.append(
                _item(
                    "review_valuation_tension",
                    row["name"],
                    "medium",
                    f"{below_cash_reason}，但{tension}，应先复核估值水位与 expected_return。",
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
                f"{below_cash_reason}，继续持有需要额外论文支撑。",
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
            f"第一大持仓 {largest['weight']:.1%} 超过 {TOP1_LIMIT:.0%} 集中度上限。",
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
    high_valuation_tensions: dict[str, dict[str, Any]],
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
            suggested_weight = _target_or_limit(row, "overweight")
            items.append(
                _item(
                    "trim_to_target",
                    row["name"],
                    "high",
                    f"当前 {_weight_text(row['current_weight'])}，建议回到 {_weight_text(suggested_weight)}；当前仓位高于目标仓位或上限。",
                    row["current_weight"],
                    suggested_weight,
                )
            )
        elif row["status"] == "underweight":
            if row["name"] in high_valuation_tensions:
                tension = _tension_message(
                    high_valuation_tensions, row["name"], "存在高估高预期张力"
                )
                items.append(
                    _item(
                        "review_valuation_tension",
                        row["name"],
                        "medium",
                        f"当前低配但{tension}，应先复核 PE 分位与 expected_return，再决定是否补足。",
                        row["current_weight"],
                        None,
                    )
                )
                seen_targets.add(row["name"])
                continue
            suggested_weight = _target_or_limit(row, "underweight")
            items.append(
                _item(
                    "add_to_target",
                    row["name"],
                    "medium",
                    f"当前 {_weight_text(row['current_weight'])}，建议补足到 {_weight_text(suggested_weight)}；若个股论文仍成立，可优先补足。",
                    row["current_weight"],
                    suggested_weight,
                )
            )
        seen_targets.add(row["name"])


def _append_cash_buffer(
    items: list[dict[str, Any]],
    concentration: dict[str, Any],
    opportunity_cost: dict[str, Any],
    high_valuation_tensions: dict[str, dict[str, Any]],
) -> None:
    cash_weight = concentration["cash_weight"]
    if cash_weight < MIN_CASH:
        items.append(
            _item(
                "raise_cash",
                "现金",
                "medium",
                f"现金 {cash_weight:.1%} 低于 {MIN_CASH:.0%}，组合抗冲击缓冲不足。",
                cash_weight,
                TARGET_CASH,
            )
        )
    elif cash_weight > MAX_CASH and opportunity_cost["ranked_holdings"]:
        eligible = [
            row
            for row in opportunity_cost["ranked_holdings"]
            if row["name"] not in high_valuation_tensions
        ]
        if not eligible:
            target = opportunity_cost["ranked_holdings"][0]
            tension = _tension_message(
                high_valuation_tensions, target["name"], "最高收益候选存在高估高预期张力"
            )
            items.append(
                _item(
                    "review_valuation_tension",
                    target["name"],
                    "medium",
                    f"现金 {cash_weight:.1%} 高于 {MAX_CASH:.0%}，但{tension}，应先复核估值水位再部署现金。",
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
                f"现金 {cash_weight:.1%} 高于 {MAX_CASH:.0%}，可优先研究风险调整后收益最高的已有持仓。",
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
    high_valuation_tensions = _tensions_by_type(valuation_sanity, "high_valuation_high_return")
    low_valuation_tensions = _tensions_by_type(valuation_sanity, "low_valuation_low_return")
    _append_below_cash(items, opportunity_cost, low_valuation_tensions)
    _append_allocation_drift(
        items, allocation_drift, missing_input_names, high_valuation_tensions
    )
    _append_concentration(items, rows, concentration)
    _append_cash_buffer(items, concentration, opportunity_cost, high_valuation_tensions)
    _append_missing_inputs(items, _weight_by_name(rows), opportunity_cost)
    _append_exposure_review(items, risk_flags)
    return {
        "primary_action": _primary_action(items),
        "items": items,
        "method": "基于机会成本、目标仓位偏离、集中度、估值水位张力、现金缓冲和单一暴露的机械建议；不替代个股研究。",
    }
