# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import py_compile
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_xueqiu_scraper_compiles_on_windows_paths() -> None:
    py_compile.compile(
        str(REPO / "tools" / "xueqiu_scraper.py"),
        doraise=True,
    )


def test_verify_channel_quick_outputs_under_gbk_encoding() -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "gbk"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "verify_channel_capability.py"),
            "--quick",
        ],
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="replace",
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "UnicodeEncodeError" not in proc.stdout + proc.stderr
