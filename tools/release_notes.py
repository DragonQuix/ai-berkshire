#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


GIT_FIELD_SEPARATOR = "\x1f"

CATEGORY_BY_TYPE = {
    "feat": "功能",
    "fix": "修复",
    "docs": "文档",
    "test": "测试",
    "ci": "CI / 发布工程",
    "build": "CI / 发布工程",
    "chore": "工程维护",
    "refactor": "工程维护",
    "perf": "工程维护",
    "style": "工程维护",
}

CATEGORY_ORDER = [
    "功能",
    "修复",
    "CI / 发布工程",
    "文档",
    "测试",
    "工程维护",
    "其他",
]

CONVENTIONAL_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^)]+)\))?!?:\s*(?P<summary>.+)$"
)


class Commit(NamedTuple):
    hash: str
    type: str
    scope: str | None
    summary: str

    @property
    def category(self) -> str:
        return CATEGORY_BY_TYPE.get(self.type, "其他")

    @property
    def short_hash(self) -> str:
        return self.hash[:8]


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def parse_git_log_line(line: str) -> Commit:
    commit_hash, separator, subject = line.partition(GIT_FIELD_SEPARATOR)
    if not separator:
        raise ValueError(f"git log line missing separator: {line!r}")

    subject = subject.strip()
    match = CONVENTIONAL_RE.match(subject)
    if not match:
        return Commit(commit_hash, "other", None, subject)

    commit_type = match.group("type").lower()
    return Commit(
        commit_hash,
        commit_type if commit_type in CATEGORY_BY_TYPE else "other",
        match.group("scope"),
        match.group("summary").strip(),
    )


def collect_commits(
    repo: Path,
    from_ref: str,
    to_ref: str,
    max_count: int | None = None,
) -> list[Commit]:
    args = [
        "git",
        "log",
        f"{from_ref}..{to_ref}",
        f"--format=%H{GIT_FIELD_SEPARATOR}%s",
    ]
    if max_count is not None:
        args.append(f"--max-count={max_count}")

    completed = subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"git log failed: {message}")

    return [
        parse_git_log_line(line)
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def _format_commit(commit: Commit) -> str:
    if commit.scope:
        return f"- `{commit.short_hash}` **{commit.scope}**：{commit.summary}"
    return f"- `{commit.short_hash}` {commit.summary}"


def generate_release_notes(
    commits: list[Commit],
    from_ref: str,
    to_ref: str,
    title: str,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"范围：`{from_ref}..{to_ref}`",
        "",
        f"提交数：{len(commits)}",
        "",
    ]
    if not commits:
        lines.append("没有发现提交。")
        lines.append("")
        return "\n".join(lines)

    grouped: dict[str, list[Commit]] = {}
    for commit in commits:
        grouped.setdefault(commit.category, []).append(commit)

    for category in CATEGORY_ORDER:
        items = grouped.get(category)
        if not items:
            continue
        lines.append(f"## {category}")
        lines.append("")
        lines.extend(_format_commit(commit) for commit in items)
        lines.append("")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Markdown release notes from local git commits."
    )
    parser.add_argument(
        "--from",
        dest="from_ref",
        default="origin/main",
        help="base ref, default: origin/main",
    )
    parser.add_argument(
        "--to",
        dest="to_ref",
        default="HEAD",
        help="target ref, default: HEAD",
    )
    parser.add_argument(
        "--title",
        default="AI Berkshire Release Notes",
        help="Markdown title",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="write Markdown to file instead of stdout",
    )
    parser.add_argument(
        "--max-count",
        type=int,
        help="limit number of commits read from git log",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root, default: current tool repository",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        commits = collect_commits(
            args.repo.resolve(),
            args.from_ref,
            args.to_ref,
            args.max_count,
        )
        notes = generate_release_notes(
            commits,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            title=args.title,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(notes, encoding="utf-8", newline="\n")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
