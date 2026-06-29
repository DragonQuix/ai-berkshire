# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO / "tools"
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


def test_render_markdown_outputs_portfolio_level_sections() -> None:
    analysis = pa.analyze_portfolio(SAMPLE_HOLDINGS)
    markdown = pa.render_markdown(analysis)

    assert "# 组合级分析" in markdown
    assert "## 组合集中度" in markdown
    assert "## 行业/地域/货币暴露" in markdown
    assert "## 相关性风险" in markdown
    assert "## 压力测试" in markdown
    assert "互联网" in markdown


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


def test_codex_tool_copy_stays_in_sync() -> None:
    for filename in ["portfolio_analyzer.py", "portfolio_render.py", "portfolio_stress.py"]:
        root_tool = TOOLS_DIR / filename
        codex_tool = REPO / "codex" / "ai-berkshire" / "scripts" / "tools" / filename
        assert codex_tool.read_bytes() == root_tool.read_bytes()
