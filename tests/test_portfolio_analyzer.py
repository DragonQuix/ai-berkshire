# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO / "tools"
SAMPLE_FILE = REPO / "examples" / "portfolio-holdings.sample.json"
sys.path.insert(0, str(TOOLS_DIR))

import portfolio_analyzer as pa  # noqa: E402


SAMPLE_HOLDINGS = [
    {
        "name": "腾讯",
        "code": "00700.HK",
        "weight": 35,
        "industry": "互联网",
        "region": "中国",
        "currency": "HKD",
        "themes": ["中国互联网", "AI应用"],
    },
    {
        "name": "阿里巴巴",
        "code": "09988.HK",
        "weight": 20,
        "industry": "互联网",
        "region": "中国",
        "currency": "HKD",
        "themes": ["中国互联网", "云计算"],
    },
    {
        "name": "台积电",
        "code": "TSM",
        "weight": 15,
        "industry": "半导体",
        "region": "台湾",
        "currency": "USD",
        "themes": ["AI算力", "半导体"],
    },
    {
        "name": "英伟达",
        "code": "NVDA",
        "weight": 10,
        "industry": "半导体",
        "region": "美国",
        "currency": "USD",
        "themes": ["AI算力", "半导体"],
    },
    {
        "name": "现金",
        "weight": 20,
        "asset_type": "cash",
        "region": "现金",
        "currency": "CNY",
    },
]


def test_analyze_portfolio_normalizes_percent_weights_and_scores_concentration() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)

    concentration = analysis["concentration"]
    assert concentration["holding_count"] == 4
    assert concentration["cash_weight"] == pytest.approx(0.20)
    assert concentration["top1_weight"] == pytest.approx(0.35)
    assert concentration["top3_weight"] == pytest.approx(0.70)
    assert concentration["effective_holding_count"] == pytest.approx(4.26, abs=0.01)
    assert concentration["assessment"] == "良好"


def test_exposure_analysis_flags_industry_region_and_currency_concentration() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)

    exposures = analysis["exposures"]
    assert exposures["industry"]["互联网"] == pytest.approx(0.55)
    assert exposures["region"]["中国"] == pytest.approx(0.55)
    assert exposures["currency"]["HKD"] == pytest.approx(0.55)

    flags = {(flag["category"], flag["name"]) for flag in analysis["risk_flags"]}
    assert ("industry", "互联网") in flags
    assert ("region", "中国") in flags
    assert ("currency", "HKD") in flags


def test_correlation_analysis_identifies_overlapping_risk_pairs() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)

    pairs = analysis["correlation_risks"]
    china_internet = next(pair for pair in pairs if pair["names"] == ["腾讯", "阿里巴巴"])
    assert china_internet["combined_weight"] == pytest.approx(0.55)
    assert china_internet["risk_level"] == "high"
    assert "same_industry" in china_internet["drivers"]
    assert "shared_theme:中国互联网" in china_internet["drivers"]


def test_stress_tests_estimate_scenario_level_drawdowns() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)

    scenarios = {item["scenario"]: item for item in analysis["stress_tests"]}
    china = scenarios["china_geopolitical"]
    assert china["portfolio_impact"] == pytest.approx(-0.275)
    assert china["risk_level"] == "high"
    assert china["largest_impacts"][0]["name"] == "腾讯"
    assert china["largest_impacts"][0]["contribution"] == pytest.approx(-0.14)

    ai_cycle = scenarios["ai_capex_downcycle"]
    assert ai_cycle["portfolio_impact"] == pytest.approx(-0.21)
    assert ai_cycle["risk_level"] == "high"


def test_overall_health_reflects_severe_stress_test() -> None:
    holdings = [
        {
            "name": "腾讯",
            "weight": 25,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
        },
        {
            "name": "台积电",
            "weight": 25,
            "industry": "半导体",
            "region": "台湾",
            "currency": "TWD",
            "themes": ["晶圆制造"],
        },
        {
            "name": "Salesforce",
            "weight": 25,
            "industry": "软件",
            "region": "美国",
            "currency": "USD",
            "themes": ["云计算"],
        },
        {
            "name": "ASML",
            "weight": 25,
            "industry": "设备",
            "region": "荷兰",
            "currency": "EUR",
            "themes": ["AI光刻"],
        },
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["concentration"]["assessment"] == "需要调整"
    assert not analysis["risk_flags"]
    assert any(item["risk_level"] == "severe" for item in analysis["stress_tests"])
    assert analysis["overall_health"]["rating"] == "问题严重"


def test_overall_health_explains_rating_drivers_in_json_and_markdown() -> None:
    holdings = [
        {
            "name": "腾讯",
            "weight": 25,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
        },
        {
            "name": "台积电",
            "weight": 25,
            "industry": "半导体",
            "region": "台湾",
            "currency": "TWD",
            "themes": ["晶圆制造"],
        },
        {
            "name": "Salesforce",
            "weight": 25,
            "industry": "软件",
            "region": "美国",
            "currency": "USD",
            "themes": ["云计算"],
        },
        {
            "name": "ASML",
            "weight": 25,
            "industry": "设备",
            "region": "荷兰",
            "currency": "EUR",
            "themes": ["AI光刻"],
        },
    ]

    analysis = pa.analyze_portfolio(holdings)
    markdown = pa.render_markdown(analysis)

    assert (
        "严重压力测试：利率飙升：长久期成长资产估值压缩"
        in analysis["overall_health"]["drivers"]
    )
    assert analysis["overall_health"]["primary_driver"] == "严重压力测试：利率飙升：长久期成长资产估值压缩"
    assert "健康度依据：严重压力测试：利率飙升：长久期成长资产估值压缩" in markdown
    assert "当前最大风险：严重压力测试：利率飙升：长久期成长资产估值压缩" in markdown


def test_overall_health_explains_exposure_and_correlation_drivers() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)

    drivers = analysis["overall_health"]["drivers"]
    assert "单一暴露：互联网 55.0%" in drivers
    assert "相关性风险：腾讯 / 阿里巴巴 55.0%" in drivers


