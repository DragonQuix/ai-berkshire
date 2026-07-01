# -*- coding: utf-8 -*-
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import report_audit as audit  # noqa: E402


def _capture_stdout(func, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = func(*args, **kwargs)
    return result, buf.getvalue()


def test_extract_data_points_reads_tables_and_kv_lines() -> None:
    text = """# 腾讯投资研究

| 指标 | 2025 | 2024 | 同比 |
|---|---:|---:|---:|
| 营业收入 | 6600亿 | 5900亿 | 12% |
| 毛利率 | 55% | 53% | 2% |

市值：5800亿
PE：18.8x

> 引用块：999亿

```text
代码块收入：123亿
```
"""

    points = audit.extract_data_points(text)
    labels = {p["label"]: p for p in points}

    assert labels["营业收入 · 2025"]["reported_value"] == 6600.0
    assert labels["营业收入 · 2025"]["unit"] == "亿"
    assert labels["营业收入 · 2024"]["reported_value"] == 5900.0
    assert labels["毛利率 · 2025"]["reported_value"] == 55.0
    assert labels["市值"]["reported_value"] == 5800.0
    assert labels["PE"]["unit"] == "x"
    assert all("同比" not in p["label"] for p in points)
    assert all("引用块" not in p["label"] for p in points)
    assert all("代码块收入" not in p["label"] for p in points)


def test_extract_data_points_preserves_signed_table_percentages() -> None:
    text = """# 估值情景

| 指标 | 数值 |
|---|---:|
| 乐观涨跌幅 | +174.3% |
| 悲观涨跌幅 | -46.5% |
"""

    points = audit.extract_data_points(text)
    labels = {p["label"]: p for p in points}

    assert labels["乐观涨跌幅 · 数值"]["reported_value"] == 174.3
    assert labels["悲观涨跌幅 · 数值"]["reported_value"] == -46.5


def test_extract_data_points_flags_core_table_without_caliber_source_column() -> None:
    text = """# 数据摘要

| 指标 | 2025 | 2024 |
|---|---:|---:|
| 营业收入 | 6600亿 | 5900亿 |
| 归母净利润 | 1800亿 | 1600亿 |
"""

    points = audit.extract_data_points(text)

    flagged = [p for p in points if p.get("caliber_column_warning")]
    assert flagged
    assert all("口径/来源" in p["caliber_column_note"] for p in flagged)


def test_extract_data_points_does_not_flag_core_table_with_caliber_source_column() -> None:
    text = """# 数据摘要

| 指标 | 2025 | 口径/来源 |
|---|---:|---|
| 营业收入 | 6600亿 | 理杏仁 toi=营业总收入 |
| 归母净利润 | 1800亿 | 理杏仁 npatoshopc |
"""

    points = audit.extract_data_points(text)

    assert points
    assert all(not p.get("caliber_column_warning") for p in points)


def test_extract_data_points_skips_stress_or_bias_tables_as_non_auditable_data() -> None:
    text = """# 压力测试

| 情景 | 触发条件 | 估值影响 | 应对 |
|---|---|---:|---|
| 权益市场2026-2027熊市 | 长端利率下行，负债久期拉长 | -15% | 降低仓位 |

# 偏误自查

| 自查项 | 触发条件 | 修正动作 | 影响 |
|---|---|---|---:|
| 市值锚定偏误 | 只看历史市值高点 | 改用 EV/NBV 与 ROE 交叉验证 | 20% |
"""

    points = audit.extract_data_points(text)

    assert points == []


def test_extract_data_points_skips_misaligned_table_rows_instead_of_guessing_columns() -> None:
    text = """# 估值核验

| 指标 | 2025 | 口径/来源 |
|---|---:|---|
| PE-TTM | 12.5x | lixinger | 61.75 |
| PB | 1.83x | lixinger |
"""

    points = audit.extract_data_points(text)
    labels = {p["label"]: p for p in points}

    assert "PE-TTM · 2025" not in labels
    assert "PE-TTM · 列3" not in labels
    assert labels["PB · 2025"]["reported_value"] == 1.83


def test_sample_points_respects_minimum_cap_seed_and_line_order() -> None:
    points = [
        {"id": i, "label": f"指标{i}", "line_number": 100 - i}
        for i in range(1, 41)
    ]

    small = audit.sample_points(points[:4], ratio=0.15, seed=1)
    capped = audit.sample_points(points, ratio=0.90, seed=1)
    first = audit.sample_points(points, ratio=0.30, seed=42)
    second = audit.sample_points(points, ratio=0.30, seed=42)

    assert len(small) == 3
    assert len(capped) == 30
    assert [p["id"] for p in first] == [p["id"] for p in second]
    assert [p["line_number"] for p in first] == sorted(p["line_number"] for p in first)


def test_sample_points_supports_deep_adaptive_count_without_cap() -> None:
    points = [
        {"id": i, "label": f"指标{i}", "line_number": i}
        for i in range(1, 201)
    ]

    sampled = audit.sample_points(
        points,
        ratio=0.25,
        seed=1,
        min_points=30,
        max_points=None,
    )

    assert len(sampled) == 50


def test_render_verdict_passes_when_all_fetched_values_within_tolerance() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 100.0,
                "unit": "亿",
                "fetched_value": 101.0,
                "fetched_source": "annual-report",
                "line_number": 10,
                "raw_text": "营业收入：100亿",
            }
        ],
        report_name="demo.md",
    )

    assert result["verdict"] == "PASS"
    assert result["pass_count"] == 1
    assert result["fail_count"] == 0
    assert "准出" in out


