from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def read_text(rel_path: str) -> str:
    return (REPO / rel_path).read_text(encoding="utf-8")


def test_install_feedback_issue_template_exists() -> None:
    template = read_text(".github/ISSUE_TEMPLATE/install-feedback.yml")

    for snippet in [
        "安装反馈 / Install feedback",
        "install-feedback",
        "Platform",
        "Tool versions",
        "Install command",
        "19 Claude Code command files",
        "portfolio sample",
        "Codex skill",
        "Redact tokens",
    ]:
        assert snippet in template


def test_install_feedback_docs_define_safe_minimum_fields() -> None:
    docs = read_text("docs/install-feedback.md")

    for snippet in [
        "token、cookie、账户标识",
        "Windows PowerShell",
        "macOS/Linux shell",
        "~/.claude/commands",
        "19 个",
        "portfolio-holdings.sample.json",
        "ai-berkshire",
        "真实反馈记录",
    ]:
        assert snippet in docs


def test_readmes_link_install_feedback_entry() -> None:
    zh = read_text("README.md")
    en = read_text("README_EN.md")

    assert "docs/install-feedback.md" in zh
    assert ".github/ISSUE_TEMPLATE/install-feedback.yml" in zh
    assert "docs/install-feedback.md" in en
    assert ".github/ISSUE_TEMPLATE/install-feedback.yml" in en
