# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
FIXTURE_DIR = REPO / "tests" / "fixtures" / "investment_research_smoke"


def test_github_actions_ci_runs_offline_release_gates() -> None:
    assert WORKFLOW.is_file(), ".github/workflows/ci.yml is required"

    text = WORKFLOW.read_text(encoding="utf-8")
    required_snippets = [
        "pull_request:",
        "push:",
        "ubuntu-latest",
        "actions/setup-python",
        "python -m pytest -q",
        "python tools/verify_channel_capability.py --quick",
        "python -m compileall -q tools codex/ai-berkshire/scripts/tools",
        "python tools/release_smoke.py",
        "git diff --check",
    ]
    for snippet in required_snippets:
        assert snippet in text, f"CI workflow missing {snippet!r}"

    forbidden_snippets = [
        "LIXINGER_TOKEN",
        "tools/lxr_config.json",
        "secrets.",
        "playwright install",
    ]
    for snippet in forbidden_snippets:
        assert snippet not in text, f"CI workflow must stay offline: {snippet!r}"


def test_investment_research_smoke_fixture_captures_p1_contracts() -> None:
    datapack_path = FIXTURE_DIR / "datapack.json"
    skeleton_path = FIXTURE_DIR / "expected_report_skeleton.md"
    assert datapack_path.is_file(), "investment research smoke datapack fixture is required"
    assert skeleton_path.is_file(), "investment research smoke report skeleton is required"

    payload = json.loads(datapack_path.read_text(encoding="utf-8"))
    assert payload["_fixture"]["offline"] is True
    assert payload["_source"] == "offline_fixture"

    sections = payload["sections"]
    assert {"financials", "valuation", "verify_inputs", "industry_compare"} <= set(sections)

    meta = payload["caliber_metadata"]["financials"]
    assert meta == sections["financials"]["caliber_metadata"]
    assert meta["fields"]["q.ps.toi.t"]["caliber"] == "营业总收入"
    assert meta["currency"] == "CNY"
    assert meta["unit"] == "raw_yuan"
    assert "年报“收益”" in "\n".join(meta["notes"])

    skeleton = skeleton_path.read_text(encoding="utf-8")
    required_report_snippets = [
        "口径/来源",
        "币种",
        "单位",
        "caliber_metadata",
        "Task Agent 降级记录",
        "错误原文摘要",
        "口径待核对",
        "抽检",
    ]
    for snippet in required_report_snippets:
        assert snippet in skeleton, f"report skeleton missing {snippet!r}"
