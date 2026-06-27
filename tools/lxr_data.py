#!/usr/bin/env python3
"""面向 Skill 的高级数据接口 — 统一取数入口，遵循 理杏仁 → 妙想 → 免费源 降级链。

优先级链：
    第1顺位 理杏仁 API  → 成功返回（_source = "lixinger"）
    第2顺位 妙想 mx-data → 成功返回（_source = "mx-data"）
    第3顺位 现有免费源  → 成功返回（_source = "legacy"）
    全部失败            → 返回 {"_source": "none", "error": ...}

每个取数函数返回 dict，必含 ``_source`` 字段标注实际来源，便于报告溯源与交叉验证。

阶段 1 范围：建立回退链骨架与 financials 入口。
- 理杏仁分支：调用 cn/company/fs/non_financial（非金融财报），财报类型自动适配在阶段 2 补齐。
- 妙想分支：subprocess 调用 mx_data.py，返回其原始 JSON。
- 免费源分支：subprocess 调用 ashare_data.py financials，返回其文本输出。
统一 schema 归一化在阶段 2 完成；本阶段聚焦"降级机制可用且可验证"。

CLI：
    python tools/lxr_data.py financials 600519 --years 5 --source auto
    python tools/lxr_data.py financials 600519 --source lixinger
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from typing import Any, Callable, Optional

from lxr_client import LixingerAuthError, LixingerClient, LixingerError

# 近5年核心财务指标（全部为绝对值/每股值，expressionCalculateType = t 当期值）。
# 阶段 2 起按财报类型（insurance/bank/security）切换指标集。
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

    # ------------------------------------------------------------------
    # 通用降级链
    # ------------------------------------------------------------------

    def _run_chain(self, tiers: list) -> dict:
        """tiers: [(source_name, fn), ...]。依次尝试，首个成功即返回（含 _source）。"""
        errors = []
        for source_name, fn in tiers:
            try:
                result = fn()
                if result is None:
                    raise RuntimeError(f"{source_name} 返回 None")
                if isinstance(result, dict) and "_source" not in result:
                    result["_source"] = source_name
                return result
            except Exception as e:  # noqa: BLE001 - 降级链需捕获所有失败
                errors.append(f"{source_name}: {type(e).__name__}: {e}")
                self._log(f"[降级] {source_name} 不可用 ({type(e).__name__}: {e})")
        self._log("[错误] 全部数据源不可用")
        return {"_source": "none", "error": " | ".join(errors)}

    # ------------------------------------------------------------------
    # financials
    # ------------------------------------------------------------------

    def get_financials(
        self,
        code: str,
        years: int = 5,
        source: str = "auto",
        name: Optional[str] = None,
    ) -> dict:
        """获取近 N 年财务数据。

        - source: auto / lixinger / mx / legacy
        - name: 可选公司中文名，提升妙想 NLP 命中率
        - 返回 dict 含 _source 字段
        """
        tiers: list = []
        if source in ("auto", "lixinger"):
            tiers.append(("lixinger", lambda: self._get_financials_lixinger(code, years)))
        if source in ("auto", "mx"):
            tiers.append(("mx-data", lambda: self._get_financials_mx(code, years, name)))
        if source in ("auto", "legacy"):
            tiers.append(("legacy", lambda: self._get_financials_legacy(code, years)))
        if not tiers:
            return {"_source": "none", "error": f"未知 source: {source}"}
        return self._run_chain(tiers)

    def _get_financials_lixinger(self, code: str, years: int) -> dict:
        end = _dt.date.today()
        start = end - _dt.timedelta(days=365 * years + 10)
        payload = {
            "stockCodes": [_norm_code(code)],
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "metricsList": DEFAULT_FINANCIALS_METRICS,
        }
        ttl = self.client.config.get("data_type_ttl_seconds", {}).get("financials", 86400)
        data = self.client.post("cn/company/fs/non_financial", payload, ttl_seconds=ttl)
        return {
            "source_detail": "lixinger:cn/company/fs/non_financial",
            "code": _norm_code(code),
            "years": years,
            "report_type": "non_financial",
            "records": data if isinstance(data, list) else [],
            "metric_count": len(DEFAULT_FINANCIALS_METRICS),
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
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=120,
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
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=60,
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

    p_fin = sub.add_parser("financials", help="近N年财务数据")
    p_fin.add_argument("code", help="股票代码，如 600519")
    p_fin.add_argument("--years", type=int, default=5, help="年数（默认5）")
    p_fin.add_argument(
        "--source",
        choices=["auto", "lixinger", "mx", "legacy"],
        default="auto",
        help="数据源；auto=降级链",
    )
    p_fin.add_argument("--name", default=None, help="公司中文名（提升妙想命中率）")
    p_fin.add_argument("--quiet", action="store_true", help="静默降级日志")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "financials":
        data = LxrData(verbose=not args.quiet).get_financials(
            args.code, years=args.years, source=args.source, name=args.name
        )
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