def test_overall_health_reflects_opportunity_cost_below_cash() -> None:
    holdings = [
        {
            "name": "腾讯",
            "weight": 20,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
            "expected_return": 0.08,
            "conviction": 1.0,
        },
        {
            "name": "台积电",
            "weight": 20,
            "industry": "半导体",
            "region": "台湾",
            "currency": "TWD",
            "themes": ["晶圆制造"],
            "expected_return": 0.09,
            "conviction": 1.0,
        },
        {
            "name": "Costco",
            "weight": 20,
            "industry": "零售",
            "region": "美国",
            "currency": "USD",
            "themes": ["会员制"],
            "expected_return": 0.03,
            "conviction": 1.0,
        },
        {
            "name": "ASML",
            "weight": 20,
            "industry": "设备",
            "region": "荷兰",
            "currency": "EUR",
            "themes": ["光刻"],
            "expected_return": 0.07,
            "conviction": 1.0,
        },
        {"name": "现金", "weight": 20, "asset_type": "cash", "region": "现金", "currency": "CNY"},
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["concentration"]["assessment"] == "良好"
    assert analysis["overall_health"]["rating"] == "需要调整"
    assert analysis["overall_health"]["primary_driver"] == "机会成本：Costco 低于现金门槛"
    assert "机会成本：Costco 低于现金门槛" in analysis["overall_health"]["drivers"]


def test_overall_health_marks_missing_expected_return_as_data_insufficient() -> None:
    holdings = [
        {
            "name": "Costco",
            "weight": 20,
            "industry": "零售",
            "region": "美国",
            "currency": "USD",
            "themes": ["会员制"],
        },
        {
            "name": "Novo Nordisk",
            "weight": 20,
            "industry": "医药",
            "region": "丹麦",
            "currency": "DKK",
            "themes": ["慢病管理"],
        },
        {
            "name": "LVMH",
            "weight": 20,
            "industry": "奢侈品",
            "region": "法国",
            "currency": "EUR",
            "themes": ["高端消费"],
        },
        {
            "name": "Unilever",
            "weight": 20,
            "industry": "日用消费",
            "region": "英国",
            "currency": "GBP",
            "themes": ["必选消费"],
        },
        {"name": "现金", "weight": 20, "asset_type": "cash", "region": "现金", "currency": "CNY"},
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["concentration"]["assessment"] == "良好"
    assert not analysis["risk_flags"]
    assert not analysis["correlation_risks"]
    assert analysis["overall_health"]["rating"] == "数据不足"
    assert (
        analysis["overall_health"]["primary_driver"]
        == "数据缺口：缺少预期收益输入：Costco、Novo Nordisk、LVMH、Unilever"
    )
    assert analysis["executive_summary"]["health_rating"] == "数据不足"


def test_render_markdown_answers_top_level_primary_action() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.03, "conviction": 0.7},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.10, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.08, "conviction": 0.7},
        SAMPLE_HOLDINGS[4],
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    summary_section = markdown.split("## 组合集中度", 1)[0]

    assert "最应该做的一件事：减仓/清仓 阿里巴巴" in summary_section


def test_executive_summary_carries_top_level_report_contract() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.03, "conviction": 0.7},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.10, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.08, "conviction": 0.7},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)
    summary = analysis["executive_summary"]

    assert summary == {
        "health_rating": analysis["overall_health"]["rating"],
        "primary_risk": analysis["overall_health"]["primary_driver"],
        "primary_action": analysis["rebalance_suggestions"]["primary_action"],
        "action_method": analysis["rebalance_suggestions"]["method"],
        "data_gap_summary": "未发现首屏级数据缺口。",
        "valuation_sanity_summary": "未发现预期收益与估值水位的张力。",
        "evidence_summary": analysis["overall_health"]["summary"],
    }


def test_executive_summary_surfaces_missing_expected_return() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.03, "conviction": 0.7},
        SAMPLE_HOLDINGS[2],
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.08, "conviction": 0.7},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["executive_summary"]["data_gap_summary"] == "缺少预期收益输入：台积电"


def test_render_markdown_uses_executive_summary_for_top_section() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.03, "conviction": 0.7},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.10, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.08, "conviction": 0.7},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)
    analysis["executive_summary"] = {
        "health_rating": "测试健康度",
        "primary_risk": "测试最大风险",
        "primary_action": "测试首要动作",
        "action_method": "测试口径",
        "data_gap_summary": "测试数据缺口",
        "valuation_sanity_summary": "测试张力",
        "evidence_summary": "测试依据",
    }

    summary_section = pa.render_markdown(analysis).split("## 组合集中度", 1)[0]

    assert "整体健康度：**测试健康度**" in summary_section
    assert "当前最大风险：测试最大风险" in summary_section
    assert "最应该做的一件事：测试首要动作" in summary_section
    assert "首要动作口径：测试口径" in summary_section
    assert "数据缺口：测试数据缺口" in summary_section
    assert "估值水位张力：测试张力" in summary_section
    assert "健康度依据：测试依据" in summary_section


def test_opportunity_cost_ranks_holdings_against_cash_hurdle() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.05, "conviction": 0.6},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.18, "conviction": 0.5},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.07, "conviction": 0.4},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    opportunity = analysis["opportunity_cost"]
    assert opportunity["cash_hurdle"] == pytest.approx(0.04)
    assert [row["name"] for row in opportunity["ranked_holdings"]] == [
        "腾讯",
        "台积电",
        "阿里巴巴",
        "英伟达",
    ]
    assert opportunity["ranked_holdings"][0]["risk_adjusted_return"] == pytest.approx(0.096)
    assert opportunity["weakest_holding"]["name"] == "英伟达"
    assert [row["name"] for row in opportunity["below_cash_hurdle"]] == ["阿里巴巴", "英伟达"]


def test_zero_conviction_is_not_treated_as_default_full_conviction() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0},
        *SAMPLE_HOLDINGS[1:],
    ]

    analysis = pa.analyze_portfolio(holdings)

    tencent = analysis["opportunity_cost"]["ranked_holdings"][0]
    assert tencent["name"] == "腾讯"
    assert tencent["conviction"] == pytest.approx(0.0)
    assert tencent["risk_adjusted_return"] == pytest.approx(0.0)
    assert [row["name"] for row in analysis["opportunity_cost"]["below_cash_hurdle"]] == ["腾讯"]


def test_conviction_ratio_cannot_exceed_full_confidence() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 150},
        *SAMPLE_HOLDINGS[1:],
    ]

    with pytest.raises(ValueError, match="腾讯.conviction 不能超过 100%"):
        pa.analyze_portfolio(holdings)


