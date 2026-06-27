#!/usr/bin/env python3
"""面向 Skill 的高级数据接口 — 统一取数入口，遵循 理杏仁 → 妙想 → 免费源 降级链。

优先级链：
    第1顺位 理杏仁 API  → 成功返回（_source = "lixinger"）
    第2顺位 妙想 mx-data → 成功返回（_source = "mx-data"）
    第3顺位 现有免费源  → 成功返回（_source = "legacy"）
    全部失败            → 返回 {"_source": "none", "error": ...}

每个取数函数返回 dict，必含 ``_source`` 字段标注实际来源，便于报告溯源与交叉验证。

阶段 2 增量：
- get_financials：通过 cn/company 的 fsTableType 自动判定财报类型（非金融/银行/保险/证券/
  其他金融），路由到对应 fs 端点；指标自动剪枝（400 错误剔除无效指标后重试），适配各类型科目差异。
- get_valuation：基本面 + 估值历史分位点（PE/PB/PS/股息率 × 上市以来/20/10/5/3/1年 × 分位点%）。
- get_verification_inputs：为 financial_rigor 自动获取股价/总股本/市值/EPS/BVPS 等验算输入。

阶段 3 增量（港股 + 新增能力）：
- 全链路市场自动路由：A股 cn/* / 港股 hk/*，代码归一化（港股补零至5位 00700，A股保留6位）。
- get_kline：前复权K线（hk/company/candlestick），替代 Yahoo Finance 供动量扫描。
- get_majority_shareholders / get_shareholders_num / get_fund_shareholders：股东分析
  （A股 majority-shareholders + shareholders-num + fund-shareholders；港股 latest-shareholders + fund-shareholders）。
- get_valuation_percentiles：PE/PB/PS/股息率 × 6时间维度 × 8统计量 全分位矩阵（分批请求合并）。

CLI：
    python tools/lxr_data.py financials 601336 --years 5 --source lixinger
    python tools/lxr_data.py valuation 600519 --source lixinger
    python tools/lxr_data.py verify-inputs 601336
    python tools/lxr_data.py kline 00700 --days 120
    python tools/lxr_data.py shareholders 600519 --kind majority
    python tools/lxr_data.py percentiles 600519
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from typing import Any, Optional

from lxr_client import LixingerAuthError, LixingerClient, LixingerError, LixingerValidationError

# ---------------------------------------------------------------------------
# 指标集
# ---------------------------------------------------------------------------

FS_TYPES = ("non_financial", "bank", "insurance", "security", "other_financial", "reit")
HK_FS_TYPES = ("non_financial", "bank", "insurance", "security", "other_financial", "reit")
CN_FS_TYPES = ("non_financial", "bank", "insurance", "security", "other_financial")

# 非金融：核心绝对值指标（expressionCalculateType = t 当期值），已验证有效。
DEFAULT_FINANCIALS_METRICS = [
    "q.ps.toi.t",            # 营业总收入
    "q.ps.oi.t",             # 营业收入
    "q.ps.oc.t",             # 营业成本
    "q.ps.np.t",             # 净利润
    "q.ps.npatoshopc.t",     # 归母净利润
    "q.ps.op.t",             # 营业利润
    "q.ps.tp.t",             # 利润总额
    "q.ps.ite.t",            # 所得税费用
    "q.ps.beps.t",           # 基本每股收益
    "q.bs.ta.t",             # 资产总计
    "q.bs.tl.t",             # 负债合计
    "q.bs.toe.t",            # 所有者权益合计
    "q.bs.tetoshopc.t",      # 归母权益
    "q.bs.mc.t",             # 市值
    "q.bs.tsc.t",            # 总股数
    "q.bs.cabb.t",           # 货币资金
    "q.bs.ar.t",             # 应收账款
    "q.bs.i.t",              # 存货
    "q.cfs.ncffoa.t",        # 经营活动现金流量净额
    "q.cfs.ncffia.t",        # 投资活动现金流量净额
    "q.cfs.ncfffa.t",        # 筹资活动现金流量净额
]

# 保险：含内含价值(EV)、新业务价值(NBV)、偿付能力、保险专属科目（>50 候选，自动剪枝保有效）。
INSURANCE_FINANCIALS_METRICS = [
    # 资产负债表
    "q.bs.ta.t", "q.bs.cabb.t", "q.bs.tl.t", "q.bs.toe.t", "q.bs.tetoshopc.t",
    "q.bs.sc.t", "q.bs.mc.t", "q.bs.tsc.t", "q.bs.icr.t", "q.bs.uepr.t",
    "q.bs.cr.t", "q.bs.lir.t", "q.bs.lthir.t", "q.bs.icl.t", "q.bs.phd.t",
    "q.bs.td.t", "q.bs.ltei.t", "q.bs.fa.t", "q.bs.ia.t", "q.bs.gw.t",
    "q.bs.dita.t", "q.bs.ar.t", "q.bs.ap.t", "q.bs.ltl.t", "q.bs.bp.t",
    # 内含价值与偿付能力
    "q.bs.ev.t", "q.bs.evolahib.t", "q.bs.evolib.t", "q.bs.evohib.t",
    "q.bs.ccap.t", "q.bs.acap.t", "q.bs.mcap.t",
    # 利润表
    "q.ps.oi.t", "q.ps.pi.t", "q.ps.ep.t", "q.ps.ivi.t", "q.ps.oe.t",
    "q.ps.ce.t", "q.ps.iiicr.t", "q.ps.baae.t", "q.ps.op.t", "q.ps.tp.t",
    "q.ps.ite.t", "q.ps.np.t", "q.ps.npatoshopc.t", "q.ps.npatmsh.t",
    "q.ps.npatshaoehopc.t", "q.ps.nbv.t", "q.ps.beps.t", "q.ps.da.t", "q.ps.deps.t",
    # 现金流量表
    "q.cfs.crfp.t", "q.cfs.ncffoa.t", "q.cfs.ncffia.t", "q.cfs.ncfffa.t",
    "q.cfs.cpfc.t", "q.cfs.crfii.t",
]

# 银行/证券/其他金融：阶段 4 补齐专属指标集；阶段 2 暂复用非金融指标，自动剪枝适配。
METRICS_BY_TYPE = {
    "non_financial": DEFAULT_FINANCIALS_METRICS,
    "insurance": INSURANCE_FINANCIALS_METRICS,
}

# 估值当前值（基本面端点，单股 ≤36 指标）
DEFAULT_VALUATION_METRICS = [
    "sp", "mc", "mc_om", "cmc", "ecmc",
    "pe_ttm", "d_pe_ttm", "pb", "pb_wo_gw", "ps_ttm", "pcf_ttm", "dyr",
]

# 估值历史分位点：[指标].[时间维度].[统计量]
# 时间维度 fs=上市以来 y20/y10/y5/y3/y1；统计量 cvpos=分位点% q2v/q5v/q8v minv/maxv avgv
DEFAULT_PERCENTILE_METRICS = [
    "pe_ttm.y10.cvpos", "pe_ttm.y5.cvpos", "pe_ttm.y3.cvpos", "pe_ttm.fs.cvpos",
    "pb.y10.cvpos", "pb.y5.cvpos", "pb.y3.cvpos", "pb.fs.cvpos",
    "ps_ttm.y10.cvpos", "ps_ttm.y5.cvpos",
    "dyr.y10.cvpos", "dyr.y5.cvpos",
    "pe_ttm.y10.q5v", "pb.y10.q5v",  # 10年中位数参考值
]

# 估值分位点全矩阵：4 指标 × 6 时间维度 × 8 统计量 = 192（单股≤36，需分批请求）
PERCENTILE_METRICS_NAME = ("pe_ttm", "pb", "ps_ttm", "dyr")
PERCENTILE_GRANULARITY = ("fs", "y20", "y10", "y5", "y3", "y1")
PERCENTILE_STATS = ("cvpos", "q2v", "q5v", "q8v", "minv", "maxv", "maxpv", "avgv")

# 验算输入：总股本/市值从 fs date=latest 取当前值；EPS/BVPS 取最近年报（见 get_verification_inputs）。

# K线复权类型
KLINE_ADJUST = {
    "none": "ex_rights",         # 不复权
    "forward": "lxr_fc_rights",  # 理杏仁前复权
    "backward": "bc_rights",     # 后复权
}


class MXError(Exception):
    """妙想 skill 调用失败。"""


class LegacyError(Exception):
    """免费源（ashare_data）调用失败。"""


def _default_mx_script() -> str:
    env = os.environ.get("MX_DATA_SCRIPT", "").strip()
    if env and os.path.isfile(env):
        return env
    return os.path.join(os.path.expanduser("~"), ".claude", "skills", "mx-data", "mx_data.py")


def _default_legacy_script() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "ashare_data.py")


def _detect_market(code: str) -> str:
    """根据代码判定市场：'hk'（港股，≤5位数字或 .HK 后缀）或 'cn'（A股，6位数字）。"""
    c = code.strip().upper()
    if c.endswith(".HK"):
        return "hk"
    digits = re.sub(r"\D", "", c)
    return "hk" if len(digits) <= 5 else "cn"


def _norm_code(code: str, market: Optional[str] = None) -> str:
    """按市场归一化代码：港股补零至5位（00700），A股保留6位（600519）。"""
    m = market or _detect_market(code)
    c = code.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "").replace(".HK", "")
    digits = re.sub(r"\D", "", c)
    if m == "hk":
        return digits.zfill(5)
    return digits


def _extract_invalid_metrics(err: LixingerValidationError) -> set:
    """从校验错误中解析无效指标码。

    只信任 message 文本中 "(a,b,c) are invalid ..." 形式的括号列表——这是权威无效集。
    不使用 details 的 value 字段：某些端点（如 fundamental）的 value 是提交的全量指标列表
    而非无效子集，直接采用会误伤全部指标。
    """
    invalid = set()
    msgs: list = []
    for m in err.details or []:
        if isinstance(m, dict):
            msgs.append(m.get("message", ""))
        elif isinstance(m, str):
            msgs.append(m)
    msgs.append(str(err))
    for msg in msgs:
        if not isinstance(msg, str):
            continue
        for group in re.findall(r"\(([^()]+)\)", msg):
            invalid.update(s.strip() for s in group.split(","))
    invalid.discard("")
    return invalid


class LxrData:
    """三级数据源统一入口。"""

    def __init__(
        self,
        client: Optional[LixingerClient] = None,
        mx_script: Optional[str] = None,
        legacy_script: Optional[str] = None,
        verbose: bool = True,
    ):
        self.client = client if client is not None else LixingerClient()
        self.mx_script = mx_script or _default_mx_script()
        self.legacy_script = legacy_script or _default_legacy_script()
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr)

    def _ttl(self, data_type: str, default: int) -> int:
        return self.client.config.get("data_type_ttl_seconds", {}).get(data_type, default)

    # ------------------------------------------------------------------
    # 财报类型判定
    # ------------------------------------------------------------------

    def detect_fs_type(self, code: str) -> str:
        """通过 {market}/company 获取股票的财报类型 fsTableType（A股/港股自动路由）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        payload = {"stockCodes": [norm], "pageIndex": 0}
        data = self.client.post(f"{market}/company", payload,
                                ttl_seconds=self._ttl("company_list", 604800))
        items = data.get("list") if isinstance(data, dict) else data
        if not items or not isinstance(items, list):
            raise LixingerError(f"{market}/company 未返回公司列表: {norm}")
        fs_type = items[0].get("fsTableType") if isinstance(items[0], dict) else None
        if not fs_type:
            raise LixingerError(f"{market}/company 未返回 fsTableType: {norm}")
        return fs_type

    # ------------------------------------------------------------------
    # 通用降级链
    # ------------------------------------------------------------------

    def _run_chain(self, tiers: list) -> dict:
        errors = []
        for source_name, fn in tiers:
            try:
                result = fn()
                if result is None:
                    raise RuntimeError(f"{source_name} 返回 None")
                if isinstance(result, dict) and "_source" not in result:
                    result["_source"] = source_name
                return result
            except Exception as e:  # noqa: BLE001
                errors.append(f"{source_name}: {type(e).__name__}: {e}")
                self._log(f"[降级] {source_name} 不可用 ({type(e).__name__}: {e})")
        self._log("[错误] 全部数据源不可用")
        return {"_source": "none", "error": " | ".join(errors)}

    # ------------------------------------------------------------------
    # fs 端点调用（含指标自动剪枝）
    # ------------------------------------------------------------------

    def _post_fs(self, endpoint: str, base_payload: dict, metrics: list, ttl: int) -> tuple:
        """调用 fs 端点；遇无效指标自动剔除重试。返回 (records, used_metrics)。"""
        current = list(metrics)
        for _ in range(4):
            payload = dict(base_payload)
            payload["metricsList"] = current
            try:
                data = self.client.post(endpoint, payload, ttl_seconds=ttl)
                return data if isinstance(data, list) else [], current
            except LixingerValidationError as e:
                invalid = _extract_invalid_metrics(e)
                if not invalid:
                    raise
                pruned = [m for m in current if m not in invalid]
                if not pruned or len(pruned) == len(current):
                    raise
                self._log(f"[剪枝] {endpoint} 剔除无效指标 {sorted(invalid)}，{len(current)}→{len(pruned)}")
                current = pruned
        raise LixingerError(f"{endpoint} 指标剪枝后仍失败")

    # ------------------------------------------------------------------
    # financials
    # ------------------------------------------------------------------

    def get_financials(
        self,
        code: str,
        years: int = 5,
        source: str = "auto",
        name: Optional[str] = None,
        report_type: Optional[str] = None,
    ) -> dict:
        tiers: list = []
        if source in ("auto", "lixinger"):
            tiers.append(("lixinger", lambda: self._get_financials_lixinger(code, years, report_type)))
        if source in ("auto", "mx"):
            tiers.append(("mx-data", lambda: self._get_financials_mx(code, years, name)))
        if source in ("auto", "legacy"):
            tiers.append(("legacy", lambda: self._get_financials_legacy(code, years)))
        if not tiers:
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain(tiers)

    def _get_financials_lixinger(self, code: str, years: int, report_type: Optional[str]) -> dict:
        market = _detect_market(code)
        norm = _norm_code(code, market)
        fs_type = report_type or self.detect_fs_type(code)
        if fs_type not in FS_TYPES:
            raise LixingerError(f"未知财报类型 {fs_type}（股票 {code}）")
        endpoint = f"{market}/company/fs/{fs_type}"
        metrics = METRICS_BY_TYPE.get(fs_type, DEFAULT_FINANCIALS_METRICS)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        base = {
            "stockCodes": [norm],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        records, used = self._post_fs(endpoint, base, metrics, self._ttl("financials", 86400))
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm,
            "market": market,
            "years": years,
            "report_type": fs_type,
            "records": records,
            "metric_count": len(used),
            "available_metrics": used,
        }

    def _get_financials_mx(self, code: str, years: int, name: Optional[str]) -> dict:
        subject = name or _norm_code(code)
        query = f"{subject} 近{years}年 净利润 营业收入 营业成本"
        raw = self._call_mx_skill(query)
        return {
            "source_detail": "mx-data:nlp",
            "code": _norm_code(code),
            "years": years,
            "query": query,
            "raw": raw,
        }

    def _get_financials_legacy(self, code: str, years: int) -> dict:
        text = self._call_legacy_tool(["financials", _norm_code(code)])
        return {
            "source_detail": "legacy:ashare_data/financials",
            "code": _norm_code(code),
            "years": years,
            "text": text,
        }

    # ------------------------------------------------------------------
    # valuation + 分位点
    # ------------------------------------------------------------------

    def get_valuation(
        self,
        code: str,
        source: str = "auto",
        name: Optional[str] = None,
        report_type: Optional[str] = None,
    ) -> dict:
        tiers: list = []
        if source in ("auto", "lixinger"):
            tiers.append(("lixinger", lambda: self._get_valuation_lixinger(code, report_type)))
        if source in ("auto", "mx"):
            tiers.append(("mx-data", lambda: self._get_valuation_mx(code, name)))
        if source in ("auto", "legacy"):
            tiers.append(("legacy", lambda: self._get_valuation_legacy(code)))
        if not tiers:
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain(tiers)

    def _get_valuation_lixinger(self, code: str, report_type: Optional[str]) -> dict:
        market = _detect_market(code)
        norm = _norm_code(code, market)
        fs_type = report_type or self.detect_fs_type(code)
        endpoint = f"{market}/company/fundamental/{fs_type}"
        metrics = DEFAULT_VALUATION_METRICS + DEFAULT_PERCENTILE_METRICS
        end = _dt.date.today()
        start = end - _dt.timedelta(days=14)
        base = {
            "stockCodes": [norm],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        payload = dict(base)
        ttl = self._ttl("valuation", 3600)
        current = list(metrics)
        data = None
        for _ in range(5):
            payload["metricsList"] = current
            try:
                data = self.client.post(endpoint, payload, ttl_seconds=ttl)
                break
            except LixingerValidationError as e:
                invalid = _extract_invalid_metrics(e)
                if not invalid:
                    raise
                pruned = [m for m in current if m not in invalid]
                if not pruned or len(pruned) == len(current):
                    raise
                self._log(f"[剪枝] {endpoint} 剔除无效指标 {sorted(invalid)}，{len(current)}→{len(pruned)}")
                current = pruned
        if data is None:
            raise LixingerError(f"{endpoint} 估值指标剪枝后仍失败")
        records = data if isinstance(data, list) else []
        latest = records[-1] if records else {}
        flat = self._flatten_latest(latest)
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm,
            "market": market,
            "report_type": fs_type,
            "latest": flat,
            "record_count": len(records),
            "raw_latest": latest,
        }

    @staticmethod
    def _flatten_latest(rec: dict) -> dict:
        """把最新记录的嵌套指标拍平为 {metric_path: value}。"""
        out = {}
        if not isinstance(rec, dict):
            return out
        for k, v in rec.items():
            if k in ("date", "stockCode", "currency"):
                out[k] = v
                continue
            if isinstance(v, dict):
                LxrData._flatten_into(v, k, out)
            else:
                out[k] = v
        return out

    @staticmethod
    def _flatten_into(node, prefix, out):
        if isinstance(node, dict):
            for k, v in node.items():
                LxrData._flatten_into(v, f"{prefix}.{k}", out)
        else:
            out[prefix] = node

    def _get_valuation_mx(self, code: str, name: Optional[str]) -> dict:
        subject = name or _norm_code(code)
        raw = self._call_mx_skill(f"{subject} 最新价 市盈率 市净率 总市值 股息率")
        return {"source_detail": "mx-data:nlp", "code": _norm_code(code), "raw": raw}

    def _get_valuation_legacy(self, code: str) -> dict:
        text = self._call_legacy_tool(["valuation", _norm_code(code)])
        return {"source_detail": "legacy:ashare_data/valuation", "code": _norm_code(code), "text": text}

    # ------------------------------------------------------------------
    # 验算输入（供 financial_rigor --source lixinger）
    # ------------------------------------------------------------------

    def get_verification_inputs(self, code: str, report_type: Optional[str] = None) -> dict:
        """获取市值/估值验算输入：股价、总股本、报告市值、年化EPS、每股净资产、股息率、PE/PB。

        - 股价/市值/PE_TTM/PB/股息率来自基本面端点（当前值）。
        - 总股本来自 fs 端点 date=latest（当前股本）。
        - EPS/BVPS 取最近**年报**（当期值即全年），用于 PE=股价/年化EPS、ROE=EPS/BVPS 验算。
        """
        fs_type = report_type or self.detect_fs_type(code)
        market = _detect_market(code)
        norm = _norm_code(code, market)
        val = self._get_valuation_lixinger(code, fs_type)
        latest_val = val.get("latest", {})
        # 一次 fs 调用：近2年记录，含当前总股本 + 年报 EPS/每股净资产
        fs_endpoint = f"{market}/company/fs/{fs_type}"
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * 2 + 10)
        fs_base = {
            "stockCodes": [norm],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        fs_metrics = ["q.bs.tsc.t", "q.ps.beps.t", "q.bs.tetoshopc_ps.t"]
        fs_records, _used = self._post_fs(fs_endpoint, fs_base, fs_metrics, self._ttl("financials", 86400))
        if fs_records:
            latest_record = fs_records[-1]
            tsc = self._dig(latest_record.get("q", {}), "bs.tsc.t")
        else:
            tsc = None
        annual = [r for r in fs_records if str(r.get("date", ""))[:10].endswith("-12-31")]
        annual.sort(key=lambda r: r.get("date", ""), reverse=True)
        annual_beps = None
        annual_bvps = None
        if annual:
            q = annual[0].get("q", {}) if isinstance(annual[0], dict) else {}
            annual_beps = self._dig(q, "ps.beps.t")
            annual_bvps = self._dig(q, "bs.tetoshopc_ps.t")

        sp = latest_val.get("sp")
        mc = latest_val.get("mc")
        currency = "HKD" if market == "hk" else "CNY"
        return {
            "code": norm,
            "market": market,
            "report_type": fs_type,
            "price": sp,
            "shares": tsc,
            "reported_market_cap": mc,
            "eps": annual_beps,
            "bvps": annual_bvps,
            "pe_ttm": latest_val.get("pe_ttm"),
            "pb": latest_val.get("pb"),
            "ps_ttm": latest_val.get("ps_ttm"),
            "dividend_yield": latest_val.get("dyr"),
            "currency": currency,
            "valuation_percentiles": {
                k: v for k, v in latest_val.items() if ".cvpos" in k
            },
            "_source": "lixinger",
        }

    @staticmethod
    def _dig(node, path):
        cur = node
        for seg in path.split("."):
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            else:
                return None
        return cur

    # ------------------------------------------------------------------
    # K线数据（P3.2，替代 Yahoo Finance 用于动量扫描）
    # ------------------------------------------------------------------

    def get_kline(self, code: str, days: int = 120, adjust: str = "forward") -> dict:
        """获取前复权K线。返回 {code, market, records:[{date,open,close,high,low,volume,amount,change,to_r}]}。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=days)
        payload = {
            "stockCode": norm,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "type": KLINE_ADJUST.get(adjust, KLINE_ADJUST["forward"]),
        }
        data = self.client.post(f"{market}/company/candlestick", payload,
                                ttl_seconds=self._ttl("kline", 1800))
        records = data if isinstance(data, list) else []
        return {
            "source_detail": f"lixinger:{market}/company/candlestick",
            "code": norm,
            "market": market,
            "adjust": adjust,
            "records": records,
            "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 股东分析（P3.4）
    # ------------------------------------------------------------------

    def get_majority_shareholders(self, code: str, years: int = 3) -> dict:
        """前十大股东（A股用 cn/company/majority-shareholders；港股用 hk/company/latest-shareholders）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        if market == "hk":
            endpoint = "hk/company/latest-shareholders"
        else:
            endpoint = "cn/company/majority-shareholders"
        payload = {
            "stockCode": norm,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("shareholders", 86400))
        records = data if isinstance(data, list) else []
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm, "market": market, "records": records, "_source": "lixinger",
        }

    def get_shareholders_num(self, code: str, years: int = 5) -> dict:
        """股东人数与变化率（仅A股；港股无此端点，返回 not_available 标记）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        if market == "hk":
            return {"source_detail": "lixinger:not_available",
                    "code": norm, "market": "hk",
                    "records": [], "note": "港股无股东人数端点", "_source": "none"}
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCode": norm,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        data = self.client.post("cn/company/shareholders-num", payload,
                                ttl_seconds=self._ttl("shareholders", 86400))
        records = data if isinstance(data, list) else []
        return {
            "source_detail": "lixinger:cn/company/shareholders-num",
            "code": norm, "market": "cn", "records": records, "_source": "lixinger",
        }

    def get_fund_shareholders(self, code: str, years: int = 3) -> dict:
        """公募/内资基金持股（A股 cn/company/fund-shareholders；港股 hk/company/fund-shareholders）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCode": norm,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        endpoint = f"{market}/company/fund-shareholders"
        data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("shareholders", 86400))
        records = data if isinstance(data, list) else []
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm, "market": market, "records": records, "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 估值分位点全矩阵（P3.5）：4指标 × 6时间维度 × 8统计量
    # ------------------------------------------------------------------

    def get_valuation_percentiles(self, code: str, report_type: Optional[str] = None) -> dict:
        """请求 PE/PB/PS/股息率 的 6×8 全分位矩阵（单股≤36指标，分批请求并合并）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        fs_type = report_type or self.detect_fs_type(code)
        endpoint = f"{market}/company/fundamental/{fs_type}"
        all_metrics = [
            f"{name}.{g}.{s}"
            for name in PERCENTILE_METRICS_NAME
            for g in PERCENTILE_GRANULARITY
            for s in PERCENTILE_STATS
        ]
        end = _dt.date.today()
        start = end - _dt.timedelta(days=14)
        base = {
            "stockCodes": [norm],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        merged = {}
        used = []
        # 单股≤36，按30分批；每批遇无效指标循环剪枝，彻底失败的批次跳过（分位点为尽力而为）
        for i in range(0, len(all_metrics), 30):
            chunk = all_metrics[i:i + 30]
            payload = dict(base)
            payload["metricsList"] = chunk
            data = None
            for _ in range(4):
                try:
                    data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("valuation", 3600))
                    break
                except LixingerValidationError as e:
                    invalid = _extract_invalid_metrics(e)
                    if not invalid:
                        break
                    pruned = [m for m in chunk if m not in invalid]
                    if not pruned or len(pruned) == len(chunk):
                        chunk = pruned
                        break
                    chunk = pruned
                    payload["metricsList"] = chunk
            if data is None:
                self._log(f"[分位点] 批次 {i} 全部失败，跳过")
                continue
            records = data if isinstance(data, list) else []
            if records:
                flat = self._flatten_latest(records[-1])
                merged.update(flat)
                used.extend(chunk)
        # 结构化为 {metric: {granularity: {stat: value}}}
        matrix = {}
        for name in PERCENTILE_METRICS_NAME:
            matrix[name] = {}
            for g in PERCENTILE_GRANULARITY:
                matrix[name][g] = {}
                for s in PERCENTILE_STATS:
                    key = f"{name}.{g}.{s}"
                    if key in merged:
                        matrix[name][g][s] = merged[key]
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm, "market": market, "report_type": fs_type,
            "matrix": matrix, "metric_count": len(used), "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 子进程调用妙想 mx-data
    # ------------------------------------------------------------------

    def _call_mx_skill(self, query: str) -> dict:
        if not os.path.isfile(self.mx_script):
            raise MXError(f"mx_data 脚本不存在: {self.mx_script}")
        out_dir = os.path.join(self.client.cache.dir, "mx_out")
        os.makedirs(out_dir, exist_ok=True)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, self.mx_script, query, out_dir],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=120,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
            raise MXError("mx_data 退出码 %d: %s" % (proc.returncode, " | ".join(tail)))
        raw_path = _latest_raw_json(out_dir)
        if not raw_path:
            raise MXError("mx_data 成功但未生成 raw.json")
        with open(raw_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # 子进程调用免费源 ashare_data
    # ------------------------------------------------------------------

    def _call_legacy_tool(self, args: list) -> str:
        if not os.path.isfile(self.legacy_script):
            raise LegacyError(f"ashare_data 脚本不存在: {self.legacy_script}")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [sys.executable, self.legacy_script, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=60,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
            raise LegacyError("ashare_data 退出码 %d: %s" % (proc.returncode, " | ".join(tail)))
        return proc.stdout


def _latest_raw_json(dir_path: str) -> Optional[str]:
    latest = None
    latest_mtime = -1.0
    for name in os.listdir(dir_path):
        if name.endswith("_raw.json"):
            path = os.path.join(dir_path, name)
            try:
                m = os.path.getmtime(path)
            except OSError:
                continue
            if m > latest_mtime:
                latest_mtime = m
                latest = path
    return latest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(
        description="理杏仁高级数据接口（理杏仁 → 妙想 → 免费源 降级链）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_fin = sub.add_parser("financials", help="近N年财务数据（自动判定财报类型）")
    p_fin.add_argument("code", help="股票代码，如 600519 / 601336")
    p_fin.add_argument("--years", type=int, default=5)
    p_fin.add_argument("--source", choices=["auto", "lixinger", "mx", "legacy"], default="auto")
    p_fin.add_argument("--name", default=None, help="公司中文名（提升妙想命中率）")
    p_fin.add_argument("--report-type", default=None,
                       choices=list(FS_TYPES), help="手动指定财报类型，默认自动判定")
    p_fin.add_argument("--quiet", action="store_true")

    p_val = sub.add_parser("valuation", help="估值指标 + 历史分位点")
    p_val.add_argument("code", help="股票代码")
    p_val.add_argument("--source", choices=["auto", "lixinger", "mx", "legacy"], default="auto")
    p_val.add_argument("--name", default=None)
    p_val.add_argument("--report-type", default=None, choices=list(FS_TYPES))
    p_val.add_argument("--quiet", action="store_true")

    p_vi = sub.add_parser("verify-inputs", help="获取市值/估值验算输入（供 financial_rigor）")
    p_vi.add_argument("code", help="股票代码")
    p_vi.add_argument("--report-type", default=None, choices=list(FS_TYPES))
    p_vi.add_argument("--quiet", action="store_true")

    p_kl = sub.add_parser("kline", help="K线数据（前复权，替代 Yahoo Finance）")
    p_kl.add_argument("code", help="股票代码，如 00700 / 600519")
    p_kl.add_argument("--days", type=int, default=120)
    p_kl.add_argument("--adjust", choices=list(KLINE_ADJUST.keys()), default="forward")
    p_kl.add_argument("--quiet", action="store_true")

    p_sh = sub.add_parser("shareholders", help="股东分析（前十大/股东人数/基金持股）")
    p_sh.add_argument("code", help="股票代码")
    p_sh.add_argument("--kind", choices=["majority", "num", "fund"], default="majority")
    p_sh.add_argument("--years", type=int, default=3)
    p_sh.add_argument("--quiet", action="store_true")

    p_pc = sub.add_parser("percentiles", help="估值分位点全矩阵（4指标×6维度×8统计量）")
    p_pc.add_argument("code", help="股票代码")
    p_pc.add_argument("--report-type", default=None, choices=list(FS_TYPES))
    p_pc.add_argument("--quiet", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "financials":
        data = LxrData(verbose=not args.quiet).get_financials(
            args.code, years=args.years, source=args.source,
            name=args.name, report_type=args.report_type,
        )
    elif args.command == "valuation":
        data = LxrData(verbose=not args.quiet).get_valuation(
            args.code, source=args.source, name=args.name, report_type=args.report_type,
        )
    elif args.command == "verify-inputs":
        data = LxrData(verbose=not args.quiet).get_verification_inputs(
            args.code, report_type=args.report_type,
        )
    elif args.command == "kline":
        data = LxrData(verbose=not args.quiet).get_kline(
            args.code, days=args.days, adjust=args.adjust,
        )
    elif args.command == "shareholders":
        d = LxrData(verbose=not args.quiet)
        if args.kind == "majority":
            data = d.get_majority_shareholders(args.code, years=args.years)
        elif args.kind == "num":
            data = d.get_shareholders_num(args.code, years=args.years)
        else:
            data = d.get_fund_shareholders(args.code, years=args.years)
    elif args.command == "percentiles":
        data = LxrData(verbose=not args.quiet).get_valuation_percentiles(
            args.code, report_type=args.report_type,
        )
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
