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
        "19 AI Berkshire command files",
        "portfolio sample",
        "Codex skill",
        "Redact tokens",
    ]:
        assert snippet in template


def test_usage_feedback_issue_template_exists() -> None:
    template = read_text(".github/ISSUE_TEMPLATE/usage-feedback.yml")

    for snippet in [
        "使用体验反馈 / Usage feedback",
        "usage-feedback",
        "Workflow type",
        "Commands used",
        "Sanitized input",
        "Result and experience",
        "Friction or blockers",
        "Expected improvements",
        "anonymously quoted",
    ]:
        assert snippet in template


def test_dev_feedback_issue_template_exists() -> None:
    template = read_text(".github/ISSUE_TEMPLATE/dev-feedback.yml")

    for snippet in [
        "开发反馈 / Dev feedback",
        "dev-feedback",
        "Skill and depth",
        "Version or commit",
        "Error chain",
        "Evidence and reproduction",
        "Technical evaluation",
        "machine-readable JSON",
        "Privacy check",
    ]:
        assert snippet in template


def test_install_feedback_docs_define_safe_minimum_fields() -> None:
    docs = read_text("docs/install-feedback.md")

    for snippet in [
        "token、cookie、账户标识",
        "Windows PowerShell 7",
        "macOS/Linux shell",
        "~/.claude/commands",
        "19 个 AI Berkshire",
        "portfolio-holdings.sample.json",
        "ai-berkshire",
        "真实反馈记录",
    ]:
        assert snippet in docs


def test_usage_feedback_docs_define_safe_minimum_fields() -> None:
    docs = read_text("docs/usage-feedback.md")

    for snippet in [
        "真实持仓金额",
        "docs/dev-feedback.md",
        "使用场景",
        "/portfolio-review",
        "脱敏输入",
        "结果体验",
        "期望改进",
        "匿名引用授权",
        "真实反馈记录",
    ]:
        assert snippet in docs


def test_dev_feedback_docs_define_agent_handoff_fields() -> None:
    docs = read_text("docs/dev-feedback.md")

    for snippet in [
        "代码级复盘",
        "Skill 和深度",
        "错误链",
        "复现证据",
        "Machine-readable JSON",
        "privacy_checked",
        "docs/dev-feedback-action-plan.md",
        "真实开发反馈记录",
    ]:
        assert snippet in docs


def test_readmes_link_install_feedback_entry() -> None:
    zh = read_text("README.md")
    en = read_text("README_EN.md")

    assert "docs/install-feedback.md" in zh
    assert ".github/ISSUE_TEMPLATE/install-feedback.yml" in zh
    assert "AI Berkshire commands OK" in zh
    assert "docs/install-feedback.md" in en
    assert ".github/ISSUE_TEMPLATE/install-feedback.yml" in en
    assert "AI Berkshire commands OK" in en


def test_readmes_link_usage_feedback_entry() -> None:
    zh = read_text("README.md")
    en = read_text("README_EN.md")

    assert "docs/usage-feedback.md" in zh
    assert ".github/ISSUE_TEMPLATE/usage-feedback.yml" in zh
    assert "使用体验反馈" in zh
    assert "docs/usage-feedback.md" in en
    assert ".github/ISSUE_TEMPLATE/usage-feedback.yml" in en
    assert "Usage feedback" in en


def test_readmes_link_dev_feedback_entry() -> None:
    zh = read_text("README.md")
    en = read_text("README_EN.md")

    assert "docs/dev-feedback.md" in zh
    assert ".github/ISSUE_TEMPLATE/dev-feedback.yml" in zh
    assert "开发反馈" in zh
    assert "docs/dev-feedback.md" in en
    assert ".github/ISSUE_TEMPLATE/dev-feedback.yml" in en
    assert "Dev feedback" in en
