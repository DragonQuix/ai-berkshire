# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = REPO / "tools" / "release_smoke.py"

REQUIRED_CHECKS = {
    "skills/*.md count",
    "install.ps1 parser",
    "install.sh bash -n",
    "tools/lxr_config.json untracked",
    "release surface has no author machine paths",
    "portfolio sample json",
    "README install commands and skill count",
    "Codex package install contract",
    "release notes dry run",
}


def load_release_smoke_module():
    spec = importlib.util.spec_from_file_location("release_smoke", SMOKE_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_smoke_declares_p0_5_checks() -> None:
    module = load_release_smoke_module()

    checks = module.build_checks(REPO)
    check_names = {check.name for check in checks}

    assert REQUIRED_CHECKS <= check_names


def test_release_smoke_cli_passes_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, str(SMOKE_SCRIPT)],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS release smoke" in result.stdout
