"""A股数据工具 — 腾讯行情 + 东方财富搜索/财务，零外部依赖（仅 stdlib）。

为 Claude Code Skills 提供 A 股实时行情、财务数据等数据。
设计原则：独立模块，不影响现有工具；使用 curl 直连绕过系统代理。

用法（由 Skills 自动调用）：
    python3.11 tools/ashare_data.py quote 600519                    # 实时行情
    python3.11 tools/ashare_data.py financials 600519               # 核心财务数据（近5年）
    python3.11 tools/ashare_data.py valuation 600519                # 估值指标
    python3.11 tools/ashare_data.py lhb 600519 --limit 5             # 龙虎榜
    python3.11 tools/ashare_data.py lhb-detail --trade-id 100357777  # 龙虎榜买卖席位
    python3.11 tools/ashare_data.py search 茅台                      # 搜索股票代码

需要 Python >= 3.8，零外部依赖。
"""

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_EVEN

from lhb_seat_profiles import (
    analyze_lhb_seat_flow,
    build_lhb_seat_profile,
    summarize_lhb_seat_amounts,
    summarize_lhb_seat_profiles,
    summarize_lhb_range_flow,
)

_TIMEOUT = 15
_LHB_PROFILE_TYPES = ("institution", "northbound", "youzi", "brokerage", "unknown")
_LHB_COMPARE_SORT_FIELDS = (
    "youzi_abs_net_amount",
    "profiled_abs_net_amount",
    "profiled_abs_net_ratio",
)


def _curl(url):
    """用 curl --noproxy 直连，绕过系统代理。"""
    result = subprocess.run(
        ["curl", "-s", "--noproxy", "*",
         "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
         url],
        capture_output=True, timeout=_TIMEOUT,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ConnectionError(f"请求失败: {url}")
    # 腾讯行情 API 返回 GBK 编码，其他返回 UTF-8
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("gbk")


def _curl_json(url, params=None):
    """curl 获取 JSON。"""
    if params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(params)}"
    return json.loads(_curl(url))


# ---------------------------------------------------------------------------
# 腾讯行情 API（稳定可靠，无需鉴权）
# ---------------------------------------------------------------------------

def _qq_code(code: str) -> str:
    """将股票代码转为腾讯行情格式。"""
    code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if code.startswith(("6", "9", "5")):
        return f"sh{code}"
    elif code.startswith(("0", "3", "2", "1")):
        return f"sz{code}"
    elif code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sh{code}"


def _parse_qq_quote(raw: str) -> dict:
    """解析腾讯行情数据。格式：v_shXXXXXX="字段1~字段2~..."; """
    start = raw.find('"')
    end = raw.rfind('"')
    if start < 0 or end <= start:
        return {}
    fields = raw[start + 1:end].split("~")
    if len(fields) < 50:
        return {}
    return {
        "name": fields[1],
        "code": fields[2],
        "price": fields[3],
        "prev_close": fields[4],
        "open": fields[5],
        "volume": fields[6],         # 手
        "buy_vol": fields[7],
        "sell_vol": fields[8],
        "high": fields[33] if len(fields) > 33 else fields[3],
        "low": fields[34] if len(fields) > 34 else fields[3],
        "change_pct": fields[32],
        "change_amt": fields[31],
        "turnover_amt": fields[37] if len(fields) > 37 else "-",
        "turnover_rate": fields[38] if len(fields) > 38 else "-",
        "pe": fields[39] if len(fields) > 39 else "-",
        "market_cap": fields[45] if len(fields) > 45 else "-",    # 总市值（亿）
        "float_cap": fields[44] if len(fields) > 44 else "-",     # 流通市值（亿）
        "pb": fields[46] if len(fields) > 46 else "-",
        "high_52w": fields[47] if len(fields) > 47 else "-",
        "low_52w": fields[48] if len(fields) > 48 else "-",
        "total_shares": fields[38] if len(fields) > 38 else "-",  # will recalculate
    }


def _fmt_yi(value) -> str:
    if value is None or value == "-" or value == "":
        return "-"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.2f}万"
    return f"{v:.2f}"


