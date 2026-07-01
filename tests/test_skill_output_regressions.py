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
        "examples/portfolio-holdings.sample.json",
        "reports/portfolio-latest.md",
        "python tools/portfolio_analyzer.py analyze",
        "--cash-hurdle",
        "allocation_drift",
        "target_weight_sum",
        "target_allocation_status",
        "目标超配",
        "目标差额：未配置",
        "状态列使用中文",
        "风险等级使用中文",
        "相关性驱动因素使用中文",
        "再平衡表的优先级列和动作列使用中文",
        "复核暴露",
        "风险等级和暴露权重",
        "优先级跟随该暴露的风险等级",
        "暴露达到",
        "现金缓冲理由必须展示当前现金占比",
        "现金部署理由必须展示候选名称与风险调整后收益",
        "集中度理由必须展示第一大持仓占比",
        "目标偏离理由必须展示当前仓位与建议仓位",
        "机会成本理由必须展示风险调整后收益与现金门槛",
        "估值水位张力理由必须展示 PE 分位与预期收益",
        "review_exposure",
        "turnover_to_target",
        "turnover_to_band",
        "opportunity_cost",
        "最弱持仓",
        "低于现金门槛",
        "rebalance_suggestions",
        "stress_tests",
        "输入持仓字段错误",
        "可显式填 0",
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

PUBLIC_RELEASE_SCAN_ROOTS = [
    REPO / "README.md",
    REPO / "README_EN.md",
    REPO / "skills",
    REPO / "codex" / "ai-berkshire" / "references" / "skills",
    REPO / "docs",
]

AUTHOR_MACHINE_PATH_PATTERNS = [
    "C:/Users/admin",
    r"C:\Users\admin",
    "/Users/linxuan",
    "~/.claude/projects",
    "-Users-linxuan",
    "lixingren_docs",
]

DATA_DEPENDENCY_RELEASE_CONTRACTS = {
    "README.md": [
        "## 数据源与可选依赖",
        "核心离线能力",
        "无需 token",
        "免费/公开源能力",
        "私有增强能力",
        "LIXINGER_TOKEN",
        "MX_DATA_SCRIPT",
        "MX_SEARCH_SCRIPT",
        "MX_XUANGU_SCRIPT",
        "Playwright",
        "雪球",
        "tools/lxr_config.example.json",
        "不需要提交真实 token",
    ],
    "skills/financial-data.md": [
        "安装不依赖 LIXINGER_TOKEN",
        "无 token",
        "免费/公开源",
        "私有增强",
        "MX_DATA_SCRIPT",
        "MX_SEARCH_SCRIPT",
        "MX_XUANGU_SCRIPT",
        "Playwright",
        "雪球",
        "不需要提交真实 token",
    ],
    "docs/lixinger-data-guide.md": [
        "无 token",
        "安装失败",
        "免费/公开源",
        "私有增强",
        "MX_DATA_SCRIPT",
        "MX_SEARCH_SCRIPT",
        "MX_XUANGU_SCRIPT",
        "Playwright",
        "雪球",
        "不需要提交真实 token",
    ],
}

INSTALL_RELEASE_CONTRACTS = {
    "README.md": [
        "19 个 Skill",
        "19 个 Claude Code slash command",
        "推荐前置条件",
        "脚本硬性检查 git 和 python",
        "手动复制 `skills/*.md` 只安装命令定义",
        "保留仓库目录",
        "从仓库根目录运行",
    ],
    "README_EN.md": [
        "19 Skills",
        "19 Claude Code slash commands",
        "recommended prerequisite",
        "hard-checks git and python",
        "copying `skills/*.md` only installs command definitions",
        "keep the repository directory",
        "run from the repository root",
    ],
    "install.ps1": [
        "$ExpectedSkillCount = 19",
        "期望 19 个 Claude Code 命令",
        "已安装:               $installed / $ExpectedSkillCount 个 Claude Code 命令",
    ],
    "install.sh": [
        "EXPECTED_SKILL_COUNT=19",
        "期望 19 个 Claude Code 命令",
        '已安装:   $installed / $EXPECTED_SKILL_COUNT 个 Claude Code 命令',
    ],
}