def test_render_verdict_fails_when_both_sources_exceed_tolerance() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 100.0,
                "unit": "亿",
                "fetched_value": 110.0,
                "fetched_source": "annual-report",
                "fetched_value2": 111.0,
                "fetched_source2": "exchange",
                "line_number": 10,
                "raw_text": "营业收入：100亿",
            }
        ],
    )

    assert result["verdict"] == "FAIL"
    assert result["fail_count"] == 1
    assert result["fail_items"][0]["diff1_pct"] == 10.0
    assert "打回" in out


def test_render_verdict_warns_but_does_not_fail_when_one_source_matches() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 100.0,
                "unit": "亿",
                "fetched_value": 100.0,
                "fetched_source": "annual-report",
                "fetched_value2": 110.0,
                "fetched_source2": "vendor",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["warn_count"] == 1
    assert result["fail_count"] == 0
    assert "警告" in out


def test_render_verdict_skips_non_numeric_fetched_values() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "发布日期",
                "reported_value": 2026,
                "fetched_value": "2026-07-01",
                "fetched_source": "announcement",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["pass_count"] == 0
    assert result["fail_count"] == 0
    assert "非数值" in out


def test_render_verdict_preserves_sign_unless_absolute_magnitude_requested() -> None:
    signed_result, _ = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "悲观涨跌幅",
                "reported_value": 46.5,
                "fetched_value": -46.5,
                "fetched_source": "manual",
            }
        ],
    )
    magnitude_result, _ = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "悲观跌幅",
                "reported_value": 46.5,
                "fetched_value": -46.5,
                "fetched_source": "manual",
                "compare_mode": "absolute_magnitude",
            }
        ],
    )

    assert signed_result["verdict"] == "FAIL"
    assert magnitude_result["verdict"] == "PASS"


def test_render_verdict_normalizes_fetched_unit_before_comparison() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "MAU",
                "reported_value": 14.3,
                "unit": "亿",
                "fetched_value": 1430,
                "fetched_unit": "百万",
                "fetched_source": "annual-report",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["pass_count"] == 1
    assert result["fail_count"] == 0
    assert "单位换算" in out


def test_render_verdict_warns_on_missing_unit_with_large_magnitude_gap() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "MAU",
                "reported_value": 14.3,
                "unit": "亿",
                "fetched_value": 1430,
                "fetched_source": "annual-report",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["warn_count"] == 1
    assert result["fail_count"] == 0
    assert "疑似单位不一致" in out
    assert "fetched_unit" in out


def test_render_verdict_accepts_documented_caliber_ack() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 7518.0,
                "unit": "亿",
                "fetched_value": 8365.0,
                "fetched_source": "lixinger",
                "caliber_ack": True,
                "caliber_note": "理杏仁 toi 为营业总收入，已在报告脚注说明。",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["pass_count"] == 0
    assert result["warn_count"] == 0
    assert result["fail_count"] == 0
    assert result["caliber_ack_count"] == 1
    assert result["caliber_ack_items"][0]["caliber_note"].startswith("理杏仁 toi")
    assert "口径认可" in out


def test_render_verdict_rejects_caliber_ack_without_note() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 7518.0,
                "unit": "亿",
                "fetched_value": 8365.0,
                "fetched_source": "lixinger",
                "caliber_ack": True,
                "caliber_note": " ",
            }
        ],
    )

    assert result["verdict"] == "FAIL"
    assert result["fail_count"] == 1
    assert "打回" in out


