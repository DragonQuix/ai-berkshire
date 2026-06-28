"""龙虎榜席位画像与游资识别规则。

规则只覆盖已在本仓库引用资料中明确列出的席位关键词；未命中的营业部保持普通
brokerage，不做主观推断。
"""

from __future__ import annotations

PROFILE_SOURCE = "stock-deep-analyzer:lhb-analyzer/seat-encyclopedia"


KNOWN_ACTIVE_SEATS = (
    {
        "alias": "章盟主",
        "tier": "legend",
        "style": "大资金趋势波段，格局锁仓",
        "premium": "neutral",
        "keywords": (
            "国泰君安证券股份有限公司上海江苏路证券营业部",
            "国泰君安证券股份有限公司宁波彩虹北路证券营业部",
            "中信证券股份有限公司杭州延安路证券营业部",
        ),
    },
    {
        "alias": "孙哥",
        "tier": "legend",
        "style": "板块引导，波段锁仓",
        "premium": "neutral_positive",
        "keywords": (
            "中信证券股份有限公司上海溧阳路证券营业部",
            "中信证券股份有限公司上海古北路证券营业部",
            "中信证券股份有限公司上海分公司",
        ),
    },
    {
        "alias": "赵老哥",
        "tier": "legend",
        "style": "打板，二板定龙头",
        "premium": "positive",
        "keywords": (
            "浙商证券股份有限公司绍兴解放北路证券营业部",
            "中国银河证券股份有限公司绍兴证券营业部",
            "中国银河证券股份有限公司北京阜成路证券营业部",
        ),
    },
    {
        "alias": "佛山无影脚",
        "tier": "legend",
        "style": "一日游，翘板，砸盘王",
        "premium": "negative",
        "keywords": (
            "光大证券股份有限公司佛山绿景路证券营业部",
            "光大证券股份有限公司佛山季华六路证券营业部",
            "湘财证券股份有限公司佛山祖庙路证券营业部",
        ),
    },
    {
        "alias": "炒股养家",
        "tier": "legend",
        "style": "情绪揣摩，通道排板",
        "premium": "next_day_70",
        "keywords": (
            "华鑫证券有限责任公司上海红宝石路证券营业部",
            "华鑫证券有限责任公司上海宛平南路证券营业部",
        ),
    },
    {
        "alias": "陈小群",
        "tier": "new_gen",
        "style": "龙头接力、一线天、反核按钮",
        "premium": "next_day_57",
        "keywords": ("中国银河证券股份有限公司大连黄河路证券营业部",),
    },
    {
        "alias": "呼家楼",
        "tier": "new_gen",
        "style": "多席位协同、板块平铺扫货",
        "premium": None,
        "keywords": (
            "中信证券股份有限公司上海凯滨路证券营业部",
            "中信证券股份有限公司北京总部",
            "中信建投证券股份有限公司北京朝外大街证券营业部",
        ),
    },
    {
        "alias": "方新侠",
        "tier": "new_gen",
        "style": "大成交趋势票、格局锁仓",
        "premium": None,
        "keywords": (
            "兴业证券股份有限公司陕西分公司",
            "中信证券股份有限公司西安朱雀大街证券营业部",
        ),
    },
    {
        "alias": "作手新一",
        "tier": "new_gen",
        "style": "龙头战法，连板+趋势兼做",
        "premium": None,
        "keywords": ("国泰君安证券股份有限公司南京太平南路证券营业部",),
    },
    {
        "alias": "小鳄鱼",
        "tier": "new_gen",
        "style": "基本面辅助选股",
        "premium": None,
        "keywords": (
            "南京证券股份有限公司南京大钟亭证券营业部",
            "中金财富证券有限公司南京龙蟠中路证券营业部",
        ),
    },
    {
        "alias": "交易猿",
        "tier": "new_gen",
        "style": "大容量票锁仓、龙头加速",
        "premium": None,
        "keywords": (
            "华泰证券股份有限公司天津东丽开发区二纬路证券营业部",
            "招商证券股份有限公司福州六一中路证券营业部",
        ),
    },
    {
        "alias": "毛老板",
        "tier": "new_gen",
        "style": "AI主线大资金重仓",
        "premium": None,
        "keywords": (
            "国泰君安证券股份有限公司北京光华路证券营业部",
            "方正证券股份有限公司乐山龙游路证券营业部",
            "广发证券股份有限公司上海东方路证券营业部",
        ),
    },
    {
        "alias": "消闲派",
        "tier": "new_gen",
        "style": "满仓满融极致进攻",
        "premium": None,
        "keywords": ("华泰证券股份有限公司浙江分公司",),
    },
    {
        "alias": "拉萨天团",
        "tier": "regional",
        "style": "群狼一日游，反向指标",
        "premium": "negative",
        "keywords": ("东方财富证券股份有限公司拉萨",),
    },
    {
        "alias": "成都帮",
        "tier": "regional",
        "style": "底部黑马点火一日游",
        "premium": None,
        "keywords": ("华泰证券股份有限公司成都南一环路第二证券营业部",),
    },
    {
        "alias": "苏南帮",
        "tier": "regional",
        "style": "多席位联动低价小盘",
        "premium": None,
        "keywords": (
            "华泰证券股份有限公司无锡",
            "华泰证券股份有限公司镇江",
            "华泰证券股份有限公司南京",
        ),
    },
    {
        "alias": "宁波桑田路",
        "tier": "regional",
        "style": "连板接力",
        "premium": None,
        "keywords": ("国盛证券有限责任公司宁波桑田路证券营业部",),
    },
    {
        "alias": "六一中路",
        "tier": "new_2025",
        "style": "题材打板接力",
        "premium": None,
        "keywords": ("招商证券股份有限公司福州六一中路证券营业部",),
    },
    {
        "alias": "流沙河",
        "tier": "new_2025",
        "style": "低吸/接力新晋",
        "premium": None,
        "keywords": (
            "招商证券股份有限公司北京车公庄西路证券营业部",
            "华泰证券股份有限公司上海武定路证券营业部",
        ),
    },
    {
        "alias": "古北路",
        "tier": "new_2025",
        "style": "2025 重新活跃顶级短线",
        "premium": None,
        "keywords": ("中信证券股份有限公司上海古北路证券营业部",),
    },
)

