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
                "buy_seats": [{
                    "seat_name": (
                        "东方财富证券股份有限公司拉萨东环路第二证券营业部"
                        if trade_id == "100357777" else "机构专用"
                    ),
                    "seat_profile": (
                        {"type": "youzi", "alias": "拉萨天团"}
                        if trade_id == "100357777" else {"type": "institution", "alias": "机构专用"}
                    ),
                    "buy_amount": 762307 if trade_id == "100357777" else 400000,
                    "sell_amount": 106076 if trade_id == "100357777" else 100000,
                    "net_amount": 656231 if trade_id == "100357777" else 300000,
                }],
                "sell_seats": [{
                    "seat_name": (
                        "国金证券股份有限公司上海奉贤区金碧路证券营业部"
                        if trade_id == "100357777" else "中信证券股份有限公司杭州延安路证券营业部"
                    ),
                    "seat_profile": {"type": "brokerage", "alias": None},
                    "buy_amount": 0,
                    "sell_amount": 219258 if trade_id == "100357777" else 100000,
                    "net_amount": -219258 if trade_id == "100357777" else -100000,
                }],
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
        "filtered_count": 2,
        "dominant_type": None,
        "dominant_direction": None,
        "youzi_alias": None,
        "min_dominant_net": None,
        "records": [
            {
                "trade_id": "100357777",
                "trade_date": "2026-06-26",
                "code": "000004",
                "buy_seats": [{
                    "seat_name": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                    "seat_profile": {"type": "youzi", "alias": "拉萨天团"},
                    "buy_amount": 762307,
                    "sell_amount": 106076,
                    "net_amount": 656231,
                }],
                "sell_seats": [{
                    "seat_name": "国金证券股份有限公司上海奉贤区金碧路证券营业部",
                    "seat_profile": {"type": "brokerage", "alias": None},
                    "buy_amount": 0,
                    "sell_amount": 219258,
                    "net_amount": -219258,
                }],
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
                "buy_seats": [{
                    "seat_name": "机构专用",
                    "seat_profile": {"type": "institution", "alias": "机构专用"},
                    "buy_amount": 400000,
                    "sell_amount": 100000,
                    "net_amount": 300000,
                }],
                "sell_seats": [{
                    "seat_name": "中信证券股份有限公司杭州延安路证券营业部",
                    "seat_profile": {"type": "brokerage", "alias": None},
                    "buy_amount": 0,
                    "sell_amount": 100000,
                    "net_amount": -100000,
                }],
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
        "range_seat_profile_summary": {
            "seat_count": 4,
            "by_type": {
                "institution": {
                    "seat_count": 1,
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 400000,
                    "sell_amount": 100000,
                    "net_amount": 300000,
                },
                "northbound": {
                    "seat_count": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "buy_amount": 0,
                    "sell_amount": 0,
                    "net_amount": 0,
                },
                "youzi": {
                    "seat_count": 1,
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 762307,
                    "sell_amount": 106076,
                    "net_amount": 656231,
                },
                "brokerage": {
                    "seat_count": 2,
                    "buy_count": 0,
                    "sell_count": 2,
                    "buy_amount": 0,
                    "sell_amount": 319258,
                    "net_amount": -319258,
                },
                "unknown": {
                    "seat_count": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "buy_amount": 0,
                    "sell_amount": 0,
                    "net_amount": 0,
                },
            },
            "youzi_aliases": ["拉萨天团"],
            "youzi_alias_strengths": [{
                "alias": "拉萨天团",
                "buy_count": 1,
                "sell_count": 0,
                "buy_amount": 762307,
                "sell_amount": 106076,
                "net_amount": 656231,
                "abs_net_amount": 656231,
                "net_direction": "net_buy",
                "trade_dates": ["2026-06-26"],
                "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
            }],
            "seats": {
                "brokerage:中信证券股份有限公司杭州延安路证券营业部": {
                    "type": "brokerage",
                    "alias": None,
                    "buy_count": 0,
                    "sell_count": 1,
                    "buy_amount": 0,
                    "sell_amount": 100000,
                    "net_amount": -100000,
                    "trade_dates": ["2026-06-25"],
                    "seat_names": ["中信证券股份有限公司杭州延安路证券营业部"],
                },
                "brokerage:国金证券股份有限公司上海奉贤区金碧路证券营业部": {
                    "type": "brokerage",
                    "alias": None,
                    "buy_count": 0,
                    "sell_count": 1,
                    "buy_amount": 0,
                    "sell_amount": 219258,
                    "net_amount": -219258,
                    "trade_dates": ["2026-06-26"],
                    "seat_names": ["国金证券股份有限公司上海奉贤区金碧路证券营业部"],
                },
                "institution:机构专用": {
                    "type": "institution",
                    "alias": "机构专用",
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 400000,
                    "sell_amount": 100000,
                    "net_amount": 300000,
                    "trade_dates": ["2026-06-25"],
                    "seat_names": ["机构专用"],
                },
                "youzi:拉萨天团": {
                    "type": "youzi",
                    "alias": "拉萨天团",
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 762307,
                    "sell_amount": 106076,
                    "net_amount": 656231,
                    "trade_dates": ["2026-06-26"],
                    "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
                },
            },
            "top_seats": [
                {
                    "key": "youzi:拉萨天团",
                    "type": "youzi",
                    "alias": "拉萨天团",
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 762307,
                    "sell_amount": 106076,
                    "net_amount": 656231,
                    "trade_dates": ["2026-06-26"],
                    "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
                },
                {
                    "key": "institution:机构专用",
                    "type": "institution",
                    "alias": "机构专用",
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 400000,
                    "sell_amount": 100000,
                    "net_amount": 300000,
                    "trade_dates": ["2026-06-25"],
                    "seat_names": ["机构专用"],
                },
                {
                    "key": "brokerage:国金证券股份有限公司上海奉贤区金碧路证券营业部",
                    "type": "brokerage",
                    "alias": None,
                    "buy_count": 0,
                    "sell_count": 1,
                    "buy_amount": 0,
                    "sell_amount": 219258,
                    "net_amount": -219258,
                    "trade_dates": ["2026-06-26"],
                    "seat_names": ["国金证券股份有限公司上海奉贤区金碧路证券营业部"],
                },
                {
                    "key": "brokerage:中信证券股份有限公司杭州延安路证券营业部",
                    "type": "brokerage",
                    "alias": None,
                    "buy_count": 0,
                    "sell_count": 1,
                    "buy_amount": 0,
                    "sell_amount": 100000,
                    "net_amount": -100000,
                    "trade_dates": ["2026-06-25"],
                    "seat_names": ["中信证券股份有限公司杭州延安路证券营业部"],
                },
            ],
            "recognition_summary": {
                "profiled_seat_count": 2,
                "brokerage_or_unknown_seat_count": 2,
                "profiled_abs_net_amount": 956231,
                "profiled_seat_ratio": 0.5,
                "profiled_abs_net_ratio": 0.7497,
                "youzi_abs_net_amount": 656231,
                "youzi_abs_net_ratio": 0.5145,
                "dominant_profiled_type": "youzi",
                "dominant_profiled_direction": "net_buy",
                "dominant_profiled_net_amount": 656231,
                "youzi_alias_count": 1,
                "youzi_aliases": ["拉萨天团"],
                "top_youzi_seats": [{
                    "key": "youzi:拉萨天团",
                    "type": "youzi",
                    "alias": "拉萨天团",
                    "buy_count": 1,
                    "sell_count": 0,
                    "buy_amount": 762307,
                    "sell_amount": 106076,
                    "net_amount": 656231,
                    "trade_dates": ["2026-06-26"],
                    "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
                }],
                "top_profiled_seats": [
                    {
                        "key": "youzi:拉萨天团",
                        "type": "youzi",
                        "alias": "拉萨天团",
                        "buy_count": 1,
                        "sell_count": 0,
                        "buy_amount": 762307,
                        "sell_amount": 106076,
                        "net_amount": 656231,
                        "trade_dates": ["2026-06-26"],
                        "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
                    },
                    {
                        "key": "institution:机构专用",
                        "type": "institution",
                        "alias": "机构专用",
                        "buy_count": 1,
                        "sell_count": 0,
                        "buy_amount": 400000,
                        "sell_amount": 100000,
                        "net_amount": 300000,
                        "trade_dates": ["2026-06-25"],
                        "seat_names": ["机构专用"],
                    },
                ],
            },
        },
    }


def test_fetch_lhb_detail_range_filters_by_dominant_type_and_direction(monkeypatch):
    def fake_fetch_lhb_rows(code, limit, page, start_date=None, end_date=None):
        return [
            {"trade_id": "100357777", "trade_date": "2026-06-26", "code": "000004"},
            {"trade_id": "100357666", "trade_date": "2026-06-25", "code": "000004"},
        ]

    def fake_fetch_lhb_detail(code=None, trade_date=None, trade_id=None, limit=10):
        flow_by_id = {
            "100357777": {
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
            "100357666": {
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
        }
        return {
            "_source": "legacy",
            "source_detail": "eastmoney:lhb-detail",
            "records": [{
                "trade_id": str(trade_id),
                "trade_date": "2026-06-26" if trade_id == "100357777" else "2026-06-25",
                "code": "000004",
                "seat_flow_analysis": flow_by_id[str(trade_id)],
            }],
        }

    monkeypatch.setattr(ad, "_fetch_lhb_rows", fake_fetch_lhb_rows)
    monkeypatch.setattr(ad, "_fetch_lhb_detail", fake_fetch_lhb_detail)

    out = ad._fetch_lhb_detail_range(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        dominant_type="youzi",
        dominant_direction="net_buy",
    )

    assert out["dominant_type"] == "youzi"
    assert out["dominant_direction"] == "net_buy"
    assert out["source_lhb_count"] == 2
    assert out["filtered_count"] == 1
    assert [record["trade_id"] for record in out["records"]] == ["100357777"]
    assert out["range_flow_summary"] == {
        "record_count": 1,
        "trade_dates": ["2026-06-26"],
        "dominant_type_counts": {
            "institution": 0,
            "northbound": 0,
            "youzi": 1,
            "brokerage": 0,
            "unknown": 0,
        },
        "dominant_direction_counts": {
            "net_buy": 1,
            "net_sell": 0,
            "flat": 0,
        },
        "net_amount_by_type": {
            "institution": 0,
            "northbound": 0,
            "youzi": 656231,
            "brokerage": -219258,
            "unknown": 0,
        },
        "youzi_aliases": ["拉萨天团"],
    }


def test_fetch_lhb_detail_range_filters_by_youzi_alias(monkeypatch):
    def fake_fetch_lhb_rows(code, limit, page, start_date=None, end_date=None):
        return [
            {"trade_id": "100357777", "trade_date": "2026-06-26", "code": "000004"},
            {"trade_id": "100357666", "trade_date": "2026-06-25", "code": "000004"},
        ]

    def fake_fetch_lhb_detail(code=None, trade_date=None, trade_id=None, limit=10):
        if trade_id == "100357777":
            alias = "拉萨天团"
            flow = {
                "institution_net_amount": 0,
                "northbound_net_amount": 0,
                "youzi_net_amount": 656231,
                "brokerage_net_amount": -219258,
                "unknown_net_amount": 0,
                "dominant_type": "youzi",
                "dominant_direction": "net_buy",
                "dominant_net_amount": 656231,
                "dominant_aliases": [alias],
            }
        else:
            alias = "章盟主"
            flow = {
                "institution_net_amount": 0,
                "northbound_net_amount": 0,
                "youzi_net_amount": -500000,
                "brokerage_net_amount": 100000,
                "unknown_net_amount": 0,
                "dominant_type": "youzi",
                "dominant_direction": "net_sell",
                "dominant_net_amount": -500000,
                "dominant_aliases": [alias],
            }
        return {
            "_source": "legacy",
            "source_detail": "eastmoney:lhb-detail",
            "records": [{
                "trade_id": str(trade_id),
                "trade_date": "2026-06-26" if trade_id == "100357777" else "2026-06-25",
                "code": "000004",
                "buy_seats": [{
                    "seat_name": f"{alias}常用席位",
                    "seat_profile": {"type": "youzi", "alias": alias},
                    "buy_amount": 100 if alias == "拉萨天团" else 300,
                    "sell_amount": 20 if alias == "拉萨天团" else 900,
                    "net_amount": 80 if alias == "拉萨天团" else -600,
                }],
                "sell_seats": [],
                "seat_flow_analysis": flow,
            }],
        }

    monkeypatch.setattr(ad, "_fetch_lhb_rows", fake_fetch_lhb_rows)
    monkeypatch.setattr(ad, "_fetch_lhb_detail", fake_fetch_lhb_detail)

    out = ad._fetch_lhb_detail_range(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        youzi_alias="拉萨天团",
    )

    assert out["youzi_alias"] == "拉萨天团"
    assert out["source_lhb_count"] == 2
    assert out["filtered_count"] == 1
    assert [record["trade_id"] for record in out["records"]] == ["100357777"]
    assert out["range_flow_summary"]["record_count"] == 1
    assert out["range_flow_summary"]["youzi_aliases"] == ["拉萨天团"]
    assert out["range_seat_profile_summary"]["seat_count"] == 1
    assert out["range_seat_profile_summary"]["youzi_aliases"] == ["拉萨天团"]
    assert out["range_seat_profile_summary"]["top_seats"] == [{
        "key": "youzi:拉萨天团",
        "type": "youzi",
        "alias": "拉萨天团",
        "buy_count": 1,
        "sell_count": 0,
        "buy_amount": 100,
        "sell_amount": 20,
        "net_amount": 80,
        "trade_dates": ["2026-06-26"],
        "seat_names": ["拉萨天团常用席位"],
    }]


def test_lhb_range_seat_profile_summary_reports_recognition_signals():
    records = [{
        "trade_date": "2026-06-26",
        "buy_seats": [
            {
                "seat_name": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                "seat_profile": {"type": "youzi", "alias": "拉萨天团"},
                "buy_amount": 762307,
                "sell_amount": 106076,
                "net_amount": 656231,
            },
            {
                "seat_name": "机构专用",
                "seat_profile": {"type": "institution", "alias": "机构专用"},
                "buy_amount": 400000,
                "sell_amount": 100000,
                "net_amount": 300000,
            },
        ],
        "sell_seats": [{
            "seat_name": "国金证券股份有限公司上海奉贤区金碧路证券营业部",
            "seat_profile": {"type": "brokerage", "alias": None},
            "buy_amount": 0,
            "sell_amount": 219258,
            "net_amount": -219258,
        }],
    }]

    out = ad._summarize_lhb_range_seat_profiles(records)

    assert out["recognition_summary"] == {
        "profiled_seat_count": 2,
        "brokerage_or_unknown_seat_count": 1,
        "profiled_abs_net_amount": 956231,
        "profiled_seat_ratio": 0.6667,
        "profiled_abs_net_ratio": 0.8135,
        "youzi_abs_net_amount": 656231,
        "youzi_abs_net_ratio": 0.5583,
        "dominant_profiled_type": "youzi",
        "dominant_profiled_direction": "net_buy",
        "dominant_profiled_net_amount": 656231,
        "youzi_alias_count": 1,
        "youzi_aliases": ["拉萨天团"],
        "top_youzi_seats": [{
            "key": "youzi:拉萨天团",
            "type": "youzi",
            "alias": "拉萨天团",
            "buy_count": 1,
            "sell_count": 0,
            "buy_amount": 762307,
            "sell_amount": 106076,
            "net_amount": 656231,
            "trade_dates": ["2026-06-26"],
            "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
        }],
        "top_profiled_seats": [
            {
                "key": "youzi:拉萨天团",
                "type": "youzi",
                "alias": "拉萨天团",
                "buy_count": 1,
                "sell_count": 0,
                "buy_amount": 762307,
                "sell_amount": 106076,
                "net_amount": 656231,
                "trade_dates": ["2026-06-26"],
                "seat_names": ["东方财富证券股份有限公司拉萨东环路第二证券营业部"],
            },
            {
                "key": "institution:机构专用",
                "type": "institution",
                "alias": "机构专用",
                "buy_count": 1,
                "sell_count": 0,
                "buy_amount": 400000,
                "sell_amount": 100000,
                "net_amount": 300000,
                "trade_dates": ["2026-06-26"],
                "seat_names": ["机构专用"],
            },
        ],
    }


def test_lhb_range_seat_profile_summary_aggregates_youzi_alias_strengths():
    records = [
        {
            "trade_date": "2026-06-26",
            "buy_seats": [
                {
                    "seat_name": "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                    "seat_profile": {"type": "youzi", "alias": "拉萨天团"},
                    "buy_amount": 1000,
                    "sell_amount": 100,
                    "net_amount": 900,
                },
                {
                    "seat_name": "国泰君安证券上海江苏路证券营业部",
                    "seat_profile": {"type": "youzi", "alias": "章盟主"},
                    "buy_amount": 200,
                    "sell_amount": 0,
                    "net_amount": 200,
                },
                {
                    "seat_name": "机构专用",
                    "seat_profile": {"type": "institution", "alias": "机构专用"},
                    "buy_amount": 300,
                    "sell_amount": 0,
                    "net_amount": 300,
                },
            ],
            "sell_seats": [{
                "seat_name": "东方财富证券股份有限公司拉萨团结路第二证券营业部",
                "seat_profile": {"type": "youzi", "alias": "拉萨天团"},
                "buy_amount": 0,
                "sell_amount": 400,
                "net_amount": -400,
            }],
        },
        {
            "trade_date": "2026-06-27",
            "buy_seats": [{
                "seat_name": "未映射游资席位",
                "seat_profile": {"type": "youzi", "alias": None},
                "buy_amount": 999,
                "sell_amount": 0,
                "net_amount": 999,
            }],
            "sell_seats": [{
                "seat_name": "国泰君安证券上海江苏路证券营业部",
                "seat_profile": {"type": "youzi", "alias": "章盟主"},
                "buy_amount": 10,
                "sell_amount": 900,
                "net_amount": -890,
            }],
        },
    ]

    out = ad._summarize_lhb_range_seat_profiles(records)

    assert out["youzi_alias_strengths"] == [
        {
            "alias": "章盟主",
            "buy_count": 1,
            "sell_count": 1,
            "buy_amount": 210,
            "sell_amount": 900,
            "net_amount": -690,
            "abs_net_amount": 690,
            "net_direction": "net_sell",
            "trade_dates": ["2026-06-26", "2026-06-27"],
            "seat_names": ["国泰君安证券上海江苏路证券营业部"],
        },
        {
            "alias": "拉萨天团",
            "buy_count": 1,
            "sell_count": 1,
            "buy_amount": 1000,
            "sell_amount": 500,
            "net_amount": 500,
            "abs_net_amount": 500,
            "net_direction": "net_buy",
            "trade_dates": ["2026-06-26"],
            "seat_names": [
                "东方财富证券股份有限公司拉萨东环路第二证券营业部",
                "东方财富证券股份有限公司拉萨团结路第二证券营业部",
            ],
        },
    ]


def test_fetch_lhb_detail_range_filters_by_min_dominant_net(monkeypatch):
    def fake_fetch_lhb_rows(code, limit, page, start_date=None, end_date=None):
        return [
            {"trade_id": "100357777", "trade_date": "2026-06-26", "code": "000004"},
            {"trade_id": "100357666", "trade_date": "2026-06-25", "code": "000004"},
        ]

    def fake_fetch_lhb_detail(code=None, trade_date=None, trade_id=None, limit=10):
        flow_by_id = {
            "100357777": {
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
            "100357666": {
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
        }
        return {
            "_source": "legacy",
            "source_detail": "eastmoney:lhb-detail",
            "records": [{
                "trade_id": str(trade_id),
                "trade_date": "2026-06-26" if trade_id == "100357777" else "2026-06-25",
                "code": "000004",
                "seat_flow_analysis": flow_by_id[str(trade_id)],
            }],
        }

    monkeypatch.setattr(ad, "_fetch_lhb_rows", fake_fetch_lhb_rows)
    monkeypatch.setattr(ad, "_fetch_lhb_detail", fake_fetch_lhb_detail)

    out = ad._fetch_lhb_detail_range(
        code="000004",
        start_date="2026-06-01",
        end_date="2026-06-26",
        min_dominant_net=500000,
    )

    assert out["min_dominant_net"] == 500000
    assert out["source_lhb_count"] == 2
    assert out["filtered_count"] == 1
    assert [record["trade_id"] for record in out["records"]] == ["100357777"]
    assert out["range_flow_summary"]["record_count"] == 1
    assert out["range_flow_summary"]["net_amount_by_type"]["youzi"] == 656231


def test_fetch_lhb_compare_ranks_codes_by_youzi_recognition(monkeypatch):
    calls = []

    def fake_fetch_range(
        code,
        start_date,
        end_date,
        list_limit=20,
        page=1,
        detail_limit=10,
        dominant_type=None,
        dominant_direction=None,
        youzi_alias=None,
        min_dominant_net=None,
    ):
        calls.append({
            "code": code,
            "start_date": start_date,
            "end_date": end_date,
            "list_limit": list_limit,
            "page": page,
            "detail_limit": detail_limit,
            "dominant_type": dominant_type,
            "dominant_direction": dominant_direction,
            "youzi_alias": youzi_alias,
            "min_dominant_net": min_dominant_net,
        })
        if code == "000004":
            return _lhb_compare_payload(
                code="000004",
                filtered_count=2,
                trade_dates=["2026-06-26"],
                profiled_abs_net_amount=500000,
                profiled_abs_net_ratio=0.5,
                youzi_abs_net_amount=300000,
                youzi_abs_net_ratio=0.3,
                top_alias="拉萨天团",
                top_alias_net=300000,
                youzi_aliases=["拉萨天团", "章盟主"],
            )
        return _lhb_compare_payload(
            code="000005",
            filtered_count=1,
            trade_dates=["2026-06-25"],
            profiled_abs_net_amount=800000,
            profiled_abs_net_ratio=0.8,
            youzi_abs_net_amount=700000,
            youzi_abs_net_ratio=0.7,
            top_alias="章盟主",
            top_alias_net=-700000,
        )

    monkeypatch.setattr(ad, "_fetch_lhb_detail_range", fake_fetch_range)

    out = ad._fetch_lhb_compare(
        codes=["000004", "000005"],
        start_date="2026-06-01",
        end_date="2026-06-26",
        list_limit=30,
        page=2,
        detail_limit=7,
        dominant_type="youzi",
        dominant_direction="net_buy",
        youzi_alias="拉萨天团",
        min_dominant_net=200000,
    )

    assert calls == [
        {
            "code": "000004",
            "start_date": "2026-06-01",
            "end_date": "2026-06-26",
            "list_limit": 30,
            "page": 2,
            "detail_limit": 7,
            "dominant_type": "youzi",
            "dominant_direction": "net_buy",
            "youzi_alias": "拉萨天团",
            "min_dominant_net": 200000,
        },
        {
            "code": "000005",
            "start_date": "2026-06-01",
            "end_date": "2026-06-26",
            "list_limit": 30,
            "page": 2,
            "detail_limit": 7,
            "dominant_type": "youzi",
            "dominant_direction": "net_buy",
            "youzi_alias": "拉萨天团",
            "min_dominant_net": 200000,
        },
    ]
    assert out == {
        "_source": "legacy",
        "source_detail": "eastmoney:lhb-compare",
        "codes": ["000004", "000005"],
        "start_date": "2026-06-01",
        "end_date": "2026-06-26",
        "list_limit": 30,
        "detail_limit": 7,
        "page": 2,
        "dominant_type": "youzi",
        "dominant_direction": "net_buy",
        "youzi_alias": "拉萨天团",
        "min_dominant_net": 200000,
        "sort_by": "youzi_abs_net_amount",
        "comparison_summary": {
            "code_count": 2,
            "matched_code_count": 2,
            "top_code_by_youzi_abs_net": "000005",
            "top_code_by_profiled_abs_net": "000005",
            "top_code_by_profiled_abs_net_ratio": "000005",
            "shared_youzi_aliases": ["章盟主"],
            "youzi_alias_frequency": [
                {"alias": "章盟主", "code_count": 2, "codes": ["000004", "000005"]},
                {"alias": "拉萨天团", "code_count": 1, "codes": ["000004"]},
            ],
        },
        "rows": [
            {
                "rank": 1,
                "code": "000005",
                "filtered_count": 1,
                "trade_dates": ["2026-06-25"],
                "profiled_abs_net_amount": 800000,
                "profiled_abs_net_ratio": 0.8,
                "youzi_abs_net_amount": 700000,
                "youzi_abs_net_ratio": 0.7,
                "dominant_profiled_type": "youzi",
                "dominant_profiled_direction": "net_sell",
                "dominant_profiled_net_amount": -700000,
                "youzi_alias_count": 1,
                "youzi_aliases": ["章盟主"],
                "top_youzi_alias": "章盟主",
                "top_youzi_alias_net_amount": -700000,
                "top_youzi_alias_abs_net_amount": 700000,
                "top_youzi_alias_direction": "net_sell",
            },
            {
                "rank": 2,
                "code": "000004",
                "filtered_count": 2,
                "trade_dates": ["2026-06-26"],
                "profiled_abs_net_amount": 500000,
                "profiled_abs_net_ratio": 0.5,
                "youzi_abs_net_amount": 300000,
                "youzi_abs_net_ratio": 0.3,
                "dominant_profiled_type": "youzi",
                "dominant_profiled_direction": "net_buy",
                "dominant_profiled_net_amount": 300000,
                "youzi_alias_count": 2,
                "youzi_aliases": ["拉萨天团", "章盟主"],
                "top_youzi_alias": "拉萨天团",
                "top_youzi_alias_net_amount": 300000,
                "top_youzi_alias_abs_net_amount": 300000,
                "top_youzi_alias_direction": "net_buy",
            },
        ],
    }


def _lhb_compare_payload(
    code,
    filtered_count,
    trade_dates,
    profiled_abs_net_amount,
    profiled_abs_net_ratio,
    youzi_abs_net_amount,
    youzi_abs_net_ratio,
    top_alias,
    top_alias_net,
    youzi_aliases=None,
):
    return {
        "code": code,
        "filtered_count": filtered_count,
        "range_flow_summary": {"trade_dates": trade_dates},
        "range_seat_profile_summary": {
            "youzi_alias_strengths": [{
                "alias": top_alias,
                "net_amount": top_alias_net,
                "abs_net_amount": abs(top_alias_net),
                "net_direction": "net_buy" if top_alias_net > 0 else "net_sell",
            }],
            "recognition_summary": {
                "profiled_abs_net_amount": profiled_abs_net_amount,
                "profiled_abs_net_ratio": profiled_abs_net_ratio,
                "youzi_abs_net_amount": youzi_abs_net_amount,
                "youzi_abs_net_ratio": youzi_abs_net_ratio,
                "dominant_profiled_type": "youzi",
                "dominant_profiled_direction": "net_buy" if top_alias_net > 0 else "net_sell",
                "dominant_profiled_net_amount": top_alias_net,
                "youzi_alias_count": len(youzi_aliases or [top_alias]),
                "youzi_aliases": youzi_aliases or [top_alias],
            },
        },
    }
