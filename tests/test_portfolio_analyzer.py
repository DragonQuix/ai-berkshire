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
    assert "## 压力测试" in markdown.stdout
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["opportunity_cost"]["ranked_holdings"]
    assert payload["stress_tests"]
    assert "allocation_drift" in payload
    assert "rebalance_suggestions" in payload


def test_codex_tool_copy_stays_in_sync() -> None:
    for filename in [
        "portfolio_allocation.py",
        "portfolio_analyzer.py",
        "portfolio_input.py",
        "portfolio_opportunity.py",
        "portfolio_rebalance.py",
        "portfolio_render.py",
        "portfolio_stress.py",
    ]:
        root_tool = TOOLS_DIR / filename
        codex_tool = REPO / "codex" / "ai-berkshire" / "scripts" / "tools" / filename
        assert codex_tool.read_bytes() == root_tool.read_bytes()
