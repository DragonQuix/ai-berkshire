# -*- coding: utf-8 -*-
"""verify_multi_agent_permissions.py
权限安全多 Agent 静态校验。

扫描 `skills/*.md` 与 `codex/ai-berkshire/references/skills/*.md`，拦截旧式
"后台 Agent 自行联网 / 取数 / 写文件"句式。允许出现明确的否定、防护或
Team Lead 兜底表述，例如"不得让后台 Agent 自行联网"。

用法:
    python tools/verify_multi_agent_permissions.py

退出码: 0 = 未发现高风险句式；非 0 = 存在失败项。
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RiskRule:
    name: str
    pattern: re.Pattern[str]
    reason: str


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (
            (candidate / "skills").is_dir()
            and (candidate / "codex" / "ai-berkshire" / "references" / "skills").is_dir()
        ):
            return candidate
    return Path(__file__).resolve().parent.parent


REPO = _find_repo_root(Path(__file__).resolve())

SKILL_DIRS = (
    Path("skills"),
    Path("codex") / "ai-berkshire" / "references" / "skills",
)

ALLOW_CONTEXT_MARKERS = (
    "不得",
    "不要",
    "不能",
    "禁止",
    "不调用",
    "不检索",
    "不写",
    "不改写",
    "不自行",
    "只读",
    "只能读取",
    "只使用",
    "注入",
    "不取数",
    "不再",
    "不得依赖",
    "不得把",
    "避免",
    "权限安全",
    "权限受限",
    "不会触发权限阻塞",
    "补数请求",
    "Team Lead",
    "主 Agent",
    "当前主 Agent",
)

HIGH_RISK_RULES = (
    RiskRule(
        "agent-direct-tool-use",
        re.compile(
            r"(后台\s*Agent|子\s*Agent|角色\s*Agent|侦察\s*Agent|作者\s*Agent|编辑\s*Agent|读者\s*Agent|Agent)"
            r".{0,50}(WebSearch|WebFetch|Bash|Write|Edit|mx-search|mx-data|理杏仁)",
            re.IGNORECASE,
        ),
        "Agent 句式直接绑定联网、命令、写入或取数工具",
    ),
    RiskRule(
        "agent-direct-data-work",
        re.compile(
            r"(后台\s*Agent|子\s*Agent|角色\s*Agent|侦察\s*Agent|作者\s*Agent|编辑\s*Agent|读者\s*Agent|Agent)"
            r".{0,50}(自行|各自|分别|独立)?\s*(联网|搜索|检索|取数|拉取|下载|抓取|运行命令|写文件|写入|保存)",
            re.IGNORECASE,
        ),
        "Agent 句式直接承担联网、取数、命令执行或写文件",
    ),
    RiskRule(
        "delegate-privileged-work-to-agent",
        re.compile(
            r"(把|将|交给|分派给|委托).{0,40}"
            r"(后台\s*Agent|子\s*Agent|角色\s*Agent|侦察\s*Agent|作者\s*Agent|编辑\s*Agent|读者\s*Agent|Agent)"
            r".{0,60}(联网|搜索|检索|取数|拉取|下载|抓取|运行命令|写文件|写入|保存|WebSearch|WebFetch|Bash|Write|Edit)",
            re.IGNORECASE,
        ),
        "主流程把权限敏感工作交给 Agent",
    ),
    RiskRule(
        "task-agent-privileged-tools",
        re.compile(
            r"(Task|TeamCreate|subagent).{0,90}"
            r"(WebSearch|WebFetch|Bash|Write|Edit|mx-search|mx-data|理杏仁|搜索|取数|写文件|保存)",
            re.IGNORECASE,
        ),
        "Task/TeamCreate/subagent 配置中出现权限敏感工具或职责",
    ),
)


def _pass(msg: str) -> None:
    print(f"PASS: {msg}")


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")


def iter_skill_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for rel_dir in SKILL_DIRS:
        root = repo / rel_dir
        if root.exists():
            files.extend(sorted(root.glob("*.md")))
    return files


def _context(lines: list[str], index: int) -> str:
    start = max(0, index - 1)
    end = min(len(lines), index + 2)
    return "\n".join(lines[start:end])


def _is_allowed_context(text: str) -> bool:
    return any(marker in text for marker in ALLOW_CONTEXT_MARKERS)


def scan_file(path: Path, repo: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    failures: list[str] = []
    rel = path.relative_to(repo).as_posix()

    for idx, line in enumerate(lines):
        context = _context(lines, idx)
        for rule in HIGH_RISK_RULES:
            if not rule.pattern.search(line):
                continue
            if _is_allowed_context(context):
                continue
            failures.append(
                f"{rel}:{idx + 1}: {rule.name}: {rule.reason}: {line.strip()}"
            )
    return failures


def check_permissions(repo: Path | None = None, verbose: bool = True) -> int:
    repo = repo or REPO
    files = iter_skill_files(repo)
    failures: list[str] = []
    for path in files:
        failures.extend(scan_file(path, repo))

    if failures:
        for item in failures:
            _fail(item)
        return 1

    if verbose:
        _pass(f"高风险后台 Agent 旧句式扫描通过 ({len(files)} files)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="权限安全多 Agent 静态校验")
    ap.add_argument(
        "--repo",
        type=Path,
        default=REPO,
        help="仓库根目录，默认自动从脚本位置向上查找",
    )
    args = ap.parse_args()

    repo = args.repo.resolve()
    print(f"== verify_multi_agent_permissions.py (repo={repo}) ==")
    rc = check_permissions(repo=repo, verbose=True)
    print(f"\n== 结果: {'全部通过' if rc == 0 else '存在失败'} (exit={rc}) ==")
    return rc


if __name__ == "__main__":
    sys.exit(main())
