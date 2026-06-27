#!/usr/bin/env python3
"""financial_rigor 单元测试。"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, TOOLS_DIR)

import financial_rigor as fr  # noqa: E402


class TestDividendYield(unittest.TestCase):
    def test_decimal_yield_ratio(self):
        # 理杏仁 dyr=0.0409 表示 4.09%
        dps = fr._dividend_per_share_from_yield(1000.0, 0.0409)
        self.assertAlmostEqual(dps, 40.9, places=2)

    def test_percent_yield_form(self):
        dps = fr._dividend_per_share_from_yield(100.0, 4.09)
        self.assertAlmostEqual(dps, 4.09, places=2)


if __name__ == "__main__":
    unittest.main()
