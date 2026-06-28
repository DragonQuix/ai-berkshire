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


def test_contract_and_investment_team_reference_validate_command() -> None:
    docs = read_text("docs/team-research-output-contract.md")
    root = read_text("skills/investment-team.md")
    codex = read_text("codex/ai-berkshire/references/skills/investment-team.md")

    for text in (docs, root, codex):
        assert "python tools/team_research_outputs.py validate" in text


def test_contract_and_investment_team_define_ref_consistency_gate() -> None:
    docs = read_text("docs/team-research-output-contract.md")
    root = read_text("skills/investment-team.md")
    codex = read_text("codex/ai-berkshire/references/skills/investment-team.md")

    for text in (docs, root, codex):
        assert "未定义来源 ref" in text
        assert "source-index.md" in text
        assert "data-pack.json" in text
        assert "audit-results.json" in text
        assert "source_refs" in text
        assert "source_ref" in text


def test_contract_and_investment_team_reference_audit_extract_command() -> None:
    docs = read_text("docs/team-research-output-contract.md")
    root = read_text("skills/investment-team.md")
    codex = read_text("codex/ai-berkshire/references/skills/investment-team.md")

    for text in (docs, root, codex):
        assert "audit-extract" in text
        assert "python tools/team_research_outputs.py audit-extract" in text
        assert "--ratio" in text
        assert "--seed" in text


def test_contract_defines_audit_item_status_enum_and_verdict_consistency() -> None:
    docs = read_text("docs/team-research-output-contract.md")

    # item.status 合法取值
    for status in ("pass", "fail", "pending"):
        assert status in docs
    # verdict 与 status 一致性规则：contract 写明 verdict=pass 要求所有 item status==pass
    assert "verdict" in docs
    assert "status == pass" in docs
    # pass/fail 抽检项必须携带核验值与来源 ref
    assert "verified_value" in docs
    assert "source_ref" in docs


def test_contract_documents_audit_extract_resets_verdict() -> None:
    docs = read_text("docs/team-research-output-contract.md")

    assert "audit-extract" in docs
    # 重新抽取抽检清单必须把 verdict 重置为 reject
    assert "reject" in docs
    assert "pending" in docs
