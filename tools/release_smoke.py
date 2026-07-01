#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, NamedTuple


EXPECTED_SKILL_COUNT = 19

AUTHOR_MACHINE_PATH_PATTERNS = [
    "C:/Users/admin",
    r"C:\Users\admin",
    "/Users/linxuan",
    "~/.claude/projects",
    "-Users-linxuan",
    "lixingren_docs",
]

LEGACY_SKILL_COUNT_PATTERNS = [
    "18" + " 个",
    "16" + " clear",
    "16" + " 个",
    "16" + " Skills",
]

CODEX_REQUIRED_TOOL_FILES = [
    "financial_rigor.py",
    "report_audit.py",
    "portfolio_analyzer.py",
    "team_research_outputs.py",
    "lxr_data.py",
    "md2html.py",
    "verify_channel_capability.py",
]


class CheckResult(NamedTuple):
    ok: bool
    detail: str


class Check(NamedTuple):
    name: str
    run: Callable[[], CheckResult]


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _run(args: list[str], repo: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def _find_executable(candidates: list[str]) -> str | None:
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return None


def _release_surface_files(repo: Path) -> list[Path]:
    roots = [
        repo / "README.md",
        repo / "README_EN.md",
        repo / "skills",
        repo / "codex" / "ai-berkshire" / "references" / "skills",
        repo / "docs",
        repo / "install.ps1",
        repo / "install.sh",
    ]
    roadmap = repo / "docs" / "ROADMAP.md"
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(path for path in files if path != roadmap)


def _fail_from_process(label: str, completed: subprocess.CompletedProcess[str]) -> CheckResult:
    output = (completed.stderr or completed.stdout).strip()
    if not output:
        output = f"exit code {completed.returncode}"
    return CheckResult(False, f"{label}: {output}")


def check_skill_count(repo: Path) -> CheckResult:
    skill_files = sorted((repo / "skills").glob("*.md"))
    actual = len(skill_files)
    if actual != EXPECTED_SKILL_COUNT:
        names = ", ".join(path.name for path in skill_files)
        return CheckResult(False, f"expected {EXPECTED_SKILL_COUNT}, got {actual}: {names}")
    return CheckResult(True, f"{actual} skill files")


def check_install_ps1_parser(repo: Path) -> CheckResult:
    executable = _find_executable(["pwsh", "powershell"])
    if executable is None:
        return CheckResult(False, "pwsh/powershell not found")
    install_path = str(repo / "install.ps1").replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{install_path}', "
        "[ref]$tokens, [ref]$errors) > $null; "
        "if ($errors.Count) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
    )
    completed = _run([executable, "-NoProfile", "-NonInteractive", "-Command", command], repo)
    if completed.returncode != 0:
        return _fail_from_process("install.ps1 parse failed", completed)
    return CheckResult(True, Path(executable).name)


def check_install_sh_syntax(repo: Path) -> CheckResult:
    executable = _find_executable(["bash"])
    if executable is None:
        return CheckResult(False, "bash not found")
    completed = _run([executable, "-n", "install.sh"], repo)
    if completed.returncode != 0:
        return _fail_from_process("install.sh syntax failed", completed)
    return CheckResult(True, Path(executable).name)


def check_lxr_config_untracked(repo: Path) -> CheckResult:
    completed = _run(["git", "ls-files", "--error-unmatch", "tools/lxr_config.json"], repo)
    if completed.returncode == 0:
        return CheckResult(False, "tools/lxr_config.json is tracked by git")
    return CheckResult(True, "tools/lxr_config.json is not tracked")


def check_release_surface_paths(repo: Path) -> CheckResult:
    offenders: list[str] = []
    for path in _release_surface_files(repo):
        text = path.read_text(encoding="utf-8", errors="replace")
        rel_path = path.relative_to(repo).as_posix()
        for pattern in AUTHOR_MACHINE_PATH_PATTERNS:
            if pattern in text:
                offenders.append(f"{rel_path}: contains {pattern!r}")
    if offenders:
        return CheckResult(False, "\n".join(offenders))
    return CheckResult(True, "no author machine paths")


def check_portfolio_sample_json(repo: Path) -> CheckResult:
    sample = repo / "examples" / "portfolio-holdings.sample.json"
    completed = _run(
        [
            sys.executable,
            str(repo / "tools" / "portfolio_analyzer.py"),
            "analyze",
            str(sample),
            "--format",
            "json",
        ],
        repo,
    )
    if completed.returncode != 0:
        return _fail_from_process("portfolio sample failed", completed)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return CheckResult(False, f"portfolio output is not JSON: {exc}")
    required_keys = {"holdings", "executive_summary", "rebalance_suggestions"}
    missing = sorted(required_keys - set(payload))
    if missing:
        return CheckResult(False, f"portfolio output missing keys: {', '.join(missing)}")
    return CheckResult(True, f"{len(payload['holdings'])} holdings analyzed")


