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


def test_lhb_params_filter_specific_stock_and_date_range():
    params = ad._eastmoney_lhb_params(
        "000004", limit=10, page=1, start_date="2026-06-01", end_date="2026-06-26"
    )

    assert params["filter"] == (
        '(SECURITY_CODE="000004")(TRADE_DATE>=\'2026-06-01\')'
        "(TRADE_DATE<='2026-06-26')"
    )


def test_normalize_lhb_row_keeps_core_fields():
    row = {
        "TRADE_ID": "100357777",
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
        "trade_id": "100357777",
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


def test_lhb_detail_params_filter_by_trade_id():
    params = ad._eastmoney_lhb_detail_params("buy", trade_id="100357777", limit=5)

    assert params["reportName"] == "RPT_BILLBOARD_DAILYDETAILSBUY"
    assert params["pageSize"] == "5"
    assert params["filter"] == '(TRADE_ID="100357777")'
    assert params["sortColumns"] == "BUY"
    assert params["sortTypes"] == "-1"


def test_normalize_lhb_detail_seat_row_classifies_institution():
    row = {
        "TRADE_ID": "100357777",
        "TRADE_DATE": "2026-06-26 00:00:00",
        "SECURITY_CODE": "000004",
        "SECUCODE": "000004.SZ",
        "SECURITY_NAME_ABBR": "国华退",
        "EXPLANATION": "退市整理期",
        "OPERATEDEPT_CODE": "0",
        "OPERATEDEPT_NAME": "机构专用",
        "BUY": 1000000,
        "SELL": 250000,
        "NET": 750000,
        "TOTAL_BUYRIO": 0.12,
        "TOTAL_SELLRIO": 0.03,
        "RISE_PROBABILITY_3DAY": 66.6,
        "TOTAL_BUYER_SALESTIMES_3DAY": 12,
    }

    out = ad._normalize_lhb_detail_seat(row, "buy")

    assert out == {
        "trade_id": "100357777",
        "trade_date": "2026-06-26",
        "code": "000004",
        "secucode": "000004.SZ",
        "name": "国华退",
        "reason": "退市整理期",
        "rank_type": "buy",
        "seat_code": "0",
        "seat_name": "机构专用",
        "seat_category": "institution",
        "seat_profile": {
            "type": "institution",
            "alias": "机构专用",
            "tier": "institution",
            "style": "机构资金席位",
            "premium": "neutral",
            "matched_keyword": "机构专用",
            "match_type": "rule",
            "profile_source": "rule:seat-name",
        },
        "buy_amount": 1000000,
        "sell_amount": 250000,
        "net_amount": 750000,
        "buy_ratio": 0.12,
        "sell_ratio": 0.03,
        "rise_probability_3day": 66.6,
        "buyer_sales_times_3day": 12,
        "source_detail": "eastmoney:lhb-detail",
        "_source": "legacy",
    }


def test_normalize_lhb_detail_seat_row_identifies_known_youzi_profile():
    row = {
        "TRADE_ID": "100357777",
        "TRADE_DATE": "2026-06-26 00:00:00",
        "SECURITY_CODE": "000004",
        "SECUCODE": "000004.SZ",
        "SECURITY_NAME_ABBR": "国华退",
        "EXPLANATION": "退市整理期",
        "OPERATEDEPT_CODE": "10472087",
        "OPERATEDEPT_NAME": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
        "BUY": 762307,
        "SELL": 106076,
        "NET": 656231,
    }

    out = ad._normalize_lhb_detail_seat(row, "buy")

    assert out["seat_category"] == "brokerage"
    assert out["seat_profile"] == {
        "type": "youzi",
        "alias": "拉萨天团",
        "tier": "regional",
        "style": "群狼一日游，反向指标",
        "premium": "negative",
        "matched_keyword": "东方财富证券股份有限公司拉萨",
        "match_type": "contains",
        "profile_source": "stock-deep-analyzer:lhb-analyzer/seat-encyclopedia",
    }


def test_fetch_lhb_detail_groups_buy_and_sell_seats(monkeypatch):
    calls = []

    def fake_curl_json(url, params):
        calls.append(params)
        report = params["reportName"]
        if report == "RPT_BILLBOARD_DAILYDETAILS":
            return {"result": {"data": [{
                "TRADE_ID": "100357777",
                "TRADE_DATE": "2026-06-26 00:00:00",
                "SECURITY_CODE": "000004",
                "SECUCODE": "000004.SZ",
                "SECURITY_NAME_ABBR": "国华退",
                "EXPLANATION": "退市整理期",
                "CLOSE_PRICE": 0.28,
                "CHANGE_RATE": 7.6923,
                "ACCUM_AMOUNT": 2971598,
                "ACCUM_VOLUME": 11358930,
                "TOTAL_BUY": 1931424,
                "TOTAL_SELL": 926973,
                "TOTAL_NET": 1004451,
            }]}}
        if report == "RPT_BILLBOARD_DAILYDETAILSBUY":
            return {"result": {"data": [{
                "TRADE_ID": "100357777",
                "TRADE_DATE": "2026-06-26 00:00:00",
                "SECURITY_CODE": "000004",
                "OPERATEDEPT_CODE": "10472087",
                "OPERATEDEPT_NAME": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                "EXPLANATION": "退市整理期",
                "BUY": 762307,
                "SELL": 106076,
                "NET": 656231,
            }]}}
        if report == "RPT_BILLBOARD_DAILYDETAILSSELL":
            return {"result": {"data": [{
                "TRADE_ID": "100357777",
                "TRADE_DATE": "2026-06-26 00:00:00",
                "SECURITY_CODE": "000004",
                "OPERATEDEPT_CODE": "10467671",
                "OPERATEDEPT_NAME": "国金证券股份有限公司上海奉贤区金碧路证券营业部",
                "EXPLANATION": "退市整理期",
                "BUY": 0,
                "SELL": 219258,
                "NET": -219258,
            }]}}
        raise AssertionError(report)

    monkeypatch.setattr(ad, "_curl_json", fake_curl_json)

    out = ad._fetch_lhb_detail(trade_id="100357777")

    assert [c["reportName"] for c in calls] == [
        "RPT_BILLBOARD_DAILYDETAILS",
        "RPT_BILLBOARD_DAILYDETAILSBUY",
        "RPT_BILLBOARD_DAILYDETAILSSELL",
    ]
    assert out["source_detail"] == "eastmoney:lhb-detail"
    assert out["records"][0]["trade_id"] == "100357777"
    assert out["records"][0]["buy_seats"][0]["seat_code"] == "10472087"
    assert out["records"][0]["sell_seats"][0]["seat_code"] == "10467671"
    assert out["records"][0]["seat_profile_summary"] == {
        "buy": {
            "institution": 0,
            "northbound": 0,
            "youzi": 1,
            "brokerage": 0,
            "unknown": 0,
            "aliases": ["拉萨天团"],
        },
        "sell": {
            "institution": 0,
            "northbound": 0,
            "youzi": 0,
            "brokerage": 1,
            "unknown": 0,
            "aliases": [],
        },
    }
    assert out["records"][0]["seat_amount_summary"]["youzi"] == {
        "buy_amount": 762307,
        "sell_amount": 106076,
        "net_amount": 656231,
        "buy_count": 1,
        "sell_count": 0,
        "aliases": ["拉萨天团"],
    }
    assert out["records"][0]["seat_amount_summary"]["brokerage"] == {
        "buy_amount": 0,
        "sell_amount": 219258,
        "net_amount": -219258,
        "buy_count": 0,
        "sell_count": 1,
        "aliases": [],
    }
    assert out["records"][0]["seat_flow_analysis"] == {
        "institution_net_amount": 0,
        "northbound_net_amount": 0,
        "youzi_net_amount": 656231,
        "brokerage_net_amount": -219258,
        "unknown_net_amount": 0,
        "dominant_type": "youzi",
        "dominant_direction": "net_buy",
        "dominant_net_amount": 656231,
        "dominant_aliases": ["拉萨天团"],
    }


def test_fetch_lhb_detail_range_uses_lhb_trade_ids(monkeypatch):
    detail_calls = []

    def fake_fetch_lhb_rows(code, limit, page, start_date=None, end_date=None):
        assert code == "000004"
        assert limit == 50
        assert page == 1
        assert start_date == "2026-06-01"
        assert end_date == "2026-06-26"
        return [
            {"trade_id": "100357777", "trade_date": "2026-06-26", "code": "000004"},
            {"trade_id": "100357666", "trade_date": "2026-06-25", "code": "000004"},
        ]

    def fake_fetch_lhb_detail(code=None, trade_date=None, trade_id=None, limit=10):
        detail_calls.append({
            "code": code,
            "trade_date": trade_date,
            "trade_id": trade_id,
            "limit": limit,
        })
        if trade_id == "100357777":
            flow = {
                "institution_net_amount": 0,
                "northbound_net_amount": 0,
                "youzi_net_amount": 656231,
                "brokerage_net_amount": -219258,
                "unknown_net_amount": 0,
                "dominant_type": "youzi",
                "dominant_direction": "net_buy",
                "dominant_net_amount": 656231,
                "dominant_aliases": ["拉萨天团"],
            }
        else:
            flow = {
                "institution_net_amount": 300000,
                "northbound_net_amount": 0,
                "youzi_net_amount": 0,
                "brokerage_net_amount": -100000,
                "unknown_net_amount": 0,
                "dominant_type": "institution",
                "dominant_direction": "net_buy",
                "dominant_net_amount": 300000,
                "dominant_aliases": [],
            }
        return {
            "_source": "legacy",
            "source_detail": "eastmoney:lhb-detail",
            "records": [{
                "trade_id": str(trade_id),
                "trade_date": "2026-06-26" if trade_id == "100357777" else "2026-06-25",
                "code": "000004",
                "seat_flow_analysis": flow,
            }],
        }

    monkeypatch.setattr(ad, "_fetch_lhb_rows", fake_fetch_lhb_rows)
    monkeypatch.setattr(ad, "_fetch_lhb_detail", fake_fetch_lhb_detail)

    out = ad._fetch_lhb_detail_range(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        list_limit=50,
        page=1,
        detail_limit=7,
    )

    assert detail_calls == [
        {"code": None, "trade_date": None, "trade_id": "100357777", "limit": 7},
        {"code": None, "trade_date": None, "trade_id": "100357666", "limit": 7},
    ]
    assert out == {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb-detail-range",
        "code": "000004",
        "start_date": "2026-06-01",
        "end_date": "2026-06-26",
        "list_limit": 50,
        "detail_limit": 7,
        "page": 1,
        "source_lhb_count": 2,
        "records": [
            {
                "trade_id": "100357777",
                "trade_date": "2026-06-26",
                "code": "000004",
                "seat_flow_analysis": {
                    "institution_net_amount": 0,
                    "northbound_net_amount": 0,
                    "youzi_net_amount": 656231,
                    "brokerage_net_amount": -219258,
                    "unknown_net_amount": 0,
                    "dominant_type": "youzi",
                    "dominant_direction": "net_buy",
                    "dominant_net_amount": 656231,
                    "dominant_aliases": ["拉萨天团"],
                },
            },
            {
                "trade_id": "100357666",
                "trade_date": "2026-06-25",
                "code": "000004",
                "seat_flow_analysis": {
                    "institution_net_amount": 300000,
                    "northbound_net_amount": 0,
                    "youzi_net_amount": 0,
                    "brokerage_net_amount": -100000,
                    "unknown_net_amount": 0,
                    "dominant_type": "institution",
                    "dominant_direction": "net_buy",
                    "dominant_net_amount": 300000,
                    "dominant_aliases": [],
                },
            },
        ],
        "range_flow_summary": {
            "record_count": 2,
            "trade_dates": ["2026-06-25", "2026-06-26"],
            "dominant_type_counts": {
                "institution": 1,
                "northbound": 0,
                "youzi": 1,
                "brokerage": 0,
                "unknown": 0,
            },
            "dominant_direction_counts": {
                "net_buy": 2,
                "net_sell": 0,
                "flat": 0,
            },
            "net_amount_by_type": {
                "institution": 300000,
                "northbound": 0,
                "youzi": 656231,
                "brokerage": -319258,
                "unknown": 0,
            },
            "youzi_aliases": ["拉萨天团"],
        },
    }
