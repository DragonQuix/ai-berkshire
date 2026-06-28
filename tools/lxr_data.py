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

阶段 4 增量（保险/银行/证券深度 + 营收构成 + 公司治理）：
- get_industry_deep：保险(EV/NBV/偿付能力/营运利润/保险业务收支)、银行(资本充足率/净息差/不良/拨备)、
  证券(经纪/投行/资管/自营)专属深度报表，自动判定类型 + 指标自动剪枝，附 deep_summary 关键字段近3年值。
- get_revenue_constitution：分产品/分地区营收构成（dataList 收入/占比/毛利率 + 境内/境外）。
- get_governance：高管增减持 + 大股东增减持（A股）；港股董事权益变动。

阶段 5 增量（宏观 + 指数估值 + 行业对比）：
- get_macro_national_debt / get_macro_interest_rates / get_bond_yield_10y：国债收益率（10年期）+ LPR/Shibor/MLF 利率，利差分析输入。
- get_index_valuation：沪深300/恒生指数等 PE/PB/PS/股息率 当前值 + 10年分位点 + 收盘点位。
- get_industry_of_stock / get_industry_valuation / compare_industry_valuation：申万二级行业归属 + 行业估值 + 公司vs行业估值对比表。

CLI：
    python tools/lxr_data.py financials 601336 --years 5 --source lixinger
    python tools/lxr_data.py valuation 600519 --source lixinger
    python tools/lxr_data.py verify-inputs 601336
    python tools/lxr_data.py kline 00700 --days 120
    python tools/lxr_data.py shareholders 600519 --kind majority
    python tools/lxr_data.py percentiles 600519
    python tools/lxr_data.py industry-deep 601336 --years 5
    python tools/lxr_data.py revenue 600519 --years 3
    python tools/lxr_data.py governance 601336 --years 2
    python tools/lxr_data.py macro-debt --area cn
    python tools/lxr_data.py macro-rates --area cn
    python tools/lxr_data.py index-val 000300 --market cn
    python tools/lxr_data.py industry-compare 600519
    python tools/lxr_data.py datapack 601336 --years 5
    python tools/lxr_data.py quality-metrics 600519 --years 10
    python tools/lxr_data.py lhb 600519 --limit 5
    python tools/lxr_data.py lhb-detail --trade-id 100357777
    python tools/lxr_data.py lhb-compare 000004 000005 --start-date 2026-06-01 --end-date 2026-06-26
    python tools/lxr_data.py mx-search "新华保险最新公告"
    python tools/lxr_data.py mx-xuangu "ROE大于15%的A股，返回前10只"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import tempfile
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
    "q.ps.ie.t",             # 利息费用（利息覆盖倍数）
    "q.ps.fe.t",             # 财务费用（利息费用缺失时备用）
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

_SKIP_INTEREST_COVERAGE = frozenset({"bank", "insurance", "security", "other_financial"})


def _annual_fs_records(records: list) -> list:
    annual = [r for r in records if str(r.get("date", ""))[:10].endswith("-12-31")]
    annual.sort(key=lambda r: r.get("date", ""))
    return annual


def _dig_q(node, path: str):
    cur = node
    for seg in path.split("."):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return None
    return cur


def _fs_metric(record: dict, path: str):
    q = record.get("q", {}) if isinstance(record, dict) else {}
    p = path[2:] if path.startswith("q.") else path
    return _dig_q(q, p)


def _safe_ratio(num, den):
    if num is None or den is None:
        return None
    try:
        d = float(den)
        if d == 0:
            return None
        return float(num) / d
    except (TypeError, ValueError):
        return None


def _datapack_source(pack: dict, include_mx: bool) -> str:
    if not include_mx:
        return "lixinger"
    sections = pack.get("sections", {})
    mx_keys = [k for k in ("mx_quote", "mx_news") if k in sections]
    if not mx_keys:
        return "lixinger"
    ok_flags = []
    for key in mx_keys:
        sec = sections[key]
        if not isinstance(sec, dict):
            ok_flags.append(False)
            continue
        src = sec.get("_source", "none")
        ok_flags.append(src not in (None, "", "none") and not sec.get("error"))
    if all(ok_flags):
        return "lixinger+mx"
    if not any(ok_flags):
        return "lixinger"
    return "lixinger+partial-mx"


def _compute_quality_checks(report_type: str, annual: list, roe_years: int, fcf_years: int) -> dict:
    """从年报序列计算 /quality-screen 7 条硬指标及通过/失败判定。"""
    if not annual:
        return {"error": "无年报数据", "checks": {}}

    roe_slice = annual[-roe_years:]
    roe_vals = [
        _safe_ratio(_fs_metric(r, "ps.npatoshopc.t"), _fs_metric(r, "bs.tetoshopc.t"))
        for r in roe_slice
    ]
    roe_vals = [v for v in roe_vals if v is not None]
    roe_avg = sum(roe_vals) / len(roe_vals) if roe_vals else None

    fcf_slice = annual[-fcf_years:]
    fcf_annual = []
    for r in fcf_slice:
        ocf = _fs_metric(r, "cfs.ncffoa.t")
        icf = _fs_metric(r, "cfs.ncffia.t")
        if ocf is None:
            continue
        icf_val = float(icf) if icf is not None else 0.0
        fcf_annual.append(float(ocf) + icf_val)
    fcf_5y_sum = sum(fcf_annual) if fcf_annual else None

    latest = annual[-1]
    op = _fs_metric(latest, "ps.op.t")
    ie = _fs_metric(latest, "ps.ie.t")
    if ie is None or float(ie) == 0:
        fe = _fs_metric(latest, "ps.fe.t")
        ie = abs(float(fe)) if fe is not None and float(fe) != 0 else ie
    skip_interest = report_type in _SKIP_INTEREST_COVERAGE
    interest_cov = None if skip_interest else _safe_ratio(op, abs(float(ie)) if ie is not None else None)

    gm_vals = []
    for r in annual[-10:]:
        oi = _fs_metric(r, "ps.oi.t")
        oc = _fs_metric(r, "ps.oc.t")
        if oi is not None and oc is not None and float(oi) != 0:
            gm_vals.append((float(oi) - float(oc)) / float(oi))
    gm_avg = sum(gm_vals) / len(gm_vals) if gm_vals else None

    ocf_ni_vals = [
        _safe_ratio(_fs_metric(r, "cfs.ncffoa.t"), _fs_metric(r, "ps.np.t"))
        for r in annual[-5:]
    ]
    ocf_ni_vals = [v for v in ocf_ni_vals if v is not None]
    ocf_ni_avg = sum(ocf_ni_vals) / len(ocf_ni_vals) if ocf_ni_vals else None

    nm_vals = [
        _safe_ratio(_fs_metric(r, "ps.np.t"), _fs_metric(r, "ps.oi.t"))
        for r in annual[-10:]
    ]
    nm_vals = [v for v in nm_vals if v is not None]
    nm_avg = sum(nm_vals) / len(nm_vals) if nm_vals else None

    dilution_pct = None
    dilution_note = None
    if len(annual) >= fcf_years + 1:
        tsc_old = _fs_metric(annual[-(fcf_years + 1)], "bs.tsc.t")
        tsc_new = _fs_metric(annual[-1], "bs.tsc.t")
        if tsc_old is not None and tsc_new is not None and float(tsc_old) != 0:
            dilution_pct = (float(tsc_new) - float(tsc_old)) / float(tsc_old) * 100.0
        elif tsc_old is None or tsc_new is None:
            dilution_note = "q.bs.tsc.t 在理杏仁 fs 年报中缺失"
    else:
        dilution_note = f"年报不足 {fcf_years + 1} 期，无法计算 {fcf_years} 年股本膨胀"

    def _chk(name, value, threshold, op="gte", na=False):
        row = {"metric": name, "value": value, "threshold": threshold}
        if na:
            row.update(status="na", pass_=None, note="银行/保险/证券不适用")
            return row
        if value is None:
            row.update(status="missing", pass_=None, note="数据不足")
            return row
        if op == "gte":
            passed = value >= threshold
        elif op == "lte":
            passed = value <= threshold
        else:
            passed = value > threshold
        row.update(status="pass" if passed else "fail", pass_=passed)
        return row

    checks = {
        "roe_10y_avg": _chk("①10年平均ROE", roe_avg, 0.08),
        "fcf_5y_cumulative": _chk("②5年累计FCF", fcf_5y_sum, 0, op="gt"),
        "interest_coverage": _chk("③利息覆盖", interest_cov, 2.0, na=skip_interest),
        "gross_margin_avg": _chk("④长期毛利率", gm_avg, 0.15),
        "ocf_ni_5y_avg": _chk("⑤OCF/NI 5年均值", ocf_ni_avg, 0.7),
        "net_margin_avg": _chk("⑥长期净利率", nm_avg, 0.05),
        "share_dilution_5y": _chk("⑦5年股本膨胀", dilution_pct, 20.0, op="lte"),
    }
    fail_count = sum(1 for c in checks.values() if c.get("pass_") is False)
    missing = sum(1 for c in checks.values() if c.get("status") == "missing")
    return {
        "summary": {
            "roe_10y_avg": roe_avg,
            "fcf_5y_cumulative": fcf_5y_sum,
            "interest_coverage": interest_cov,
            "gross_margin_avg": gm_avg,
            "ocf_ni_5y_avg": ocf_ni_avg,
            "net_margin_avg": nm_avg,
            "share_dilution_5y_pct": dilution_pct,
            "share_dilution_note": dilution_note,
            "annual_years_used": len(annual),
            "fcf_method": "sum(ncffoa + ncffia) 近5年年报；ncffia 为投资活动现金流净额",
        },
        "checks": checks,
        "result": "fail" if fail_count else ("incomplete" if missing else "pass"),
        "fail_count": fail_count,
        "missing_count": missing,
    }