SUMMARY_KEYS = ("institution", "northbound", "youzi", "brokerage", "unknown")


def build_lhb_seat_profile(seat_name: str | None, seat_category: str) -> dict:
    text = str(seat_name or "")
    if seat_category == "institution":
        return {
            "type": "institution",
            "alias": "机构专用",
            "tier": "institution",
            "style": "机构资金席位",
            "premium": "neutral",
            "matched_keyword": "机构专用",
            "match_type": "rule",
            "profile_source": "rule:seat-name",
        }
    if seat_category == "northbound":
        keyword = "沪股通专用" if "沪股通专用" in text else "深股通专用"
        return {
            "type": "northbound",
            "alias": "北向资金",
            "tier": "northbound",
            "style": "沪股通/深股通北向资金席位",
            "premium": "neutral",
            "matched_keyword": keyword,
            "match_type": "rule",
            "profile_source": "rule:seat-name",
        }
    if seat_category == "unknown":
        return _empty_profile("unknown")

    for profile in KNOWN_ACTIVE_SEATS:
        for keyword in profile["keywords"]:
            if keyword in text:
                return {
                    "type": "youzi",
                    "alias": profile["alias"],
                    "tier": profile["tier"],
                    "style": profile["style"],
                    "premium": profile["premium"],
                    "matched_keyword": keyword,
                    "match_type": "contains",
                    "profile_source": PROFILE_SOURCE,
                }
    return _empty_profile("brokerage")


def summarize_lhb_seat_profiles(buy_seats: list[dict], sell_seats: list[dict]) -> dict:
    return {
        "buy": _summarize_side(buy_seats),
        "sell": _summarize_side(sell_seats),
    }


def summarize_lhb_seat_amounts(buy_seats: list[dict], sell_seats: list[dict]) -> dict:
    summary = {key: _empty_amount_bucket() for key in SUMMARY_KEYS}
    for seat in buy_seats:
        _add_amounts(summary, seat, "buy")
    for seat in sell_seats:
        _add_amounts(summary, seat, "sell")
    return summary


def _empty_profile(profile_type: str) -> dict:
    return {
        "type": profile_type,
        "alias": None,
        "tier": None,
        "style": None,
        "premium": None,
        "matched_keyword": None,
        "match_type": None,
        "profile_source": None,
    }


def _summarize_side(seats: list[dict]) -> dict:
    summary = {key: 0 for key in SUMMARY_KEYS}
    aliases = []
    for seat in seats:
        profile = seat.get("seat_profile") or {}
        profile_type = profile.get("type") or seat.get("seat_category") or "unknown"
        if profile_type not in summary:
            profile_type = "brokerage"
        summary[profile_type] += 1
        alias = profile.get("alias")
        if profile_type == "youzi" and alias and alias not in aliases:
            aliases.append(alias)
    summary["aliases"] = aliases
    return summary


def _empty_amount_bucket() -> dict:
    return {
        "buy_amount": 0,
        "sell_amount": 0,
        "net_amount": 0,
        "buy_count": 0,
        "sell_count": 0,
        "aliases": [],
    }


def _add_amounts(summary: dict, seat: dict, side: str) -> None:
    profile = seat.get("seat_profile") or {}
    profile_type = profile.get("type") or seat.get("seat_category") or "unknown"
    if profile_type not in summary:
        profile_type = "brokerage"
    bucket = summary[profile_type]
    bucket["buy_amount"] += _numeric_amount(seat.get("buy_amount"))
    bucket["sell_amount"] += _numeric_amount(seat.get("sell_amount"))
    bucket["net_amount"] += _numeric_amount(seat.get("net_amount"))
    bucket[f"{side}_count"] += 1
    alias = profile.get("alias")
    if profile_type == "youzi" and alias and alias not in bucket["aliases"]:
        bucket["aliases"].append(alias)


def _numeric_amount(value) -> int | float:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return value
    try:
        num = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0
    return int(num) if num.is_integer() else num
