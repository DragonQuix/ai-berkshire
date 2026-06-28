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
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from report_audit import extract_data_points, sample_points


ROLE_FILES = {
    "business-analyst.md": "business-analyst",
    "financial-analyst.md": "financial-analyst",
    "industry-researcher.md": "industry-researcher",
    "risk-assessor.md": "risk-assessor",
}

REQUIRED_ROOT_FILES = (
    "data-pack.json",
    "source-index.md",
    "audit-results.json",
    "最终报告.md",
)

SOURCE_REF_RE = re.compile(r"\b[SEPA]\d+\b")
REPORT_REF_CUE_RE = re.compile(r"(引用|source-index|source_refs?)", re.IGNORECASE)

AUDIT_ITEM_STATUSES = ("pass", "fail", "pending")
AUDIT_REQUIRED_FIELDS = ("claim", "report_location", "expected_value")


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


def _load_json(path: Path, invalid_files: list[dict[str, str]]) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        invalid_files.append({"file": path.name, "reason": f"invalid json: {exc}"})
        return None


def extract_source_index_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if SOURCE_REF_RE.fullmatch(first):
            refs.add(first)
    return refs


def extract_report_refs(text: str) -> set[str]:
    refs: set[str] = set()
    ref_columns: set[int] = set()
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(set(cell) <= {"-", ":"} for cell in cells):
                continue
            header_columns = {
                idx for idx, cell in enumerate(cells)
                if "来源" in cell or "ref" in cell.lower()
            }
            if header_columns:
                ref_columns = header_columns
                continue
            if ref_columns:
                for idx in ref_columns:
                    if idx < len(cells):
                        refs.update(SOURCE_REF_RE.findall(cells[idx]))
                continue
        else:
            ref_columns = set()
        if REPORT_REF_CUE_RE.search(line):
            refs.update(SOURCE_REF_RE.findall(line))
    return refs