# ---------------------------------------------------------------------------
# 阶段4：行业深度指标集（保险/银行/证券专属，单股≤128，自动剪枝保有效）
# ---------------------------------------------------------------------------

# 保险深度：内含价值(EV)/新业务价值(NBV)/偿付能力/营运利润/保险业务收支 + 完整报表覆盖（>100候选，自动剪枝）
INSURANCE_DEEP_METRICS = [
    # —— 资产负债表 ——
    "q.bs.ta.t", "q.bs.cabb.t", "q.bs.pr.t", "q.bs.ar.t", "q.bs.ir.t",
    "q.bs.rir.t", "q.bs.dfa.t", "q.bs.ica.t", "q.bs.rica.t", "q.bs.phpl.t",
    "q.bs.ltar.t", "q.bs.laatc.t", "q.bs.td.t", "q.bs.t_fi.t", "q.bs.fiaac.t",
    "q.bs.fiafvtpol.t", "q.bs.afsfa.t", "q.bs.ltei.t", "q.bs.sd.t", "q.bs.rei.t",
    "q.bs.fa.t", "q.bs.ia.t", "q.bs.gw.t", "q.bs.roua.t", "q.bs.dita.t", "q.bs.oa.t",
    # —— 负债 ——
    "q.bs.tl.t", "q.bs.tl_ta_r.t", "q.bs.stl.t", "q.bs.dfl.t", "q.bs.fasurpa.t",
    "q.bs.cd.t", "q.bs.icl.t", "q.bs.ricl.t", "q.bs.ap.t", "q.bs.pria.t",
    "q.bs.facp.t", "q.bs.sawp.t", "q.bs.tp.t", "q.bs.cp.t", "q.bs.phdp.t",
    "q.bs.phd.t", "q.bs.icr.t", "q.bs.uepr.t", "q.bs.cr.t", "q.bs.lir.t",
    "q.bs.lthir.t", "q.bs.ltl.t", "q.bs.bp.t", "q.bs.ditl.t", "q.bs.ol.t",
    # —— 所有者权益 ——
    "q.bs.toe.t", "q.bs.sc.t", "q.bs.capr.t", "q.bs.oci.t", "q.bs.surr.t",
    "q.bs.pogr.t", "q.bs.rtp.t", "q.bs.tetshaoehopc.t", "q.bs.tetoshopc.t",
    "q.bs.tetoshopc_ps.t", "q.bs.etmsh.t",
    # —— 内含价值与偿付能力 ——
    "q.bs.ev.t", "q.bs.evolahib.t", "q.bs.evolib.t", "q.bs.evohib.t",
    "q.bs.ccap.t", "q.bs.acap.t", "q.bs.mcap.t", "q.bs.coresr.t", "q.bs.compsr.t",
    # —— 利润表（保险业务收支 + 利润）——
    "q.ps.oi.t", "q.ps.pi.t", "q.ps.ripi.t", "q.ps.pctri.t", "q.ps.ciupr.t",
    "q.ps.ep.t", "q.ps.ir.t", "q.ps.niifb.t", "q.ps.nnifaci.t", "q.ps.ivi.t",
    "q.ps.ciofv.t", "q.ps.ei.t", "q.ps.adi.t", "q.ps.oic.t", "q.ps.ooi.t",
    "q.ps.oe.t", "q.ps.s.t", "q.ps.ce.t", "q.ps.iiicr.t", "q.ps.phdrfpip.t",
    "q.ps.rie.t", "q.ps.faceoio.t", "q.ps.ise.t", "q.ps.baae.t", "q.ps.tas.t",
    "q.ps.op.t", "q.ps.tp.t", "q.ps.ite.t", "q.ps.np.t", "q.ps.npatshaoehopc.t",
    "q.ps.npatoshopc.t", "q.ps.npatmsh.t", "q.ps.opatshopc.t", "q.ps.nbv.t",
    "q.ps.wroe.t", "q.ps.beps.t", "q.ps.deps.t", "q.ps.da.t", "q.ps.d_np_r.t",
    # —— 现金流量表关键项 ——
    "q.cfs.crfp.t", "q.cfs.cpfc.t", "q.cfs.ncffoa.t", "q.cfs.ncffia.t",
    "q.cfs.ncfffa.t", "q.cfs.stciffoa.t", "q.cfs.stcoffoa.t",
    # —— 估值与股本 ——
    "q.bs.mc.t", "q.bs.tsc.t", "q.bs.csc.t", "q.bs.pe_ttm.t", "q.bs.pb.t",
    "q.bs.ps_ttm.t", "q.bs.dyr.t",
    # —— 区域收入 ——
    "q.ps.d_oi.t", "q.ps.d_oi_r.t", "q.ps.o_oi.t", "q.ps.o_oi_r.t",
]

