# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (REPO / rel_path).read_text(encoding="utf-8")


def test_team_research_output_contract_defines_required_artifacts() -> None:
    text = read_text("docs/team-research-output-contract.md")

    required_terms = [
        "data-pack.json",
        "source-index.md",
        "role-briefs/",
        "audit-results.json",
        "最终报告.md",
        "关键数据溯源",
        "冲突仲裁",
        "Team Lead",
    ]

    for term in required_terms:
        assert term in text


def test_investment_team_requires_output_contract_and_final_traceability() -> None:
    root = read_text("skills/investment-team.md")
    codex = read_text("codex/ai-berkshire/references/skills/investment-team.md")

    for text in (root, codex):
        assert "docs/team-research-output-contract.md" in text
        assert "role-briefs/" in text
        assert "audit-results.json" in text
        assert "最终报告中的关键数据必须能追溯" in text
        assert "角色结论与最终结论冲突" in text
        assert "Team Lead 的仲裁理由" in text


def test_investment_team_references_scaffold_tool() -> None:
    root = read_text("skills/investment-team.md")
    codex = read_text("codex/ai-berkshire/references/skills/investment-team.md")

    for text in (root, codex):
        assert "python tools/team_research_outputs.py" in text
        assert "--ticker" in text
        assert "--market" in text
