#!/usr/bin/env python3
"""financial_rigor 单元测试。"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, TOOLS_DIR)
REPO_ROOT = Path(__file__).resolve().parents[1]

import financial_rigor as fr  # noqa: E402


def _capture_stdout(func, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


def _run_financial_rigor_cli(*args):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "financial_rigor.py"), *args],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


class TestDividendYield(unittest.TestCase):
    def test_decimal_yield_ratio(self):
        # 理杏仁 dyr=0.0409 表示 4.09%
        dps = fr._dividend_per_share_from_yield(1000.0, 0.0409)
        self.assertAlmostEqual(dps, 40.9, places=2)

    def test_percent_yield_form(self):
        dps = fr._dividend_per_share_from_yield(100.0, 4.09)
        self.assertAlmostEqual(dps, 4.09, places=2)


class TestMarketCapVerification(unittest.TestCase):
    def test_market_cap_passes_when_deviation_within_one_percent(self):
        result, out = _capture_stdout(fr.verify_market_cap, 10, 100, 1000, "CNY")

        self.assertTrue(result)
        self.assertIn("验证通过", out)
        self.assertIn("0.00%", out)

    def test_market_cap_warns_but_passes_when_deviation_within_five_percent(self):
        result, out = _capture_stdout(fr.verify_market_cap, 10, 100, 970, "CNY")

        self.assertTrue(result)
        self.assertIn("可接受范围", out)

    def test_market_cap_fails_when_deviation_exceeds_five_percent(self):
        result, out = _capture_stdout(fr.verify_market_cap, 10, 100, 900, "CNY")

        self.assertFalse(result)
        self.assertIn("警告", out)
        self.assertIn("> 5%", out)


class TestValuationVerification(unittest.TestCase):
    def test_valuation_returns_core_ratios_from_raw_inputs(self):
        result, _ = _capture_stdout(
            fr.verify_valuation,
            100,
            eps=5,
            bvps=25,
            fcf_per_share=10,
            dividend=4,
            revenue_per_share=50,
        )

        self.assertEqual(20.0, result["PE"])
        self.assertEqual(4.0, result["PB"])
        self.assertEqual(20.0, result["ROE"])
        self.assertEqual(10.0, result["P_FCF"])
        self.assertEqual(10.0, result["FCF_Yield"])
        self.assertEqual(4.0, result["Dividend_Yield"])
        self.assertEqual(2.0, result["PS"])

    def test_valuation_skips_zero_denominators(self):
        result, out = _capture_stdout(fr.verify_valuation, 100, eps=0, bvps=0)

        self.assertEqual({}, result)
        self.assertIn("EPS为0", out)


class TestCrossValidation(unittest.TestCase):
    def test_cross_validate_marks_consistent_sources(self):
        result, out = _capture_stdout(
            fr.cross_validate,
            "revenue",
            {"annual_report": 100, "exchange": 101, "vendor": 99},
            "亿",
            2.0,
        )

        self.assertTrue(result["all_consistent"])
        self.assertEqual(100.0, result["consensus"])
        self.assertIn("数据一致", out)

    def test_cross_validate_flags_outlier_source(self):
        result, out = _capture_stdout(
            fr.cross_validate,
            "revenue",
            {"annual_report": 100, "exchange": 100, "vendor": 130},
            "亿",
            2.0,
        )

        self.assertFalse(result["all_consistent"])
        self.assertEqual(100.0, result["consensus"])
        self.assertIn("存在来源偏差", out)

    def test_cross_validate_warns_when_values_have_suspicious_magnitude_gap(self):
        result, out = _capture_stdout(
            fr.cross_validate,
            "market_cap",
            {"annual_report": 41302, "vendor": 413.02},
            "亿",
            2.0,
        )

        self.assertTrue(result["magnitude_warning"])
        self.assertIn("疑似单位不一致", out)

    def test_cross_validate_prints_caliber_and_uses_reference_median_wording(self):
        result, out = _capture_stdout(
            fr.cross_validate,
            "revenue",
            {"annual_report": 100, "vendor": 101},
            "亿",
            2.0,
            caliber="年报披露收益口径",
        )

        self.assertEqual("年报披露收益口径", result["caliber"])
        self.assertIn("口径说明: 年报披露收益口径", out)
        self.assertIn("参考中位数", out)
        self.assertNotIn("加权中位数", out)


class TestThreeScenarioValuation(unittest.TestCase):
    def test_cli_normalizes_percent_growth_inputs_and_warns_on_stderr(self):
        proc = _run_financial_rigor_cli(
            "three-scenario",
            "--price",
            "100",
            "--eps",
            "5",
            "--shares",
            "10",
            "--growth",
            "30",
            "15",
            "-5",
            "--pe",
            "25",
            "20",
            "10",
            "--years",
            "1",
            "--currency",
            "CNY",
        )

        self.assertEqual(0, proc.returncode, msg=f"stderr:\n{proc.stderr}")
        self.assertIn("growth 参数疑似百分数", proc.stderr)
        self.assertIn("30%", proc.stdout)
        self.assertIn("15%", proc.stdout)
        self.assertIn("-5%", proc.stdout)
        self.assertNotIn("3000%", proc.stdout)
        self.assertNotIn("1500%", proc.stdout)
        self.assertNotIn("-500%", proc.stdout)


class TestBenfordCheck(unittest.TestCase):
    def test_benford_returns_none_for_small_samples(self):
        result, out = _capture_stdout(fr.benford_check, [1, 2, 3])

        self.assertIsNone(result)
        self.assertIn("样本量不足", out)

    def test_benford_flags_nonconforming_distribution(self):
        values = [9000 + i for i in range(90)]
        result, out = _capture_stdout(fr.benford_check, values)

        self.assertIsNotNone(result)
        self.assertFalse(result["is_conforming"])
        self.assertIn("Nonconforming", result["conformity"])
        self.assertIn("分布异常", out)


class TestExactCalc(unittest.TestCase):
    def test_exact_calc_allows_basic_financial_expression(self):
        result, out = _capture_stdout(fr.exact_calc, "510 * 9.11e9")

        self.assertEqual(4646100000000.0, result)
        self.assertIn("精确值", out)

    def test_exact_calc_rejects_unsafe_expression(self):
        result, out = _capture_stdout(fr.exact_calc, "__import__('os')")

        self.assertIsNone(result)
        self.assertIn("不安全的表达式", out)


class TestWindowsCliEncoding(unittest.TestCase):
    def test_cli_reconfigures_gbk_stdio_to_avoid_unicode_encode_errors(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "gbk"
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "financial_rigor.py"),
                "verify-market-cap",
                "--price",
                "10",
                "--shares",
                "100",
                "--reported",
                "1000",
                "--currency",
                "CNY",
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
        )

        stdout = proc.stdout.decode("utf-8", errors="replace")
        stderr = proc.stderr.decode("utf-8", errors="replace")
        self.assertEqual(
            0,
            proc.returncode,
            msg=f"stdout:\n{stdout}\nstderr:\n{stderr}",
        )
        self.assertIn("验证通过", stdout)


if __name__ == "__main__":
    unittest.main()