def test_expected_return_allows_negative_percent_values() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": -5, "conviction": 1.0},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.03, "conviction": 1.0},
        *SAMPLE_HOLDINGS[2:],
    ]

    analysis = pa.analyze_portfolio(holdings)

    opportunity = analysis["opportunity_cost"]
    tencent = next(row for row in opportunity["ranked_holdings"] if row["name"] == "腾讯")
    assert tencent["expected_return"] == pytest.approx(-0.05)
    assert tencent["risk_adjusted_return"] == pytest.approx(-0.05)
    assert tencent["spread_to_cash"] == pytest.approx(-0.09)
    assert [row["name"] for row in opportunity["below_cash_hurdle"]] == ["阿里巴巴", "腾讯"]
    assert opportunity["weakest_holding"]["name"] == "腾讯"


@pytest.mark.parametrize(
    "field, message",
    [
        ("expected_return", "腾讯.expected_return 必须是数字"),
        ("conviction", "腾讯.conviction 必须是数字"),
    ],
)
def test_opportunity_inputs_must_be_numeric(field: str, message: str) -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8, field: "not-a-number"},
        *SAMPLE_HOLDINGS[1:],
    ]

    with pytest.raises(ValueError, match=message):
        pa.analyze_portfolio(holdings)


def test_analyze_portfolio_allows_custom_cash_hurdle() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.05, "conviction": 1.0},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.08, "conviction": 1.0},
        *SAMPLE_HOLDINGS[2:],
    ]

    analysis = pa.analyze_portfolio(holdings, cash_hurdle=0.06)

    opportunity = analysis["opportunity_cost"]
    assert opportunity["cash_hurdle"] == pytest.approx(0.06)
    assert [row["name"] for row in opportunity["below_cash_hurdle"]] == ["腾讯"]
    assert analysis["rebalance_suggestions"]["primary_action"] == "减仓/清仓 腾讯"


def test_rebalance_suggestions_turn_diagnostics_into_actions() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 55, "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "weight": 20, "expected_return": 0.03, "conviction": 0.7},
        {**SAMPLE_HOLDINGS[2], "weight": 15},
        {**SAMPLE_HOLDINGS[3], "weight": 8, "expected_return": 0.06, "conviction": 0.5},
        {**SAMPLE_HOLDINGS[4], "weight": 2},
    ]

    analysis = pa.analyze_portfolio(holdings)

    suggestions = analysis["rebalance_suggestions"]
    assert suggestions["primary_action"] == "减仓/清仓 阿里巴巴"
    actions = {(item["action"], item["target"]) for item in suggestions["items"]}
    assert ("reduce_or_exit", "阿里巴巴") in actions
    assert ("trim_to_limit", "腾讯") in actions
    assert ("raise_cash", "现金") in actions
    assert ("fill_inputs", "台积电") in actions
    ali = next(item for item in suggestions["items"] if item["target"] == "阿里巴巴")
    assert ali["current_weight"] == pytest.approx(0.20)
    assert ali["suggested_weight"] == pytest.approx(0.0)


def test_rebalance_missing_input_reason_only_mentions_expected_return() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.08},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.07},
        SAMPLE_HOLDINGS[2],
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.06},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    missing = next(
        item
        for item in analysis["rebalance_suggestions"]["items"]
        if item["action"] == "fill_inputs"
    )
    assert missing["target"] == "台积电"
    assert missing["reason"] == "缺少 expected_return，无法纳入机会成本排序。"
    assert "conviction" not in missing["reason"]


def test_allocation_drift_flags_target_weight_deviations() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 45, "target_weight": 35, "max_weight": 40},
        {**SAMPLE_HOLDINGS[1], "weight": 12, "target_weight": 20, "min_weight": 15},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "target_weight": 15, "min_weight": 10, "max_weight": 20},
        {**SAMPLE_HOLDINGS[3], "weight": 8},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 20},
    ]

    analysis = pa.analyze_portfolio(holdings)

    drift = analysis["allocation_drift"]
    assert drift["has_targets"] is True
    assert drift["primary_drift"]["name"] == "腾讯"
    rows = {row["name"]: row for row in drift["items"]}
    assert rows["腾讯"]["status"] == "overweight"
    assert rows["腾讯"]["drift_to_target"] == pytest.approx(0.10)
    assert rows["腾讯"]["max_weight"] == pytest.approx(0.40)
    assert rows["阿里巴巴"]["status"] == "underweight"
    assert rows["阿里巴巴"]["drift_to_target"] == pytest.approx(-0.08)
    assert rows["台积电"]["status"] == "within_band"
    assert [row["name"] for row in drift["needs_attention"]] == ["腾讯", "阿里巴巴"]
    assert drift["sell_to_target"] == pytest.approx(0.10)
    assert drift["buy_to_target"] == pytest.approx(0.08)
    assert drift["turnover_to_target"] == pytest.approx(0.10)
    assert drift["unmatched_cash_delta"] == pytest.approx(0.02)
    assert drift["target_weight_sum"] == pytest.approx(0.90)
    assert drift["target_allocation_status"] == "under_allocated"
    assert drift["target_gap_to_full_allocation"] == pytest.approx(0.10)
    assert drift["targeted_current_weight"] == pytest.approx(0.92)
    assert drift["untargeted_current_weight"] == pytest.approx(0.08)


def test_allocation_drift_classifies_full_and_over_allocated_targets() -> None:
    full_targets = [
        {**SAMPLE_HOLDINGS[0], "weight": 35, "target_weight": 35},
        {**SAMPLE_HOLDINGS[1], "weight": 20, "target_weight": 20},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "target_weight": 15},
        {**SAMPLE_HOLDINGS[3], "weight": 10, "target_weight": 10},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 20},
    ]
    over_targets = [
        {**SAMPLE_HOLDINGS[0], "weight": 35, "target_weight": 45},
        {**SAMPLE_HOLDINGS[1], "weight": 20, "target_weight": 25},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "target_weight": 20},
        {**SAMPLE_HOLDINGS[3], "weight": 10, "target_weight": 10},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 10},
    ]

    full_drift = pa.analyze_portfolio(full_targets)["allocation_drift"]
    over_drift = pa.analyze_portfolio(over_targets)["allocation_drift"]

    assert full_drift["target_weight_sum"] == pytest.approx(1.0)
    assert full_drift["target_allocation_status"] == "fully_allocated"
    assert over_drift["target_weight_sum"] == pytest.approx(1.10)
    assert over_drift["target_allocation_status"] == "over_allocated"
    assert over_drift["target_gap_to_full_allocation"] == pytest.approx(-0.10)


