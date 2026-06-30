#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _target_status_label(status: str) -> str:
    labels = {
        "not_configured": "未配置",
        "under_allocated": "目标合计低于 100%",
        "fully_allocated": "目标合计约等于 100%",
        "over_allocated": "目标合计超过 100%",
    }
    return labels.get(status, status)


def _target_gap_text(drift: dict[str, Any]) -> str:
    gap = drift["target_gap_to_full_allocation"]
    if drift["target_allocation_status"] == "not_configured":
        return "目标差额：未配置"
    if drift["target_allocation_status"] == "over_allocated":
        return f"目标超配：{_pct(abs(gap))}"
    if drift["target_allocation_status"] == "fully_allocated":
        return "目标差额：0.0%"
    return f"未分配目标：{_pct(gap)}"


def _allocation_item_status_label(status: str) -> str:
    labels = {
        "overweight": "超配",
        "underweight": "低配",
        "within_band": "约束内",
    }
    return labels.get(status, status)


def _rebalance_action_label(action: str) -> str:
    labels = {
        "reduce_or_exit": "减仓/清仓",
        "trim_to_target": "下调至目标/上限",
        "add_to_target": "提高至目标/下限",
        "trim_to_limit": "下调至集中度上限",
        "raise_cash": "提高现金",
        "deploy_cash_review": "研究现金用途",
        "fill_inputs": "补齐输入",
        "review_exposure": "复核暴露",
        "hold": "维持观察",
    }
    return labels.get(action, action)


def _rebalance_priority_label(priority: str) -> str:
    labels = {
        "high": "高",
        "medium": "中",
        "low": "低",
    }
    return labels.get(priority, priority)


def _risk_level_label(level: str) -> str:
    labels = {
        "severe": "严重",
        "high": "高",
        "medium": "中",
        "low": "低",
    }
    return labels.get(level, level)


def _correlation_driver_label(driver: str) -> str:
    labels = {
        "same_industry": "同行业",
        "same_region": "同地区",
        "same_currency": "同货币",
    }
    if driver.startswith("shared_theme:"):
        return f"共同主题：{driver.split(':', 1)[1]}"
    return labels.get(driver, driver)


def _render_group(title: str, groups: dict[str, float]) -> list[str]:
    lines = [f"### {title}", "", "| 分类 | 占比 |", "|---|---:|"]
    lines.extend(f"| {name} | {_pct(weight)} |" for name, weight in groups.items())
    return lines + [""]


def _append_correlation(lines: list[str], analysis: dict[str, Any]) -> None:
    lines.extend(["## 相关性风险", ""])
    risks = analysis["correlation_risks"]
    if not risks:
        lines.append("未发现至少两个风险驱动重叠的持仓组合。")
        return
    lines.extend(["| 持仓组合 | 合计占比 | 等级 | 驱动因素 |", "|---|---:|---|---|"])
    for pair in risks:
        drivers = ", ".join(_correlation_driver_label(driver) for driver in pair["drivers"])
        lines.append(
            "| "
            + " / ".join(pair["names"])
            + f" | {_pct(pair['combined_weight'])} | {_risk_level_label(pair['risk_level'])} | "
            + drivers
            + " |"
        )


def _append_stress(lines: list[str], analysis: dict[str, Any]) -> None:
    lines.extend(["", "## 压力测试", "", "| 情景 | 组合影响 | 等级 | 最大拖累 |", "|---|---:|---|---|"])
    for item in analysis["stress_tests"]:
        drag = item["largest_impacts"][0]
        lines.append(
            f"| {item['assumption']} | {_pct(item['portfolio_impact'])} | "
            f"{_risk_level_label(item['risk_level'])} | {drag['name']} {_pct(drag['contribution'])} |"
        )


def _append_opportunity(lines: list[str], analysis: dict[str, Any]) -> None:
    opportunity = analysis["opportunity_cost"]
    lines.extend(
        [
            "",
            "## 机会成本",
            "",
            f"现金门槛：{_pct(opportunity['cash_hurdle'])}",
            "",
        ]
    )
    ranked = opportunity["ranked_holdings"]
    if ranked:
        lines.extend(["| 排名 | 标的 | 占比 | 预期年化 | 确定性 | 风险调整后 |", "|---:|---|---:|---:|---:|---:|"])
        for idx, row in enumerate(ranked, start=1):
            lines.append(
                f"| {idx} | {row['name']} | {_pct(row['weight'])} | "
                f"{_pct(row['expected_return'])} | {_pct(row['conviction'])} | "
                f"{_pct(row['risk_adjusted_return'])} |"
            )
    weakest = opportunity["weakest_holding"]
    if weakest:
        lines.append(f"\n最弱持仓：{weakest['name']}（风险调整后 {_pct(weakest['risk_adjusted_return'])}）")
    if opportunity["below_cash_hurdle"]:
        below_cash = "、".join(
            f"{row['name']}（风险调整后 {_pct(row['risk_adjusted_return'])}）"
            for row in opportunity["below_cash_hurdle"]
        )
        lines.append(f"\n低于现金门槛：{below_cash}")
    if opportunity["missing_inputs"]:
        names = "、".join(opportunity["missing_inputs"])
        lines.append(f"\n数据不足：缺少预期收益输入：{names}")


