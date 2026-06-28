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


def _write_audit(company_dir: Path, items: list, verdict: str = "reject") -> None:
    audit_path = company_dir / "audit-results.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["items"] = items
    audit["verdict"] = verdict
    audit_path.write_text(json.dumps(audit, ensure_ascii=False), encoding="utf-8")


def _audit_item(**overrides) -> dict:
    base = {
        "claim": "收入 6600 亿",
        "report_location": "核心数据速览",
        "source_ref": "S1",
        "expected_value": "6600亿",
        "verified_value": "6600亿",
        "status": "pass",
        "note": "",
    }
    base.update(overrides)
    return base


def _seed_source_index(company_dir: Path) -> None:
    (company_dir / "source-index.md").write_text(
        "# 腾讯 来源索引\n\n"
        "| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| S1 | 年报 | 2025 年报 | 2026-03-20 | https://example.com | web | 财务口径核对 | 高 |\n",
        encoding="utf-8",
    )


def test_validate_team_research_outputs_rejects_invalid_item_status(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(status="maybe")], verdict="reject")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "item 0 status must be pass/fail/pending",
    } in result["invalid_files"]


def test_validate_team_research_outputs_rejects_item_missing_required_fields(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(claim="", expected_value="")], verdict="reject")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "item 0 missing required fields: claim, expected_value",
    } in result["invalid_files"]


def test_validate_team_research_outputs_rejects_pass_item_without_verification(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(verified_value="", source_ref="")], verdict="reject")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "item 0 status pass requires verified_value and source_ref",
    } in result["invalid_files"]


def test_validate_team_research_outputs_rejects_verdict_pass_with_pending_items(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(status="pending", source_ref="", verified_value="")], verdict="pass")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "verdict pass requires all items status pass",
    } in result["invalid_files"]


def test_validate_team_research_outputs_rejects_verdict_pass_with_fail_items(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(status="fail")], verdict="pass")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "verdict pass requires all items status pass",
    } in result["invalid_files"]


def test_validate_team_research_outputs_rejects_verdict_pass_with_empty_items(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [], verdict="pass")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "verdict pass requires non-empty items",
    } in result["invalid_files"]


def test_validate_team_research_outputs_passes_all_pass_items_with_verdict_pass(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item(), _audit_item(claim="毛利率 55%", expected_value="55%")], verdict="pass")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "pass"
    assert result["invalid_files"] == []


FINAL_REPORT_WITH_DATA = """# 腾讯 投资研究最终报告

## 核心数据速览

| 指标 | 2024 | 2023 |
|---|---:|---:|
| 营业收入 | 6600 | 5900 |
| 毛利率 | 55 | 53 |

市值：5800亿

## 关键数据溯源

- 收入引用 S1。

## 角色冲突与 Team Lead 仲裁

- 未发现影响最终结论的角色冲突。
"""


def _seed_final_report_with_data(company_dir: Path) -> None:
    (company_dir / "最终报告.md").write_text(FINAL_REPORT_WITH_DATA, encoding="utf-8")