POST_INSTALL_SELF_CHECK_CONTRACTS = {
    "README.md": [
        "## 安装后自检",
        "~/.claude/commands",
        "19 个 AI Berkshire 命令",
        "AI Berkshire commands OK",
        "portfolio-holdings.sample.json",
        "python tools/portfolio_analyzer.py analyze",
        "--format json",
        "/dyp-ask",
        "/portfolio-review",
        "新开 Claude Code 会话",
        "用上面的命令名检查",
    ],
    "README_EN.md": [
        "## Post-install self-check",
        "~/.claude/commands",
        "19 AI Berkshire commands",
        "AI Berkshire commands OK",
        "portfolio-holdings.sample.json",
        "python tools/portfolio_analyzer.py analyze",
        "--format json",
        "/dyp-ask",
        "/portfolio-review",
        "start a new Claude Code session",
        "command-name check above",
    ],
}

TASK_AGENT_DEGRADATION_SKILLS = [
    "deep-company-series.md",
    "earnings-team.md",
    "industry-research.md",
    "investment-checklist.md",
    "investment-research.md",
    "investment-team.md",
    "management-deep-dive.md",
    "news-pulse.md",
    "private-company-research.md",
    "wechat-article.md",
]

TASK_AGENT_DEGRADATION_SNIPPETS = [
    "Agent 降级记录",
    "路由失败可能间歇性发生",
    "每次 TeamCreate/TaskCreate/后台 Agent 派发",
    "必须独立捕获",
    "不得因前一次成功假设后续也成功",
    "同一路由失败后不反复重试",
    "model route not configured",
    "timeout",
    "permission denied",
    "失败 Agent",
    "错误原文摘要",
    "降级方式",
    "影响范围",
    "不得把失败当作未发生",
    "顺序角色模拟",
]

TASK_AGENT_DEGRADATION_REDACTION_SNIPPETS = [
    "错误摘要脱敏标准",
    "可保留：模型名",
    "错误码",
    "HTTP 状态",
    "必须删除：本机绝对路径",
    "token",
    "cookie",
    "账户名",
    "deepseek-v4-flash 路由未配置",
]

HK_INDUSTRY_COMPARE_FALLBACK_SNIPPETS = [
    "港股行业对比降级",
    "申万行业分类仅覆盖A股",
    "mx-xuangu",
    "手工指定同业",
    "港股行业龙头",
    "不要求申万同行分位",
]

DEEP_AUDIT_DEPTH_SNIPPETS = [
    "--depth deep",
    "25%",
    "至少 30 点",
    "不再 30 点封顶",
]

FINANCIAL_CALIBER_METADATA_CONTRACTS = {
    "financial-data.md": [
        "caliber_metadata",
        "toi=营业总收入",
        "年报“收益”",
        "币种",
        "单位",
        "口径待核对",
    ],
    "investment-research.md": [
        "口径/来源",
        "caliber_metadata",
        "toi=营业总收入",
        "保险股用 oi=营业收入",
        "年报“收益”",
        "币种",
        "单位",
        "cross-validate",
        "--caliber",
    ],
}

LEGACY_SKILL_COUNT_PATTERNS = [
    "18" + " 个",
    "16" + " clear",
    "16" + " 个",
    "16" + " Skills",
]

DEV_FEEDBACK_SECOND_VALIDATION_ITEMS = [
    "P1-A1",
    "P1-A2",
    "P1-A3",
    "P1-B1",
    "P1-B2",
    "P1-B3",
    "P1-C1",
    "P1-D1",
    "P1-E1",
    "P1-E2",
    "P1-E3",
    "P2-E4",
    "P2-E5",
    "P2-E6",
]


def public_release_files() -> list[Path]:
    files: list[Path] = []
    for root in PUBLIC_RELEASE_SCAN_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        files.extend(path for path in root.rglob("*") if path.is_file())
    roadmap = REPO / "docs" / "ROADMAP.md"
    return sorted(path for path in files if path != roadmap)


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


def test_public_release_files_do_not_contain_author_machine_paths() -> None:
    offenders: list[str] = []
    for path in public_release_files():
        text = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(REPO).as_posix()
        for pattern in AUTHOR_MACHINE_PATH_PATTERNS:
            if pattern in text:
                offenders.append(f"{rel_path}: contains {pattern!r}")

    assert not offenders, "作者机器路径不能进入发布面文件:\n" + "\n".join(offenders)