def test_allocation_drift_estimates_minimum_band_rebalance_without_targets() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 45, "max_weight": 40},
        {**SAMPLE_HOLDINGS[1], "weight": 10, "min_weight": 15},
        {**SAMPLE_HOLDINGS[2], "weight": 20, "min_weight": 15, "max_weight": 25},
        {**SAMPLE_HOLDINGS[3], "weight": 5},
        {**SAMPLE_HOLDINGS[4], "weight": 20},
    ]

    analysis = pa.analyze_portfolio(holdings)

    drift = analysis["allocation_drift"]
    rows = {row["name"]: row for row in drift["items"]}
    assert rows["腾讯"]["adjustment_to_band"] == pytest.approx(-0.05)
    assert rows["阿里巴巴"]["adjustment_to_band"] == pytest.approx(0.05)
    assert rows["台积电"]["adjustment_to_band"] == pytest.approx(0.0)
    assert drift["sell_to_band"] == pytest.approx(0.05)
    assert drift["buy_to_band"] == pytest.approx(0.05)
    assert drift["turnover_to_band"] == pytest.approx(0.05)
    assert drift["unmatched_band_cash_delta"] == pytest.approx(0.0)


@pytest.mark.parametrize(
    "override, message",
    [
        ({"min_weight": 40, "max_weight": 30}, "腾讯.min_weight 不能大于 max_weight"),
        ({"target_weight": 20, "min_weight": 30}, "腾讯.target_weight 不能低于 min_weight"),
        ({"target_weight": 50, "max_weight": 40}, "腾讯.target_weight 不能高于 max_weight"),
    ],
)
def test_allocation_constraints_must_be_internally_consistent(
    override: dict[str, float],
    message: str,
) -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], **override},
        *SAMPLE_HOLDINGS[1:],
    ]

    with pytest.raises(ValueError, match=message):
        pa.analyze_portfolio(holdings)


@pytest.mark.parametrize("field", ["target_weight", "min_weight", "max_weight"])
def test_allocation_constraint_ratios_cannot_exceed_full_weight(field: str) -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], field: 150},
        *SAMPLE_HOLDINGS[1:],
    ]

    with pytest.raises(ValueError, match=f"腾讯.{field} 不能超过 100%"):
        pa.analyze_portfolio(holdings)


def test_allocation_constraints_allow_zero_target_and_bounds() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "target_weight": 0,
            "min_weight": 0,
            "max_weight": 0,
        },
        *SAMPLE_HOLDINGS[1:],
    ]

    analysis = pa.analyze_portfolio(holdings)

    tencent = analysis["allocation_drift"]["items"][0]
    assert tencent["name"] == "腾讯"
    assert tencent["target_weight"] == pytest.approx(0.0)
    assert tencent["min_weight"] == pytest.approx(0.0)
    assert tencent["max_weight"] == pytest.approx(0.0)
    assert tencent["status"] == "overweight"


def test_holding_weight_ratio_cannot_exceed_full_weight() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 150},
        *SAMPLE_HOLDINGS[1:],
    ]

    with pytest.raises(ValueError, match="腾讯.weight 不能超过 100%"):
        pa.analyze_portfolio(holdings)


def test_holding_names_must_be_unique() -> None:
    holdings = [
        SAMPLE_HOLDINGS[0],
        {**SAMPLE_HOLDINGS[1], "name": "腾讯"},
        *SAMPLE_HOLDINGS[2:],
    ]

    with pytest.raises(ValueError, match="持仓名称重复：腾讯"):
        pa.analyze_portfolio(holdings)


def test_non_empty_holding_codes_must_be_unique() -> None:
    holdings = [
        SAMPLE_HOLDINGS[0],
        {**SAMPLE_HOLDINGS[1], "name": "腾讯控股", "code": "00700.HK"},
        *SAMPLE_HOLDINGS[2:],
    ]

    with pytest.raises(ValueError, match="持仓代码重复：00700.HK"):
        pa.analyze_portfolio(holdings)


def test_rebalance_suggestions_prioritize_allocation_drift_actions() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 45,
            "target_weight": 30,
            "max_weight": 35,
            "expected_return": 0.12,
            "conviction": 0.9,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 10,
            "target_weight": 20,
            "min_weight": 15,
            "expected_return": 0.10,
            "conviction": 0.9,
        },
        {**SAMPLE_HOLDINGS[2], "weight": 20, "target_weight": 20},
        {**SAMPLE_HOLDINGS[3], "weight": 5},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 20},
    ]

    analysis = pa.analyze_portfolio(holdings)

    suggestions = analysis["rebalance_suggestions"]
    assert suggestions["primary_action"] == "下调 腾讯 至目标仓位/上限"
    actions = {(item["action"], item["target"]) for item in suggestions["items"]}
    assert ("trim_to_target", "腾讯") in actions
    assert ("add_to_target", "阿里巴巴") in actions
    tencent = next(item for item in suggestions["items"] if item["target"] == "腾讯")
    alibaba = next(item for item in suggestions["items"] if item["target"] == "阿里巴巴")
    assert tencent["current_weight"] == pytest.approx(0.45)
    assert tencent["suggested_weight"] == pytest.approx(0.30)
    assert alibaba["current_weight"] == pytest.approx(0.10)
    assert alibaba["suggested_weight"] == pytest.approx(0.20)


def test_rebalance_does_not_add_underweight_holding_without_expected_return() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 30,
            "target_weight": 30,
            "expected_return": 0.08,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 10,
            "target_weight": 20,
            "min_weight": 15,
        },
        {
            **SAMPLE_HOLDINGS[2],
            "weight": 20,
            "target_weight": 20,
            "expected_return": 0.09,
        },
        {**SAMPLE_HOLDINGS[3], "weight": 20, "expected_return": 0.07},
        {**SAMPLE_HOLDINGS[4], "weight": 20},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    targets = [item["target"] for item in suggestions["items"]]
    alibaba = next(item for item in suggestions["items"] if item["target"] == "阿里巴巴")
    assert targets.count("阿里巴巴") == 1
    assert alibaba["action"] == "fill_inputs"
    assert alibaba["suggested_weight"] is None
    assert ("add_to_target", "阿里巴巴") not in {
        (item["action"], item["target"]) for item in suggestions["items"]
    }
    assert suggestions["primary_action"] == "补齐 阿里巴巴 预期收益输入"