def _append_allocation_drift(lines: list[str], analysis: dict[str, Any]) -> None:
    drift = analysis["allocation_drift"]
    lines.extend(
        [
            "",
            "## 目标仓位偏离",
            "",
            f"目标仓位合计：{_pct(drift['target_weight_sum'])}，{_target_gap_text(drift)}",
            f"目标覆盖状态：{_target_status_label(drift['target_allocation_status'])}",
            f"已设目标持仓当前占比：{_pct(drift['targeted_current_weight'])}，未设目标持仓当前占比：{_pct(drift['untargeted_current_weight'])}",
            f"理论换手率：{_pct(drift['turnover_to_target'])}",
            f"目标买入合计：{_pct(drift['buy_to_target'])}，目标卖出合计：{_pct(drift['sell_to_target'])}",
            f"约束区间最小换手率：{_pct(drift['turnover_to_band'])}",
            f"回到约束区间买入合计：{_pct(drift['buy_to_band'])}，卖出合计：{_pct(drift['sell_to_band'])}",
            "",
        ]
    )
    if not drift["has_targets"]:
        lines.append("未提供 `target_weight`、`min_weight` 或 `max_weight`，跳过目标仓位偏离诊断。")
        return
    lines.extend(
        [
            f"容差：{_pct(drift['tolerance'])}",
            "",
            "| 标的 | 当前占比 | 目标占比 | 下限 | 上限 | 偏离 | 回到约束区间调整 | 状态 |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in drift["items"]:
        target = "-" if item["target_weight"] is None else _pct(item["target_weight"])
        min_weight = "-" if item["min_weight"] is None else _pct(item["min_weight"])
        max_weight = "-" if item["max_weight"] is None else _pct(item["max_weight"])
        drift_value = "-" if item["drift_to_target"] is None else _pct(item["drift_to_target"])
        lines.append(
            f"| {item['name']} | {_pct(item['current_weight'])} | {target} | "
            f"{min_weight} | {max_weight} | {drift_value} | "
            f"{_pct(item['adjustment_to_band'])} | {_allocation_item_status_label(item['status'])} |"
        )


def _append_rebalance(lines: list[str], analysis: dict[str, Any]) -> None:
    suggestions = analysis["rebalance_suggestions"]
    lines.extend(
        [
            "",
            "## 再平衡建议",
            "",
            f"首要动作：**{suggestions['primary_action']}**",
            "",
            "| 优先级 | 动作 | 标的/暴露 | 当前占比 | 建议占比 | 理由 |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    if not suggestions["items"]:
        lines.append("| 低 | 维持观察 | 组合 | - | - | 暂无机械调仓建议，维持观察。 |")
        return
    for item in suggestions["items"]:
        current = "-" if item["current_weight"] is None else _pct(item["current_weight"])
        suggested = "-" if item["suggested_weight"] is None else _pct(item["suggested_weight"])
        priority = _rebalance_priority_label(item["priority"])
        action = _rebalance_action_label(item["action"])
        lines.append(
            f"| {priority} | {action} | {item['target']} | {current} | {suggested} | "
            f"{item['reason']} |"
        )


def _append_flags(lines: list[str], analysis: dict[str, Any]) -> None:
    lines.extend(["", "## 风险提示", ""])
    flags = analysis["risk_flags"]
    if flags:
        lines.extend(f"- {flag['message']}（{_risk_level_label(flag['level'])}）" for flag in flags)
    else:
        lines.append("- 未发现超过 50% 的单一暴露。")


def render_markdown(analysis: dict[str, Any]) -> str:
    c = analysis["concentration"]
    summary = analysis["executive_summary"]
    lines = [
        "# 组合级分析",
        "",
        f"整体健康度：**{summary['health_rating']}**",
        f"当前最大风险：{summary['primary_risk']}",
        f"最应该做的一件事：{summary['primary_action']}",
        f"首要动作口径：{summary['action_method']}",
        f"健康度依据：{summary['evidence_summary']}",
        "",
        "## 组合集中度",
        "",
        "| 指标 | 当前值 |",
        "|---|---:|",
        f"| 非现金持仓数 | {c['holding_count']} |",
        f"| 第一大持仓占比 | {_pct(c['top1_weight'])} |",
        f"| 前三大持仓占比 | {_pct(c['top3_weight'])} |",
        f"| 现金占比 | {_pct(c['cash_weight'])} |",
        f"| 有效持仓数 | {c['effective_holding_count']:.2f} |",
        f"| 集中度判断 | {c['assessment']} |",
        "",
        "## 行业/地域/货币暴露",
        "",
    ]
    labels = {"industry": "行业", "region": "地域", "currency": "货币", "theme": "主题"}
    for key, title in labels.items():
        lines.extend(_render_group(title, analysis["exposures"][key]))
    _append_correlation(lines, analysis)
    _append_stress(lines, analysis)
    _append_opportunity(lines, analysis)
    _append_allocation_drift(lines, analysis)
    _append_rebalance(lines, analysis)
    _append_flags(lines, analysis)
    return "\n".join(lines) + "\n"