def extract_json_source_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_ref" and isinstance(item, str) and SOURCE_REF_RE.fullmatch(item):
                refs.add(item)
            elif key == "source_refs" and isinstance(item, list):
                refs.update(ref for ref in item if isinstance(ref, str) and SOURCE_REF_RE.fullmatch(ref))
            else:
                refs.update(extract_json_source_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(extract_json_source_refs(item))
    return refs


def _add_undefined_ref_error(
    filename: str,
    refs: set[str],
    source_refs: set[str],
    invalid_files: list[dict[str, str]],
) -> list[str]:
    undefined = sorted(refs - source_refs)
    if undefined:
        invalid_files.append({
            "file": filename,
            "reason": f"undefined source refs: {', '.join(undefined)}",
        })
    return undefined


def _validate_audit_items(audit: dict[str, Any], invalid_files: list[dict[str, str]]) -> None:
    """校验 audit-results.json.items[*] 结构与 verdict/status 一致性。

    规则：
      - items 必须是列表。
      - 每个 item 必须是 dict，status 必须是 pass/fail/pending。
      - claim/report_location/expected_value 必须非空。
      - source_ref 非空时必须匹配 [SEPA]<digits> 格式，否则会被
        extract_json_source_refs 漏掉而绕过 undefined ref 检查。
      - status 为 pass/fail 时，verified_value 与 source_ref 必须非空。
      - verdict 为 pass 时，items 必须非空且全部 status == pass。
    """
    items = audit.get("items")
    if not isinstance(items, list):
        invalid_files.append({"file": "audit-results.json", "reason": "items must be a list"})
        return
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            invalid_files.append({
                "file": "audit-results.json",
                "reason": f"item {idx} must be an object",
            })
            continue
        status = item.get("status")
        if status not in AUDIT_ITEM_STATUSES:
            invalid_files.append({
                "file": "audit-results.json",
                "reason": f"item {idx} status must be pass/fail/pending",
            })
        missing = [f for f in AUDIT_REQUIRED_FIELDS if not item.get(f)]
        if missing:
            invalid_files.append({
                "file": "audit-results.json",
                "reason": f"item {idx} missing required fields: {', '.join(missing)}",
            })
        src_ref = item.get("source_ref", "")
        if src_ref and not SOURCE_REF_RE.fullmatch(src_ref):
            invalid_files.append({
                "file": "audit-results.json",
                "reason": f"item {idx} source_ref must match [SEPA]<digits>: {src_ref!r}",
            })
        if status in {"pass", "fail"} and (not item.get("verified_value") or not item.get("source_ref")):
            invalid_files.append({
                "file": "audit-results.json",
                "reason": f"item {idx} status {status} requires verified_value and source_ref",
            })
    verdict = audit.get("verdict")
    if verdict == "pass":
        if not items:
            invalid_files.append({
                "file": "audit-results.json",
                "reason": "verdict pass requires non-empty items",
            })
        elif not all(isinstance(item, dict) and item.get("status") == "pass" for item in items):
            invalid_files.append({
                "file": "audit-results.json",
                "reason": "verdict pass requires all items status pass",
            })


def _format_expected_value(value: Any, unit: str) -> str:
    """把抽检数据点的数值+单位格式化为 contract 中的 expected_value 字符串。"""
    if isinstance(value, (int, float)) and isinstance(value, float) and value.is_integer():
        num = str(int(value))
    elif isinstance(value, (int, float)):
        num = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        num = str(value)
    return f"{num} {unit}".strip() if unit else num


def audit_extract(
    company_dir: str | Path,
    ratio: float = 0.15,
    seed: int | None = None,
) -> dict[str, Any]:
    """从最终报告采样生成 contract 格式的抽检清单，写回 audit-results.json。

    复用 tools/report_audit.py 的数据点抽取与采样逻辑，把每个采样点映射为
    `audit-results.json.items[*]` 的 contract 结构（status=pending，verdict 强制
    重置为 reject）。Team Lead 随后逐项补 source_ref / verified_value / status，
    再交给 validate 把关。

    最终报告不存在时抛 FileNotFoundError。
    """
    root = Path(company_dir)
    report_path = root / "最终报告.md"
    if not report_path.exists():
        raise FileNotFoundError(f"最终报告不存在: {report_path}")

    points = extract_data_points(report_path.read_text(encoding="utf-8"))
    sampled = sample_points(points, ratio=ratio, seed=seed)
    items = [
        {
            "claim": point["label"],
            "report_location": f"第{point['line_number']}行",
            "source_ref": "",
            "expected_value": _format_expected_value(point["reported_value"], point["unit"]),
            "verified_value": "",
            "status": "pending",
            "note": f"原文摘录: {point['raw_text']}",
        }
        for point in sampled
    ]

    audit_path = root / "audit-results.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    else:
        audit = {
            "report": str(report_path),
            "generated_at": date.today().isoformat(),
            "sample_ratio": ratio,
            "items": [],
            "verdict": "reject",
        }
    audit["items"] = items
    audit["sample_ratio"] = ratio
    # 重新抽取抽检清单意味着前一次的 pass 判决失效，必须重新核验后再改回 pass
    audit["verdict"] = "reject"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return {
        "company_dir": str(root),
        "report": str(report_path),
        "extracted": len(points),
        "sampled": len(sampled),
        "sample_ratio": ratio,
        "seed": seed,
    }


def validate_team_research_outputs(company_dir: str | Path) -> dict[str, Any]:
    root = Path(company_dir)
    missing_files: list[str] = []
    invalid_files: list[dict[str, str]] = []
    undefined_refs: list[str] = []

    for filename in REQUIRED_ROOT_FILES:
        if not (root / filename).exists():
            missing_files.append(filename)

    role_dir = root / "role-briefs"
    for filename in ROLE_FILES:
        rel = f"role-briefs/{filename}"
        if not (role_dir / filename).exists():
            missing_files.append(rel)

    data_pack_path = root / "data-pack.json"
    data_pack_refs: set[str] = set()
    if data_pack_path.exists():
        data_pack = _load_json(data_pack_path, invalid_files)
        if data_pack is not None:
            if data_pack.get("meta", {}).get("owner") != "Team Lead":
                invalid_files.append({"file": "data-pack.json", "reason": "meta.owner must be Team Lead"})
            data_pack_refs = extract_json_source_refs(data_pack)

    audit_path = root / "audit-results.json"
    audit_refs: set[str] = set()
    if audit_path.exists():
        audit = _load_json(audit_path, invalid_files)
        if audit is not None:
            if audit.get("verdict") not in {"pass", "reject"}:
                invalid_files.append({"file": "audit-results.json", "reason": "verdict must be pass or reject"})
            _validate_audit_items(audit, invalid_files)
            audit_refs = extract_json_source_refs(audit)

    source_refs: set[str] = set()
    source_index_path = root / "source-index.md"
    if source_index_path.exists():
        source_refs = extract_source_index_refs(source_index_path.read_text(encoding="utf-8"))

    undefined_all: set[str] = set()
    undefined_all.update(_add_undefined_ref_error("data-pack.json", data_pack_refs, source_refs, invalid_files))
    undefined_all.update(_add_undefined_ref_error("audit-results.json", audit_refs, source_refs, invalid_files))

    report_path = root / "最终报告.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8")
        for section in ("## 关键数据溯源", "## 角色冲突与 Team Lead 仲裁"):
            if section not in report:
                invalid_files.append({"file": "最终报告.md", "reason": f"missing section: {section}"})
        report_refs = extract_report_refs(report)
        undefined_all.update(_add_undefined_ref_error("最终报告.md", report_refs, source_refs, invalid_files))

    undefined_refs = sorted(undefined_all)

    status = "pass" if not missing_files and not invalid_files else "fail"
    return {
        "company_dir": str(root),
        "status": status,
        "missing_files": missing_files,
        "invalid_files": invalid_files,
        "undefined_refs": undefined_refs,
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] not in {"init", "validate", "audit-extract", "-h", "--help"}:
        sys.argv.insert(1, "init")

    parser = argparse.ArgumentParser(description="初始化或校验 /investment-team 结构化产物目录")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="初始化结构化产物目录")
    init_parser.add_argument("company", help="公司名，例如 腾讯")
    init_parser.add_argument("--reports-dir", default="reports", help="报告根目录，默认 reports")
    init_parser.add_argument("--ticker", default="", help="证券代码，例如 00700")
    init_parser.add_argument("--market", default="", help="市场，例如 hk/cn/us")
    init_parser.add_argument("--date", default=None, help="生成日期 YYYY-MM-DD，默认今天")
    init_parser.add_argument("--overwrite", action="store_true", help="覆盖已有文件")
    init_parser.add_argument("--json", action="store_true", help="输出 JSON")

    validate_parser = subparsers.add_parser("validate", help="校验结构化产物目录")
    validate_parser.add_argument("company_dir", help="公司报告目录，例如 reports/腾讯")
    validate_parser.add_argument("--json", action="store_true", help="输出 JSON")

    audit_parser = subparsers.add_parser(
        "audit-extract",
        help="从最终报告采样生成 contract 格式抽检清单",
    )
    audit_parser.add_argument("company_dir", help="公司报告目录，例如 reports/腾讯")
    audit_parser.add_argument("--ratio", type=float, default=0.15, help="抽样比例，默认 0.15")
    audit_parser.add_argument("--seed", type=int, default=None, help="随机种子（可选，用于复现）")
    audit_parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if args.command in {None, "init"}:
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

    if args.command == "audit-extract":
        try:
            result = audit_extract(args.company_dir, ratio=args.ratio, seed=args.seed)
        except FileNotFoundError as exc:
            print(f"错误: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"company_dir: {result['company_dir']}")
            print(f"report: {result['report']}")
            print(f"extracted: {result['extracted']}")
            print(f"sampled: {result['sampled']}")
            print(f"sample_ratio: {result['sample_ratio']}")
            if result["seed"] is not None:
                print(f"seed: {result['seed']}")
        return 0

    result = validate_team_research_outputs(args.company_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"company_dir: {result['company_dir']}")
        print(f"status: {result['status']}")
        print(f"missing: {len(result['missing_files'])}")
        print(f"invalid: {len(result['invalid_files'])}")
    if result["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
