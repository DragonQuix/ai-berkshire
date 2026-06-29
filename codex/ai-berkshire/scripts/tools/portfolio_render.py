#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


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
        lines.append(
            "| "
            + " / ".join(pair["names"])
            + f" | {_pct(pair['combined_weight'])} | {pair['risk_level']} | "
            + ", ".join(pair["drivers"])
            + " |"
        )


def _append_stress(lines: list[str], analysis: dict[str, Any]) -> None:
    lines.extend(["", "## 压力测试", "", "| 情景 | 组合影响 | 等级 | 最大拖累 |", "|---|---:|---|---|"])
    for item in analysis["stress_tests"]:
        drag = item["largest_impacts"][0]
        lines.append(
            f"| {item['assumption']} | {_pct(item['portfolio_impact'])} | "
            f"{item['risk_level']} | {drag['name']} {_pct(drag['contribution'])} |"
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
    if opportunity["below_cash_hurdle"]:
        names = "、".join(row["name"] for row in opportunity["below_cash_hurdle"])
        lines.append(f"\n低于现金门槛：{names}")
    if opportunity["missing_inputs"]:
        names = "、".join(opportunity["missing_inputs"])
        lines.append(f"\n缺少预期收益输入：{names}")


def _append_flags(lines: list[str], analysis: dict[str, Any]) -> None:
    lines.extend(["", "## 风险提示", ""])
    flags = analysis["risk_flags"]
    if flags:
        lines.extend(f"- {flag['message']}（{flag['level']}）" for flag in flags)
    else:
        lines.append("- 未发现超过 50% 的单一暴露。")


def render_markdown(analysis: dict[str, Any]) -> str:
    c = analysis["concentration"]
    lines = [
        "# 组合级分析",
        "",
        f"整体健康度：**{analysis['overall_health']['rating']}**",
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
    _append_flags(lines, analysis)
    return "\n".join(lines) + "\n"