def test_rebalance_does_not_add_underweight_high_valuation_tension() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 20,
            "target_weight": 20,
            "expected_return": 0.08,
            "pe_percentile": 0.50,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 10,
            "target_weight": 20,
            "min_weight": 15,
            "expected_return": 0.25,
            "pe_percentile": 0.92,
        },
        {**SAMPLE_HOLDINGS[2], "weight": 20, "target_weight": 20, "expected_return": 0.09},
        {**SAMPLE_HOLDINGS[3], "weight": 20, "expected_return": 0.07},
        {**SAMPLE_HOLDINGS[4], "weight": 30, "target_weight": 30},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    alibaba = next(item for item in suggestions["items"] if item["target"] == "阿里巴巴")
    assert alibaba["action"] == "review_valuation_tension"
    assert alibaba["suggested_weight"] is None
    assert "高估高预期" in alibaba["reason"]
    assert ("add_to_target", "阿里巴巴") not in {
        (item["action"], item["target"]) for item in suggestions["items"]
    }
    assert suggestions["primary_action"] == "复核 阿里巴巴 估值水位张力"


def test_rebalance_does_not_exit_low_valuation_low_return_without_review() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 20,
            "expected_return": 0.03,
            "pe_percentile": 0.15,
        },
        {**SAMPLE_HOLDINGS[1], "weight": 20, "expected_return": 0.08},
        {**SAMPLE_HOLDINGS[2], "weight": 20, "expected_return": 0.09},
        {**SAMPLE_HOLDINGS[3], "weight": 20, "expected_return": 0.07},
        {**SAMPLE_HOLDINGS[4], "weight": 20},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    tencent = next(item for item in suggestions["items"] if item["target"] == "腾讯")
    assert tencent["action"] == "review_valuation_tension"
    assert tencent["suggested_weight"] is None
    assert "低估低预期" in tencent["reason"]
    assert ("reduce_or_exit", "腾讯") not in {
        (item["action"], item["target"]) for item in suggestions["items"]
    }
    assert suggestions["primary_action"] == "复核 腾讯 估值水位张力"


def test_rebalance_deploy_cash_skips_high_valuation_tension_candidate() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 15, "expected_return": 0.25, "pe_percentile": 0.92},
        {**SAMPLE_HOLDINGS[1], "weight": 15, "expected_return": 0.12, "pe_percentile": 0.50},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "expected_return": 0.08},
        {**SAMPLE_HOLDINGS[3], "weight": 10, "expected_return": 0.06},
        {**SAMPLE_HOLDINGS[4], "weight": 45},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    deploy = next(item for item in suggestions["items"] if item["action"] == "deploy_cash_review")
    assert deploy["target"] == "阿里巴巴"
    assert all(
        item["target"] != "腾讯" or item["action"] != "deploy_cash_review"
        for item in suggestions["items"]
    )
    assert suggestions["primary_action"] == "研究现金用途：阿里巴巴"


def test_rebalance_reviews_valuation_tension_when_all_cash_deploy_candidates_are_high_valuation() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 15, "expected_return": 0.25, "pe_percentile": 0.92},
        {**SAMPLE_HOLDINGS[1], "weight": 15, "expected_return": 0.20, "pe_percentile": 0.88},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "expected_return": 0.18, "pe_percentile": 0.85},
        {**SAMPLE_HOLDINGS[3], "weight": 10, "expected_return": 0.16, "pe_percentile": 0.82},
        {**SAMPLE_HOLDINGS[4], "weight": 45},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    assert not any(item["action"] == "deploy_cash_review" for item in suggestions["items"])
    review = next(item for item in suggestions["items"] if item["action"] == "review_valuation_tension")
    assert review["target"] == "腾讯"
    assert suggestions["primary_action"] == "复核 腾讯 估值水位张力"


def test_rebalance_primary_action_names_exposure_review() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 30,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
            "expected_return": 0.10,
            "conviction": 1.0,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 25,
            "industry": "互联网",
            "region": "美国",
            "currency": "USD",
            "themes": ["云计算"],
            "expected_return": 0.09,
            "conviction": 1.0,
        },
        {
            **SAMPLE_HOLDINGS[2],
            "weight": 25,
            "industry": "半导体",
            "region": "台湾",
            "currency": "TWD",
            "themes": ["AI算力"],
            "expected_return": 0.08,
            "conviction": 1.0,
        },
        {**SAMPLE_HOLDINGS[4], "weight": 20},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    review = next(item for item in suggestions["items"] if item["action"] == "review_exposure")
    assert review["target"] == "互联网"
    assert review["priority"] == "medium"
    assert suggestions["primary_action"] == "复核 互联网 单一暴露"
    assert "单一暴露" in suggestions["method"]


def test_rebalance_exposure_review_prioritizes_highest_exposure_risk() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 20,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["AI"],
            "expected_return": 0.10,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 20,
            "industry": "互联网",
            "region": "美国",
            "currency": "USD",
            "themes": ["AI"],
            "expected_return": 0.09,
        },
        {
            **SAMPLE_HOLDINGS[2],
            "weight": 15,
            "industry": "互联网",
            "region": "台湾",
            "currency": "TWD",
            "themes": ["AI"],
            "expected_return": 0.08,
        },
        {
            **SAMPLE_HOLDINGS[3],
            "weight": 25,
            "industry": "半导体",
            "region": "日本",
            "currency": "JPY",
            "themes": ["AI"],
            "expected_return": 0.07,
        },
        {**SAMPLE_HOLDINGS[4], "weight": 20},
    ]

    suggestions = pa.analyze_portfolio(holdings)["rebalance_suggestions"]

    review = next(item for item in suggestions["items"] if item["action"] == "review_exposure")
    assert review["target"] == "AI"
    assert review["priority"] == "high"
    assert review["current_weight"] == pytest.approx(0.80)
    assert suggestions["primary_action"] == "复核 AI 单一暴露"


def test_render_markdown_outputs_portfolio_level_sections() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.05, "conviction": 0.6},
        *SAMPLE_HOLDINGS[2:],
    ]
    analysis = pa.analyze_portfolio(holdings)
    markdown = pa.render_markdown(analysis)

    assert "# 组合级分析" in markdown
    assert "## 组合集中度" in markdown
    assert "## 行业/地域/货币暴露" in markdown
    assert "## 相关性风险" in markdown
    assert "## 压力测试" in markdown
    assert "## 机会成本" in markdown
    assert "## 目标仓位偏离" in markdown
    assert "目标仓位合计" in markdown
    assert "目标覆盖状态" in markdown
    assert "理论换手率" in markdown
    assert "约束区间最小换手率" in markdown
    assert "## 再平衡建议" in markdown
    assert "互联网" in markdown


