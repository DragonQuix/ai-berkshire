#!/usr/bin/env python3
"""lxr_data 阶段3 逻辑单元测试 — 纯 mock，不依赖网络与真实 token。

覆盖：
- 市场探测与代码归一（港股补零5位 / A股6位）。
- _extract_invalid_metrics：fundamental 端点 value=全量列表时只取 message 括号子集（关键回归）。
- 端点路由：港股 hk/*、A股 cn/*；K线用 stockCode 单值；港股股东用 latest-shareholders。
- _post_fs 自动剪枝：遇无效指标剔除并重试。
- get_valuation_percentiles：分批请求合并并构建 4×6×8 矩阵。
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, TOOLS_DIR)

import lxr_data as lxd  # noqa: E402
from lxr_client import LixingerValidationError  # noqa: E402


class _FakeCache:
    def __init__(self):
        self.dir = tempfile.gettempdir()


class FakeClient:
    """按 endpoint 队列返回 canned 数据；队列为异常实例则抛出。"""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}
        self.config = {}
        self.cache = _FakeCache()

    def post(self, endpoint, payload, ttl_seconds=None):
        self.calls.append((endpoint, payload))
        queue = self._responses.get(endpoint, [])
        if not queue:
            return []
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _val_err(msg):
    return LixingerValidationError(msg, details=[{"message": msg}])


class TestMarketDetection(unittest.TestCase):
    def test_detect_hk(self):
        self.assertEqual(lxd._detect_market("00700"), "hk")
        self.assertEqual(lxd._detect_market("0700.HK"), "hk")
        self.assertEqual(lxd._detect_market("9888"), "hk")
        self.assertEqual(lxd._detect_market("9988.HK"), "hk")

    def test_detect_cn(self):
        self.assertEqual(lxd._detect_market("600519"), "cn")
        self.assertEqual(lxd._detect_market("000001"), "cn")
        self.assertEqual(lxd._detect_market("601336.SH"), "cn")

    def test_norm_hk_pads(self):
        self.assertEqual(lxd._norm_code("0700.HK"), "00700")
        self.assertEqual(lxd._norm_code("9888"), "09888")
        self.assertEqual(lxd._norm_code("00700"), "00700")

    def test_norm_cn_keeps6(self):
        self.assertEqual(lxd._norm_code("600519"), "600519")
        self.assertEqual(lxd._norm_code("601336.SH"), "601336")


class TestExtractInvalidMetrics(unittest.TestCase):
    def test_fundamental_value_is_full_list_ignored(self):
        """fundamental 端点 value=全量提交列表，必须只取 message 括号子集，不得误伤全部。"""
        full = ["sp", "mc", "cmc", "ecmc", "pe_ttm", "pb", "d_pe_ttm", "pb_wo_gw"]
        err = LixingerValidationError(
            "(cmc,ecmc,d_pe_ttm,pb_wo_gw) are invalid price metrics",
            details=[{"value": full, "path": ["metricsList"],
                      "message": "(cmc,ecmc,d_pe_ttm,pb_wo_gw) are invalid price metrics"}],
        )
        invalid = lxd._extract_invalid_metrics(err)
        self.assertEqual(invalid, {"cmc", "ecmc", "d_pe_ttm", "pb_wo_gw"})
        # 关键：不得包含 valid 指标
        self.assertNotIn("sp", invalid)
        self.assertNotIn("pe_ttm", invalid)

    def test_fs_single_metric(self):
        err = LixingerValidationError("(q.ps.op.t) are invalid fs metrics",
                                      details=[{"message": "(q.ps.op.t) are invalid fs metrics"}])
        self.assertEqual(lxd._extract_invalid_metrics(err), {"q.ps.op.t"})

    def test_str_details_and_str_err_fallback(self):
        err = LixingerValidationError("ValidationError: (a,b,c) are invalid", details=[])
        self.assertEqual(lxd._extract_invalid_metrics(err), {"a", "b", "c"})


class TestEndpointRouting(unittest.TestCase):
    def _make(self, responses):
        return lxd.LxrData(client=FakeClient(responses), verbose=False)

    def test_financials_routes_hk(self):
        cli = FakeClient({
            "hk/company": [{"list": [{"fsTableType": "non_financial"}]}],
            "hk/company/fs/non_financial": [[{"date": "2025-12-31", "q": {}}]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        d.get_financials("00700", years=2, source="lixinger")
        eps = [e for e, _ in cli.calls]
        self.assertIn("hk/company", eps)
        self.assertIn("hk/company/fs/non_financial", eps)
        # 代码归一为 00700
        fs_call = next(p for e, p in cli.calls if e == "hk/company/fs/non_financial")
        self.assertEqual(fs_call["stockCodes"], ["00700"])

    def test_valuation_routes_cn(self):
        cli = FakeClient({
            "cn/company": [{"list": [{"fsTableType": "non_financial"}]}],
            "cn/company/fundamental/non_financial": [[{"date": "2026-06-26", "sp": 1271.1}]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_valuation("600519", source="lixinger")
        eps = [e for e, _ in cli.calls]
        self.assertIn("cn/company/fundamental/non_financial", eps)
        self.assertEqual(r["_source"], "lixinger")

    def test_kline_uses_single_stockCode(self):
        cli = FakeClient({"hk/company/candlestick": [
            [{"date": "2026-06-26", "close": 411.8, "high": 415.0, "volume": 1}]]})
        d = lxd.LxrData(client=cli, verbose=False)
        d.get_kline("0700.HK", days=10)
        ep, payload = cli.calls[-1]
        self.assertEqual(ep, "hk/company/candlestick")
        # K线用 stockCode 单值（非数组）
        self.assertEqual(payload["stockCode"], "00700")
        self.assertNotIn("stockCodes", payload)

    def test_majority_shareholders_hk_vs_cn(self):
        cli = FakeClient({"hk/company/latest-shareholders": [[{"name": "Naspers"}]],
                          "cn/company/majority-shareholders": [[{"name": "HKSCC"}]]})
        d = lxd.LxrData(client=cli, verbose=False)
        d.get_majority_shareholders("00700", years=1)
        d.get_majority_shareholders("600519", years=1)
        eps = [e for e, _ in cli.calls]
        self.assertIn("hk/company/latest-shareholders", eps)
        self.assertIn("cn/company/majority-shareholders", eps)

    def test_shareholders_num_hk_not_available(self):
        cli = FakeClient({})
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_shareholders_num("00700", years=1)
        self.assertEqual(r["_source"], "none")
        self.assertEqual(r["note"], "港股无股东人数端点")
        # 不应发起任何网络调用
        self.assertEqual(cli.calls, [])


class TestPostFsAutoPrune(unittest.TestCase):
    def test_prune_invalid_and_retry(self):
        err = _val_err("(q.ps.op.t) are invalid fs metrics")
        cli = FakeClient({
            "hk/company": [{"list": [{"fsTableType": "non_financial"}]}],
            "hk/company/fs/non_financial": [err, [{"date": "2025-12-31", "q": {}}]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_financials("00700", years=1, source="lixinger")
        # 两次 fs 调用：第一次 400，第二次成功
        fs_calls = [p for e, p in cli.calls if e == "hk/company/fs/non_financial"]
        self.assertEqual(len(fs_calls), 2)
        self.assertIn("q.ps.op.t", fs_calls[0]["metricsList"])
        self.assertNotIn("q.ps.op.t", fs_calls[1]["metricsList"])
        self.assertEqual(r["_source"], "lixinger")


class TestValuationPercentilesMatrix(unittest.TestCase):
    def test_matrix_built_and_chunked(self):
        # 单批返回拍平后的全 192 指标（用首条记录的 flat 结构模拟）
        def fake_record(metrics):
            rec = {}
            cur = rec
            for m in metrics:
                cur[m] = 0.5  # 简化：直接顶层键（_flatten_latest 会拍平嵌套，这里用顶层）
            return rec
        # 构造一个嵌套结构以验证拍平
        all_metrics = [
            f"{n}.{g}.{s}" for n in lxd.PERCENTILE_METRICS_NAME
            for g in lxd.PERCENTILE_GRANULARITY for s in lxd.PERCENTILE_STATS
        ]
        # 把指标构造成 nested dict: {pe_ttm: {y10: {cvpos: 0.5, ...}}}
        nested = {}
        for m in all_metrics:
            parts = m.split(".")
            cur = nested
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = 0.5
        record = {"date": "2026-06-26", **nested}
        cli = FakeClient({
            "cn/company": [{"list": [{"fsTableType": "non_financial"}]}],
            "cn/company/fundamental/non_financial": [[record]] * 10,
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_valuation_percentiles("600519")
        # 应分批（ceil(192/30)=7 次请求）
        fund_calls = [p for e, p in cli.calls if e == "cn/company/fundamental/non_financial"]
        self.assertGreaterEqual(len(fund_calls), 7)
        matrix = r["matrix"]
        # 抽查若干单元格
        self.assertEqual(matrix["pe_ttm"]["y10"]["cvpos"], 0.5)
        self.assertEqual(matrix["pb"]["y5"]["q5v"], 0.5)
        self.assertEqual(matrix["dyr"]["fs"]["avgv"], 0.5)


if __name__ == "__main__":
    unittest.main()