# 银行深度：资本充足率/净息差/不良/拨备/存贷
BANK_DEEP_METRICS = [
    "q.bs.car.t", "q.bs.ct1car.t", "q.bs.t1car.t",     # 资本充足率/核心一级/一级
    "q.bs.nis.t", "q.bs.nim.t",                          # 净利差/净息差
    "q.bs.npl.t", "q.bs.llr_npl_r.t",                    # 不良贷款余额/拨备覆盖率
    "q.bs.cd.t", "q.bs.laatc.t",                         # 客户存款/发放贷款及垫款
    "q.bs.ta.t", "q.bs.tl.t", "q.bs.toe.t", "q.bs.tetoshopc.t",
    "q.ps.oi.t", "q.ps.nii.t", "q.ps.nfaci.t",          # 营业收入/净利息收入/手续费净收入
    "q.ps.ii.t", "q.ps.ie.t",                            # 利息收入/支出
    "q.ps.np.t", "q.ps.npatoshopc.t", "q.ps.beps.t", "q.ps.wroe.t",
    "q.bs.tsc.t", "q.bs.mc.t", "q.bs.pb.t", "q.bs.pe_ttm.t",
]

# 证券深度：经纪/投行/资管/自营/投资收益
SECURITY_DEEP_METRICS = [
    "q.ps.oi.t", "q.ps.nii.t", "q.ps.nfaci.t",          # 营业收入/净利息/手续费净收入
    "q.ps.nfifb.t", "q.ps.nfifib.t", "q.ps.nfifam.t",   # 经纪/投行/资管业务净收入
    "q.ps.ivi.t", "q.ps.ciofv.t",                        # 投资收益/公允价值变动
    "q.ps.np.t", "q.ps.npatoshopc.t", "q.ps.beps.t", "q.ps.wroe.t",
    "q.bs.ta.t", "q.bs.toe.t", "q.bs.tetoshopc.t", "q.bs.tsc.t", "q.bs.mc.t",
    "q.bs.pb.t", "q.bs.pe_ttm.t",
    "q.bs.pc_pesaid_nc_r.t", "q.bs.pc_pnesaid_nc_r.t",  # 自营权益/非权益类占净资本
]

DEEP_METRICS_BY_TYPE = {
    "insurance": INSURANCE_DEEP_METRICS,
    "bank": BANK_DEEP_METRICS,
    "security": SECURITY_DEEP_METRICS,
}