def test_render_markdown_labels_over_allocated_target_gap_as_positive_excess() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 35, "target_weight": 45},
        {**SAMPLE_HOLDINGS[1], "weight": 20, "target_weight": 25},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "target_weight": 20},
        {**SAMPLE_HOLDINGS[3], "weight": 10, "target_weight": 10},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 10},
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))

    assert "目标覆盖状态：目标合计超过 100%" in markdown
    assert "目标超配：10.0%" in markdown
    assert "未分配目标：-10.0%" not in markdown


def test_render_markdown_labels_unconfigured_targets_without_fake_gap() -> None:
    markdown = pa.render_markdown(pa.analyze_portfolio(SAMPLE_HOLDINGS))

    assert "目标覆盖状态：未配置" in markdown
    assert "目标差额：未配置" in markdown
    assert "未分配目标：100.0%" not in markdown


def test_render_markdown_localizes_allocation_item_statuses() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 45, "target_weight": 35, "max_weight": 40},
        {**SAMPLE_HOLDINGS[1], "weight": 12, "target_weight": 20, "min_weight": 15},
        {**SAMPLE_HOLDINGS[2], "weight": 15, "target_weight": 15, "min_weight": 10, "max_weight": 20},
        {**SAMPLE_HOLDINGS[3], "weight": 8},
        {**SAMPLE_HOLDINGS[4], "weight": 20, "target_weight": 20},
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))

    assert "| 腾讯 | 45.0% | 35.0% | - | 40.0% | 10.0% | -5.0% | 超配 |" in markdown
    assert "| 阿里巴巴 | 12.0% | 20.0% | 15.0% | - | -8.0% | 3.0% | 低配 |" in markdown
    assert "| 台积电 | 15.0% | 15.0% | 10.0% | 20.0% | 0.0% | 0.0% | 约束内 |" in markdown
    assert "overweight" not in markdown
    assert "underweight" not in markdown
    assert "within_band" not in markdown


def test_render_markdown_localizes_rebalance_actions() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "weight": 55, "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "weight": 20, "expected_return": 0.03, "conviction": 0.7},
        {**SAMPLE_HOLDINGS[2], "weight": 15},
        {**SAMPLE_HOLDINGS[3], "weight": 8, "expected_return": 0.06, "conviction": 0.5},
        {**SAMPLE_HOLDINGS[4], "weight": 2},
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    rebalance_section = markdown.split("## 再平衡建议", 1)[1].split("\n## ", 1)[0]

    assert "| 高 | 减仓/清仓 | 阿里巴巴 | 20.0% | 0.0% |" in rebalance_section
    assert "| 高 | 下调至集中度上限 | 腾讯 | 55.0% | 40.0% |" in rebalance_section
    assert "| 中 | 提高现金 | 现金 | 2.0% | 10.0% |" in rebalance_section
    assert "| 中 | 补齐输入 | 台积电 | 15.0% | - |" in rebalance_section
    assert "| high |" not in rebalance_section
    assert "| medium |" not in rebalance_section
    assert "| low |" not in rebalance_section
    assert "reduce_or_exit" not in markdown
    assert "trim_to_limit" not in markdown
    assert "raise_cash" not in markdown
    assert "fill_inputs" not in markdown


def test_render_markdown_localizes_empty_rebalance_row() -> None:
    holdings = [
        {
            "name": "腾讯",
            "weight": 20,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
            "expected_return": 0.08,
            "conviction": 1.0,
        },
        {
            "name": "台积电",
            "weight": 20,
            "industry": "半导体",
            "region": "台湾",
            "currency": "USD",
            "themes": ["制造"],
            "expected_return": 0.09,
            "conviction": 1.0,
        },
        {
            "name": "Costco",
            "weight": 20,
            "industry": "零售",
            "region": "美国",
            "currency": "USD",
            "themes": ["会员制"],
            "expected_return": 0.07,
            "conviction": 1.0,
        },
        {
            "name": "茅台",
            "weight": 20,
            "industry": "消费",
            "region": "中国",
            "currency": "CNY",
            "themes": ["白酒"],
            "expected_return": 0.06,
            "conviction": 1.0,
        },
        {"name": "现金", "weight": 20, "asset_type": "cash", "region": "现金", "currency": "CNY"},
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    rebalance_section = markdown.split("## 再平衡建议", 1)[1].split("\n## ", 1)[0]

    assert "| 低 | 维持观察 | 组合 | - | - | 暂无机械调仓建议，维持观察。 |" in rebalance_section
    assert "| low |" not in rebalance_section
    assert "| hold |" not in rebalance_section


def test_render_markdown_localizes_valuation_tension_rebalance_action() -> None:
    holdings = [
        {
            **SAMPLE_HOLDINGS[0],
            "weight": 20,
            "target_weight": 20,
            "expected_return": 0.08,
        },
        {
            **SAMPLE_HOLDINGS[1],
            "weight": 10,
            "target_weight": 20,
            "min_weight": 15,
            "expected_return": 0.25,
            "pe_percentile": 0.92,
        },
        {**SAMPLE_HOLDINGS[2], "weight": 20, "target_weight": 20, "expected_return": 0.09},
        {**SAMPLE_HOLDINGS[3], "weight": 20, "expected_return": 0.07},
        {**SAMPLE_HOLDINGS[4], "weight": 30, "target_weight": 30},
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    rebalance_section = markdown.split("## 再平衡建议", 1)[1].split("\n## ", 1)[0]

    assert "| 中 | 复核估值张力 | 阿里巴巴 | 10.0% | - |" in rebalance_section
    assert "review_valuation_tension" not in rebalance_section


def test_render_markdown_localizes_risk_levels() -> None:
    markdown = pa.render_markdown(pa.analyze_portfolio(SAMPLE_HOLDINGS))
    correlation_section = markdown.split("## 相关性风险", 1)[1].split("\n## ", 1)[0]
    stress_section = markdown.split("## 压力测试", 1)[1].split("\n## ", 1)[0]
    flags_section = markdown.split("## 风险提示", 1)[1]

    assert "| 腾讯 / 阿里巴巴 | 55.0% | 高 |" in correlation_section
    assert "| 中美/地缘风险升级：中国与台湾资产折价扩大 | -27.5% | 高 |" in stress_section
    assert "（中）" in flags_section
    for section in (correlation_section, stress_section, flags_section):
        assert "| high |" not in section
        assert "| medium |" not in section
        assert "| low |" not in section
        assert "（high）" not in section
        assert "（medium）" not in section
        assert "（low）" not in section


def test_render_markdown_localizes_severe_stress_risk_level() -> None:
    holdings = [
        {
            "name": "腾讯",
            "weight": 50,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["平台经济"],
        },
        {
            "name": "阿里巴巴",
            "weight": 50,
            "industry": "互联网",
            "region": "中国",
            "currency": "HKD",
            "themes": ["云计算"],
        },
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    stress_section = markdown.split("## 压力测试", 1)[1].split("\n## ", 1)[0]

    assert "| 中美/地缘风险升级：中国与台湾资产折价扩大 | -40.0% | 严重 |" in stress_section
    assert "| severe |" not in stress_section


def test_render_markdown_localizes_correlation_drivers() -> None:
    markdown = pa.render_markdown(pa.analyze_portfolio(SAMPLE_HOLDINGS))
    correlation_section = markdown.split("## 相关性风险", 1)[1].split("\n## ", 1)[0]

    assert "同行业, 同地区, 同货币, 共同主题：中国互联网" in correlation_section
    assert "共同主题：AI算力, 共同主题：半导体" in correlation_section
    assert "same_industry" not in correlation_section
    assert "same_region" not in correlation_section
    assert "same_currency" not in correlation_section
    assert "shared_theme:" not in correlation_section


def test_render_markdown_highlights_weakest_holding_in_opportunity_cost() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.05, "conviction": 0.6},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.18, "conviction": 0.5},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.07, "conviction": 0.4},
        SAMPLE_HOLDINGS[4],
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    opportunity_section = markdown.split("## 机会成本", 1)[1].split("\n## ", 1)[0]

    assert "最弱持仓：英伟达（风险调整后 2.8%）" in opportunity_section


