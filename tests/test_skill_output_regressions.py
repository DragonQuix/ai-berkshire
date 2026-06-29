# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (REPO / rel_path).read_text(encoding="utf-8")


def skill_channels(name: str) -> tuple[str, str]:
    return (
        f"skills/{name}",
        f"codex/ai-berkshire/references/skills/{name}",
    )


REPORT_OUTPUT_CONTRACTS = {
    "investment-research.md": [
        "reports/{公司名}/{公司名}-research-{YYYYMMDD}.md",
        "python tools/report_audit.py extract",
        "python tools/report_audit.py verdict",
    ],
    "earnings-review.md": [
        "reports/{公司名}/{公司名}-earnings-{期间}.md",
        "python tools/report_audit.py extract",
        "python tools/report_audit.py verdict",
    ],
    "industry-research.md": [
        "reports/{行业名}-industry-{YYYYMMDD}.md",
        "python tools/report_audit.py extract",
        "python tools/report_audit.py verdict",
    ],
    "investment-checklist.md": [
        "reports/{公司名}/{公司名}-checklist-{YYYYMMDD}.md",
        "reports/多公司对比-checklist-{YYYYMMDD}.md",
    ],
    "management-deep-dive.md": [
        "reports/{公司名}/{公司名}-management-{YYYYMMDD}.md",
        "tools/financial_rigor.py verify-valuation",
    ],
    "thesis-tracker.md": [
        "reports/{公司名}/{公司名}-thesis.md",
        "tools/financial_rigor.py verify-valuation",
    ],
    "portfolio-review.md": [
        "reports/portfolio-latest.md",
        "python tools/portfolio_analyzer.py analyze",
        "stress_tests",
        "tools/financial_rigor.py verify-valuation",
        "tools/financial_rigor.py three-scenario",
    ],
    "private-company-research.md": [
        "reports/{公司名}/{公司名}-private-{YYYYMMDD}.md",
        "reports/{公司名}/{公司名}-private-source-pack-{YYYYMMDD}.md",
    ],
    "compare.md": [
        "reports/多公司对比-{主标的}-{YYYYMMDD}.md",
        "reports/{主标的}vs{次标的}-对比-{YYYYMMDD}.md",
    ],
    "industry-funnel.md": [
        "reports/{行业名}-funnel-{YYYYMMDD}.md",
        "python tools/report_audit.py extract",
        "python tools/report_audit.py verdict",
    ],
    "news-pulse.md": [
        "reports/{公司名}/{公司名}-news-{YYYYMMDD}.md",
    ],
    "wechat-article.md": [
        "reports/AI产业研究/",
        "reports/{公司名}/",
        "公众号-{主题关键词}-{YYYYMMDD}.md",
    ],
}


LEGACY_OUTPUT_PATTERNS = [
    "~/[公司名]投资研究报告.md",
    "~/[行业名]产业链投资研究报告.md",
    '~/巴菲特Checklist-[公司名或"多公司对比"].md',
    "reports/{公司名}-earnings-{期间}.md",
    "reports/{公司名}-management-{YYYYMMDD}.md",
    "reports/{公司名}-thesis.md",
]


@pytest.mark.parametrize("skill_name, required_snippets", REPORT_OUTPUT_CONTRACTS.items())
def test_report_skills_pin_project_output_contracts(skill_name: str, required_snippets: list[str]) -> None:
    for rel_path in skill_channels(skill_name):
        text = read_text(rel_path)
        for snippet in required_snippets:
            assert snippet in text, f"{rel_path} missing {snippet!r}"


@pytest.mark.parametrize("skill_name", REPORT_OUTPUT_CONTRACTS)
def test_report_skills_do_not_use_legacy_home_output_paths(skill_name: str) -> None:
    for rel_path in skill_channels(skill_name):
        text = read_text(rel_path)
        for pattern in LEGACY_OUTPUT_PATTERNS:
            assert pattern not in text, f"{rel_path} still contains legacy output path {pattern!r}"
