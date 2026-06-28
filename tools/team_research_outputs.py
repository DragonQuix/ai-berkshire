#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize /investment-team output artifacts.

The tool scaffolds the P1 team-research output contract without doing any
research. It creates empty, explicit templates that Team Lead can fill during
the workflow.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


ROLE_FILES = {
    "business-analyst.md": "business-analyst",
    "financial-analyst.md": "financial-analyst",
    "industry-researcher.md": "industry-researcher",
    "risk-assessor.md": "risk-assessor",
}


def build_data_pack(company: str, ticker: str, market: str, generated_at: str) -> dict[str, Any]:
    return {
        "meta": {
            "company": company,
            "ticker": ticker,
            "market": market,
            "generated_at": generated_at,
            "owner": "Team Lead",
        },
        "financials": {
            "currency": "",
            "unit": "",
            "periods": [],
            "source_refs": [],
        },
        "valuation": {
            "price": None,
            "market_cap_checked": None,
            "source_refs": [],
        },
        "business_segments": [],
        "management_and_governance": [],
        "industry_and_competition": [],
        "risks_and_counterevidence": [],
        "tool_outputs": [],
        "known_gaps": [],
    }


def render_source_index(company: str) -> str:
    return f"""# {company} 来源索引

| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |
|---|---|---|---|---|---|---|---|

## 反证材料

-

## 已知缺口

-
"""


def render_role_brief(company: str, role: str) -> str:
    return f"""# {company} {role} 角色简报

## 角色输入范围

- `data-pack.json` 字段：
- `source-index.md` ref：

## 核心结论与评分

-

## 使用的证据

-

## 反面证据

-

## 不确定性

-

## 补数请求

-

## 与其他角色可能冲突的判断

-
"""


def build_audit_results(company: str, generated_at: str) -> dict[str, Any]:
    return {
        "report": f"reports/{company}/最终报告.md",
        "generated_at": generated_at,
        "sample_ratio": 0.15,
        "items": [],
        "verdict": "reject",
    }


def render_final_report(company: str, generated_at: str) -> str:
    return f"""# {company} 投资研究最终报告

**日期**：{generated_at}

## 一句话结论

> 待补充。

## 四维评分总表

| 维度 | 框架 | 评分(1-5星) | 核心判断 | 来源/ref |
|---|---|---:|---|---|

## 核心数据速览

| 指标 | 数值 | 期间 | 口径 | 来源/ref |
|---|---:|---|---|---|

## 各维度分析摘要

-

## 投资论点（Bull vs Bear）

### 看多逻辑

-

### 看空逻辑

-

## 最终投资建议

-

## 关键数据溯源

- 财务与估值数字必须引用 `data-pack.json` 字段和 `source-index.md` ref。
- 行业、竞争、治理与风险事实必须引用 `source-index.md` ref。
- 工具验算结果必须引用 `data-pack.json.tool_outputs` 或报告内命令输出摘要。

## 角色冲突与 Team Lead 仲裁

- 未发现影响最终结论的角色冲突。检查范围：`role-briefs/` 四份角色简报。
"""


def _write_text(path: Path, text: str, overwrite: bool, created: list[str], skipped: list[str]) -> None:
    if path.exists() and not overwrite:
        skipped.append(str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    created.append(str(path))


def _write_json(path: Path, data: dict[str, Any], overwrite: bool, created: list[str], skipped: list[str]) -> None:
    _write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        overwrite=overwrite,
        created=created,
        skipped=skipped,
    )


def init_team_research_outputs(
    reports_dir: str | Path,
    company: str,
    ticker: str = "",
    market: str = "",
    generated_at: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    generated_at = generated_at or date.today().isoformat()
    reports_root = Path(reports_dir)
    company_dir = reports_root / company
    role_dir = company_dir / "role-briefs"
    created: list[str] = []
    skipped: list[str] = []

    _write_json(
        company_dir / "data-pack.json",
        build_data_pack(company, ticker, market, generated_at),
        overwrite,
        created,
        skipped,
    )
    _write_text(company_dir / "source-index.md", render_source_index(company), overwrite, created, skipped)
    for filename, role in ROLE_FILES.items():
        _write_text(role_dir / filename, render_role_brief(company, role), overwrite, created, skipped)
    _write_json(
        company_dir / "audit-results.json",
        build_audit_results(company, generated_at),
        overwrite,
        created,
        skipped,
    )
    _write_text(company_dir / "最终报告.md", render_final_report(company, generated_at), overwrite, created, skipped)

    return {
        "company_dir": str(company_dir),
        "created_files": created,
        "skipped_files": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化 /investment-team 结构化产物目录")
    parser.add_argument("company", help="公司名，例如 腾讯")
    parser.add_argument("--reports-dir", default="reports", help="报告根目录，默认 reports")
    parser.add_argument("--ticker", default="", help="证券代码，例如 00700")
    parser.add_argument("--market", default="", help="市场，例如 hk/cn/us")
    parser.add_argument("--date", default=None, help="生成日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有文件")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    result = init_team_research_outputs(
        reports_dir=args.reports_dir,
        company=args.company,
        ticker=args.ticker,
        market=args.market,
        generated_at=args.date,
        overwrite=args.overwrite,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"company_dir: {result['company_dir']}")
        print(f"created: {len(result['created_files'])}")
        print(f"skipped: {len(result['skipped_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