def test_render_markdown_shows_returns_for_below_cash_hurdle_holdings() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.05, "conviction": 0.6},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.18, "conviction": 0.5},
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.07, "conviction": 0.4},
        SAMPLE_HOLDINGS[4],
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    opportunity_section = markdown.split("## 机会成本", 1)[1].split("\n## ", 1)[0]

    assert "低于现金门槛：阿里巴巴（风险调整后 3.0%）、英伟达（风险调整后 2.8%）" in opportunity_section


def test_render_markdown_marks_missing_expected_return_as_data_insufficient() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.08},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.07},
        SAMPLE_HOLDINGS[2],
        {**SAMPLE_HOLDINGS[3], "expected_return": 0.06},
        SAMPLE_HOLDINGS[4],
    ]

    markdown = pa.render_markdown(pa.analyze_portfolio(holdings))
    opportunity_section = markdown.split("## 机会成本", 1)[1].split("\n## ", 1)[0]

    assert "数据不足：缺少预期收益输入：台积电" in opportunity_section


def test_cli_outputs_json_from_holdings_file(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    input_path.write_text(json.dumps({"holdings": SAMPLE_HOLDINGS}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["_source"] == "portfolio_analyzer"
    assert payload["overall_health"]["rating"] == "需要调整"
    assert payload["concentration"]["top1_weight"] == pytest.approx(0.35)


def test_cli_accepts_custom_cash_hurdle(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.05, "conviction": 1.0},
        {**SAMPLE_HOLDINGS[1], "expected_return": 0.08, "conviction": 1.0},
        *SAMPLE_HOLDINGS[2:],
    ]
    input_path.write_text(json.dumps({"holdings": holdings}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
            "--cash-hurdle",
            "6",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["opportunity_cost"]["cash_hurdle"] == pytest.approx(0.06)
    assert [row["name"] for row in payload["opportunity_cost"]["below_cash_hurdle"]] == ["腾讯"]


def test_cli_accepts_zero_cash_hurdle(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    input_path.write_text(json.dumps({"holdings": SAMPLE_HOLDINGS}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
            "--cash-hurdle",
            "0",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["opportunity_cost"]["cash_hurdle"] == pytest.approx(0.0)


def test_cli_rejects_cash_hurdle_above_full_weight(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    input_path.write_text(json.dumps({"holdings": SAMPLE_HOLDINGS}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
            "--cash-hurdle",
            "150",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode != 0
    assert "--cash-hurdle 不能超过 100%" in completed.stderr


def test_cli_rejects_invalid_holding_without_traceback(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 150},
        *SAMPLE_HOLDINGS[1:],
    ]
    input_path.write_text(json.dumps({"holdings": holdings}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode != 0
    assert "输入持仓字段错误" in completed.stderr
    assert str(input_path) in completed.stderr
    assert "腾讯.conviction 不能超过 100%" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_non_numeric_opportunity_input_with_field_context(tmp_path: Path) -> None:
    input_path = tmp_path / "holdings.json"
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": "bad-input", "conviction": 0.8},
        *SAMPLE_HOLDINGS[1:],
    ]
    input_path.write_text(json.dumps({"holdings": holdings}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 2
    assert "输入持仓字段错误" in completed.stderr
    assert str(input_path) in completed.stderr
    assert "腾讯.expected_return 必须是数字" in completed.stderr
    assert "could not convert string" not in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_missing_input_file_without_traceback(tmp_path: Path) -> None:
    input_path = tmp_path / "missing-holdings.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 2
    assert "无法读取输入文件" in completed.stderr
    assert str(input_path) in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_malformed_json_without_traceback(tmp_path: Path) -> None:
    input_path = tmp_path / "broken-holdings.json"
    input_path.write_text('{"holdings": [', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 2
    assert "输入 JSON 解析失败" in completed.stderr
    assert str(input_path) in completed.stderr
    assert "Traceback" not in completed.stderr


def test_cli_rejects_wrong_json_shape_with_file_context(tmp_path: Path) -> None:
    input_path = tmp_path / "wrong-shape.json"
    input_path.write_text(json.dumps({"positions": []}, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(input_path),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 2
    assert "输入 JSON 结构错误" in completed.stderr
    assert str(input_path) in completed.stderr
    assert "必须是持仓数组，或包含 holdings 数组的对象" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_sample_portfolio_file_runs_through_cli() -> None:
    sample = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    codex_sample = REPO / "codex" / "ai-berkshire" / "examples" / "portfolio-holdings.sample.json"
    assert codex_sample.read_bytes() == SAMPLE_FILE.read_bytes()
    assert len(sample["holdings"]) >= 5
    assert all(
        "expected_return" in row and "conviction" in row
        for row in sample["holdings"]
        if row.get("asset_type") != "cash"
    )

    markdown = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(SAMPLE_FILE),
            "--format",
            "markdown",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    json_result = subprocess.run(
        [
            sys.executable,
            str(TOOLS_DIR / "portfolio_analyzer.py"),
            "analyze",
            str(SAMPLE_FILE),
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert markdown.returncode == 0, markdown.stderr
    assert "## 机会成本" in markdown.stdout
    assert "## 估值水位张力" in markdown.stdout
    assert "高估高预期" in markdown.stdout
    assert "## 压力测试" in markdown.stdout
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["opportunity_cost"]["ranked_holdings"]
    assert payload["stress_tests"]
    assert "allocation_drift" in payload
    assert "rebalance_suggestions" in payload
    assert payload["valuation_sanity"]["tension_count"] == 1
    assert payload["valuation_sanity"]["tensions"][0]["name"] == "台积电"


def test_valuation_sanity_flags_high_valuation_high_return() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.25, "conviction": 0.8, "pe_percentile": 0.92},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    tensions = analysis["valuation_sanity"]["tensions"]
    assert len(tensions) == 1
    assert tensions[0]["name"] == "腾讯"
    assert tensions[0]["tension_type"] == "high_valuation_high_return"
    assert tensions[0]["pe_percentile"] == pytest.approx(0.92)
    assert tensions[0]["expected_return"] == pytest.approx(0.25)
    assert analysis["valuation_sanity"]["tension_count"] == 1


def test_valuation_sanity_flags_low_valuation_low_return() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.02, "conviction": 0.8, "pe_percentile": 0.15},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    tensions = analysis["valuation_sanity"]["tensions"]
    assert len(tensions) == 1
    assert tensions[0]["tension_type"] == "low_valuation_low_return"
    assert tensions[0]["expected_return"] == pytest.approx(0.02)
    assert tensions[0]["pe_percentile"] == pytest.approx(0.15)


def test_valuation_sanity_skips_when_pe_percentile_missing() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.25, "conviction": 0.8},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["valuation_sanity"]["tensions"] == []
    assert analysis["valuation_sanity"]["tension_count"] == 0


def test_valuation_sanity_skips_when_expected_return_missing() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "pe_percentile": 0.92},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["valuation_sanity"]["tensions"] == []


def test_valuation_sanity_no_tension_when_consistent() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.10, "conviction": 0.8, "pe_percentile": 0.5},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["valuation_sanity"]["tensions"] == []


def test_overall_health_downgrades_on_valuation_tension() -> None:
    holdings = [
        {"name": "A", "code": "A", "weight": 15, "industry": "X", "region": "Y", "currency": "USD", "expected_return": 0.25, "conviction": 0.8, "pe_percentile": 0.92},
        {"name": "B", "code": "B", "weight": 15, "industry": "P", "region": "Q", "currency": "EUR", "expected_return": 0.10, "conviction": 0.8, "pe_percentile": 0.5},
        {"name": "C", "code": "C", "weight": 15, "industry": "M", "region": "N", "currency": "JPY", "expected_return": 0.10, "conviction": 0.8},
        {"name": "D", "code": "D", "weight": 15, "industry": "R", "region": "S", "currency": "GBP", "expected_return": 0.10, "conviction": 0.8},
        {"name": "现金", "weight": 40, "asset_type": "cash", "currency": "CNY"},
    ]

    analysis = pa.analyze_portfolio(holdings)

    assert analysis["overall_health"]["rating"] in {"需要调整", "问题严重"}
    assert any("估值水位张力" in d for d in analysis["overall_health"]["drivers"])


def test_executive_summary_surfaces_valuation_tension() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.25, "conviction": 0.8, "pe_percentile": 0.92, "weight": 5},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.10, "conviction": 0.8, "pe_percentile": 0.5, "weight": 10},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)

    summary = analysis["executive_summary"]["valuation_sanity_summary"]
    assert "腾讯" in summary
    assert "高估高预期" in summary


def test_render_markdown_includes_valuation_sanity_section() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.25, "conviction": 0.8, "pe_percentile": 0.92, "weight": 5},
        {**SAMPLE_HOLDINGS[2], "expected_return": 0.10, "conviction": 0.8, "pe_percentile": 0.5, "weight": 10},
        SAMPLE_HOLDINGS[4],
    ]

    analysis = pa.analyze_portfolio(holdings)
    markdown = pa.render_markdown(analysis)

    assert "## 估值水位张力" in markdown
    assert "高估高预期" in markdown
    assert "high_valuation_high_return" not in markdown


def test_pe_percentile_optional_ratio_validation() -> None:
    holdings = [
        {**SAMPLE_HOLDINGS[0], "expected_return": 0.12, "conviction": 0.8, "pe_percentile": 150},
        SAMPLE_HOLDINGS[4],
    ]

    with pytest.raises(ValueError, match="pe_percentile"):
        pa.analyze_portfolio(holdings)


def test_sample_holdings_run_with_pe_percentile() -> None:
    raw = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    analysis = pa.analyze_portfolio(raw["holdings"])
    assert "valuation_sanity" in analysis
    assert "tensions" in analysis["valuation_sanity"]
    assert analysis["valuation_sanity"]["tension_count"] == 1
    assert analysis["valuation_sanity"]["tensions"][0]["tension_type"] == "high_valuation_high_return"


def test_codex_tool_copy_stays_in_sync() -> None:
    for filename in [
        "portfolio_allocation.py",
        "portfolio_analyzer.py",
        "portfolio_input.py",
        "portfolio_opportunity.py",
        "portfolio_rebalance.py",
        "portfolio_render.py",
        "portfolio_stress.py",
        "portfolio_valuation_sanity.py",
    ]:
        root_tool = TOOLS_DIR / filename
        codex_tool = REPO / "codex" / "ai-berkshire" / "scripts" / "tools" / filename
        assert codex_tool.read_bytes() == root_tool.read_bytes()