def test_render_verdict_surfaces_caliber_column_metadata_warning() -> None:
    result, out = _capture_stdout(
        audit.render_verdict,
        [
            {
                "id": 1,
                "label": "营业收入",
                "reported_value": 100.0,
                "unit": "亿",
                "fetched_value": 100.0,
                "fetched_source": "annual-report",
                "line_number": 8,
                "caliber_column_warning": True,
                "caliber_column_note": "核心数据表缺少口径/来源列",
            }
        ],
    )

    assert result["verdict"] == "PASS"
    assert result["warn_count"] == 0
    assert result["metadata_warn_count"] == 1
    assert result["metadata_warn_items"][0]["line_number"] == 8
    assert "元数据警告" in out
    assert "口径/来源" in out


def test_cli_extract_outputs_json_template(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        "| 指标 | 2025 |\n|---|---:|\n| 营业收入 | 6600亿 |\n| 毛利率 | 55% |\n"
        "市值：5800亿\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "extract",
            "--report",
            str(report),
            "--ratio",
            "1.0",
            "--seed",
            "1",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert "抽检清单 JSON" in proc.stdout
    assert '"fetched_value": null' in proc.stdout
    assert '"report_unit": "亿"' in proc.stdout
    assert '"fetched_unit": null' in proc.stdout


def test_cli_extract_output_writes_clean_json_file(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    output = tmp_path / "extract.json"
    report.write_text(
        "| 指标 | 2025 |\n|---|---:|\n| 营业收入 | 6600亿 |\n| 毛利率 | 55% |\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "extract",
            "--report",
            str(report),
            "--ratio",
            "1.0",
            "--seed",
            "1",
            "-o",
            str(output),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data
    assert data[0]["fetched_value"] is None
    assert "抽检清单 JSON" not in proc.stdout
    assert "抽检清单 JSON 已写入" in proc.stderr


def test_cli_extract_deep_depth_uses_adaptive_sample_count(tmp_path: Path) -> None:
    report = tmp_path / "deep-report.md"
    output = tmp_path / "extract.json"
    rows = "\n".join(
        f"| 指标{i} | {1000 + i}亿 | annual-report |"
        for i in range(1, 141)
    )
    report.write_text(
        "| 指标 | 2025 | 口径/来源 |\n|---|---:|---|\n" + rows + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "extract",
            "--report",
            str(report),
            "--depth",
            "deep",
            "--seed",
            "1",
            "-o",
            str(output),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(data) == 35
    assert "抽样比例：25%" in proc.stdout
    assert "抽检数量：35" in proc.stdout


def test_cli_verdict_exit_code_reflects_pass_or_fail() -> None:
    passing = [{
        "id": 1,
        "label": "营业收入",
        "reported_value": 100.0,
        "unit": "亿",
        "fetched_value": 100.0,
        "fetched_source": "annual-report",
    }]
    failing = [{**passing[0], "fetched_value": 110.0}]

    pass_proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "verdict",
            "--results",
            json.dumps(passing, ensure_ascii=False),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    fail_proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "verdict",
            "--results",
            json.dumps(failing, ensure_ascii=False),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert pass_proc.returncode == 0, pass_proc.stderr
    assert fail_proc.returncode == 1
    assert "准出" in pass_proc.stdout
    assert "打回" in fail_proc.stdout


def test_cli_verdict_writes_pure_json_output_file(tmp_path: Path) -> None:
    output = tmp_path / "verdict.json"
    results = [{
        "id": 1,
        "label": "MAU",
        "reported_value": 14.3,
        "unit": "亿",
        "fetched_value": 1430,
        "fetched_unit": "百万",
        "fetched_source": "annual-report",
    }]

    proc = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools" / "report_audit.py"),
            "verdict",
            "--results",
            json.dumps(results, ensure_ascii=False),
            "-o",
            str(output),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert "准出" in proc.stdout
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS"
    assert payload["pass_count"] == 1
    assert payload["fail_count"] == 0


def test_codex_copy_matches_root_report_audit_tool() -> None:
    root = (REPO / "tools" / "report_audit.py").read_text(encoding="utf-8")
    codex = (
        REPO / "codex" / "ai-berkshire" / "scripts" / "tools" / "report_audit.py"
    ).read_text(encoding="utf-8")

    assert codex == root