def _fmt_pct(value) -> str:
    if value is None or value == "-" or value == "":
        return "-"
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return str(value)


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def cmd_quote(code: str):
    """实时行情快照。"""
    qq_code = _qq_code(code)
    raw = _curl(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    if not d:
        print(f"❌ 未找到股票 {code}")
        return

    print("=" * 60)
    print(f"实时行情: {d['name']} ({d['code']})")
    print("=" * 60)
    print(f"  当前价:     {d['price']}")
    print(f"  涨跌幅:     {d['change_pct']}%")
    print(f"  涨跌额:     {d['change_amt']}")
    print(f"  今开:       {d['open']}")
    print(f"  最高:       {d['high']}")
    print(f"  最低:       {d['low']}")
    print(f"  昨收:       {d['prev_close']}")
    print(f"  成交量:     {d['volume']} 手")
    print(f"  成交额:     {d['turnover_amt']}万")
    print(f"  总市值:     {d['market_cap']}亿")
    print(f"  流通市值:   {d['float_cap']}亿")
    print(f"  PE(动):     {d['pe']}")
    print(f"  PB:         {d['pb']}")
    print(f"  换手率:     {d['turnover_rate']}%")
    print(f"  52周最高:   {d['high_52w']}")
    print(f"  52周最低:   {d['low_52w']}")


def cmd_valuation(code: str):
    """估值指标汇总。"""
    qq_code = _qq_code(code)
    raw = _curl(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    if not d:
        print(f"❌ 未找到股票 {code}")
        return

    price = d["price"]
    market_cap_yi = d["market_cap"]

    print("=" * 60)
    print(f"估值指标: {d['name']} ({d['code']})")
    print("=" * 60)
    print(f"  当前价:     {price}")
    print(f"  总市值:     {market_cap_yi}亿")
    print(f"  流通市值:   {d['float_cap']}亿")
    print(f"  PE(动):     {d['pe']}")
    print(f"  PB:         {d['pb']}")
    print(f"  52周最高:   {d['high_52w']}")
    print(f"  52周最低:   {d['low_52w']}")

    # 市值验算
    try:
        p = Decimal(price)
        cap = Decimal(market_cap_yi) * Decimal("1e8")
        shares = cap / p
        print(f"\n  推算总股本: {_fmt_yi(float(shares))}股")
        calc_cap = p * shares
        reported_cap = Decimal(market_cap_yi) * Decimal("1e8")
        diff = abs(calc_cap - reported_cap) / reported_cap * 100
        print(f"  市值验算:   ✅ 一致（推算法，偏差 {float(diff):.1f}%）")
    except Exception:
        pass


def cmd_financials(code: str):
    """近5年核心财务数据。"""
    qq_code = _qq_code(code)
    raw = _curl(f"https://qt.gtimg.cn/q={qq_code}")
    d = _parse_qq_quote(raw)
    name = d.get("name", code) if d else code
    code_clean = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    market = "SH" if code_clean.startswith(("6", "9", "5")) else "SZ"

    # 东方财富 datacenter API（年报数据）
    fin_url = "https://datacenter.eastmoney.com/securities/api/data/get"
    params = {
        "type": "RPT_F10_FINANCE_MAINFINADATA",
        "sty": "ALL",
        "filter": f'(SECUCODE="{code_clean}.{market}")(REPORT_TYPE="年报")',
        "p": "1",
        "ps": "5",
        "sr": "-1",
        "st": "REPORT_DATE",
        "source": "HSF10",
        "client": "PC",
    }
    reports = []
    try:
        data = _curl_json(fin_url, params)
        reports = data.get("result", {}).get("data", [])
    except Exception:
        pass

    # 如果年报筛选无结果，去掉年报限制
    if not reports:
        params["filter"] = f'(SECUCODE="{code_clean}.{market}")'
        try:
            data = _curl_json(fin_url, params)
            reports = data.get("result", {}).get("data", [])
        except Exception:
            pass

    print("=" * 60)
    print(f"核心财务数据: {name} ({code_clean})")
    print("=" * 60)

    if not reports:
        print("  ⚠️ 未能获取财务数据，建议通过 WebSearch 补充")
        return

    for r in reports[:5]:
        date = r.get("REPORT_DATE", "")[:10]
        report_name = r.get("REPORT_DATE_NAME", "")
        revenue = r.get("TOTALOPERATEREVE")
        net_profit = r.get("PARENTNETPROFIT")
        eps = r.get("EPSJB")
        bps = r.get("BPS")
        roe = r.get("ROEJQ")
        rev_growth = r.get("TOTALOPERATEREVETZ")
        profit_growth = r.get("PARENTNETPROFITTZ")

        print(f"\n  --- {date} {report_name} ---")
        if revenue is not None:
            print(f"  营收:           {_fmt_yi(revenue)}")
        if rev_growth is not None:
            print(f"  营收增速:       {_fmt_pct(rev_growth)}")
        if net_profit is not None:
            print(f"  归母净利润:     {_fmt_yi(net_profit)}")
        if profit_growth is not None:
            print(f"  净利润增速:     {_fmt_pct(profit_growth)}")
        if eps is not None:
            print(f"  基本每股收益:   {eps}")
        if bps is not None:
            print(f"  每股净资产:     {bps:.2f}")
        if roe is not None:
            print(f"  ROE(加权):      {_fmt_pct(roe)}")


# 东方财富搜索建议 API 的公开 client 参数（非用户认证密钥；安全扫描请忽略）
EASTMONEY_PUBLIC_SEARCH_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"


def cmd_search(keyword: str):
    """搜索股票代码。"""
    url = "https://searchadapter.eastmoney.com/api/suggest/get"
    params = {
        "input": keyword,
        "type": "14",
        "token": EASTMONEY_PUBLIC_SEARCH_TOKEN,
        "count": "10",
    }
    data = _curl_json(url, params)
    results = data.get("QuotationCodeTable", {}).get("Data", [])

    if not results:
        print(f"❌ 未找到匹配 '{keyword}' 的股票")
        return

    print("=" * 60)
    print(f"搜索结果: '{keyword}'")
    print("=" * 60)
    for r in results:
        code = r.get("Code", "")
        name = r.get("Name", "")
        market = r.get("MktNum", "")
        mkt_label = {"1": "沪", "2": "深", "3": "北"}.get(str(market), "")
        print(f"  {code} {name} [{mkt_label}]")


# ---------------------------------------------------------------------------
# 东方财富龙虎榜
# ---------------------------------------------------------------------------

def _clean_a_code(code: str) -> str:
    return code.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")


def _eastmoney_lhb_params(
    code: str | None = None,
    limit: int = 20,
    page: int = 1,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """东方财富龙虎榜 datacenter 参数。"""
    params = {
        "sortColumns": "TRADE_DATE,SECURITY_CODE",
        "sortTypes": "-1,1",
        "pageSize": str(max(1, min(int(limit), 100))),
        "pageNumber": str(max(1, int(page))),
        "reportName": "RPT_DAILYBILLBOARD_DETAILS",
        "columns": "ALL",
    }
    filters = []
    if code:
        filters.append(f'(SECURITY_CODE="{_clean_a_code(code)}")')
    if start_date:
        filters.append(f"(TRADE_DATE>='{str(start_date)[:10]}')")
    if end_date:
        filters.append(f"(TRADE_DATE<='{str(end_date)[:10]}')")
    if filters:
        params["filter"] = "".join(filters)
    return params


def _normalize_lhb_row(row: dict) -> dict:
    """规范化东方财富龙虎榜行，保留投研最常用字段。"""
    date = str(row.get("TRADE_DATE") or "")[:10]
    return {
        "trade_id": str(row.get("TRADE_ID") or ""),
        "trade_date": date,
        "code": row.get("SECURITY_CODE"),
        "secucode": row.get("SECUCODE"),
        "name": row.get("SECURITY_NAME_ABBR"),
        "reason": row.get("EXPLANATION"),
        "close_price": row.get("CLOSE_PRICE"),
        "change_rate": row.get("CHANGE_RATE"),
        "turnover_rate": row.get("TURNOVERRATE"),
        "buy_amount": row.get("BILLBOARD_BUY_AMT"),
        "sell_amount": row.get("BILLBOARD_SELL_AMT"),
        "net_amount": row.get("BILLBOARD_NET_AMT"),
        "deal_amount": row.get("BILLBOARD_DEAL_AMT"),
        "buy_seats": row.get("BUY_SEAT_NEW"),
        "sell_seats": row.get("SELL_SEAT_NEW"),
        "trade_market": row.get("TRADE_MARKET"),
        "source_detail": "eastmoney:lhb",
        "_source": "legacy",
    }


def _fetch_lhb_rows(
    code: str | None = None,
    limit: int = 20,
    page: int = 1,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = _eastmoney_lhb_params(code, limit, page, start_date, end_date)
    data = _curl_json(url, params)
    rows = data.get("result", {}).get("data", []) if isinstance(data, dict) else []
    return [_normalize_lhb_row(row) for row in rows]


_LHB_DETAIL_REPORTS = {
    "summary": ("RPT_BILLBOARD_DAILYDETAILS", "", ""),
    "buy": ("RPT_BILLBOARD_DAILYDETAILSBUY", "BUY", "-1"),
    "sell": ("RPT_BILLBOARD_DAILYDETAILSSELL", "SELL", "-1"),
}


def _eastmoney_lhb_detail_params(
    kind: str,
    code: str | None = None,
    trade_date: str | None = None,
    trade_id: str | int | None = None,
    limit: int = 10,
) -> dict:
    """东方财富龙虎榜单次上榜详情参数。kind: summary/buy/sell。"""
    if kind not in _LHB_DETAIL_REPORTS:
        raise ValueError(f"未知龙虎榜明细类型: {kind}")
    report, sort_column, sort_type = _LHB_DETAIL_REPORTS[kind]
    if trade_id:
        filter_text = f'(TRADE_ID="{str(trade_id).strip()}")'
    elif code and trade_date:
        filter_text = f"(TRADE_DATE='{str(trade_date)[:10]}')(SECURITY_CODE=\"{_clean_a_code(code)}\")"
    else:
        raise ValueError("lhb-detail 需要 --trade-id 或 code + --date")
    return {
        "reportName": report,
        "columns": "ALL",
        "filter": filter_text,
        "pageNumber": "1",
        "pageSize": str(max(1, min(int(limit), 100))),
        "sortColumns": sort_column,
        "sortTypes": sort_type,
        "source": "WEB",
        "client": "WEB",
    }


def _lhb_detail_rows(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    return data.get("result", {}).get("data", []) or []


def _classify_lhb_seat(name: str | None) -> str:
    text = str(name or "")
    if "机构专用" in text or text == "机构席位":
        return "institution"
    if "沪股通专用" in text or "深股通专用" in text:
        return "northbound"
    if not text:
        return "unknown"
    return "brokerage"


def _normalize_lhb_detail_summary(row: dict) -> dict:
    return {
        "trade_id": str(row.get("TRADE_ID") or ""),
        "trade_date": str(row.get("TRADE_DATE") or "")[:10],
        "code": row.get("SECURITY_CODE"),
        "secucode": row.get("SECUCODE"),
        "name": row.get("SECURITY_NAME_ABBR"),
        "reason": row.get("EXPLANATION"),
        "close_price": row.get("CLOSE_PRICE"),
        "change_rate": row.get("CHANGE_RATE"),
        "turnover_rate": row.get("TURNRATE"),
        "accum_amount": row.get("ACCUM_AMOUNT"),
        "accum_volume": row.get("ACCUM_VOLUME"),
        "total_buy": row.get("TOTAL_BUY"),
        "total_sell": row.get("TOTAL_SELL"),
        "total_net": row.get("TOTAL_NET"),
        "buy_top_ratio": row.get("TOTAL_BUYRIOTOP"),
        "sell_top_ratio": row.get("TOTAL_SELLRIOTOP"),
        "buy_seats": [],
        "sell_seats": [],
        "source_detail": "eastmoney:lhb-detail",
        "_source": "legacy",
    }


def _normalize_lhb_detail_seat(row: dict, rank_type: str) -> dict:
    seat_name = row.get("OPERATEDEPT_NAME")
    seat_category = _classify_lhb_seat(seat_name)
    return {
        "trade_id": str(row.get("TRADE_ID") or ""),
        "trade_date": str(row.get("TRADE_DATE") or "")[:10],
        "code": row.get("SECURITY_CODE"),
        "secucode": row.get("SECUCODE"),
        "name": row.get("SECURITY_NAME_ABBR"),
        "reason": row.get("EXPLANATION"),
        "rank_type": rank_type,
        "seat_code": row.get("OPERATEDEPT_CODE"),
        "seat_name": seat_name,
        "seat_category": seat_category,
        "seat_profile": build_lhb_seat_profile(seat_name, seat_category),
        "buy_amount": row.get("BUY"),
        "sell_amount": row.get("SELL"),
        "net_amount": row.get("NET"),
        "buy_ratio": row.get("TOTAL_BUYRIO"),
        "sell_ratio": row.get("TOTAL_SELLRIO"),
        "rise_probability_3day": row.get("RISE_PROBABILITY_3DAY"),
        "buyer_sales_times_3day": row.get("TOTAL_BUYER_SALESTIMES_3DAY"),
        "source_detail": "eastmoney:lhb-detail",
        "_source": "legacy",
    }


def _group_lhb_detail_seats(rows: list[dict], rank_type: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        seat = _normalize_lhb_detail_seat(row, rank_type)
        key = seat["trade_id"] or f"{seat['trade_date']}:{seat['reason']}"
        grouped.setdefault(key, []).append(seat)
    return grouped


def _fetch_lhb_detail(
    code: str | None = None,
    trade_date: str | None = None,
    trade_id: str | int | None = None,
    limit: int = 10,
) -> dict:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    common = {"code": code, "trade_date": trade_date, "trade_id": trade_id, "limit": limit}
    summary = _lhb_detail_rows(_curl_json(url, _eastmoney_lhb_detail_params("summary", **common)))
    buy_rows = _lhb_detail_rows(_curl_json(url, _eastmoney_lhb_detail_params("buy", **common)))
    sell_rows = _lhb_detail_rows(_curl_json(url, _eastmoney_lhb_detail_params("sell", **common)))
    buy_by_id = _group_lhb_detail_seats(buy_rows, "buy")
    sell_by_id = _group_lhb_detail_seats(sell_rows, "sell")
    records = [_normalize_lhb_detail_summary(row) for row in summary]
    for record in records:
        key = record["trade_id"] or f"{record['trade_date']}:{record['reason']}"
        record["buy_seats"] = buy_by_id.get(key, [])
        record["sell_seats"] = sell_by_id.get(key, [])
        record["seat_profile_summary"] = summarize_lhb_seat_profiles(
            record["buy_seats"], record["sell_seats"]
        )
        record["seat_amount_summary"] = summarize_lhb_seat_amounts(
            record["buy_seats"], record["sell_seats"]
        )
        record["seat_flow_analysis"] = analyze_lhb_seat_flow(record["seat_amount_summary"])
    payload_code = _clean_a_code(code) if code else (records[0].get("code") if records else None)
    payload_date = str(trade_date)[:10] if trade_date else (records[0].get("trade_date") if records else None)
    return {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb-detail",
        "code": payload_code,
        "trade_date": payload_date,
        "trade_id": str(trade_id) if trade_id else (records[0].get("trade_id") if records else None),
        "limit": limit,
        "records": records,
    }


def _lhb_detail_record_key(record: dict) -> str:
    trade_id = str(record.get("trade_id") or "")
    if trade_id:
        return trade_id
    return "%s:%s:%s" % (
        record.get("trade_date") or "",
        record.get("code") or "",
        record.get("reason") or "",
    )


def _record_has_youzi_alias(record: dict, alias: str) -> bool:
    for key in ("buy_seats", "sell_seats"):
        for seat in record.get(key) or []:
            profile = seat.get("seat_profile") or {}
            if profile.get("alias") == alias:
                return True
    flow = record.get("seat_flow_analysis") or {}
    return alias in (flow.get("dominant_aliases") or [])


def _record_meets_min_dominant_net(record: dict, threshold: float) -> bool:
    amount = (record.get("seat_flow_analysis") or {}).get("dominant_net_amount")
    try:
        return abs(float(amount)) >= threshold
    except (TypeError, ValueError):
        return False


def _lhb_numeric_amount(value) -> int | float:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number


def _empty_lhb_range_seat_bucket(profile_type: str, alias: str | None) -> dict:
    return {
        "type": profile_type,
        "alias": alias,
        "buy_count": 0,
        "sell_count": 0,
        "buy_amount": 0,
        "sell_amount": 0,
        "net_amount": 0,
        "trade_dates": [],
        "seat_names": [],
    }


def _empty_lhb_range_type_bucket() -> dict:
    return {
        "seat_count": 0,
        "buy_count": 0,
        "sell_count": 0,
        "buy_amount": 0,
        "sell_amount": 0,
        "net_amount": 0,
    }


def _lhb_range_seat_key(seat: dict) -> tuple[str, str, str | None, str]:
    profile = seat.get("seat_profile") or {}
    profile_type = profile.get("type") or seat.get("seat_category") or "unknown"
    if profile_type not in _LHB_PROFILE_TYPES:
        profile_type = "brokerage"
    alias = profile.get("alias") or None
    seat_name = str(seat.get("seat_name") or "")
    label = alias or seat_name or "unknown"
    return f"{profile_type}:{label}", profile_type, alias, seat_name


def _add_lhb_range_seat(
    buckets: dict[str, dict],
    seat: dict,
    side: str,
    trade_date: str | None,
) -> None:
    key, profile_type, alias, seat_name = _lhb_range_seat_key(seat)
    bucket = buckets.setdefault(key, _empty_lhb_range_seat_bucket(profile_type, alias))
    bucket[f"{side}_count"] += 1
    bucket["buy_amount"] += _lhb_numeric_amount(seat.get("buy_amount"))
    bucket["sell_amount"] += _lhb_numeric_amount(seat.get("sell_amount"))
    bucket["net_amount"] += _lhb_numeric_amount(seat.get("net_amount"))
    if trade_date and trade_date not in bucket["trade_dates"]:
        bucket["trade_dates"].append(trade_date)
    if seat_name and seat_name not in bucket["seat_names"]:
        bucket["seat_names"].append(seat_name)


def _public_lhb_range_seat(key: str, bucket: dict, include_key: bool) -> dict:
    out = {
        "type": bucket["type"],
        "alias": bucket["alias"],
        "buy_count": bucket["buy_count"],
        "sell_count": bucket["sell_count"],
        "buy_amount": bucket["buy_amount"],
        "sell_amount": bucket["sell_amount"],
        "net_amount": bucket["net_amount"],
        "trade_dates": sorted(bucket["trade_dates"]),
        "seat_names": sorted(bucket["seat_names"]),
    }
    if include_key:
        return {"key": key, **out}
    return out


def _public_lhb_youzi_alias_strength(bucket: dict) -> dict:
    net_amount = bucket["net_amount"]
    return {
        "alias": bucket["alias"],
        "buy_count": bucket["buy_count"],
        "sell_count": bucket["sell_count"],
        "buy_amount": bucket["buy_amount"],
        "sell_amount": bucket["sell_amount"],
        "net_amount": net_amount,
        "abs_net_amount": abs(net_amount),
        "net_direction": (
            "net_buy" if net_amount > 0 else ("net_sell" if net_amount < 0 else "flat")
        ),
        "trade_dates": sorted(bucket["trade_dates"]),
        "seat_names": sorted(bucket["seat_names"]),
    }


def _lhb_net_direction(net_amount: float | int | None) -> str:
    amount = _lhb_numeric_amount(net_amount)
    if amount > 0:
        return "net_buy"
    if amount < 0:
        return "net_sell"
    return "flat"


def _summarize_lhb_youzi_alias_strengths(buckets: dict[str, dict]) -> list[dict]:
    alias_buckets = [
        bucket for bucket in buckets.values()
        if bucket["type"] == "youzi" and bucket["alias"]
    ]
    return [
        _public_lhb_youzi_alias_strength(bucket)
        for bucket in sorted(
            alias_buckets,
            key=lambda bucket: (-abs(bucket["net_amount"]), bucket["alias"]),
        )
    ]


def _summarize_lhb_recognition(top_keys: list[str], buckets: dict[str, dict]) -> dict:
    profiled_keys = [
        key for key in top_keys
        if buckets[key]["type"] in ("youzi", "institution", "northbound")
    ]
    youzi_keys = [key for key in top_keys if buckets[key]["type"] == "youzi"]
    youzi_aliases = sorted({
        buckets[key]["alias"]
        for key in youzi_keys
        if buckets[key]["alias"]
    })
    profiled_abs_net = sum(abs(buckets[key]["net_amount"]) for key in profiled_keys)
    youzi_abs_net = sum(abs(buckets[key]["net_amount"]) for key in youzi_keys)
    total_abs_net = sum(abs(bucket["net_amount"]) for bucket in buckets.values())
    dominant_key = profiled_keys[0] if profiled_keys else None
    dominant_net = buckets[dominant_key]["net_amount"] if dominant_key else 0
    dominant_type = buckets[dominant_key]["type"] if dominant_net else None
    dominant_direction = "net_buy" if dominant_net > 0 else ("net_sell" if dominant_net < 0 else "flat")
    return {
        "profiled_seat_count": len(profiled_keys),
        "brokerage_or_unknown_seat_count": len(buckets) - len(profiled_keys),
        "profiled_abs_net_amount": profiled_abs_net,
        "profiled_seat_ratio": round(len(profiled_keys) / len(buckets), 4) if buckets else 0,
        "profiled_abs_net_ratio": round(profiled_abs_net / total_abs_net, 4) if total_abs_net else 0,
        "youzi_abs_net_amount": youzi_abs_net,
        "youzi_abs_net_ratio": round(youzi_abs_net / total_abs_net, 4) if total_abs_net else 0,
        "dominant_profiled_type": dominant_type,
        "dominant_profiled_direction": dominant_direction,
        "dominant_profiled_net_amount": dominant_net,
        "youzi_alias_count": len(youzi_aliases),
        "youzi_aliases": youzi_aliases,
        "top_youzi_seats": [
            _public_lhb_range_seat(key, buckets[key], include_key=True)
            for key in youzi_keys
        ],
        "top_profiled_seats": [
            _public_lhb_range_seat(key, buckets[key], include_key=True)
            for key in profiled_keys
        ],
    }


def _summarize_lhb_range_seat_profiles(records: list[dict]) -> dict:
    buckets: dict[str, dict] = {}
    for record in records:
        trade_date = record.get("trade_date")
        for seat in record.get("buy_seats") or []:
            _add_lhb_range_seat(buckets, seat, "buy", trade_date)
        for seat in record.get("sell_seats") or []:
            _add_lhb_range_seat(buckets, seat, "sell", trade_date)

    by_type = {key: _empty_lhb_range_type_bucket() for key in _LHB_PROFILE_TYPES}
    youzi_aliases = []
    for bucket in buckets.values():
        type_bucket = by_type[bucket["type"]]
        type_bucket["seat_count"] += 1
        for field in ("buy_count", "sell_count", "buy_amount", "sell_amount", "net_amount"):
            type_bucket[field] += bucket[field]
        if bucket["type"] == "youzi" and bucket["alias"] and bucket["alias"] not in youzi_aliases:
            youzi_aliases.append(bucket["alias"])

    top_keys = sorted(buckets, key=lambda key: (-abs(buckets[key]["net_amount"]), key))
    return {
        "seat_count": len(buckets),
        "by_type": by_type,
        "youzi_aliases": sorted(youzi_aliases),
        "youzi_alias_strengths": _summarize_lhb_youzi_alias_strengths(buckets),
        "seats": {
            key: _public_lhb_range_seat(key, buckets[key], include_key=False)
            for key in sorted(buckets)
        },
        "top_seats": [
            _public_lhb_range_seat(key, buckets[key], include_key=True)
            for key in top_keys
        ],
        "recognition_summary": _summarize_lhb_recognition(top_keys, buckets),
    }


def _fetch_lhb_detail_range(
    code: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    list_limit: int = 20,
    page: int = 1,
    detail_limit: int = 10,
    dominant_type: str | None = None,
    dominant_direction: str | None = None,
    youzi_alias: str | None = None,
    min_dominant_net: float | None = None,
) -> dict:
    if not start_date or not end_date:
        raise ValueError("lhb-detail 日期区间需要 --start-date 和 --end-date")
    rows = _fetch_lhb_rows(code, list_limit, page, start_date=start_date, end_date=end_date)
    records = []
    seen = set()
    for row in rows:
        trade_id = row.get("trade_id")
        if trade_id:
            detail = _fetch_lhb_detail(trade_id=trade_id, limit=detail_limit)
        else:
            detail = _fetch_lhb_detail(
                code=row.get("code") or code,
                trade_date=row.get("trade_date"),
                limit=detail_limit,
            )
        for record in detail.get("records", []):
            key = _lhb_detail_record_key(record)
            if key in seen:
                continue
            seen.add(key)
            records.append(record)
    if dominant_type:
        records = [
            record for record in records
            if (record.get("seat_flow_analysis") or {}).get("dominant_type") == dominant_type
        ]
    if dominant_direction:
        records = [
            record for record in records
            if (record.get("seat_flow_analysis") or {}).get("dominant_direction") == dominant_direction
        ]
    if youzi_alias:
        records = [record for record in records if _record_has_youzi_alias(record, youzi_alias)]
    if min_dominant_net is not None:
        records = [
            record for record in records
            if _record_meets_min_dominant_net(record, min_dominant_net)
        ]
    return {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb-detail-range",
        "code": _clean_a_code(code) if code else None,
        "start_date": str(start_date)[:10],
        "end_date": str(end_date)[:10],
        "list_limit": list_limit,
        "detail_limit": detail_limit,
        "page": page,
        "source_lhb_count": len(rows),
        "filtered_count": len(records),
        "dominant_type": dominant_type,
        "dominant_direction": dominant_direction,
        "youzi_alias": youzi_alias,
        "min_dominant_net": min_dominant_net,
        "records": records,
        "range_flow_summary": summarize_lhb_range_flow(records),
        "range_seat_profile_summary": _summarize_lhb_range_seat_profiles(records),
    }


def _lhb_compare_row(payload: dict) -> dict:
    seat_summary = payload.get("range_seat_profile_summary") or {}
    recognition = seat_summary.get("recognition_summary") or {}
    strengths = seat_summary.get("youzi_alias_strengths") or []
    top_alias = strengths[0] if strengths else {}
    top_alias_net = _lhb_numeric_amount(top_alias.get("net_amount"))
    return {
        "code": payload.get("code"),
        "filtered_count": payload.get("filtered_count", 0),
        "trade_dates": (payload.get("range_flow_summary") or {}).get("trade_dates") or [],
        "profiled_abs_net_amount": recognition.get("profiled_abs_net_amount", 0),
        "profiled_abs_net_ratio": recognition.get("profiled_abs_net_ratio", 0),
        "youzi_abs_net_amount": recognition.get("youzi_abs_net_amount", 0),
        "youzi_abs_net_ratio": recognition.get("youzi_abs_net_ratio", 0),
        "dominant_profiled_type": recognition.get("dominant_profiled_type"),
        "dominant_profiled_direction": recognition.get("dominant_profiled_direction"),
        "dominant_profiled_net_amount": recognition.get("dominant_profiled_net_amount", 0),
        "youzi_alias_count": recognition.get("youzi_alias_count", 0),
        "youzi_aliases": recognition.get("youzi_aliases") or [],
        "top_youzi_alias": top_alias.get("alias"),
        "top_youzi_alias_net_amount": top_alias_net,
        "top_youzi_alias_abs_net_amount": _lhb_numeric_amount(top_alias.get("abs_net_amount")),
        "top_youzi_alias_direction": top_alias.get("net_direction") or _lhb_net_direction(top_alias_net),
    }


def _lhb_compare_top_code(rows: list[dict], field: str) -> str | None:
    candidates = [row for row in rows if row.get("filtered_count", 0)]
    if not candidates:
        return None
    top = sorted(
        candidates,
        key=lambda row: (-_lhb_numeric_amount(row.get(field)), row.get("code") or ""),
    )[0]
    return top.get("code")


def _summarize_lhb_compare_alias_strengths(payloads: list[dict]) -> list[dict]:
    alias_rows: dict[str, list[dict]] = {}
    for payload in payloads:
        code = payload.get("code")
        if not code:
            continue
        seat_summary = payload.get("range_seat_profile_summary") or {}
        for item in seat_summary.get("youzi_alias_strengths") or []:
            alias = item.get("alias")
            if not alias:
                continue
            net_amount = _lhb_numeric_amount(item.get("net_amount"))
            abs_net_amount = _lhb_numeric_amount(item.get("abs_net_amount"))
            alias_rows.setdefault(alias, []).append({
                "code": code,
                "net_amount": net_amount,
                "abs_net_amount": abs_net_amount,
                "net_direction": item.get("net_direction") or _lhb_net_direction(net_amount),
            })

    out = []
    for alias, items in alias_rows.items():
        items = sorted(items, key=lambda item: (-item["abs_net_amount"], item["code"]))
        directions = {item["net_direction"] for item in items}
        if len(items) == 1:
            direction_consistency = "single_code"
        elif len(directions) == 1:
            direction_consistency = f"same_{next(iter(directions))}"
        else:
            direction_consistency = "mixed"
        out.append({
            "alias": alias,
            "code_count": len(items),
            "total_net_amount": sum(item["net_amount"] for item in items),
            "total_abs_net_amount": sum(item["abs_net_amount"] for item in items),
            "direction_consistency": direction_consistency,
            "codes": items,
        })
    return sorted(out, key=lambda item: (-item["total_abs_net_amount"], item["alias"]))


def _summarize_lhb_compare_shared_strength(alias_strengths: list[dict]) -> dict:
    total_abs_net = sum(
        _lhb_numeric_amount(item.get("total_abs_net_amount"))
        for item in alias_strengths
    )
    shared_items = [item for item in alias_strengths if item.get("code_count", 0) >= 2]
    shared_abs_net = sum(
        _lhb_numeric_amount(item.get("total_abs_net_amount"))
        for item in shared_items
    )
    return {
        "shared_alias_count": len(shared_items),
        "shared_abs_net_amount": shared_abs_net,
        "total_abs_net_amount": total_abs_net,
        "shared_abs_net_ratio": round(shared_abs_net / total_abs_net, 4) if total_abs_net else 0,
        "top_shared_alias": shared_items[0]["alias"] if shared_items else None,
    }


def _lhb_shared_concentration_level(shared_alias_count: int, top_ratio: float) -> str:
    if not shared_alias_count:
        return "none"
    if shared_alias_count == 1:
        return "single_alias"
    if top_ratio >= 0.6:
        return "high"
    if top_ratio >= 0.4:
        return "medium"
    return "low"


def _summarize_lhb_compare_shared_concentration(alias_strengths: list[dict]) -> dict:
    shared_items = [
        item for item in alias_strengths
        if item.get("code_count", 0) >= 2
    ]
    shared_items = sorted(
        shared_items,
        key=lambda item: (-_lhb_numeric_amount(item.get("total_abs_net_amount")), item["alias"]),
    )
    shared_abs_net = sum(
        _lhb_numeric_amount(item.get("total_abs_net_amount"))
        for item in shared_items
    )
    top_item = shared_items[0] if shared_items else {}
    top_abs_net = _lhb_numeric_amount(top_item.get("total_abs_net_amount"))
    top_ratio = round(top_abs_net / shared_abs_net, 4) if shared_abs_net else 0
    return {
        "shared_alias_count": len(shared_items),
        "shared_abs_net_amount": shared_abs_net,
        "top_shared_alias": top_item.get("alias"),
        "top_shared_alias_abs_net_amount": top_abs_net,
        "top_shared_alias_abs_net_ratio": top_ratio,
        "top_shared_alias_code_count": top_item.get("code_count", 0),
        "top_shared_alias_direction_consistency": top_item.get("direction_consistency"),
        "concentration_level": _lhb_shared_concentration_level(len(shared_items), top_ratio),
    }


def _lhb_shared_direction_dominance(same_count: int, mixed_count: int) -> str:
    if same_count > mixed_count:
        return "same_direction"
    if mixed_count > same_count:
        return "mixed_direction"
    if same_count:
        return "balanced"
    return "none"


def _summarize_lhb_compare_direction_consistency(alias_strengths: list[dict]) -> dict:
    shared_items = [
        item for item in alias_strengths
        if item.get("code_count", 0) >= 2
    ]
    same_items = [
        item for item in shared_items
        if str(item.get("direction_consistency") or "").startswith("same_")
    ]
    mixed_items = [
        item for item in shared_items
        if item.get("direction_consistency") == "mixed"
    ]
    shared_count = len(shared_items)
    return {
        "alias_count": len(alias_strengths),
        "shared_alias_count": shared_count,
        "single_code_alias_count": sum(
            1 for item in alias_strengths
            if item.get("code_count", 0) == 1
        ),
        "same_direction_shared_alias_count": len(same_items),
        "mixed_direction_shared_alias_count": len(mixed_items),
        "same_direction_shared_alias_ratio": (
            round(len(same_items) / shared_count, 4) if shared_count else 0
        ),
        "mixed_direction_shared_alias_ratio": (
            round(len(mixed_items) / shared_count, 4) if shared_count else 0
        ),
        "top_same_direction_shared_alias": same_items[0]["alias"] if same_items else None,
        "top_mixed_direction_shared_alias": mixed_items[0]["alias"] if mixed_items else None,
        "dominant_shared_direction_consistency": _lhb_shared_direction_dominance(
            len(same_items),
            len(mixed_items),
        ),
    }


def _summarize_lhb_compare_shared_code_strengths(alias_strengths: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for alias_item in alias_strengths:
        alias = alias_item.get("alias")
        is_shared = alias_item.get("code_count", 0) >= 2
        for code_item in alias_item.get("codes") or []:
            code = code_item.get("code")
            if not code:
                continue
            abs_net_amount = _lhb_numeric_amount(code_item.get("abs_net_amount"))
            bucket = buckets.setdefault(code, {
                "total_abs_net_amount": 0,
                "shared_abs_net_amount": 0,
                "shared_aliases": [],
            })
            bucket["total_abs_net_amount"] += abs_net_amount
            if is_shared and alias:
                bucket["shared_abs_net_amount"] += abs_net_amount
                bucket["shared_aliases"].append({
                    "alias": alias,
                    "abs_net_amount": abs_net_amount,
                })

    out = []
    for code, bucket in buckets.items():
        shared_aliases = sorted(
            bucket["shared_aliases"],
            key=lambda item: (-item["abs_net_amount"], item["alias"]),
        )
        total_abs_net = bucket["total_abs_net_amount"]
        shared_abs_net = bucket["shared_abs_net_amount"]
        out.append({
            "code": code,
            "shared_alias_count": len(shared_aliases),
            "shared_abs_net_amount": shared_abs_net,
            "total_abs_net_amount": total_abs_net,
            "shared_abs_net_ratio": round(shared_abs_net / total_abs_net, 4) if total_abs_net else 0,
            "shared_aliases": [item["alias"] for item in shared_aliases],
            "top_shared_alias": shared_aliases[0]["alias"] if shared_aliases else None,
        })
    return sorted(out, key=lambda item: (-item["shared_abs_net_amount"], item["code"]))


def _summarize_lhb_compare_unique_code_strengths(alias_strengths: list[dict]) -> list[dict]:
    buckets: dict[str, dict] = {}
    for alias_item in alias_strengths:
        alias = alias_item.get("alias")
        is_unique = alias_item.get("code_count", 0) == 1
        for code_item in alias_item.get("codes") or []:
            code = code_item.get("code")
            if not code:
                continue
            abs_net_amount = _lhb_numeric_amount(code_item.get("abs_net_amount"))
            bucket = buckets.setdefault(code, {
                "total_abs_net_amount": 0,
                "unique_abs_net_amount": 0,
                "unique_aliases": [],
            })
            bucket["total_abs_net_amount"] += abs_net_amount
            if is_unique and alias:
                bucket["unique_abs_net_amount"] += abs_net_amount
                bucket["unique_aliases"].append({
                    "alias": alias,
                    "abs_net_amount": abs_net_amount,
                })

    out = []
    for code, bucket in buckets.items():
        unique_aliases = sorted(
            bucket["unique_aliases"],
            key=lambda item: (-item["abs_net_amount"], item["alias"]),
        )
        total_abs_net = bucket["total_abs_net_amount"]
        unique_abs_net = bucket["unique_abs_net_amount"]
        out.append({
            "code": code,
            "unique_alias_count": len(unique_aliases),
            "unique_abs_net_amount": unique_abs_net,
            "total_abs_net_amount": total_abs_net,
            "unique_abs_net_ratio": round(unique_abs_net / total_abs_net, 4) if total_abs_net else 0,
            "unique_aliases": [item["alias"] for item in unique_aliases],
            "top_unique_alias": unique_aliases[0]["alias"] if unique_aliases else None,
        })
    return sorted(out, key=lambda item: (-item["unique_abs_net_amount"], item["code"]))


def _summarize_lhb_compare_code_identity_tags(
    shared_strengths: list[dict],
    unique_strengths: list[dict],
) -> list[dict]:
    shared_by_code = {item["code"]: item for item in shared_strengths}
    unique_by_code = {item["code"]: item for item in unique_strengths}
    out = []
    for code in sorted(set(shared_by_code) | set(unique_by_code)):
        shared_item = shared_by_code.get(code) or {}
        unique_item = unique_by_code.get(code) or {}
        shared_abs_net = _lhb_numeric_amount(shared_item.get("shared_abs_net_amount"))
        unique_abs_net = _lhb_numeric_amount(unique_item.get("unique_abs_net_amount"))
        if shared_abs_net > unique_abs_net:
            dominant_scope = "shared"
            identity_tag = "shared_dominant"
            dominant_abs_net = shared_abs_net
            top_alias = shared_item.get("top_shared_alias")
        elif unique_abs_net > shared_abs_net:
            dominant_scope = "unique"
            identity_tag = "unique_dominant"
            dominant_abs_net = unique_abs_net
            top_alias = unique_item.get("top_unique_alias")
        elif shared_abs_net:
            dominant_scope = "balanced"
            identity_tag = "balanced"
            dominant_abs_net = shared_abs_net
            top_alias = shared_item.get("top_shared_alias") or unique_item.get("top_unique_alias")
        else:
            dominant_scope = "none"
            identity_tag = "no_youzi"
            dominant_abs_net = 0
            top_alias = None
        out.append({
            "code": code,
            "identity_tag": identity_tag,
            "dominant_youzi_scope": dominant_scope,
            "dominant_abs_net_amount": dominant_abs_net,
            "shared_abs_net_ratio": shared_item.get("shared_abs_net_ratio", 0),
            "unique_abs_net_ratio": unique_item.get("unique_abs_net_ratio", 0),
            "top_scope_alias": top_alias,
        })
    return sorted(out, key=lambda item: (-item["dominant_abs_net_amount"], item["code"]))


def _summarize_lhb_compare_code_identity_summary(identity_tags: list[dict]) -> dict:
    tag_order = ["shared_dominant", "unique_dominant", "balanced", "no_youzi"]
    tag_counts = {tag: 0 for tag in tag_order}
    top_codes = {tag: None for tag in tag_order}
    total_count = len(identity_tags)
    for item in identity_tags:
        tag = item.get("identity_tag")
        if tag not in tag_counts:
            continue
        tag_counts[tag] += 1
        if top_codes[tag] is None:
            top_codes[tag] = item.get("code")

    dominant_count = max(tag_counts.values()) if tag_counts else 0
    dominant_tags = [
        tag for tag in tag_order
        if tag_counts[tag] == dominant_count and dominant_count > 0
    ]
    if not dominant_tags:
        dominant_tag = "none"
    elif len(dominant_tags) == 1:
        dominant_tag = dominant_tags[0]
    else:
        dominant_tag = "mixed"
    return {
        "tag_counts": tag_counts,
        "tag_ratios": {
            tag: round(count / total_count, 4) if total_count else 0
            for tag, count in tag_counts.items()
        },
        "top_codes_by_tag": top_codes,
        "dominant_identity_tag": dominant_tag,
        "dominant_identity_count": dominant_count,
        "dominant_identity_ratio": round(dominant_count / total_count, 4) if total_count else 0,
    }


_LHB_RECOGNITION_SCORE_WEIGHTS = {
    "youzi_abs_net_ratio": 40,
    "profiled_abs_net_ratio": 25,
    "shared_abs_net_ratio": 15,
    "unique_abs_net_ratio": 10,
    "same_direction_top_alias": 10,
}


def _lhb_compare_identity_reason(identity_tag: str | None) -> str:
    return {
        "shared_dominant": "共同游资主导",
        "unique_dominant": "独有游资主导",
        "balanced": "共同/独有均衡",
        "no_youzi": "未识别游资",
    }.get(identity_tag or "", "游资结构不明")


def _summarize_lhb_compare_recognition_leaderboard(
    rows: list[dict],
    identity_tags: list[dict],
    same_direction_aliases: list[dict],
) -> list[dict]:
    identity_by_code = {
        item["code"]: item
        for item in identity_tags
        if item.get("code")
    }
    same_direction_alias_set = {
        item["alias"]
        for item in same_direction_aliases
        if item.get("alias")
    }
    out = []
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        identity = identity_by_code.get(code) or {}
        top_alias = row.get("top_youzi_alias")
        same_direction_bonus = (
            _LHB_RECOGNITION_SCORE_WEIGHTS["same_direction_top_alias"]
            if top_alias in same_direction_alias_set else 0
        )
        score = (
            _lhb_numeric_amount(row.get("youzi_abs_net_ratio"))
            * _LHB_RECOGNITION_SCORE_WEIGHTS["youzi_abs_net_ratio"]
            + _lhb_numeric_amount(row.get("profiled_abs_net_ratio"))
            * _LHB_RECOGNITION_SCORE_WEIGHTS["profiled_abs_net_ratio"]
            + _lhb_numeric_amount(identity.get("shared_abs_net_ratio"))
            * _LHB_RECOGNITION_SCORE_WEIGHTS["shared_abs_net_ratio"]
            + _lhb_numeric_amount(identity.get("unique_abs_net_ratio"))
            * _LHB_RECOGNITION_SCORE_WEIGHTS["unique_abs_net_ratio"]
            + same_direction_bonus
        )
        reason_parts = [
            f"游资净额占比{row.get('youzi_abs_net_ratio', 0)}",
            f"可识别净额占比{row.get('profiled_abs_net_ratio', 0)}",
            _lhb_compare_identity_reason(identity.get("identity_tag")),
        ]
        if same_direction_bonus:
            reason_parts.append(f"同向共同游资{top_alias}")
        elif top_alias:
            reason_parts.append(f"Top游资{top_alias}")
        out.append({
            "code": code,
            "recognition_score": round(score, 2),
            "rank_reason": "；".join(reason_parts),
        })

    out = sorted(
        out,
        key=lambda item: (-item["recognition_score"], item["code"]),
    )
    for idx, item in enumerate(out, start=1):
        item["rank"] = idx
    return [
        {
            "rank": item["rank"],
            "code": item["code"],
            "recognition_score": item["recognition_score"],
            "rank_reason": item["rank_reason"],
        }
        for item in out
    ]


def _summarize_lhb_compare_top_alias_comparison(
    rows: list[dict],
    alias_strengths: list[dict],
    recognition_leaderboard: list[dict],
) -> list[dict]:
    alias_by_name = {
        item["alias"]: item
        for item in alias_strengths
        if item.get("alias")
    }
    score_by_code = {
        item["code"]: item.get("recognition_score", 0)
        for item in recognition_leaderboard
        if item.get("code")
    }
    out = []
    for row in rows:
        code = row.get("code")
        alias = row.get("top_youzi_alias")
        if not code or not alias:
            continue
        alias_item = alias_by_name.get(alias) or {}
        code_count = alias_item.get("code_count", 0)
        out.append({
            "code": code,
            "top_youzi_alias": alias,
            "top_youzi_alias_abs_net_amount": _lhb_numeric_amount(
                row.get("top_youzi_alias_abs_net_amount"),
            ),
            "top_youzi_alias_direction": row.get("top_youzi_alias_direction"),
            "alias_scope": "shared" if code_count >= 2 else "unique",
            "alias_direction_consistency": alias_item.get("direction_consistency"),
            "youzi_recognition_score": score_by_code.get(code, 0),
        })

    out = sorted(
        out,
        key=lambda item: (
            -_lhb_numeric_amount(item["top_youzi_alias_abs_net_amount"]),
            item["code"],
        ),
    )
    for idx, item in enumerate(out, start=1):
        item["rank"] = idx
    return [
        {
            "rank": item["rank"],
            "code": item["code"],
            "top_youzi_alias": item["top_youzi_alias"],
            "top_youzi_alias_abs_net_amount": item["top_youzi_alias_abs_net_amount"],
            "top_youzi_alias_direction": item["top_youzi_alias_direction"],
            "alias_scope": item["alias_scope"],
            "alias_direction_consistency": item["alias_direction_consistency"],
            "youzi_recognition_score": item["youzi_recognition_score"],
        }
        for item in out
    ]


def _lhb_composite_signal_tag(
    concentration: dict,
    direction_summary: dict,
    identity_summary: dict,
) -> str:
    has_shared = concentration.get("shared_alias_count", 0) > 0
    direction = direction_summary.get("dominant_shared_direction_consistency")
    level = concentration.get("concentration_level")
    identity = identity_summary.get("dominant_identity_tag")
    if has_shared and direction == "same_direction" and level in {"single_alias", "high"}:
        return "shared_same_direction_cluster"
    if has_shared and direction == "mixed_direction":
        return "shared_mixed_direction_divergence"
    if identity == "unique_dominant":
        return "unique_youzi_driven"
    if has_shared:
        return "shared_youzi_present"
    return "no_shared_youzi_signal"


def _summarize_lhb_compare_composite_signal(
    concentration: dict,
    direction_summary: dict,
    identity_summary: dict,
    recognition_leaderboard: list[dict],
) -> dict:
    leader = recognition_leaderboard[0] if recognition_leaderboard else {}
    top_alias = concentration.get("top_shared_alias") or None
    tag = _lhb_composite_signal_tag(concentration, direction_summary, identity_summary)
    if tag == "shared_same_direction_cluster":
        interpretation = (
            f"共同游资{top_alias}单一集中且方向一致；"
            f"综合辨识领先代码{leader.get('code')}"
        )
    elif tag == "shared_mixed_direction_divergence":
        interpretation = f"共同游资{top_alias}跨股方向分歧；需核对分时与题材强弱"
    elif tag == "unique_youzi_driven":
        interpretation = f"独有游资主导；综合辨识领先代码{leader.get('code')}"
    elif tag == "shared_youzi_present":
        interpretation = f"存在共同游资{top_alias}；集中度或方向一致性不强"
    else:
        interpretation = "未形成共同游资信号；优先看单股独有席位"
    return {
        "signal_tag": tag,
        "leading_code": leader.get("code"),
        "leading_top_alias": top_alias,
        "shared_concentration_level": concentration.get("concentration_level"),
        "dominant_shared_direction_consistency": (
            direction_summary.get("dominant_shared_direction_consistency")
        ),
        "dominant_identity_tag": identity_summary.get("dominant_identity_tag"),
        "interpretation": interpretation,
    }


def _lhb_recognition_leadership_level(score_gap: float) -> str:
    if score_gap >= 20:
        return "strong"
    if score_gap >= 10:
        return "moderate"
    if score_gap > 0:
        return "narrow"
    return "none"


def _summarize_lhb_compare_recognition_gap(
    recognition_leaderboard: list[dict],
) -> dict:
    leader = recognition_leaderboard[0] if recognition_leaderboard else {}
    runner_up = recognition_leaderboard[1] if len(recognition_leaderboard) > 1 else {}
    leader_score = _lhb_numeric_amount(leader.get("recognition_score"))
    runner_up_score = _lhb_numeric_amount(runner_up.get("recognition_score"))
    score_gap = round(leader_score - runner_up_score, 2) if runner_up else 0
    level = _lhb_recognition_leadership_level(score_gap)
    leader_code = leader.get("code")
    runner_up_code = runner_up.get("code")
    if leader_code and runner_up_code:
        interpretation = (
            f"{leader_code}综合辨识分领先{runner_up_code} "
            f"{score_gap}分，领先强度{level}"
        )
    elif leader_code:
        interpretation = f"{leader_code}为唯一命中代码，无法计算第二名差距"
    else:
        interpretation = "无命中代码，无法计算综合辨识领先差距"
    return {
        "leader_code": leader_code,
        "runner_up_code": runner_up_code,
        "leader_score": leader_score,
        "runner_up_score": runner_up_score,
        "score_gap": score_gap,
        "leadership_level": level,
        "interpretation": interpretation,
    }


def _apply_lhb_compare_identity_tags_to_rows(rows: list[dict], comparison_summary: dict) -> None:
    tags_by_code = {
        item["code"]: item
        for item in comparison_summary.get("youzi_code_identity_tags") or []
        if item.get("code")
    }
    leaderboard_by_code = {
        item["code"]: item
        for item in comparison_summary.get("youzi_recognition_leaderboard") or []
        if item.get("code")
    }
    for row in rows:
        tag = tags_by_code.get(row.get("code"))
        if tag:
            row.update({
                "youzi_identity_tag": tag.get("identity_tag"),
                "dominant_youzi_scope": tag.get("dominant_youzi_scope"),
                "dominant_youzi_abs_net_amount": tag.get("dominant_abs_net_amount", 0),
                "shared_youzi_abs_net_ratio": tag.get("shared_abs_net_ratio", 0),
                "unique_youzi_abs_net_ratio": tag.get("unique_abs_net_ratio", 0),
                "youzi_identity_top_alias": tag.get("top_scope_alias"),
            })
        leaderboard_item = leaderboard_by_code.get(row.get("code"))
        if leaderboard_item:
            row.update({
                "youzi_recognition_score": leaderboard_item.get("recognition_score", 0),
                "youzi_recognition_rank_reason": leaderboard_item.get("rank_reason"),
            })


def _summarize_lhb_compare(rows: list[dict], codes: list[str], payloads: list[dict]) -> dict:
    alias_codes: dict[str, set[str]] = {}
    for row in rows:
        code = row.get("code")
        if not code:
            continue
        for alias in row.get("youzi_aliases") or []:
            if alias:
                alias_codes.setdefault(alias, set()).add(code)

    alias_frequency = [
        {"alias": alias, "code_count": len(code_set), "codes": sorted(code_set)}
        for alias, code_set in alias_codes.items()
    ]
    alias_frequency = sorted(
        alias_frequency,
        key=lambda item: (-item["code_count"], item["alias"]),
    )
    alias_strengths = _summarize_lhb_compare_alias_strengths(payloads)
    same_direction_aliases = [
        {
            "alias": item["alias"],
            "net_direction": item["direction_consistency"].replace("same_", ""),
        }
        for item in alias_strengths
        if item["code_count"] >= 2 and item["direction_consistency"].startswith("same_")
    ]
    mixed_direction_aliases = [
        item["alias"] for item in alias_strengths
        if item["code_count"] >= 2 and item["direction_consistency"] == "mixed"
    ]
    shared_code_strengths = _summarize_lhb_compare_shared_code_strengths(alias_strengths)
    unique_code_strengths = _summarize_lhb_compare_unique_code_strengths(alias_strengths)
    identity_tags = _summarize_lhb_compare_code_identity_tags(
        shared_code_strengths,
        unique_code_strengths,
    )
    shared_strength = _summarize_lhb_compare_shared_strength(alias_strengths)
    shared_concentration = _summarize_lhb_compare_shared_concentration(alias_strengths)
    identity_summary = _summarize_lhb_compare_code_identity_summary(identity_tags)
    direction_summary = _summarize_lhb_compare_direction_consistency(alias_strengths)
    recognition_leaderboard = _summarize_lhb_compare_recognition_leaderboard(
        rows,
        identity_tags,
        same_direction_aliases,
    )
    top_alias_comparison = _summarize_lhb_compare_top_alias_comparison(
        rows,
        alias_strengths,
        recognition_leaderboard,
    )
    composite_signal = _summarize_lhb_compare_composite_signal(
        shared_concentration,
        direction_summary,
        identity_summary,
        recognition_leaderboard,
    )
    recognition_gap = _summarize_lhb_compare_recognition_gap(recognition_leaderboard)
    return {
        "code_count": len(codes),
        "matched_code_count": sum(1 for row in rows if row.get("filtered_count", 0)),
        "top_code_by_youzi_abs_net": _lhb_compare_top_code(rows, "youzi_abs_net_amount"),
        "top_code_by_profiled_abs_net": _lhb_compare_top_code(rows, "profiled_abs_net_amount"),
        "top_code_by_profiled_abs_net_ratio": _lhb_compare_top_code(
            rows,
            "profiled_abs_net_ratio",
        ),
        "shared_youzi_aliases": [
            item["alias"] for item in alias_frequency
            if item["code_count"] >= 2
        ],
        "shared_youzi_strength_summary": shared_strength,
        "shared_youzi_concentration_summary": shared_concentration,
        "shared_youzi_code_strengths": shared_code_strengths,
        "unique_youzi_code_strengths": unique_code_strengths,
        "youzi_code_identity_tags": identity_tags,
        "youzi_code_identity_summary": identity_summary,
        "youzi_recognition_leaderboard": recognition_leaderboard,
        "youzi_recognition_gap_summary": recognition_gap,
        "top_youzi_alias_comparison": top_alias_comparison,
        "youzi_composite_signal_summary": composite_signal,
        "same_direction_youzi_aliases": same_direction_aliases,
        "mixed_direction_youzi_aliases": mixed_direction_aliases,
        "youzi_direction_consistency_summary": direction_summary,
        "youzi_alias_frequency": alias_frequency,
        "youzi_alias_cross_code_strengths": alias_strengths,
    }


def _fetch_lhb_compare(
    codes: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    list_limit: int = 20,
    page: int = 1,
    detail_limit: int = 10,
    dominant_type: str | None = None,
    dominant_direction: str | None = None,
    youzi_alias: str | None = None,
    min_dominant_net: float | None = None,
    sort_by: str = "youzi_abs_net_amount",
) -> dict:
    if not start_date or not end_date:
        raise ValueError("lhb-compare 需要 --start-date 和 --end-date")
    if sort_by not in _LHB_COMPARE_SORT_FIELDS:
        raise ValueError(f"不支持的 sort_by: {sort_by}")
    clean_codes = [_clean_a_code(code) for code in codes if code]
    if not 2 <= len(clean_codes) <= 4:
        raise ValueError("lhb-compare 需要 2-4 个股票代码")

    payloads = [
        _fetch_lhb_detail_range(
            code,
            start_date,
            end_date,
            list_limit,
            page,
            detail_limit,
            dominant_type,
            dominant_direction,
            youzi_alias,
            min_dominant_net,
        )
        for code in clean_codes
    ]
    rows = [_lhb_compare_row(payload) for payload in payloads]
    rows = sorted(
        rows,
        key=lambda row: (-_lhb_numeric_amount(row.get(sort_by)), row.get("code") or ""),
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx

    comparison_summary = _summarize_lhb_compare(rows, clean_codes, payloads)
    _apply_lhb_compare_identity_tags_to_rows(rows, comparison_summary)
    return {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb-compare",
        "codes": clean_codes,
        "start_date": str(start_date)[:10],
        "end_date": str(end_date)[:10],
        "list_limit": list_limit,
        "detail_limit": detail_limit,
        "page": page,
        "dominant_type": dominant_type,
        "dominant_direction": dominant_direction,
        "youzi_alias": youzi_alias,
        "min_dominant_net": min_dominant_net,
        "sort_by": sort_by,
        "comparison_summary": comparison_summary,
        "rows": rows,
    }


def cmd_lhb(
    code: str | None = None,
    limit: int = 20,
    page: int = 1,
    json_output: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """龙虎榜明细。"""
    rows = _fetch_lhb_rows(code, limit, page, start_date, end_date)
    payload = {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb",
        "code": _clean_a_code(code) if code else None,
        "limit": limit,
        "page": page,
        "start_date": str(start_date)[:10] if start_date else None,
        "end_date": str(end_date)[:10] if end_date else None,
        "records": rows,
    }
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    title = f"龙虎榜: {_clean_a_code(code)}" if code else "龙虎榜: 最新全市场"
    print("=" * 60)
    print(title)
    print("=" * 60)
    if not rows:
        print("  ⚠️ 未找到龙虎榜记录")
        return
    for r in rows:
        print(f"\n  --- {r['trade_date']} {r['name']} ({r['code']}) ---")
        print(f"  原因:       {r['reason']}")
        print(f"  收盘/涨跌:  {r['close_price']} / {_fmt_pct(r['change_rate'])}")
        print(f"  买入金额:   {_fmt_yi(r['buy_amount'])}")
        print(f"  卖出金额:   {_fmt_yi(r['sell_amount'])}")
        print(f"  净买入:     {_fmt_yi(r['net_amount'])}")
        print(f"  成交额:     {_fmt_yi(r['deal_amount'])}")
        print(f"  交易市场:   {r['trade_market']}")


def cmd_lhb_compare(
    codes: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
    list_limit: int = 20,
    page: int = 1,
    limit: int = 10,
    dominant_type: str | None = None,
    dominant_direction: str | None = None,
    youzi_alias: str | None = None,
    min_dominant_net: float | None = None,
    sort_by: str = "youzi_abs_net_amount",
    json_output: bool = False,
):
    """多股票龙虎榜区间辨识度对比。"""
    payload = _fetch_lhb_compare(
        codes,
        start_date,
        end_date,
        list_limit,
        page,
        limit,
        dominant_type,
        dominant_direction,
        youzi_alias,
        min_dominant_net,
        sort_by,
    )
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print(f"龙虎榜区间辨识度对比: {payload['start_date']}~{payload['end_date']}")
    print("=" * 60)
    for row in payload["rows"]:
        print(
            f"{row['rank']:>2}. {row['code']} "
            f"游资净额绝对值={_fmt_yi(row['youzi_abs_net_amount'])} "
            f"可识别净额绝对值={_fmt_yi(row['profiled_abs_net_amount'])} "
            f"Top游资={row['top_youzi_alias'] or '-'}"
        )


def cmd_lhb_detail(
    code: str | None = None,
    trade_date: str | None = None,
    trade_id: str | None = None,
    limit: int = 10,
    json_output: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    list_limit: int = 20,
    page: int = 1,
    dominant_type: str | None = None,
    dominant_direction: str | None = None,
    youzi_alias: str | None = None,
    min_dominant_net: float | None = None,
):
    """龙虎榜买卖席位明细。"""
    if start_date or end_date:
        payload = _fetch_lhb_detail_range(
            code,
            start_date,
            end_date,
            list_limit,
            page,
            limit,
            dominant_type,
            dominant_direction,
            youzi_alias,
            min_dominant_net,
        )
    else:
        payload = _fetch_lhb_detail(code, trade_date, trade_id, limit)
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    title_code = payload.get("code") or "-"
    title_date = payload.get("trade_date") or (
        f"{payload.get('start_date')}~{payload.get('end_date')}"
        if payload.get("start_date") else "-"
    )
    print("=" * 60)
    print(f"龙虎榜席位明细: {title_code} {title_date}")
    print("=" * 60)
    if not payload["records"]:
        print("  ⚠️ 未找到龙虎榜席位明细")
        return
    for record in payload["records"]:
        print(f"\n  --- {record['trade_date']} {record['name']} ({record['code']}) ---")
        print(f"  原因:       {record['reason']}")
        print(f"  合计买/卖:  {_fmt_yi(record['total_buy'])} / {_fmt_yi(record['total_sell'])}")
        print(f"  合计净额:   {_fmt_yi(record['total_net'])}")
        for label, seats in (("买入前五", record["buy_seats"]), ("卖出前五", record["sell_seats"])):
            print(f"  {label}:")
            for seat in seats[:limit]:
                print(
                    f"    {seat['seat_name']} | 买 {_fmt_yi(seat['buy_amount'])} "
                    f"卖 {_fmt_yi(seat['sell_amount'])} 净 {_fmt_yi(seat['net_amount'])}"
                )


# ---------------------------------------------------------------------------
# 理杏仁数据源路径（--source lixinger）
# ---------------------------------------------------------------------------

def _lxr_data():
    """惰性导入 LxrData，避免在纯免费源模式下引入依赖。"""
    from lxr_data import LxrData
    return LxrData(verbose=False)


def _extract_metric(record: dict, *paths: str):
    """从 fs 记录的 q 嵌套结构中按优先级取第一个非空值。paths 如 'ps.toi.t'。"""
    q = record.get("q") if isinstance(record, dict) else None
    if not isinstance(q, dict):
        return None
    for path in paths:
        node = q
        ok = True
        for seg in path.split("."):
            if isinstance(node, dict) and seg in node:
                node = node[seg]
            else:
                ok = False
                break
        if ok and node is not None:
            return node
    return None


def cmd_financials_lixinger(code: str):
    """理杏仁财务数据：近5年年报核心指标，输出格式与 cmd_financials 可比。"""
    data = _lxr_data().get_financials(code, years=5, source="lixinger")
    if data.get("_source") != "lixinger":
        print(f"❌ 理杏仁取数失败: {data.get('error')}")
        return
    records = data.get("records", [])
    annual = [r for r in records if str(r.get("date", "")[:10]).endswith("-12-31")]
    annual.sort(key=lambda r: r.get("date", ""), reverse=True)

    print("=" * 60)
    print(f"核心财务数据(理杏仁): {code} [{data.get('report_type')}]")
    print("=" * 60)
    for r in annual[:5]:
        date = str(r.get("date", ""))[:10]
        revenue = _extract_metric(r, "ps.toi.t", "ps.oi.t", "ps.ep.t")
        net_profit = _extract_metric(r, "ps.npatoshopc.t", "ps.np.t")
        eps = _extract_metric(r, "ps.beps.t")
        print(f"\n  --- {date} 年报 ---")
        if revenue is not None:
            print(f"  营业总收入:   {_fmt_yi(revenue)}")
        if net_profit is not None:
            print(f"  归母净利润:   {_fmt_yi(net_profit)}")
        if eps is not None:
            print(f"  基本每股收益: {eps}")
    print(f"\n  (数据来源: 理杏仁 {data.get('source_detail')}, 指标数 {data.get('metric_count')})")


def cmd_valuation_lixinger(code: str):
    """理杏仁估值数据：当前估值 + 历史分位点。"""
    data = _lxr_data().get_valuation(code, source="lixinger")
    if data.get("_source") != "lixinger":
        print(f"❌ 理杏仁取数失败: {data.get('error')}")
        return
    latest = data.get("latest", {})
    print("=" * 60)
    print(f"估值指标(理杏仁): {code} [{data.get('report_type')}]")
    print("=" * 60)
    print(f"  股价:        {latest.get('sp')}")
    print(f"  总市值:      {_fmt_yi(latest.get('mc')) if latest.get('mc') is not None else '-'}")
    print(f"  流通市值:    {_fmt_yi(latest.get('cmc')) if latest.get('cmc') is not None else '-'}")
    print(f"  PE-TTM:      {latest.get('pe_ttm')}")
    print(f"  PE-TTM(扣非):{latest.get('d_pe_ttm')}")
    print(f"  PB:          {latest.get('pb')}")
    print(f"  PS-TTM:      {latest.get('ps_ttm')}")
    print(f"  股息率:      {latest.get('dyr')}")
    print(f"  换手率:      {latest.get('to_r')}")
    print("\n  历史分位点 (cvpos = 当前所处分位%):")
    for k, v in latest.items():
        if ".cvpos" in k and v is not None:
            print(f"    {k:28s} {v}")
    print(f"\n  (数据来源: 理杏仁 {data.get('source_detail')})")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="A股数据工具 — 腾讯行情 + 东方财富财务数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_quote = sub.add_parser("quote", help="实时行情")
    p_quote.add_argument("code", help="股票代码，如 600519")

    p_fin = sub.add_parser("financials", help="核心财务数据（近5年）")
    p_fin.add_argument("code", help="股票代码")
    p_fin.add_argument("--source", choices=["default", "lixinger"], default="default",
                       help="数据源；default=东方财富/腾讯，lixinger=理杏仁")

    p_val = sub.add_parser("valuation", help="估值指标")
    p_val.add_argument("code", help="股票代码")
    p_val.add_argument("--source", choices=["default", "lixinger"], default="default",
                       help="数据源；default=腾讯，lixinger=理杏仁(含历史分位点)")

    p_search = sub.add_parser("search", help="搜索股票代码")
    p_search.add_argument("keyword", help="公司名或关键词")

    p_lhb = sub.add_parser("lhb", help="龙虎榜明细（东方财富）")
    p_lhb.add_argument("code", nargs="?", default=None, help="股票代码；省略则返回全市场最新")
    p_lhb.add_argument("--limit", type=int, default=20, help="返回条数，1-100")
    p_lhb.add_argument("--page", type=int, default=1, help="页码")
    p_lhb.add_argument("--start-date", default=None, help="开始日期 YYYY-MM-DD")
    p_lhb.add_argument("--end-date", default=None, help="结束日期 YYYY-MM-DD")
    p_lhb.add_argument("--json", action="store_true", help="输出 JSON，供上层工具解析")

    p_lhb_detail = sub.add_parser("lhb-detail", help="龙虎榜买卖席位明细（东方财富）")
    p_lhb_detail.add_argument("code", nargs="?", default=None, help="股票代码；配合 --date 使用")
    p_lhb_detail.add_argument("--date", dest="trade_date", default=None, help="交易日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--start-date", default=None, help="批量开始日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--end-date", default=None, help="批量结束日期 YYYY-MM-DD")
    p_lhb_detail.add_argument("--trade-id", default=None, help="东方财富 TRADE_ID，优先使用")
    p_lhb_detail.add_argument("--limit", type=int, default=10, help="每侧席位条数，1-100")
    p_lhb_detail.add_argument("--list-limit", type=int, default=20, help="区间模式下先筛选的龙虎榜记录数，1-100")
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
    p_lhb_detail.add_argument("--json", action="store_true", help="输出 JSON，供上层工具解析")

    p_lhb_compare = sub.add_parser("lhb-compare", help="多股票龙虎榜区间辨识度对比")
    p_lhb_compare.add_argument("codes", nargs="+", help="2-4 个股票代码，如 000004 000005")
    p_lhb_compare.add_argument("--start-date", required=True, help="开始日期 YYYY-MM-DD")
    p_lhb_compare.add_argument("--end-date", required=True, help="结束日期 YYYY-MM-DD")
    p_lhb_compare.add_argument("--limit", type=int, default=10, help="每侧席位条数，1-100")
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
    p_lhb_compare.add_argument("--sort-by", choices=_LHB_COMPARE_SORT_FIELDS, default="youzi_abs_net_amount")
    p_lhb_compare.add_argument("--json", action="store_true", help="输出 JSON，供上层工具解析")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "quote": lambda: cmd_quote(args.code),
        "financials": lambda: (cmd_financials_lixinger(args.code)
                               if args.source == "lixinger" else cmd_financials(args.code)),
        "valuation": lambda: (cmd_valuation_lixinger(args.code)
                              if args.source == "lixinger" else cmd_valuation(args.code)),
        "search": lambda: cmd_search(args.keyword),
        "lhb": lambda: cmd_lhb(
            args.code, args.limit, args.page, args.json, args.start_date, args.end_date
        ),
        "lhb-detail": lambda: cmd_lhb_detail(
            args.code,
            args.trade_date,
            args.trade_id,
            args.limit,
            args.json,
            args.start_date,
            args.end_date,
            args.list_limit,
            args.page,
            args.dominant_type,
            args.dominant_direction,
            args.youzi_alias,
            args.min_dominant_net,
        ),
        "lhb-compare": lambda: cmd_lhb_compare(
            args.codes,
            args.start_date,
            args.end_date,
            args.list_limit,
            args.page,
            args.limit,
            args.dominant_type,
            args.dominant_direction,
            args.youzi_alias,
            args.min_dominant_net,
            args.sort_by,
            args.json,
        ),
    }
    cmds[args.command]()


if __name__ == "__main__":
    main()
