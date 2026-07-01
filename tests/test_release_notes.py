# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "tools" / "release_notes.py"


def load_release_notes_module():
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_release_notes_groups_conventional_commits() -> None:
    module = load_release_notes_module()
    commits = [
        module.Commit("abe2842d", "fix", "metadata", "增加财务口径元数据"),
        module.Commit("5d46ce1b", "ci", None, "增加离线回归门禁"),
        module.Commit("20ea36d9", "docs", "feedback", "增加技能执行复盘"),
        module.Commit("1234567a", "other", None, "手工补充说明"),
    ]

    text = module.generate_release_notes(
        commits,
        from_ref="origin/main",
        to_ref="HEAD",
        title="P1 本地待发布变更",
    )

    assert "# P1 本地待发布变更" in text
    assert "范围：`origin/main..HEAD`" in text
    assert "## 修复" in text
    assert "- `abe2842d` **metadata**：增加财务口径元数据" in text
    assert "## CI / 发布工程" in text
    assert "- `5d46ce1b` 增加离线回归门禁" in text
    assert "## 文档" in text
    assert "## 其他" in text


def test_parse_git_subject_handles_scopes_and_plain_messages() -> None:
    module = load_release_notes_module()

    parsed = module.parse_git_log_line("fc0504c7\x1ffix(rigor): 增强金融严谨性工具参数防呆")
    assert parsed.type == "fix"
    assert parsed.scope == "rigor"
    assert parsed.summary == "增强金融严谨性工具参数防呆"

    plain = module.parse_git_log_line("1234567a\x1f补充说明")
    assert plain.type == "other"
    assert plain.scope is None
    assert plain.summary == "补充说明"


def test_cli_writes_release_notes_file(tmp_path: Path) -> None:
    module = load_release_notes_module()
    output = tmp_path / "release-notes.md"

    code = module.main(
        [
            "--from",
            "HEAD",
            "--to",
            "HEAD",
            "--output",
            str(output),
            "--title",
            "空变更测试",
        ]
    )

    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "# 空变更测试" in text
    assert "范围：`HEAD..HEAD`" in text
    assert "没有发现提交" in text
