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


def test_validate_team_research_outputs_passes_scaffold(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )

    result = tro.validate_team_research_outputs(tmp_path / "腾讯")

    assert result["status"] == "pass"
    assert result["missing_files"] == []
    assert result["invalid_files"] == []


def test_validate_team_research_outputs_reports_missing_and_invalid_files(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    (tmp_path / "腾讯" / "source-index.md").unlink()
    audit_path = tmp_path / "腾讯" / "audit-results.json"
    audit_path.write_text('{"verdict": "maybe"}\n', encoding="utf-8")

    result = tro.validate_team_research_outputs(tmp_path / "腾讯")

    assert result["status"] == "fail"
    assert "source-index.md" in result["missing_files"]
    assert {
        "file": "audit-results.json",
        "reason": "verdict must be pass or reject",
    } in result["invalid_files"]


def test_validate_team_research_outputs_passes_defined_report_refs(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    (company_dir / "source-index.md").write_text(
        "# 腾讯 来源索引\n\n"
        "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| S1 | 年报 | 2025 年报 | 2026-03-20 | https://example.com | web | 财务口径核对 | 高 |\n",
        encoding="utf-8",
    )
    (company_dir / "最终报告.md").write_text(
        "# 腾讯 投资研究最终报告\n\n"
        "| 指标 | 数值 | 期间 | 口径 | 来源/ref |\n"
        "|---|---:|---|---|---|\n"
        "| 收入 | 6600亿 | 2025 | IFRS | S1 |\n\n"
        "## 关键数据溯源\n\n- 收入引用 S1。\n\n"
        "## 角色冲突与 Team Lead 仲裁\n\n- 未发现影响最终结论的角色冲突。\n",
        encoding="utf-8",
    )

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "pass"
    assert result["undefined_refs"] == []


def test_validate_team_research_outputs_reports_undefined_report_refs(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    (company_dir / "source-index.md").write_text(
        "# 腾讯 来源索引\n\n"
        "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| S1 | 年报 | 2025 年报 | 2026-03-20 | https://example.com | web | 财务口径核对 | 高 |\n",
        encoding="utf-8",
    )
    (company_dir / "最终报告.md").write_text(
        "# 腾讯 投资研究最终报告\n\n"
        "| 指标 | 数值 | 期间 | 口径 | 来源/ref |\n"
        "|---|---:|---|---|---|\n"
        "| 收入 | 6600亿 | 2025 | IFRS | S404 |\n\n"
        "## 关键数据溯源\n\n- 收入引用 S404。\n\n"
        "## 角色冲突与 Team Lead 仲裁\n\n- 未发现影响最终结论的角色冲突。\n",
        encoding="utf-8",
    )

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert result["undefined_refs"] == ["S404"]
    assert {
        "file": "最终报告.md",
        "reason": "undefined source refs: S404",
    } in result["invalid_files"]


def test_validate_team_research_outputs_ignores_roadmap_stage_labels(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    (company_dir / "source-index.md").write_text(
        "# 腾讯 来源索引\n\n"
        "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| S1 | 年报 | 2025 年报 | 2026-03-20 | https://example.com | web | 财务口径核对 | 高 |\n",
        encoding="utf-8",
    )
    (company_dir / "最终报告.md").write_text(
        "# 腾讯 投资研究最终报告\n\n"
        "P1 阶段目标是提升团队研究产物质量，不应被识别为来源 ref。\n\n"
        "| 指标 | 数值 | 期间 | 口径 | 来源/ref |\n"
        "|---|---:|---|---|---|\n"
        "| 收入 | 6600亿 | 2025 | IFRS | S1 |\n\n"
        "## 关键数据溯源\n\n- 收入引用 S1。\n\n"
        "## 角色冲突与 Team Lead 仲裁\n\n- 未发现影响最终结论的角色冲突。\n",
        encoding="utf-8",
    )

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "pass"
    assert result["undefined_refs"] == []


def test_validate_team_research_outputs_reports_undefined_data_pack_refs(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    data_pack_path = company_dir / "data-pack.json"
    data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
    data_pack["financials"]["source_refs"] = ["S1", "S404"]
    data_pack_path.write_text(json.dumps(data_pack, ensure_ascii=False), encoding="utf-8")
    (company_dir / "source-index.md").write_text(
        "# 腾讯 来源索引\n\n"
        "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| S1 | 年报 | 2025 年报 | 2026-03-20 | https://example.com | web | 财务口径核对 | 高 |\n",
        encoding="utf-8",
    )

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert result["undefined_refs"] == ["S404"]
    assert {
        "file": "data-pack.json",
        "reason": "undefined source refs: S404",
    } in result["invalid_files"]


def test_validate_team_research_outputs_reports_undefined_audit_refs(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path,
        company="腾讯",
        ticker="00700",
        market="hk",
        generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    audit_path = company_dir / "audit-results.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["items"] = [{
        "claim": "收入 6600 亿",
        "report_location": "核心数据速览",
        "source_ref": "S404",
        "expected_value": "6600亿",
        "verified_value": "",
        "status": "pending",
        "note": "",
    }]
    audit_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert result["undefined_refs"] == ["S404"]
    assert {
        "file": "audit-results.json",
        "reason": "undefined source refs: S404",
    } in result["invalid_files"]
