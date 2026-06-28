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


class TestIndustryDeepAndGovernance(unittest.TestCase):
    def _insurance_record(self, ev, nbv, date="2025-12-31"):
        return {"date": date, "q": {"bs": {"ev": {"t": ev}}, "ps": {"nbv": {"t": nbv}}}}

    def test_industry_deep_insurance_summary(self):
        cli = FakeClient({
            "cn/company": [{"list": [{"fsTableType": "insurance"}]}],
            "cn/company/fs/insurance": [
                [self._insurance_record(287840000000, 9842000000, "2025-12-31"),
                 self._insurance_record(258448000000, 6253000000, "2024-12-31")]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_industry_deep("601336", years=2)
        self.assertEqual(r["_source"], "lixinger")
        self.assertEqual(r["report_type"], "insurance")
        ds = r["deep_summary"]
        self.assertEqual(len(ds["ev"]), 2)
        self.assertEqual(ds["ev"][0]["value"], 287840000000)
        self.assertEqual(ds["nbv"][0]["value"], 9842000000)

    def test_industry_deep_summary_pure(self):
        annual = [
            {"date": "2025-12-31", "q": {"bs": {"car": {"t": 0.1824}}, "ps": {}}},
            {"date": "2024-12-31", "q": {"bs": {"car": {"t": 0.1905}}, "ps": {}}},
        ]
        ds = lxd.LxrData._industry_deep_summary("bank", annual)
        self.assertEqual(ds["car"][0]["value"], 0.1824)

    def test_revenue_constitution(self):
        cli = FakeClient({
            "cn/company/operation-revenue-constitution": [
                [{"date": "2025-12-31", "d_oi": 1.0e12,
                  "dataList": [{"itemName": "茅台酒", "revenue": 1.0e11, "revenuePercentage": 0.85}]}]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_revenue_constitution("600519", years=1)
        self.assertEqual(r["_source"], "lixinger")
        self.assertGreater(len(r["records"]), 0)
        self.assertIn("dataList", r["records"][0])

    def test_governance_cn(self):
        cli = FakeClient({
            "cn/company/senior-executive-shares-change": [[{"executiveName": "张三", "changedShares": 10000}]],
            "cn/company/major-shareholders-shares-change": [[{"shareholderName": "大股东A", "changedShares": -5000}]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_governance("601336", years=1)
        self.assertEqual(r["_source"], "lixinger")
        self.assertEqual(len(r["executive_changes"]), 1)
        self.assertEqual(len(r["major_shareholder_changes"]), 1)

    def test_governance_hk_director(self):
        cli = FakeClient({"hk/company/hot/director_equity_change": [[{"directorName": "李四"}]]})
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_governance("00700", years=1)
        self.assertEqual(r["market"], "hk")
        self.assertEqual(len(r["director_changes"]), 1)
        eps = [e for e, _ in cli.calls]
        self.assertIn("hk/company/hot/director_equity_change", eps)


class TestMacroAndIndexValuation(unittest.TestCase):
    def test_flatten_index_val_flat_keys(self):
        rec = {"date": "2026-06-26", "pe_ttm.y10.mcw.cv": 14.33,
               "pe_ttm.y10.mcw.cvpos": 0.85, "cp": 4868.22}
        out = lxd.LxrData._flatten_index_val(rec)
        self.assertEqual(out["pe_ttm"]["cv"], 14.33)
        self.assertEqual(out["pe_ttm"]["cvpos"], 0.85)
        self.assertEqual(out["cp"], 4868.22)
        self.assertIsNone(out["pb"]["cv"])

    def test_interest_rates_latest_non_null(self):
        # 各指标仅更新日有值；按日期降序后取每指标最新非空
        cli = FakeClient({"macro/interest-rates": [[
            {"date": "2026-05-21", "shibor_m3": 0.014065},
            {"date": "2026-05-20", "lpr_y1": 0.03, "lpr_y5": 0.035, "shibor_m3": 0.014045},
            {"date": "2026-05-19", "shibor_m3": 0.01404},
        ]]})
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_macro_interest_rates(area="cn", years=1)
        self.assertEqual(r["latest"]["lpr_y1"], 0.03)
        self.assertEqual(r["latest"]["lpr_y5"], 0.035)
        self.assertEqual(r["latest"]["shibor_m3"], 0.014065)

    def test_bond_yield_10y(self):
        cli = FakeClient({"macro/national-debt": [[
            {"date": "2026-06-26", "tcm_y10": 0.0173, "tcm_y1": 0.015},
        ]]})
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_bond_yield_10y(area="cn")
        self.assertAlmostEqual(r["yield_10y"], 0.0173)

    def test_industry_of_stock_level_two(self):
        cli = FakeClient({
            "cn/industry/constituents/sw_2021": [[
                {"stockCode": "340000", "constituents": [{"stockCode": "600519"}]},
                {"stockCode": "340500", "constituents": [{"stockCode": "600519"}]},
                {"stockCode": "340501", "constituents": [{"stockCode": "600519"}]},
            ]],
            "cn/industry": [[
                {"stockCode": "340000", "name": "食品饮料", "level": "one"},
                {"stockCode": "340500", "name": "白酒", "level": "two"},
                {"stockCode": "340501", "name": "白酒", "level": "three"},
            ]],
        })
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_industry_of_stock("600519", source="sw_2021", level="two")
        self.assertEqual(r["industry_code"], "340500")
        self.assertEqual(r["industry_name"], "白酒")
        self.assertEqual(r["level"], "two")

    def test_industry_of_stock_hk_not_available(self):
        d = lxd.LxrData(client=FakeClient(), verbose=False)
        r = d.get_industry_of_stock("00700")
        self.assertIsNone(r["industry_code"])
        self.assertEqual(r["_source"], "none")

    def test_industry_valuation_uses_no_cp(self):
        cli = FakeClient({"cn/industry/fundamental/sw_2021": [[
            {"date": "2026-06-26", "pe_ttm.y10.mcw.cv": 17.78, "pe_ttm.y10.mcw.cvpos": 0.016},
        ]]})
        d = lxd.LxrData(client=cli, verbose=False)
        r = d.get_industry_valuation("340500", source="sw_2021")
        sent = [p for e, p in cli.calls if e == "cn/industry/fundamental/sw_2021"][0]
        self.assertNotIn("cp", sent["metricsList"])
        self.assertEqual(r["valuation"]["pe_ttm"]["cv"], 17.78)

    def test_industry_constituents_for_stock_anchor_first(self):
        cli = FakeClient({
            "cn/industry/constituents/sw_2021": [[
                {"stockCode": "340000", "constituents": [
                    {"stockCode": "600519"}, {"stockCode": "000568"}, {"stockCode": "000596"},
                ]},
                {"stockCode": "340500", "constituents": [
                    {"stockCode": "000568"}, {"stockCode": "600519"}, {"stockCode": "000596"},
                ]},
            ]],
            "cn/industry": [[
                {"stockCode": "340000", "name": "食品饮料", "level": "one"},
                {"stockCode": "340500", "name": "白酒", "level": "two"},
            ]],
        })
        d = lxd.LxrData(client=cli, verbose=False)

        r = d.get_industry_constituents_for_stock("600519", max_codes=3)

        self.assertEqual(r["_source"], "lixinger")
        self.assertEqual(r["industry_code"], "340500")
        self.assertEqual(r["industry_name"], "白酒")
        self.assertEqual(r["codes"], ["600519", "000568", "000596"])

    def test_lhb_industry_compare_uses_industry_constituents(self):
        d = lxd.LxrData(client=FakeClient(), verbose=False)
        calls = []

        def fake_compare(**kwargs):
            calls.append(kwargs)
            return {
                "_source": "legacy",
                "source_detail": "legacy:ashare_data/lhb-compare",
                "codes": kwargs["codes"],
                "rows": [{"code": "000568", "rank": 1}],
            }

        fake_industry = {
            "_source": "lixinger",
            "source_detail": "lixinger:industry-constituents",
            "anchor_code": "600519",
            "industry_code": "340500",
            "industry_name": "白酒",
            "level": "two",
            "codes": ["600519", "000568", "000596"],
            "constituent_count": 3,
        }
        with mock.patch.object(d, "get_industry_constituents_for_stock", return_value=fake_industry):
            with mock.patch.object(d, "get_lhb_compare", side_effect=fake_compare):
                out = d.get_lhb_industry_compare(
                    "600519",
                    start_date="2026-06-01",
                    end_date="2026-06-26",
                    max_codes=3,
                    min_recognition_score=50,
                    sort_by="youzi_recognition_score",
                )

        self.assertEqual(calls[0]["codes"], ["600519", "000568", "000596"])
        self.assertEqual(calls[0]["min_recognition_score"], 50)
        self.assertEqual(calls[0]["sort_by"], "youzi_recognition_score")
        self.assertEqual(out["source_detail"], "lixinger+legacy:lhb-industry-compare")
        self.assertEqual(out["industry"]["industry_name"], "白酒")
        self.assertEqual(out["compare"]["rows"][0]["code"], "000568")

    def test_format_lhb_industry_compare_text_shows_roadmap_summary(self):
        payload = {
            "anchor_code": "600519",
            "industry": {
                "industry_name": "白酒",
                "industry_code": "340500",
                "codes": ["600519", "000568"],
                "constituent_count": 2,
            },
            "compare": {
                "start_date": "2026-06-01",
                "end_date": "2026-06-26",
                "comparison_summary": {
                    "compare_readiness_summary": {
                        "readiness_level": "actionable",
                        "primary_reason": "strong_leadership",
                        "interpretation": "样本全命中且领先差距明确",
                    },
                    "code_coverage_summary": {
                        "matched_code_count": 2,
                        "code_count": 2,
                        "coverage_level": "full",
                    },
                    "youzi_recognition_gap_summary": {
                        "leader_code": "600519",
                        "runner_up_code": "000568",
                        "score_gap": 18.2,
                        "leadership_level": "moderate",
                    },
                    "youzi_composite_signal_summary": {
                        "signal_tag": "shared_youzi_present",
                        "leading_code": "600519",
                        "interpretation": "存在共同游资",
                    },
                    "top_youzi_alias_comparison": [{
                        "code": "600519",
                        "top_youzi_alias": "章盟主",
                        "top_youzi_alias_abs_net_amount": 120000000,
                        "alias_scope": "shared",
                        "youzi_recognition_score": 73.0,
                    }],
                    "youzi_direction_consistency_summary": {
                        "dominant_shared_direction_consistency": "same_direction",
                        "same_direction_shared_alias_count": 1,
                        "shared_alias_count": 1,
                        "mixed_direction_shared_alias_count": 0,
                    },
                    "shared_youzi_code_strengths": [{
                        "code": "600519",
                        "top_shared_alias": "章盟主",
                        "shared_abs_net_amount": 120000000,
                        "shared_abs_net_ratio": 0.6,
                    }],
                    "unique_youzi_code_strengths": [{
                        "code": "000568",
                        "top_unique_alias": "拉萨天团",
                        "unique_abs_net_amount": 50000000,
                        "unique_abs_net_ratio": 0.4,
                    }],
                },
                "rows": [{
                    "rank": 1,
                    "code": "600519",
                    "youzi_abs_net_amount": 150000000,
                    "profiled_abs_net_amount": 180000000,
                    "top_youzi_alias": "章盟主",
                    "youzi_recognition_score": 73.0,
                    "youzi_identity_tag": "shared_dominant",
                }],
            },
        }

        text = lxd.format_lhb_industry_compare_text(payload)

        self.assertIn("同申万行业龙虎榜辨识度对比", text)
        self.assertIn("对比可用性: actionable", text)
        self.assertIn("命中覆盖: 2/2 full", text)
        self.assertIn("领先差距: 600519 领先 000568 18.2分", text)
        self.assertIn("组合信号: shared_youzi_present", text)
        self.assertIn("Top游资横向: 600519 章盟主", text)
        self.assertIn("方向一致性: same_direction", text)
        self.assertIn("共同游资贡献Top: 600519 章盟主", text)
        self.assertIn("独有游资贡献Top: 000568 拉萨天团", text)
        self.assertIn("1. 600519", text)


class TestQualityMetrics(unittest.TestCase):
    def test_compute_quality_checks_pass(self):
        def rec(date, **vals):
            q = {}
            for path, v in vals.items():
                cur = q
                parts = path.split(".")
                for p in parts[:-1]:
                    cur = cur.setdefault(p, {})
                cur[parts[-1]] = {"t": v}
            return {"date": date, "q": q}

        annual = [
            rec(f"{y}-12-31", **{
                "ps.npatoshopc": 10e9, "bs.tetoshopc": 40e9,
                "ps.oi": 20e9, "ps.oc": 8e9, "ps.np": 5e9,
                "cfs.ncffoa": 6e9, "cfs.ncffia": -1e9,
                "ps.op": 7e9, "ps.ie": 0.5e9, "bs.tsc": 1e9,
            })
            for y in range(2016, 2026)
        ]
        out = lxd._compute_quality_checks("non_financial", annual, 10, 5)
        self.assertEqual(out["result"], "pass")
        self.assertTrue(out["checks"]["roe_10y_avg"]["pass_"])
        self.assertTrue(out["checks"]["fcf_5y_cumulative"]["pass_"])
        self.assertEqual(out["checks"]["share_dilution_5y"]["status"], "pass")

    def test_share_dilution_missing_when_annual_window_too_short(self):
        def rec(date, tsc):
            return {"date": date, "q": {"bs": {"tsc": {"t": tsc}}, "ps": {"np": {"t": 1}, "oi": {"t": 10}},
                    "cfs": {"ncffoa": {"t": 1}, "ncffia": {"t": 0}}}}

        annual = [rec(f"{y}-12-31", 1e9) for y in range(2021, 2026)]
        out = lxd._compute_quality_checks("non_financial", annual, 5, 5)
        self.assertEqual(out["checks"]["share_dilution_5y"]["status"], "missing")
        self.assertIn("年报不足", out["summary"].get("share_dilution_note", ""))

    def test_share_dilution_computed_with_six_annual_points(self):
        def rec(date, tsc):
            return {"date": date, "q": {"bs": {"tsc": {"t": tsc}}, "ps": {"np": {"t": 1}, "oi": {"t": 10}},
                    "cfs": {"ncffoa": {"t": 1}, "ncffia": {"t": 0}}}}

        annual = [rec(f"{y}-12-31", 1e9 if y < 2025 else 1.1e9) for y in range(2020, 2026)]
        out = lxd._compute_quality_checks("non_financial", annual, 5, 5)
        self.assertEqual(out["checks"]["share_dilution_5y"]["status"], "pass")
        self.assertAlmostEqual(out["summary"]["share_dilution_5y_pct"], 10.0, places=1)

    def test_interest_coverage_na_for_bank(self):
        annual = [{"date": "2025-12-31", "q": {"ps": {"np": {"t": 1}}, "bs": {"tsc": {"t": 1}}}}]
        out = lxd._compute_quality_checks("bank", annual, 10, 5)
        self.assertEqual(out["checks"]["interest_coverage"]["status"], "na")

    def test_datapack_source_no_mx(self):
        pack = {"sections": {"financials": {"_source": "lixinger"}}}
        self.assertEqual(lxd._datapack_source(pack, False), "lixinger")

    def test_datapack_source_with_mx(self):
        pack = {
            "sections": {
                "financials": {"_source": "lixinger"},
                "mx_quote": {"_source": "mx-data"},
                "mx_news": {"_source": "mx-search"},
            }
        }
        self.assertEqual(lxd._datapack_source(pack, True), "lixinger+mx")


def test_datapack_does_not_cache_failed_sections(monkeypatch):
    from lxr_data import LxrData

    class FakeCache:
        def __init__(self):
            self.saved = None

        def get(self, endpoint, payload, ttl_seconds):
            return (self.saved is not None), self.saved

        def set(self, endpoint, payload, value):
            self.saved = value

    class FakeClient:
        def __init__(self):
            self.config = {"data_type_ttl_seconds": {}}
            self.cache = FakeCache()

    calls = {"mx_news": 0}
    d = LxrData(client=FakeClient(), verbose=False)

    monkeypatch.setattr("lxr_data._detect_market", lambda code: "cn")
    monkeypatch.setattr("lxr_data._norm_code", lambda code, market=None: "600519")
    monkeypatch.setattr(d, "detect_fs_type", lambda code: "non_financial")
    monkeypatch.setattr(d, "get_financials", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_valuation", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_verification_inputs", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_valuation_percentiles", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_governance", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_majority_shareholders", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_revenue_constitution", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "compare_industry_valuation", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "mx_data", lambda *a, **k: {"_source": "mx-data", "raw": {"ok": True}})

    def flaky_mx_news(*args, **kwargs):
        calls["mx_news"] += 1
        if calls["mx_news"] == 1:
            raise RuntimeError("temporary timeout")
        return {"_source": "mx-search", "raw": {"ok": True}}

    monkeypatch.setattr(d, "mx_search", flaky_mx_news)

    first = d.get_research_datapack("600519", include_mx=True, ttl_seconds=3600)
    assert first["_source"] == "lixinger+partial-mx"
    assert first["sections"]["mx_news"]["_source"] == "none"
    assert d.client.cache.saved is None

    second = d.get_research_datapack("600519", include_mx=True, ttl_seconds=3600)
    assert second["_source"] == "lixinger+mx"
    assert second["sections"]["mx_news"]["_source"] == "mx-search"
    assert d.client.cache.saved is second
    assert calls["mx_news"] == 2


def test_mx_script_constructor_override_is_used_for_mx_data(tmp_path, monkeypatch):
    from lxr_data import LxrData

    script = tmp_path / "mx_data_fake.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "query = sys.argv[1]\n"
        "out_dir = pathlib.Path(sys.argv[2])\n"
        "out_dir.mkdir(parents=True, exist_ok=True)\n"
        "(out_dir / 'mx_data_fake_raw.json').write_text(json.dumps({'query': query, 'ok': True}), encoding='utf-8')\n",
        encoding="utf-8",
    )

    class FakeCache:
        dir = str(tmp_path / "cache")

        def get(self, endpoint, payload, ttl_seconds):
            return False, None

        def set(self, endpoint, payload, value):
            pass

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = FakeCache()

    d = LxrData(client=FakeClient(), mx_script=str(script), verbose=False)
    result = d.call_mx("mx-data", "贵州茅台 最新价", ttl_seconds=0)

    assert result["_source"] == "mx-data"
    assert result["raw"]["ok"] is True
    assert result["raw"]["query"] == "贵州茅台 最新价"


def test_get_lhb_uses_legacy_ashare_json(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","code":"600519","records":'
            '[{"trade_date":"2013-01-28","code":"600519","net_amount":-378891552.32}]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb("600519", limit=3, page=2)

    assert calls == [["lhb", "600519", "--limit", "3", "--page", "2", "--json"]]
    assert out["_source"] == "legacy"
    assert out["source_detail"] == "legacy:ashare_data/lhb"
    assert out["records"][0]["net_amount"] == -378891552.32


def test_get_lhb_detail_uses_legacy_ashare_json(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-detail",'
            '"trade_id":"100357777","records":[{"trade_id":"100357777",'
            '"buy_seats":[{"seat_name":"机构专用"}],"sell_seats":[]}]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_detail(trade_id="100357777")

    assert calls == [["lhb-detail", "--trade-id", "100357777", "--json"]]
    assert out["_source"] == "legacy"
    assert out["source_detail"] == "legacy:ashare_data/lhb-detail"
    assert out["records"][0]["buy_seats"][0]["seat_name"] == "机构专用"


def test_get_lhb_detail_passes_date_range_to_legacy_ashare(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-detail-range",'
            '"code":"000004","start_date":"2026-06-01","end_date":"2026-06-26",'
            '"records":[{"trade_id":"100357777"}]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_detail(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        limit=7,
    )

    assert calls == [[
        "lhb-detail", "000004", "--start-date", "2026-06-01",
        "--end-date", "2026-06-26", "--limit", "7", "--json",
    ]]
    assert out["_source"] == "legacy"
    assert out["source_detail"] == "legacy:ashare_data/lhb-detail"
    assert out["records"][0]["trade_id"] == "100357777"


def test_get_lhb_detail_passes_dominant_filters_to_legacy_ashare(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-detail-range",'
            '"dominant_type":"youzi","dominant_direction":"net_buy","records":[]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_detail(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        dominant_type="youzi",
        dominant_direction="net_buy",
    )

    assert calls == [[
        "lhb-detail", "000004", "--start-date", "2026-06-01",
        "--end-date", "2026-06-26", "--dominant-type", "youzi",
        "--dominant-direction", "net_buy", "--json",
    ]]
    assert out["_source"] == "legacy"
    assert out["dominant_type"] == "youzi"
    assert out["dominant_direction"] == "net_buy"


def test_get_lhb_detail_passes_youzi_alias_to_legacy_ashare(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-detail-range",'
            '"youzi_alias":"拉萨天团","records":[]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_detail(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        youzi_alias="拉萨天团",
    )

    assert calls == [[
        "lhb-detail", "000004", "--start-date", "2026-06-01",
        "--end-date", "2026-06-26", "--youzi-alias", "拉萨天团", "--json",
    ]]
    assert out["_source"] == "legacy"
    assert out["youzi_alias"] == "拉萨天团"


def test_get_lhb_detail_passes_min_dominant_net_to_legacy_ashare(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-detail-range",'
            '"min_dominant_net":500000,"records":[]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_detail(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        min_dominant_net=500000,
    )

    assert calls == [[
        "lhb-detail", "000004", "--start-date", "2026-06-01",
        "--end-date", "2026-06-26", "--min-dominant-net", "500000", "--json",
    ]]
    assert out["_source"] == "legacy"
    assert out["min_dominant_net"] == 500000


def test_get_lhb_compare_passes_codes_and_filters_to_legacy_ashare(monkeypatch):
    from lxr_data import LxrData

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = _FakeCache()

    d = LxrData(client=FakeClient(), verbose=False)
    calls = []

    def fake_legacy(args):
        calls.append(args)
        return (
            '{"_source":"legacy","source_detail":"eastmoney:lhb-compare",'
            '"codes":["000004","000005"],"rows":[{"code":"000005","rank":1}]}'
        )

    monkeypatch.setattr(d, "_call_legacy_tool", fake_legacy)

    out = d.get_lhb_compare(
        codes=["000004", "000005"],
        start_date="2026-06-01",
        end_date="2026-06-26",
        list_limit=30,
        page=2,
        limit=7,
        dominant_type="youzi",
        dominant_direction="net_buy",
        youzi_alias="拉萨天团",
        min_dominant_net=200000,
        min_recognition_score=50,
        sort_by="profiled_abs_net_amount",
    )

    assert calls == [[
        "lhb-compare", "000004", "000005",
        "--start-date", "2026-06-01",
        "--end-date", "2026-06-26",
        "--limit", "7",
        "--list-limit", "30",
        "--page", "2",
        "--dominant-type", "youzi",
        "--dominant-direction", "net_buy",
        "--youzi-alias", "拉萨天团",
        "--min-dominant-net", "200000",
        "--min-recognition-score", "50",
        "--sort-by", "profiled_abs_net_amount",
        "--json",
    ]]
    assert out["_source"] == "legacy"
    assert out["source_detail"] == "legacy:ashare_data/lhb-compare"
    assert out["rows"][0]["code"] == "000005"


def test_lhb_industry_compare_cli_prints_text_by_default(monkeypatch, capsys):
    payload = {
        "anchor_code": "600519",
        "industry": {"industry_name": "白酒", "industry_code": "340500", "codes": ["600519"]},
        "compare": {
            "start_date": "2026-06-01",
            "end_date": "2026-06-26",
            "comparison_summary": {
                "compare_readiness_summary": {
                    "readiness_level": "reference_only",
                    "primary_reason": "weak_leadership",
                },
                "code_coverage_summary": {
                    "matched_code_count": 1,
                    "code_count": 1,
                    "coverage_level": "full",
                },
            },
            "rows": [],
        },
    }

    class FakeLxrData:
        def __init__(self, verbose=True):
            self.verbose = verbose

        def get_lhb_industry_compare(self, *args, **kwargs):
            return payload

    monkeypatch.setattr(lxd, "LxrData", FakeLxrData)
    monkeypatch.setattr(sys, "argv", [
        "lxr_data.py",
        "lhb-industry-compare",
        "600519",
        "--start-date",
        "2026-06-01",
        "--end-date",
        "2026-06-26",
    ])

    lxd._cli()

    out = capsys.readouterr().out
    assert "同申万行业龙虎榜辨识度对比" in out
    assert "对比可用性: reference_only" in out
    assert not out.lstrip().startswith("{")


if __name__ == "__main__":
    unittest.main()
