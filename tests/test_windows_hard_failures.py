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


def test_expected_skill_count_matches_actual_skill_files() -> None:
    """verify_channel_capability 的 EXPECTED_SKILL_COUNT 必须与实际 skill 数一致。

    回归保护：新增 /compare skill 后计数从 18 升至 19；若再增删 skill 必须同步
    更新 EXPECTED_SKILL_COUNT，否则 verify_channel_capability --quick 会硬失败。
    """
    root_skills = sorted(p.name for p in (REPO / "skills").glob("*.md"))
    codex_skills = sorted(
        p.name for p in (REPO / "codex" / "ai-berkshire" / "references" / "skills").glob("*.md")
    )
    assert "compare.md" in root_skills
    assert root_skills == codex_skills  # root/codex 必须配对
    # 读取 verify_channel_capability.py 里的 EXPECTED_SKILL_COUNT 字面量
    vcc = (REPO / "tools" / "verify_channel_capability.py").read_text(encoding="utf-8")
    import re
    m = re.search(r"EXPECTED_SKILL_COUNT\s*=\s*(\d+)", vcc)
    assert m, "EXPECTED_SKILL_COUNT 未定义"
    assert int(m.group(1)) == len(root_skills) == len(codex_skills)


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


def test_verify_channel_quick_validates_team_regression_samples() -> None:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
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
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "-- F) 团队研究回归样例校验 --" in proc.stdout
    assert "tencent-supplement-loop" in proc.stdout