def test_audit_extract_writes_contract_format_items(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_final_report_with_data(company_dir)
    _seed_source_index(company_dir)

    summary = tro.audit_extract(company_dir, ratio=1.0)
    assert summary["sampled"] >= 3
    assert summary["sample_ratio"] == 1.0
    assert summary["report"] == str(company_dir / "最终报告.md")

    audit = json.loads((company_dir / "audit-results.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "reject"
    assert audit["sample_ratio"] == 1.0
    assert isinstance(audit["items"], list) and audit["items"]

    for item in audit["items"]:
        assert set(item.keys()) == {
            "claim", "report_location", "source_ref",
            "expected_value", "verified_value", "status", "note",
        }
        assert item["status"] == "pending"
        assert item["source_ref"] == ""
        assert item["verified_value"] == ""
        assert item["claim"]
        assert item["report_location"]
        assert item["expected_value"]
        assert "原文摘录" in item["note"]

    # 草稿抽检清单（verdict=reject + pending items）必须能通过结构校验
    result = tro.validate_team_research_outputs(company_dir)
    assert result["status"] == "pass"
    assert result["invalid_files"] == []


def test_audit_extract_is_idempotent_and_resets_verdict(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_final_report_with_data(company_dir)

    # 先伪造一份已通过的抽检结果
    _seed_source_index(company_dir)
    _write_audit(company_dir, [_audit_item()], verdict="pass")
    assert json.loads((company_dir / "audit-results.json").read_text(encoding="utf-8"))["verdict"] == "pass"

    # 重新抽取应重置 verdict 并覆盖 items（固定种子保证顺序确定性）
    tro.audit_extract(company_dir, ratio=1.0, seed=7)
    audit = json.loads((company_dir / "audit-results.json").read_text(encoding="utf-8"))
    assert audit["verdict"] == "reject"
    assert all(item["status"] == "pending" for item in audit["items"])

    # 再次抽取，结果一致（idempotent）
    first = audit["items"]
    tro.audit_extract(company_dir, ratio=1.0, seed=7)
    second = json.loads((company_dir / "audit-results.json").read_text(encoding="utf-8"))["items"]
    assert [i["claim"] for i in first] == [i["claim"] for i in second]


def test_audit_extract_errors_when_final_report_missing(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    (company_dir / "最终报告.md").unlink()

    import pytest
    with pytest.raises(FileNotFoundError):
        tro.audit_extract(company_dir, ratio=1.0)


def test_audit_extract_respects_ratio_and_seed(tmp_path: Path) -> None:
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_final_report_with_data(company_dir)

    full = tro.audit_extract(company_dir, ratio=1.0)
    assert full["sampled"] == full["extracted"]

    # 同一种子两次抽取应得到完全一致的 claim 序列
    tro.audit_extract(company_dir, ratio=0.6, seed=42)
    items_first = json.loads(
        (company_dir / "audit-results.json").read_text(encoding="utf-8")
    )["items"]
    second = tro.audit_extract(company_dir, ratio=0.6, seed=42)
    items_second = json.loads(
        (company_dir / "audit-results.json").read_text(encoding="utf-8")
    )["items"]
    assert [i["claim"] for i in items_first] == [i["claim"] for i in items_second]
    assert second["seed"] == 42


def test_validate_rejects_non_standard_source_ref_format(tmp_path: Path) -> None:
    """source_ref 非空但不符合 [SEPA]<digits> 格式时必须打回，避免绕过 undefined ref 检查。"""
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    # "annual-report" 非 S/E/P/A+数字 格式，extract_json_source_refs 不会收集，
    # 故 undefined 检查会漏掉它；但 _validate_audit_items 必须按格式拦截
    _write_audit(company_dir, [_audit_item(source_ref="annual-report")], verdict="pass")

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    assert {
        "file": "audit-results.json",
        "reason": "item 0 source_ref must match [SEPA]<digits>: 'annual-report'",
    } in result["invalid_files"]


def test_validate_rejects_non_standard_source_ref_even_when_pending(tmp_path: Path) -> None:
    """pending item 也要求 source_ref 一旦填写就必须符合 [SEPA]<digits> 格式。"""
    tro.init_team_research_outputs(
        reports_dir=tmp_path, company="腾讯", ticker="00700",
        market="hk", generated_at="2026-06-28",
    )
    company_dir = tmp_path / "腾讯"
    _seed_source_index(company_dir)
    _write_audit(
        company_dir,
        [_audit_item(status="pending", source_ref="annual-report", verified_value="")],
        verdict="reject",
    )

    result = tro.validate_team_research_outputs(company_dir)

    assert result["status"] == "fail"
    reason = next(
        (r for r in result["invalid_files"] if r["file"] == "audit-results.json"), None
    )
    assert reason is not None
    assert "source_ref must match [SEPA]<digits>" in reason["reason"]