@pytest.mark.parametrize("rel_path, required_snippets", DATA_DEPENDENCY_RELEASE_CONTRACTS.items())
def test_data_dependency_release_contracts_are_documented(
    rel_path: str,
    required_snippets: list[str],
) -> None:
    text = read_text(rel_path)
    for snippet in required_snippets:
        assert snippet in text, f"{rel_path} missing data dependency contract {snippet!r}"


@pytest.mark.parametrize("rel_path, required_snippets", INSTALL_RELEASE_CONTRACTS.items())
def test_install_release_contracts_are_documented(
    rel_path: str,
    required_snippets: list[str],
) -> None:
    text = read_text(rel_path)
    for snippet in required_snippets:
        assert snippet in text, f"{rel_path} missing install release contract {snippet!r}"


def test_public_release_files_do_not_contain_legacy_skill_counts() -> None:
    offenders: list[str] = []
    for path in public_release_files():
        text = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(REPO).as_posix()
        for pattern in LEGACY_SKILL_COUNT_PATTERNS:
            if pattern in text:
                offenders.append(f"{rel_path}: contains {pattern!r}")

    assert not offenders, "发布面文件不能继续使用旧 Skill 数量:\n" + "\n".join(offenders)


@pytest.mark.parametrize("rel_path, required_snippets", POST_INSTALL_SELF_CHECK_CONTRACTS.items())
def test_post_install_self_check_contracts_are_documented(
    rel_path: str,
    required_snippets: list[str],
) -> None:
    text = read_text(rel_path)
    for snippet in required_snippets:
        assert snippet in text, f"{rel_path} missing post-install self-check {snippet!r}"


@pytest.mark.parametrize("skill_name", TASK_AGENT_DEGRADATION_SKILLS)
def test_task_agent_degradation_contracts_are_documented(skill_name: str) -> None:
    for rel_path in skill_channels(skill_name):
        text = read_text(rel_path)
        for snippet in TASK_AGENT_DEGRADATION_SNIPPETS:
            assert snippet in text, f"{rel_path} missing task-agent degradation contract {snippet!r}"


@pytest.mark.parametrize("skill_name", TASK_AGENT_DEGRADATION_SKILLS)
def test_task_agent_degradation_redaction_examples_are_documented(skill_name: str) -> None:
    for rel_path in skill_channels(skill_name):
        text = read_text(rel_path)
        for snippet in TASK_AGENT_DEGRADATION_REDACTION_SNIPPETS:
            assert snippet in text, f"{rel_path} missing task-agent redaction example {snippet!r}"


def test_investment_research_documents_hk_industry_compare_fallback() -> None:
    for rel_path in skill_channels("investment-research.md"):
        text = read_text(rel_path)
        for snippet in HK_INDUSTRY_COMPARE_FALLBACK_SNIPPETS:
            assert snippet in text, f"{rel_path} missing HK industry compare fallback {snippet!r}"


def test_investment_research_documents_deep_audit_depth() -> None:
    for rel_path in skill_channels("investment-research.md"):
        text = read_text(rel_path)
        for snippet in DEEP_AUDIT_DEPTH_SNIPPETS:
            assert snippet in text, f"{rel_path} missing deep audit depth contract {snippet!r}"


@pytest.mark.parametrize("skill_name, required_snippets", FINANCIAL_CALIBER_METADATA_CONTRACTS.items())
def test_financial_caliber_metadata_contracts_are_documented(
    skill_name: str,
    required_snippets: list[str],
) -> None:
    for rel_path in skill_channels(skill_name):
        text = read_text(rel_path)
        for snippet in required_snippets:
            assert snippet in text, f"{rel_path} missing financial caliber metadata contract {snippet!r}"


def test_dev_feedback_action_plan_tracks_second_validation_evidence() -> None:
    text = read_text("docs/dev-feedback-action-plan.md")
    assert "## 9. 二次验证跟踪字段" in text
    assert "反馈项 | 状态 | 二次验证证据" in text
    assert "docs/dev-feedback-investment-research-deep-20260701.md" in text
    for item in DEV_FEEDBACK_SECOND_VALIDATION_ITEMS:
        assert f"| {item} |" in text, f"dev-feedback action plan missing second validation row for {item}"
