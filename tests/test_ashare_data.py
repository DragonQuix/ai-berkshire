"""ashare_data 免费源单元测试。"""

from __future__ import annotations

import os
import sys

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, TOOLS_DIR)

import ashare_data as ad  # noqa: E402


def test_lhb_params_filter_specific_stock():
    params = ad._eastmoney_lhb_params("600519", limit=7, page=2)

    assert params["reportName"] == "RPT_DAILYBILLBOARD_DETAILS"
    assert params["pageSize"] == "7"
    assert params["pageNumber"] == "2"
    assert params["filter"] == '(SECURITY_CODE="600519")'
    assert params["sortColumns"] == "TRADE_DATE,SECURITY_CODE"


def test_normalize_lhb_row_keeps_core_fields():
    row = {
        "TRADE_DATE": "2026-06-26 00:00:00",
        "SECURITY_CODE": "000004",
        "SECUCODE": "000004.SZ",
        "SECURITY_NAME_ABBR": "国华退",
        "EXPLANATION": "退市整理期",
        "CLOSE_PRICE": 0.28,
        "CHANGE_RATE": 7.6923,
        "TURNOVERRATE": 8.9944,
        "BILLBOARD_BUY_AMT": 1931424,
        "BILLBOARD_SELL_AMT": 926973,
        "BILLBOARD_NET_AMT": 1004451,
        "BILLBOARD_DEAL_AMT": 2858397,
        "BUY_SEAT_NEW": "11111",
        "SELL_SEAT_NEW": "11111",
        "TRADE_MARKET": "深交所风险警示板",
    }

    out = ad._normalize_lhb_row(row)

    assert out == {
        "trade_date": "2026-06-26",
        "code": "000004",
        "secucode": "000004.SZ",
        "name": "国华退",
        "reason": "退市整理期",
        "close_price": 0.28,
        "change_rate": 7.6923,
        "turnover_rate": 8.9944,
        "buy_amount": 1931424,
        "sell_amount": 926973,
        "net_amount": 1004451,
        "deal_amount": 2858397,
        "buy_seats": "11111",
        "sell_seats": "11111",
        "trade_market": "深交所风险警示板",
        "source_detail": "eastmoney:lhb",
        "_source": "legacy",
    }
