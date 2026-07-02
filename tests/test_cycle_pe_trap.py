# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "cycle_pe_trap.py"


def load_cycle_pe_trap():
    assert TOOL.exists(), "tools/cycle_pe_trap.py missing"
    spec = importlib.util.spec_from_file_location("cycle_pe_trap", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_oil_gas_low_pe_at_peak_flags_high_cycle_trap_risk() -> None:
    tool = load_cycle_pe_trap()

    result = tool.analyze_cycle_pe_trap(
        industry="油气",
        pe_percentile=47.4,
        net_profit=[247, 703, 718, 1238, 1221],
        revenue=[2000, 2500, 3000, 3500, 3982],
        commodity_price=82.0,
    )

    assert result["is_cyclical"] is True
    assert result["cycle_position"] == "top"
    assert result["risk_level"] == "high"
    assert result["risk_score"] >= 75
    assert "low_mid_pe_at_peak" in result["signals"]
    assert "earnings_near_peak" in result["signals"]
    assert "commodity_price_high" in result["signals"]


def test_non_cyclical_industry_returns_not_applicable() -> None:
    tool = load_cycle_pe_trap()

    result = tool.analyze_cycle_pe_trap(
        industry="软件",
        pe_percentile=35,
        net_profit=[10, 12, 15, 20, 28],
        revenue=[100, 120, 150, 190, 240],
    )

    assert result["is_cyclical"] is False
    assert result["cycle_position"] == "non_cyclical"
    assert result["risk_level"] == "not_applicable"
    assert result["risk_score"] == 0


def test_cli_outputs_json_for_cycle_trap_check() -> None:
    assert TOOL.exists(), "tools/cycle_pe_trap.py missing"

    proc = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--industry",
            "油气",
            "--pe-percentile",
            "47.4",
            "--net-profit",
            "[247, 703, 718, 1238, 1221]",
            "--revenue",
            "[2000, 2500, 3000, 3500, 3982]",
            "--commodity-price",
            "82",
            "--format",
            "json",
        ],
        cwd=REPO,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["cycle_position"] == "top"
    assert payload["risk_level"] == "high"
