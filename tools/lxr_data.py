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

CLI：
    python tools/lxr_data.py financials 601336 --years 5 --source lixinger
    python tools/lxr_data.py valuation 600519 --source lixinger
    python tools/lxr_data.py verify-inputs 601336
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

FS_TYPES = ("non_financial", "bank", "insurance", "security", "other_financial")

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

# 验算输入：总股本/市值从 fs date=latest 取当前值；EPS/BVPS 取最近年报（见 get_verification_inputs）。


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


def _norm_code(code: str) -> str:
    return code.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")


def _extract_invalid_metrics(err: LixingerValidationError) -> set:
    """从校验错误中解析无效指标码。"""
    invalid = set()
    for m in err.details:
        if isinstance(m, dict):
            val = m.get("value")
            if isinstance(val, list):
                invalid.update(str(v) for v in val)
            msg = m.get("message", "")
            if isinstance(msg, str):
                invalid.update(re.findall(r"\(([^()]+)\)", msg))
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
        """通过 cn/company 获取股票的财报类型 fsTableType。"""
        payload = {"stockCodes": [_norm_code(code)], "pageIndex": 0}
        data = self.client.post("cn/company", payload, ttl_seconds=self._ttl("company_list", 604800))
        items = data.get("list") if isinstance(data, dict) else data
        if not items or not isinstance(items, list):
            raise LixingerError(f"cn/company 未返回公司列表: {code}")
        fs_type = items[0].get("fsTableType") if isinstance(items[0], dict) else None
        if not fs_type:
            raise LixingerError(f"cn/company 未返回 fsTableType: {code}")
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
        fs_type = report_type or self.detect_fs_type(code)
        if fs_type not in FS_TYPES:
            raise LixingerError(f"未知财报类型 {fs_type}（股票 {code}）")
        endpoint = f"cn/company/fs/{fs_type}"
        metrics = METRICS_BY_TYPE.get(fs_type, DEFAULT_FINANCIALS_METRICS)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        base = {
            "stockCodes": [_norm_code(code)],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        records, used = self._post_fs(endpoint, base, metrics, self._ttl("financials", 86400))
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": _norm_code(code),
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
        fs_type = report_type or self.detect_fs_type(code)
        endpoint = f"cn/company/fundamental/{fs_type}"
        metrics = DEFAULT_VALUATION_METRICS + DEFAULT_PERCENTILE_METRICS
        end = _dt.date.today()
        start = end - _dt.timedelta(days=14)
        base = {
            "stockCodes": [_norm_code(code)],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        payload = dict(base)
        payload["metricsList"] = metrics
        ttl = self._ttl("valuation", 3600)
        try:
            data = self.client.post(endpoint, payload, ttl_seconds=ttl)
        except LixingerValidationError as e:
            # 分位点指标在某些类型可能不支持，剔除后重试
            invalid = _extract_invalid_metrics(e)
            if not invalid:
                raise
            metrics = [m for m in metrics if m not in invalid]
            payload["metricsList"] = metrics
            data = self.client.post(endpoint, payload, ttl_seconds=ttl)
        records = data if isinstance(data, list) else []
        latest = records[-1] if records else {}
        flat = self._flatten_latest(latest)
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": _norm_code(code),
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
        val = self._get_valuation_lixinger(code, fs_type)
        latest_val = val.get("latest", {})
        # 一次 fs 调用：近2年记录，含当前总股本 + 年报 EPS/每股净资产
        fs_endpoint = f"cn/company/fs/{fs_type}"
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * 2 + 10)
        fs_base = {
            "stockCodes": [_norm_code(code)],
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
        return {
            "code": _norm_code(code),
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
            "currency": "CNY",
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
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