def check_readme_install_contract(repo: Path) -> CheckResult:
    requirements = {
        "README.md": [
            "19 个 Skill",
            "19 个 Claude Code slash command",
            "git clone https://github.com/DragonQuix/ai-berkshire.git",
            "bash install.sh",
            "pwsh install.ps1",
            "~/.claude/commands",
        ],
        "README_EN.md": [
            "19 Skills",
            "19 Claude Code slash commands",
            "git clone https://github.com/DragonQuix/ai-berkshire.git",
            "bash install.sh",
            "pwsh install.ps1",
            "~/.claude/commands",
        ],
    }
    missing: list[str] = []
    for rel_path, snippets in requirements.items():
        text = (repo / rel_path).read_text(encoding="utf-8", errors="replace")
        for snippet in snippets:
            if snippet not in text:
                missing.append(f"{rel_path}: missing {snippet!r}")
        for pattern in LEGACY_SKILL_COUNT_PATTERNS:
            if pattern in text:
                missing.append(f"{rel_path}: contains legacy count {pattern!r}")
    if missing:
        return CheckResult(False, "\n".join(missing))
    return CheckResult(True, "README install commands and counts are aligned")


def check_codex_package_contract(repo: Path) -> CheckResult:
    package = repo / "codex" / "ai-berkshire"
    reference_skills = package / "references" / "skills"
    bundled_tools = package / "scripts" / "tools"
    root_tools = repo / "tools"
    problems: list[str] = []

    if not (package / "SKILL.md").is_file():
        problems.append("codex/ai-berkshire/SKILL.md is missing")

    references = sorted(reference_skills.glob("*.md"))
    if len(references) != EXPECTED_SKILL_COUNT:
        problems.append(
            "codex references expected "
            f"{EXPECTED_SKILL_COUNT}, got {len(references)}"
        )

    for filename in CODEX_REQUIRED_TOOL_FILES:
        if not (bundled_tools / filename).is_file():
            problems.append(f"codex bundled tool missing: {filename}")

    if (bundled_tools / "lxr_config.json").exists():
        problems.append("codex bundle must not include private lxr_config.json")

    for codex_tool in sorted(bundled_tools.glob("*.py")):
        root_tool = root_tools / codex_tool.name
        if not root_tool.exists():
            problems.append(f"codex bundled tool has no root counterpart: {codex_tool.name}")
        elif codex_tool.read_bytes() != root_tool.read_bytes():
            problems.append(f"codex bundled tool is stale: {codex_tool.name}")

    if problems:
        return CheckResult(False, "\n".join(problems))
    return CheckResult(
        True,
        f"{len(references)} references, {len(list(bundled_tools.glob('*.py')))} tools synced",
    )


def check_release_notes_dry_run(repo: Path) -> CheckResult:
    completed = _run(
        [
            sys.executable,
            str(repo / "tools" / "release_notes.py"),
            "--from",
            "HEAD",
            "--to",
            "HEAD",
            "--title",
            "release smoke",
        ],
        repo,
    )
    if completed.returncode != 0:
        return _fail_from_process("release notes dry run failed", completed)
    if "# release smoke" not in completed.stdout or "没有发现提交" not in completed.stdout:
        return CheckResult(False, "release notes dry run output missing expected markers")
    return CheckResult(True, "release_notes.py can render Markdown without commits")


def build_checks(repo: Path) -> list[Check]:
    repo = repo.resolve()
    return [
        Check("skills/*.md count", lambda: check_skill_count(repo)),
        Check("install.ps1 parser", lambda: check_install_ps1_parser(repo)),
        Check("install.sh bash -n", lambda: check_install_sh_syntax(repo)),
        Check("tools/lxr_config.json untracked", lambda: check_lxr_config_untracked(repo)),
        Check(
            "release surface has no author machine paths",
            lambda: check_release_surface_paths(repo),
        ),
        Check("portfolio sample json", lambda: check_portfolio_sample_json(repo)),
        Check(
            "README install commands and skill count",
            lambda: check_readme_install_contract(repo),
        ),
        Check(
            "Codex package install contract",
            lambda: check_codex_package_contract(repo),
        ),
        Check("release notes dry run", lambda: check_release_notes_dry_run(repo)),
    ]


def main() -> int:
    _ensure_utf8_stdio()
    repo = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for check in build_checks(repo):
        result = check.run()
        status = "PASS" if result.ok else "FAIL"
        print(f"[{status}] {check.name}: {result.detail}")
        if not result.ok:
            failures.append(check.name)
    if failures:
        print(f"FAIL release smoke: {len(failures)} check(s) failed", file=sys.stderr)
        return 1
    print("PASS release smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
