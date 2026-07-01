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

LEGACY_SKILL_COUNT_PATTERNS = [
    "18" + " 个",
    "16" + " clear",
    "16" + " 个",
    "16" + " Skills",
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
