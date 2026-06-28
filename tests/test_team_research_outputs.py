# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import team_research_outputs as tro  # noqa: E402


def test_init_team_research_outputs_creates_required_artifacts(tmp_path: Path) -> None:
    result = tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )

    company_dir = tmp_path / "腾讯"
    assert result["company_dir"] == str(company_dir)
    assert sorted(Path(p).name for p in result["created_files"]) == [
        "audit-results.json",
        "business-analyst.md",
        "data-pack.json",
        "financial-analyst.md",
        "industry-researcher.md",
        "risk-assessor.md",
        "source-index.md",
        "最终报告.md",
    ]

    data_pack = json.loads((company_dir / "data-pack.json").read_text(encoding="utf-8"))
    assert data_pack["meta"] == {
        "company": "腾讯",
        "ticker": "00700",
        "market": "hk",
        "generated_at": "2026-06-28",
        "owner": "Team Lead",
    }
    assert data_pack["financials"]["source_refs"] == []
    assert data_pack["known_gaps"] == []

    source_index = (company_dir / "source-index.md").read_text(encoding="utf-8")
    assert "# 腾讯 来源索引" in source_index
    assert "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |" in source_index

    role_brief = (company_dir / "role-briefs" / "financial-analyst.md").read_text(encoding="utf-8")
    assert "## 使用的证据" in role_brief
    assert "## 反面证据" in role_brief
    assert "## 补数请求" in role_brief

    audit = json.loads((company_dir / "audit-results.json").read_text(encoding="utf-8"))
    assert audit["report"] == "reports/腾讯/最终报告.md"
    assert audit["verdict"] == "reject"
    assert audit["items"] == []

    final_report = (company_dir / "最终报告.md").read_text(encoding="utf-8")
    assert "## 关键数据溯源" in final_report
    assert "## 角色冲突与 Team Lead 仲裁" in final_report


def test_init_team_research_outputs_does_not_overwrite_existing_files(tmp_path: Path) -> None:
    company_dir = tmp_path / "腾讯"
    company_dir.mkdir()
    existing = company_dir / "source-index.md"
    existing.write_text("KEEP", encoding="utf-8")

    result = tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
        overwrite=False,
    )

    assert existing.read_text(encoding="utf-8") == "KEEP"
    assert str(existing) in result["skipped_files"]
    assert str(existing) not in result["created_files"]


def test_codex_copy_matches_root_tool() -> None:
    root = (REPO / "tools" / "team_research_outputs.py").read_text(encoding="utf-8")
    codex = (
        REPO / "codex" / "ai-berkshire" / "scripts" / "tools" / "team_research_outputs.py"
    ).read_text(encoding="utf-8")
    assert codex == root