# 保险深度关键字段（用于准出摘要：EV/NBV/偿付能力）
INSURANCE_DEEP_KEY_FIELDS = {
    "ev": "q.bs.ev.t", "nbv": "q.ps.nbv.t",
    "coresr": "q.bs.coresr.t", "compsr": "q.bs.compsr.t",
    "opatshopc": "q.ps.opatshopc.t", "pi": "q.ps.pi.t",
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

# 港股董事权益变动（hot 端点：stockCodes + metricsList，无日期区间）
HK_DIRECTOR_EQUITY_METRICS = [
    "dec_a_last", "dec_cap_rc_last",
    "dec_a_m1", "dec_a_m3", "dec_a_m6", "dec_a_y1", "dec_a_y2", "dec_a_y3",
    "dec_cap_rc_m1", "dec_cap_rc_m3", "dec_cap_rc_m6",
    "dec_cap_rc_y1", "dec_cap_rc_y2", "dec_cap_rc_y3",
]


class MXError(Exception):
    """妙想 skill 调用失败。"""


class LegacyError(Exception):
    """免费源（ashare_data）调用失败。"""


def _default_mx_script() -> str:
    """妙想 mx_data.py 默认路径（兼容旧接口）。"""
    return _resolve_mx_script("mx-data")


_MX_SKILLS = ("mx-data", "mx-search", "mx-xuangu")
_MX_TTL_DEFAULT = 3600  # 妙想日限额敏感，默认 1h 磁盘缓存


def _resolve_mx_script(skill: str) -> str:
    """解析妙想 skill 脚本路径：环境变量 > ~/.claude > ~/.codex。"""
    skill = skill.strip().lower()
    if skill not in _MX_SKILLS:
        raise MXError(f"未知妙想 skill: {skill}（支持 {_MX_SKILLS}）")
    env_keys = {
        "mx-data": "MX_DATA_SCRIPT",
        "mx-search": "MX_SEARCH_SCRIPT",
        "mx-xuangu": "MX_XUANGU_SCRIPT",
    }
    env_val = os.environ.get(env_keys[skill], "").strip()
    if env_val and os.path.isfile(env_val):
        return env_val
    script_name = skill.replace("-", "_") + ".py"
    home = os.path.expanduser("~")
    for base in (".claude", ".codex"):
        path = os.path.join(home, base, "skills", skill, script_name)
        if os.path.isfile(path):
            return path
    return os.path.join(home, ".claude", "skills", skill, script_name)


def _mx_output_dir(cache_root: Optional[str] = None) -> str:
    """妙想输出目录（Windows 兼容，默认 %TEMP%/mx_skills）。"""
    root = cache_root or tempfile.gettempdir()
    out = os.path.join(root, "mx_skills")
    os.makedirs(out, exist_ok=True)
    return out


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
    # 行业深度报表（P4.2/P4.3：保险/银行/证券专属指标）
    # ------------------------------------------------------------------

    def get_industry_deep(self, code: str, years: int = 5, report_type: Optional[str] = None) -> dict:
        """保险/银行/证券专属深度财报。自动判定类型并选取专属指标集（自动剪枝）。

        准出要点：保险返回 EV/NBV/偿付能力/营运利润；银行返回资本充足率/净息差/不良/拨备；
        证券返回经纪/投行/资管/自营业务净收入。非金融类型回退到通用财务指标。
        """
        market = _detect_market(code)
        norm = _norm_code(code, market)
        fs_type = report_type or self.detect_fs_type(code)
        endpoint = f"{market}/company/fs/{fs_type}"
        metrics = DEEP_METRICS_BY_TYPE.get(fs_type, DEFAULT_FINANCIALS_METRICS)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        base = {
            "stockCodes": [norm],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        records, used = self._post_fs(endpoint, base, metrics, self._ttl("financials", 86400))
        annual = [r for r in records if str(r.get("date", ""))[:10].endswith("-12-31")]
        annual.sort(key=lambda r: r.get("date", ""), reverse=True)
        summary = self._industry_deep_summary(fs_type, annual)
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm, "market": market, "report_type": fs_type,
            "records": records, "metric_count": len(used),
            "available_metrics": used, "annual_count": len(annual),
            "deep_summary": summary, "_source": "lixinger",
        }

    @staticmethod
    def _industry_deep_summary(fs_type: str, annual: list) -> dict:
        """提取保险/银行/证券的关键深度字段近3年值，供准出核对。"""
        if not annual:
            return {}
        key_fields = {
            "insurance": INSURANCE_DEEP_KEY_FIELDS,
            "bank": {
                "car": "q.bs.car.t", "nim": "q.bs.nim.t",
                "npl_ratio": "q.bs.llr_npl_r.t", "npl": "q.bs.npl.t",
            },
            "security": {
                "broker": "q.ps.nfifb.t", "ib": "q.ps.nfifib.t",
                "am": "q.ps.nfifam.t", "nfaci": "q.ps.nfaci.t",
            },
        }.get(fs_type, {})
        out = {}
        for label, path in key_fields.items():
            series = []
            for r in annual[:3]:
                q = r.get("q", {}) if isinstance(r, dict) else {}
                val = LxrData._dig(q, path[2:]) if path.startswith("q.") else None
                series.append({"date": str(r.get("date", ""))[:10], "value": val})
            out[label] = series
        return out

    # ------------------------------------------------------------------
    # 营收构成（P4.4：分产品/分地区收入）
    # ------------------------------------------------------------------

    def get_revenue_constitution(self, code: str, years: int = 3) -> dict:
        """营收构成：境内/境外收入 + dataList（分产品/分地区收入、占比、毛利率）。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCode": norm,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
        }
        endpoint = f"{market}/company/operation-revenue-constitution"
        data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("revenue", 86400))
        records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        return {
            "source_detail": f"lixinger:{endpoint}",
            "code": norm, "market": market, "records": records, "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 公司治理（P4.5：高管/大股东增减持；股东数据见 P3.4）
    # ------------------------------------------------------------------

    def get_governance(self, code: str, years: int = 2) -> dict:
        """高管增减持 + 大股东增减持（A股）；港股用董事权益变动。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        date_range = {"startDate": start.strftime("%Y-%m-%d"), "endDate": end.strftime("%Y-%m-%d")}
        if market == "hk":
            payload = {
                "stockCodes": [norm],
                "metricsList": HK_DIRECTOR_EQUITY_METRICS,
            }
            data = self.client.post(
                "hk/company/hot/director_equity_change",
                payload,
                ttl_seconds=self._ttl("governance", 86400),
            )
            records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
            return {
                "source_detail": "lixinger:hk/company/hot/director_equity_change",
                "code": norm, "market": "hk",
                "director_changes": records, "executive_changes": [], "major_shareholder_changes": [],
                "_source": "lixinger",
            }
        exec_payload = {"stockCode": norm, **date_range}
        maj_payload = {"stockCode": norm, **date_range}
        exec_data = self.client.post("cn/company/senior-executive-shares-change", exec_payload,
                                     ttl_seconds=self._ttl("governance", 86400))
        maj_data = self.client.post("cn/company/major-shareholders-shares-change", maj_payload,
                                    ttl_seconds=self._ttl("governance", 86400))
        return {
            "source_detail": "lixinger:cn/company/*-shares-change",
            "code": norm, "market": "cn",
            "executive_changes": exec_data if isinstance(exec_data, list) else [],
            "major_shareholder_changes": maj_data if isinstance(maj_data, list) else [],
            "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 宏观模块（P5.1：国债收益率/利率，利差分析输入）
    # ------------------------------------------------------------------

    # 国债收益率指标（macro/national-debt，flat 指标，无 q. 前缀）
    MACRO_DEBT_METRICS = ["tcm_y10", "tcm_y30", "tcm_y5", "tcm_y1", "tcm_m3"]
    # 利率指标（macro/interest-rates，cn）
    MACRO_RATE_METRICS_CN = ["lpr_y1", "lpr_y5", "shibor_m3", "mlf_y1_r", "fr_d7"]

    def get_macro_national_debt(self, area: str = "cn", years: int = 10) -> dict:
        """国债收益率序列（中美）。返回 latest_10y 便于利差分析。"""
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "areaCode": area,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "metricsList": self.MACRO_DEBT_METRICS,
        }
        data = self.client.post("macro/national-debt", payload, ttl_seconds=self._ttl("macro", 86400))
        records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        latest = records[0] if records else {}
        # 国债每日更新，但仍按最新非空 tcm_y10 兜底
        y10 = latest.get("tcm_y10")
        if y10 is None:
            for r in records:
                if r.get("tcm_y10") is not None:
                    y10 = r.get("tcm_y10")
                    break
        return {
            "source_detail": "lixinger:macro/national-debt",
            "area": area, "records": records,
            "latest_10y": y10,
            "latest_date": str(latest.get("date", ""))[:10],
            "_source": "lixinger",
        }

    def get_macro_interest_rates(self, area: str = "cn", years: int = 5) -> dict:
        """利率序列（LPR/Shibor/MLF 等）。"""
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        metrics = self.MACRO_RATE_METRICS_CN if area == "cn" else ["hibor_m3", "hibor_y1"]
        payload = {
            "areaCode": area,
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "metricsList": metrics,
        }
        data = self.client.post("macro/interest-rates", payload, ttl_seconds=self._ttl("macro", 86400))
        records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        # 各指标仅在更新日有值（如 LPR 月度、Shibor 日度），取每个指标的最新非空值
        latest = {}
        for m in metrics:
            for r in records:
                if isinstance(r, dict) and r.get(m) is not None:
                    latest[m] = r.get(m)
                    break
        return {
            "source_detail": "lixinger:macro/interest-rates",
            "area": area, "records": records, "latest": latest,
            "_source": "lixinger",
        }

    def get_bond_yield_10y(self, area: str = "cn") -> dict:
        """准出便利方法：当前10年期国债收益率（利差分析基准）。"""
        d = self.get_macro_national_debt(area=area, years=1)
        return {
            "area": area, "yield_10y": d.get("latest_10y"),
            "date": d.get("latest_date"), "_source": "lixinger",
            "source_detail": d.get("source_detail"),
        }

    # ------------------------------------------------------------------
    # 指数估值模块（P5.2：沪深300/恒生 PE/PB 分位点）
    # ------------------------------------------------------------------

    INDEX_CODES_CN = {
        "沪深300": "000300", "上证50": "000016", "中证500": "000905",
        "中证1000": "000852", "创业板指": "399006", "科创50": "000688",
    }
    INDEX_CODES_HK = {"恒生指数": "HSI", "恒生中国企业指数": "HSCEI", "恒生科技指数": "HSTECH"}
    # 指数/行业基本面指标：4指标 × (当前值+10年分位) + 收盘点位（指数专有）
    INDEX_VAL_METRICS = [
        "pe_ttm.y10.mcw.cv", "pe_ttm.y10.mcw.cvpos",
        "pb.y10.mcw.cv", "pb.y10.mcw.cvpos",
        "ps_ttm.y10.mcw.cv", "ps_ttm.y10.mcw.cvpos",
        "dyr.y10.mcw.cv", "dyr.y10.mcw.cvpos",
        "cp",
    ]
    # 行业基本面指标：同上但无 cp（行业无收盘点位，传 cp 会触发 invalid price metrics）
    INDUSTRY_VAL_METRICS = [m for m in INDEX_VAL_METRICS if m != "cp"]

    @staticmethod
    def _flatten_index_val(record: dict) -> dict:
        """指数/行业基本面返回扁平点号键（如 pe_ttm.y10.mcw.cv），展平为 {pe_ttm:{cv,cvpos},...}。"""
        out = {}
        if not isinstance(record, dict):
            return out
        for name in ("pe_ttm", "pb", "ps_ttm", "dyr"):
            out[name] = {
                "cv": record.get(f"{name}.y10.mcw.cv"),
                "cvpos": record.get(f"{name}.y10.mcw.cvpos"),
            }
        out["cp"] = record.get("cp")
        return out

    def get_index_valuation(self, index_code: str, market: str = "cn", years: int = 10) -> dict:
        """指数估值：PE/PB/PS/股息率 当前值 + 10年分位点 + 收盘点位。"""
        endpoint = f"{market}/index/fundamental"
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCodes": [index_code],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "limit": 1,
            "metricsList": self.INDEX_VAL_METRICS,
        }
        data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("index_val", 86400))
        records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        latest = records[0] if records else {}
        return {
            "source_detail": f"lixinger:{endpoint}",
            "index_code": index_code, "market": market,
            "date": str(latest.get("date", ""))[:10],
            "valuation": self._flatten_index_val(latest),
            "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # 行业对比模块（P5.3：申万二级行业估值对比表）
    # ------------------------------------------------------------------

    def _sw_industry_map(self, source: str = "sw_2021") -> dict:
        """构建股票→所属行业码列表 + 行业码→{name,level,fsTableType}。
        constituents 省略 stockCodes 返回所有行业成分（同一股票出现在一/二/三级各一条）；
        cn/industry 不传 level 返回全部 511 条带 level 字段，用于按层级精确选取。"""
        ttl = self._ttl("industry_map", 7 * 86400)
        cons = self.client.post(f"cn/industry/constituents/{source}",
                                {"date": "latest"}, ttl_seconds=ttl)
        cons_list = cons if isinstance(cons, list) else ([cons] if isinstance(cons, dict) else [])
        info = self.client.post("cn/industry", {"source": source}, ttl_seconds=ttl)
        info_list = info if isinstance(info, list) else ([info] if isinstance(info, dict) else [])
        code_info = {}
        for it in info_list:
            if isinstance(it, dict) and it.get("stockCode"):
                code_info[it["stockCode"]] = {
                    "name": it.get("name"), "level": it.get("level"),
                    "fsTableType": it.get("fsTableType"),
                }
        stock2codes = {}
        for blk in cons_list:
            if not isinstance(blk, dict):
                continue
            ind_code = blk.get("stockCode")
            for c in blk.get("constituents", []) or []:
                sc = c.get("stockCode") if isinstance(c, dict) else None
                if sc:
                    stock2codes.setdefault(sc, []).append(ind_code)
        return {"code_info": code_info, "stock2codes": stock2codes}

    def get_industry_of_stock(self, code: str, source: str = "sw_2021", level: str = "two") -> dict:
        """返回股票所属申万行业（默认二级）。constituents 同时返回一/二/三级，按 level 精确选取。
        level: one/two/three；若目标层级缺失则降级到最细可用层级。仅支持A股。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        if market != "cn":
            return {"source_detail": "lixinger:not_available", "code": norm, "market": market,
                    "industry_code": None, "industry_name": None, "level": None,
                    "note": "申万行业分类仅覆盖A股", "_source": "none"}
        m = self._sw_industry_map(source=source)
        codes = m["stock2codes"].get(norm, [])
        if not codes:
            return {"source_detail": f"lixinger:cn/industry/constituents/{source}",
                    "code": norm, "market": "cn", "industry_code": None, "industry_name": None,
                    "level": None, "note": "未匹配到申万行业（可能为非主板/退市）", "_source": "none"}
        lvl_rank = {"one": 1, "two": 2, "three": 3}
        target_rank = lvl_rank.get(level, 2)
        # 优先精确匹配目标层级；否则取最接近且更细的层级
        chosen = None
        for cd in codes:
            ci = m["code_info"].get(cd, {})
            if ci.get("level") == level:
                chosen = (cd, ci)
                break
        if not chosen:
            best = None
            for cd in codes:
                ci = m["code_info"].get(cd, {})
                r = lvl_rank.get(ci.get("level"), 0)
                if r and (best is None or abs(r - target_rank) < abs(best[2] - target_rank)):
                    best = (cd, ci, r)
            if best:
                chosen = (best[0], best[1])
        if not chosen:
            cd = codes[0]
            chosen = (cd, m["code_info"].get(cd, {}))
        cd, ci = chosen
        return {
            "source_detail": f"lixinger:cn/industry/constituents/{source}",
            "code": norm, "market": "cn", "source": source,
            "industry_code": cd, "industry_name": ci.get("name") or cd,
            "level": ci.get("level"), "fsTableType": ci.get("fsTableType"),
            "_source": "lixinger",
        }

    def get_industry_valuation(self, industry_code: str, source: str = "sw_2021", years: int = 10) -> dict:
        """行业估值：PE/PB/PS/股息率 当前值 + 10年分位点。"""
        endpoint = f"cn/industry/fundamental/{source}"
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCodes": [industry_code],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "limit": 1,
            "metricsList": self.INDUSTRY_VAL_METRICS,
        }
        data = self.client.post(endpoint, payload, ttl_seconds=self._ttl("ind_val", 86400))
        records = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        records.sort(key=lambda r: r.get("date", ""), reverse=True)
        latest = records[0] if records else {}
        return {
            "source_detail": f"lixinger:{endpoint}",
            "industry_code": industry_code, "source": source,
            "date": str(latest.get("date", ""))[:10],
            "valuation": self._flatten_index_val(latest),
            "_source": "lixinger",
        }

    def compare_industry_valuation(self, code: str, source: str = "sw_2021", level: str = "two") -> dict:
        """一键输出：股票所属申万二级行业估值 + 公司估值 对比表。"""
        ind = self.get_industry_of_stock(code, source=source, level=level)
        result = {
            "source_detail": "lixinger:industry-compare",
            "code": ind.get("code", _norm_code(code, _detect_market(code))),
            "market": ind.get("market"), "industry": ind, "comparison": None,
            "_source": ind.get("_source"),
        }
        if not ind.get("industry_code"):
            return result
        ind_val = self.get_industry_valuation(ind["industry_code"], source=source)
        comp_val = self.get_valuation(code)
        flat = comp_val.get("latest", {}) if isinstance(comp_val, dict) else {}
        rows = []
        for name in ("pe_ttm", "pb", "ps_ttm", "dyr"):
            iv = ind_val.get("valuation", {}).get(name, {})
            rows.append({
                "metric": name,
                "industry_cv": iv.get("cv"), "industry_cvpos": iv.get("cvpos"),
                "company_cv": flat.get(name),
                "company_cvpos": flat.get(f"{name}.y10.cvpos"),
            })
        result["comparison"] = {
            "industry_valuation": ind_val,
            "company_valuation": comp_val,
            "table": rows,
        }
        return result

    # ------------------------------------------------------------------
    # 妙想 Skills 统一封装（mx-data / mx-search / mx-xuangu）
    # ------------------------------------------------------------------

    def _mx_cache_get(self, skill: str, query: str, ttl_seconds: int) -> Optional[dict]:
        hit, val = self.client.cache.get(f"mx/{skill}", {"query": query}, ttl_seconds)
        return val if hit else None

    def _mx_cache_set(self, skill: str, query: str, value: dict) -> None:
        self.client.cache.set(f"mx/{skill}", {"query": query}, value)

    def call_mx(self, skill: str, query: str, ttl_seconds: int = _MX_TTL_DEFAULT) -> dict:
        """调用妙想 skill 子进程，返回 raw JSON + 路径；带 1h 默认磁盘缓存。"""
        skill = skill.strip().lower()
        cached = self._mx_cache_get(skill, query, ttl_seconds) if ttl_seconds > 0 else None
        if cached is not None:
            return {**cached, "_cache": "hit"}

        script = self.mx_script if skill == "mx-data" else _resolve_mx_script(skill)
        if not os.path.isfile(script):
            raise MXError(f"{skill} 脚本不存在: {script}")
        out_dir = _mx_output_dir(self.client.cache.dir)
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        if skill == "mx-xuangu":
            cmd = [sys.executable, script, query, "--output-dir", out_dir]
        else:
            cmd = [sys.executable, script, query, out_dir]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=120,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
            raise MXError(f"{skill} 退出码 {proc.returncode}: {' | '.join(tail)}")
        raw_path = _latest_mx_artifact(out_dir, skill)
        raw: Any = None
        if raw_path:
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        result = {
            "_source": skill,
            "query": query,
            "raw": raw,
            "raw_path": raw_path,
            "output_dir": out_dir,
            "stdout_preview": (proc.stdout or "")[:2000],
        }
        if ttl_seconds > 0:
            self._mx_cache_set(skill, query, result)
        return result

    def mx_data(self, query: str, ttl_seconds: int = _MX_TTL_DEFAULT) -> dict:
        return self.call_mx("mx-data", query, ttl_seconds)

    def mx_search(self, query: str, ttl_seconds: int = _MX_TTL_DEFAULT) -> dict:
        return self.call_mx("mx-search", query, ttl_seconds)

    def mx_xuangu(self, query: str, ttl_seconds: int = _MX_TTL_DEFAULT) -> dict:
        return self.call_mx("mx-xuangu", query, ttl_seconds)

    # ------------------------------------------------------------------
    # /quality-screen 精确 7 指标
    # ------------------------------------------------------------------

    def get_quality_metrics(self, code: str, years: int = 10, fcf_years: int = 5) -> dict:
        """计算去劣筛选 7 条硬指标（理杏仁财报本地精算）。"""
        # 股本膨胀需 fcf_years+1 个年末点；ROE/净利率窗口取 max(years, fcf_years+1)
        span_years = min(max(years, fcf_years + 1), 10)
        fin = self.get_financials(code, years=span_years, source="lixinger")
        if fin.get("_source") != "lixinger":
            return {
                "_source": "none",
                "code": _norm_code(code, _detect_market(code)),
                "error": fin.get("error", "financials 不可用"),
            }
        report_type = fin.get("report_type", "non_financial")
        annual = _annual_fs_records(fin.get("records") or [])
        computed = _compute_quality_checks(report_type, annual, years, fcf_years)
        return {
            "source_detail": "lixinger:quality-metrics",
            "code": fin.get("code"),
            "market": fin.get("market"),
            "report_type": report_type,
            "years": years,
            "fcf_years": fcf_years,
            **computed,
            "status": computed.get("result"),
            "_source": "lixinger",
        }

    # ------------------------------------------------------------------
    # A股龙虎榜（免费源）
    # ------------------------------------------------------------------

    def get_lhb(
        self,
        code: Optional[str] = None,
        limit: int = 20,
        page: int = 1,
        source: str = "auto",
    ) -> dict:
        """获取 A 股龙虎榜明细。当前统一入口走东方财富免费源。"""
        if source not in ("auto", "legacy"):
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain([
            ("legacy", lambda: self._get_lhb_legacy(code, limit, page)),
        ])

    def _get_lhb_legacy(self, code: Optional[str], limit: int, page: int) -> dict:
        args = ["lhb"]
        if code:
            args.append(_norm_code(code, "cn"))
        args.extend(["--limit", str(limit), "--page", str(page), "--json"])
        text = self._call_legacy_tool(args)
        data = json.loads(text)
        data["source_detail"] = "legacy:ashare_data/lhb"
        if "_source" not in data:
            data["_source"] = "legacy"
        return data

    def get_lhb_detail(
        self,
        code: Optional[str] = None,
        trade_date: Optional[str] = None,
        trade_id: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        list_limit: int = 20,
        page: int = 1,
        dominant_type: Optional[str] = None,
        dominant_direction: Optional[str] = None,
        youzi_alias: Optional[str] = None,
        min_dominant_net: Optional[float] = None,
        source: str = "auto",
    ) -> dict:
        """获取 A 股龙虎榜买卖席位明细。当前统一入口走东方财富免费源。"""
        if source not in ("auto", "legacy"):
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain([
            ("legacy", lambda: self._get_lhb_detail_legacy(
                code,
                trade_date,
                trade_id,
                limit,
                start_date,
                end_date,
                list_limit,
                page,
                dominant_type,
                dominant_direction,
                youzi_alias,
                min_dominant_net,
            )),
        ])

    def _get_lhb_detail_legacy(
        self,
        code: Optional[str],
        trade_date: Optional[str],
        trade_id: Optional[str],
        limit: int,
        start_date: Optional[str],
        end_date: Optional[str],
        list_limit: int,
        page: int,
        dominant_type: Optional[str],
        dominant_direction: Optional[str],
        youzi_alias: Optional[str],
        min_dominant_net: Optional[float],
    ) -> dict:
        args = ["lhb-detail"]
        if code:
            args.append(_norm_code(code, "cn"))
        if trade_date:
            args.extend(["--date", str(trade_date)[:10]])
        if start_date:
            args.extend(["--start-date", str(start_date)[:10]])
        if end_date:
            args.extend(["--end-date", str(end_date)[:10]])
        if trade_id:
            args.extend(["--trade-id", str(trade_id)])
        if limit != 10:
            args.extend(["--limit", str(limit)])
        if list_limit != 20:
            args.extend(["--list-limit", str(list_limit)])
        if page != 1:
            args.extend(["--page", str(page)])
        if dominant_type:
            args.extend(["--dominant-type", str(dominant_type)])
        if dominant_direction:
            args.extend(["--dominant-direction", str(dominant_direction)])
        if youzi_alias:
            args.extend(["--youzi-alias", str(youzi_alias)])
        if min_dominant_net is not None:
            args.extend(["--min-dominant-net", str(min_dominant_net)])
        args.append("--json")
        text = self._call_legacy_tool(args)
        data = json.loads(text)
        data["source_detail"] = "legacy:ashare_data/lhb-detail"
        if "_source" not in data:
            data["_source"] = "legacy"
        return data

    def get_lhb_compare(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        limit: int = 10,
        list_limit: int = 20,
        page: int = 1,
        dominant_type: Optional[str] = None,
        dominant_direction: Optional[str] = None,
        youzi_alias: Optional[str] = None,
        min_dominant_net: Optional[float] = None,
        sort_by: str = "youzi_abs_net_amount",
        source: str = "auto",
    ) -> dict:
        """获取多股票 A 股龙虎榜区间辨识度对比。当前统一入口走东方财富免费源。"""
        if source not in ("auto", "legacy"):
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain([(
            "legacy",
            lambda: self._get_lhb_compare_legacy(
                codes,
                start_date,
                end_date,
                limit,
                list_limit,
                page,
                dominant_type,
                dominant_direction,
                youzi_alias,
                min_dominant_net,
                sort_by,
            ),
        )])

    def _get_lhb_compare_legacy(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        limit: int,
        list_limit: int,
        page: int,
        dominant_type: Optional[str],
        dominant_direction: Optional[str],
        youzi_alias: Optional[str],
        min_dominant_net: Optional[float],
        sort_by: str,
    ) -> dict:
        args = ["lhb-compare"]
        args.extend(_norm_code(code, "cn") for code in codes)
        args.extend(["--start-date", str(start_date)[:10], "--end-date", str(end_date)[:10]])
        if limit != 10:
            args.extend(["--limit", str(limit)])
        if list_limit != 20:
            args.extend(["--list-limit", str(list_limit)])
        if page != 1:
            args.extend(["--page", str(page)])
        if dominant_type:
            args.extend(["--dominant-type", str(dominant_type)])
        if dominant_direction:
            args.extend(["--dominant-direction", str(dominant_direction)])
        if youzi_alias:
            args.extend(["--youzi-alias", str(youzi_alias)])
        if min_dominant_net is not None:
            args.extend(["--min-dominant-net", str(min_dominant_net)])
        if sort_by != "youzi_abs_net_amount":
            args.extend(["--sort-by", str(sort_by)])
        args.append("--json")
        text = self._call_legacy_tool(args)
        data = json.loads(text)
        data["source_detail"] = "legacy:ashare_data/lhb-compare"
        if "_source" not in data:
            data["_source"] = "legacy"
        return data

    # ------------------------------------------------------------------
    # 研究数据包（跨 Skill 共享，TTL 1h）
    # ------------------------------------------------------------------

    def get_research_datapack(
        self,
        code: str,
        years: int = 5,
        name: Optional[str] = None,
        include_mx: bool = True,
        ttl_seconds: int = 3600,
    ) -> dict:
        """一次性拉取投研常用数据包，缓存 1 小时供多 Skill/多模块共享。"""
        market = _detect_market(code)
        norm = _norm_code(code, market)
        cache_key = {"code": norm, "market": market, "years": years, "include_mx": include_mx}
        hit, cached = self.client.cache.get("datapack/research", cache_key, ttl_seconds)
        if hit and isinstance(cached, dict):
            return {**cached, "_cache": "hit"}

        pack: dict[str, Any] = {
            "code": norm,
            "market": market,
            "years": years,
            "fetched_at": _dt.datetime.now().isoformat(),
            "sections": {},
        }

        def _section(key: str, fn) -> None:
            try:
                data = fn()
                pack["sections"][key] = data
            except Exception as exc:
                pack["sections"][key] = {"_source": "none", "error": str(exc)}

        _section("financials", lambda: self.get_financials(norm, years=years, source="lixinger"))
        _section("valuation", lambda: self.get_valuation(norm, source="lixinger"))
        _section("verify_inputs", lambda: self.get_verification_inputs(norm))
        _section("percentiles", lambda: self.get_valuation_percentiles(norm))
        _section("governance", lambda: self.get_governance(norm, years=2))
        _section("shareholders", lambda: self.get_majority_shareholders(norm, years=2))
        if market == "cn":
            _section("revenue", lambda: self.get_revenue_constitution(norm, years=3))
            _section("industry_compare", lambda: self.compare_industry_valuation(norm))
        fs_type = self.detect_fs_type(norm)
        if fs_type in ("insurance", "bank", "security"):
            _section("industry_deep", lambda: self.get_industry_deep(norm, years=years))
        if include_mx:
            label = name or norm
            _section("mx_quote", lambda: self.mx_data(f"{label} 最新价 涨跌幅 PE PB"))
            _section("mx_news", lambda: self.mx_search(f"{label} 最新公告 业绩"))

        pack["_source"] = _datapack_source(pack, include_mx)
        has_failed_section = any(
            isinstance(section, dict)
            and (section.get("_source") in (None, "", "none") or section.get("error"))
            for section in pack.get("sections", {}).values()
        )
        if not has_failed_section:
            self.client.cache.set("datapack/research", cache_key, pack)
        return pack

    # ------------------------------------------------------------------
    # 子进程调用妙想 mx-data（兼容旧路径）
    # ------------------------------------------------------------------

    def _call_mx_skill(self, query: str) -> dict:
        result = self.call_mx("mx-data", query, ttl_seconds=_MX_TTL_DEFAULT)
        raw = result.get("raw")
        if raw is None:
            raise MXError("mx_data 成功但未生成 raw.json")
        return raw if isinstance(raw, dict) else {}

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
    return _latest_mx_artifact(dir_path, "mx-data")


def _latest_mx_artifact(dir_path: str, skill: str) -> Optional[str]:
    """查找妙想 skill 最近一次输出的 JSON 文件。"""
    prefix = skill.replace("-", "_") + "_"
    latest: Optional[str] = None
    latest_mtime = -1.0
    for name in os.listdir(dir_path):
        if not name.startswith(prefix):
            continue
        if skill == "mx-search":
            if not name.endswith(".json"):
                continue
        elif not name.endswith("_raw.json"):
            continue
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

    p_id = sub.add_parser("industry-deep", help="行业深度报表（保险EV/NBV/偿付能力、银行资本充足率/净息差、证券经纪/投行/资管）")
    p_id.add_argument("code", help="股票代码，如 601336(保险) / 600036(银行) / 600030(证券)")
    p_id.add_argument("--years", type=int, default=5)
    p_id.add_argument("--report-type", default=None, choices=list(FS_TYPES))
    p_id.add_argument("--quiet", action="store_true")

    p_rc = sub.add_parser("revenue", help="营收构成（分产品/分地区收入、占比、毛利率）")
    p_rc.add_argument("code", help="股票代码")
    p_rc.add_argument("--years", type=int, default=3)
    p_rc.add_argument("--quiet", action="store_true")

    p_gv = sub.add_parser("governance", help="公司治理（高管/大股东增减持；港股董事权益变动）")
    p_gv.add_argument("code", help="股票代码")
    p_gv.add_argument("--years", type=int, default=2)
    p_gv.add_argument("--quiet", action="store_true")

    p_md = sub.add_parser("macro-debt", help="国债收益率（10年期等，利差分析基准）")
    p_md.add_argument("--area", default="cn", choices=["cn", "us"])
    p_md.add_argument("--years", type=int, default=10)
    p_md.add_argument("--quiet", action="store_true")

    p_mr = sub.add_parser("macro-rates", help="利率（LPR/Shibor/MLF 等）")
    p_mr.add_argument("--area", default="cn", choices=["cn", "hk", "us"])
    p_mr.add_argument("--years", type=int, default=5)
    p_mr.add_argument("--quiet", action="store_true")

    p_iv = sub.add_parser("index-val", help="指数估值（沪深300/恒生指数 PE/PB 分位点）")
    p_iv.add_argument("index_code", help="指数代码，如 000300(沪深300) / HSI(恒生)")
    p_iv.add_argument("--market", default="cn", choices=["cn", "hk"])
    p_iv.add_argument("--years", type=int, default=10)
    p_iv.add_argument("--quiet", action="store_true")

    p_ic = sub.add_parser("industry-compare", help="一键输出公司所属申万二级行业估值对比表")
    p_ic.add_argument("code", help="A股代码，如 600519")
    p_ic.add_argument("--source", default="sw_2021", choices=["sw", "sw_2021", "cni"])
    p_ic.add_argument("--level", default="two", choices=["one", "two", "three"])
    p_ic.add_argument("--quiet", action="store_true")

    p_dp = sub.add_parser("datapack", help="投研数据包（理杏仁批量+妙想，TTL 1h 缓存）")
    p_dp.add_argument("code", help="股票代码")
    p_dp.add_argument("--years", type=int, default=5)
    p_dp.add_argument("--name", default=None, help="公司中文名（妙想查询用）")
    p_dp.add_argument("--no-mx", action="store_true", help="跳过妙想 tick/资讯（节省日限额）")
    p_dp.add_argument("--quiet", action="store_true")

    p_qm = sub.add_parser("quality-metrics", help="/quality-screen 精确 7 指标（理杏仁本地计算）")
    p_qm.add_argument("code", help="股票代码")
    p_qm.add_argument("--years", type=int, default=10, help="ROE/净利率均值窗口（年）")
    p_qm.add_argument("--fcf-years", type=int, default=5, help="FCF 累计窗口（年）")
    p_qm.add_argument("--quiet", action="store_true")

    p_lhb = sub.add_parser("lhb", help="A股龙虎榜明细（东方财富免费源）")
    p_lhb.add_argument("code", nargs="?", default=None, help="股票代码；省略则返回全市场最新")
    p_lhb.add_argument("--limit", type=int, default=20)
    p_lhb.add_argument("--page", type=int, default=1)
    p_lhb.add_argument("--source", choices=["auto", "legacy"], default="auto")
    p_lhb.add_argument("--quiet", action="store_true")

    p_lhb_detail = sub.add_parser("lhb-detail", help="A股龙虎榜买卖席位明细（东方财富免费源）")
    p_lhb_detail.add_argument("code", nargs="?", default=None, help="股票代码；配合 --date 使用")
    p_lhb_detail.add_argument("--date", dest="trade_date", default=None, help="交易日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--start-date", default=None, help="批量开始日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--end-date", default=None, help="批量结束日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--trade-id", default=None, help="东方财富 TRADE_ID，优先使用")
    p_lhb_detail.add_argument("--limit", type=int, default=10)
    p_lhb_detail.add_argument("--list-limit", type=int, default=20, help="区间模式下先筛选的龙虎榜记录数")
    p_lhb_detail.add_argument("--page", type=int, default=1, help="区间模式下龙虎榜列表页码")
    p_lhb_detail.add_argument(
        "--dominant-type",
        choices=["institution", "northbound", "youzi", "brokerage", "unknown"],
        default=None,
        help="区间模式下按资金主导类型过滤",
    )
    p_lhb_detail.add_argument(
        "--dominant-direction",
        choices=["net_buy", "net_sell", "flat"],
        default=None,
        help="区间模式下按资金主导方向过滤",
    )
    p_lhb_detail.add_argument("--youzi-alias", default=None, help="区间模式下按游资/活跃席位别名过滤")
    p_lhb_detail.add_argument(
        "--min-dominant-net",
        type=float,
        default=None,
        help="区间模式下按主导资金绝对净额下限过滤",
    )
    p_lhb_detail.add_argument("--source", choices=["auto", "legacy"], default="auto")
    p_lhb_detail.add_argument("--quiet", action="store_true")

    p_lhb_compare = sub.add_parser("lhb-compare", help="A股龙虎榜多股票区间辨识度对比（东方财富免费源）")
    p_lhb_compare.add_argument("codes", nargs="+", help="2-4 个股票代码，如 000004 000005")
    p_lhb_compare.add_argument("--start-date", required=True, help="开始日期 YYYY-MM-DD")
    p_lhb_compare.add_argument("--end-date", required=True, help="结束日期 YYYY-MM-DD")
    p_lhb_compare.add_argument("--limit", type=int, default=10)
    p_lhb_compare.add_argument("--list-limit", type=int, default=20, help="每只股票先筛选的龙虎榜记录数")
    p_lhb_compare.add_argument("--page", type=int, default=1, help="龙虎榜列表页码")
    p_lhb_compare.add_argument(
        "--dominant-type",
        choices=["institution", "northbound", "youzi", "brokerage", "unknown"],
        default=None,
        help="按资金主导类型过滤",
    )
    p_lhb_compare.add_argument(
        "--dominant-direction",
        choices=["net_buy", "net_sell", "flat"],
        default=None,
        help="按资金主导方向过滤",
    )
    p_lhb_compare.add_argument("--youzi-alias", default=None, help="按游资/活跃席位别名过滤")
    p_lhb_compare.add_argument("--min-dominant-net", type=float, default=None, help="主导资金绝对净额下限")
    p_lhb_compare.add_argument(
        "--sort-by",
        choices=["youzi_abs_net_amount", "profiled_abs_net_amount", "profiled_abs_net_ratio"],
        default="youzi_abs_net_amount",
    )
    p_lhb_compare.add_argument("--source", choices=["auto", "legacy"], default="auto")
    p_lhb_compare.add_argument("--quiet", action="store_true")

    for skill in _MX_SKILLS:
        p_mx = sub.add_parser(skill, help=f"调用妙想 {skill}（1h 缓存，自动 Windows 输出目录）")
        p_mx.add_argument("query", help="自然语言查询")
        p_mx.add_argument("--ttl", type=int, default=_MX_TTL_DEFAULT, help="缓存秒数，0=不缓存")
        p_mx.add_argument("--quiet", action="store_true")

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
    elif args.command == "industry-deep":
        data = LxrData(verbose=not args.quiet).get_industry_deep(
            args.code, years=args.years, report_type=args.report_type,
        )
    elif args.command == "revenue":
        data = LxrData(verbose=not args.quiet).get_revenue_constitution(
            args.code, years=args.years,
        )
    elif args.command == "governance":
        data = LxrData(verbose=not args.quiet).get_governance(
            args.code, years=args.years,
        )
    elif args.command == "macro-debt":
        data = LxrData(verbose=not args.quiet).get_macro_national_debt(
            area=args.area, years=args.years,
        )
    elif args.command == "macro-rates":
        data = LxrData(verbose=not args.quiet).get_macro_interest_rates(
            area=args.area, years=args.years,
        )
    elif args.command == "index-val":
        data = LxrData(verbose=not args.quiet).get_index_valuation(
            args.index_code, market=args.market, years=args.years,
        )
    elif args.command == "industry-compare":
        data = LxrData(verbose=not args.quiet).compare_industry_valuation(
            args.code, source=args.source, level=args.level,
        )
    elif args.command == "quality-metrics":
        data = LxrData(verbose=not args.quiet).get_quality_metrics(
            args.code, years=args.years, fcf_years=args.fcf_years,
        )
    elif args.command == "lhb":
        data = LxrData(verbose=not args.quiet).get_lhb(
            args.code, limit=args.limit, page=args.page, source=args.source,
        )
    elif args.command == "lhb-detail":
        data = LxrData(verbose=not args.quiet).get_lhb_detail(
            args.code,
            trade_date=args.trade_date,
            trade_id=args.trade_id,
            limit=args.limit,
            start_date=args.start_date,
            end_date=args.end_date,
            list_limit=args.list_limit,
            page=args.page,
            dominant_type=args.dominant_type,
            dominant_direction=args.dominant_direction,
            youzi_alias=args.youzi_alias,
            min_dominant_net=args.min_dominant_net,
            source=args.source,
        )
    elif args.command == "lhb-compare":
        data = LxrData(verbose=not args.quiet).get_lhb_compare(
            args.codes,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
            list_limit=args.list_limit,
            page=args.page,
            dominant_type=args.dominant_type,
            dominant_direction=args.dominant_direction,
            youzi_alias=args.youzi_alias,
            min_dominant_net=args.min_dominant_net,
            sort_by=args.sort_by,
            source=args.source,
        )
    elif args.command == "datapack":
        data = LxrData(verbose=not args.quiet).get_research_datapack(
            args.code, years=args.years, name=args.name, include_mx=not args.no_mx,
        )
    elif args.command in _MX_SKILLS:
        d = LxrData(verbose=not args.quiet)
        data = d.call_mx(args.command, args.query, ttl_seconds=args.ttl)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
