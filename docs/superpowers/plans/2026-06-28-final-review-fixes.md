# Final Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 2026-06-28 独立终审发现的阻塞项与高风险 WARNING，使 AI Berkshire 项目达到“无 FAIL 准出”状态。

**Architecture:** 采用小步串行修复：先修会影响运行正确性的代码缺陷，再修 Windows 兼容和 `_source` 规范，随后同步 codex 副本与文档状态，最后运行完整验证。所有变更保持现有 CLI 与 skill 文件结构，不引入新依赖，不改变默认用户工作流。

**Tech Stack:** Python 3.12, stdlib `urllib` / `tempfile` / `subprocess`, pytest, PowerShell, Markdown skills, Codex skill bundle.

## Global Constraints

- 当前执行环境是 Windows 安装的 Codex App + Windows 侧 PowerShell，不新增 WSL、`/mnt/c`、`/home/dragonquix`、`wsl.exe` 依赖。
- 所有用户可见沟通与项目文档使用简体中文；代码标识符保持英文。
- 不提交真实 `tools/lxr_config.json`、API key、token、cookies 或本地缓存。
- 不做大规模重构；每个任务只修改直接相关文件。
- 修改 `skills/*.md` 后必须同步 `codex/ai-berkshire/references/skills/*.md`。
- 修改 `tools/*.py` 中被 Codex bundle 使用的文件后必须同步 `codex/ai-berkshire/scripts/tools/*.py`。
- 完成前必须运行直接相关 pytest、渠道校验脚本、三条端到端 datapack 验证、`git status --short`。
- Commit message 使用中文，格式为 `<type>(scope): <summary>`，例如 `fix(review): 修复终审阻塞项`。

---

## File Structure

**Code files**

- Modify: `tools/lxr_data.py`
  - 修复 `datapack` 缓存失败 section。
  - 修复 `LxrData(mx_script=...)` 构造参数在新 `call_mx()` 路径中被忽略的问题。
- Modify: `tools/lxr_client.py`
  - 移除 `Accept-Encoding: br` 或实现 Brotli 解压；本计划选择移除 `br`，保持 stdlib 零依赖。
- Modify: `tools/xueqiu_scraper.py`
  - 将 `/tmp` 默认路径改为 `tempfile.gettempdir()`，保留 `--state-path` / `--raw-json` 覆盖能力。
- Modify: `tools/verify_channel_capability.py`
  - 扩展静态检查，覆盖所有增强 skill 的 `_source` 规范和 Unix 路径残留。
- Sync: `codex/ai-berkshire/scripts/tools/lxr_data.py`
- Sync: `codex/ai-berkshire/scripts/tools/lxr_client.py`
- Sync: `codex/ai-berkshire/scripts/tools/xueqiu_scraper.py` only if it exists; current bundle does not include it, so do not create unless implementation adds it intentionally.
- Sync: `codex/ai-berkshire/scripts/tools/verify_channel_capability.py`
- Sync: `codex/ai-berkshire/scripts/tools/report_audit.py`

**Tests**

- Modify: `tests/test_lxr_data.py`
  - 增加 partial datapack 不缓存的回归测试。
  - 增加 `mx_script` 构造参数可覆盖 mx-data 脚本的回归测试。
- Modify: `tests/test_lxr_client.py`
  - 增加 `Accept-Encoding` 不包含 `br` 的断言。
- Optionally modify: `tests/test_financial_rigor.py`
  - 仅当执行过程中改动 `financial_rigor.py` 时才修改；本计划不要求修改。

**Skill and docs files**

- Modify: `skills/news-pulse.md`
- Modify: `skills/wechat-article.md`
- Modify: `skills/bottleneck-hunter.md`
- Modify: `skills/earnings-review.md`
- Modify: `skills/quality-screen.md`
- Modify: any additional `skills/*.md` containing `~/ai-berkshire`, `/tmp`, or `_source: 理杏仁`.
- Sync: matching files under `codex/ai-berkshire/references/skills/`.
- Modify: `docs/plan-lixinger-migration.md`
- Modify: `docs/plan-skill-enhancement.md`
- Modify: `docs/channel-capability-matrix.md`
- Optionally modify: `docs/lixinger-data-guide.md` if wording conflicts with actual field counts.

---

## Task 1: Fix datapack failure caching and mx script override

**Files:**

- Modify: `tools/lxr_data.py`
- Modify: `tests/test_lxr_data.py`
- Sync: `codex/ai-berkshire/scripts/tools/lxr_data.py`

**Interfaces:**

- Consumes: existing `LxrData.get_research_datapack(code, years, name, include_mx, ttl_seconds) -> dict`.
- Produces: same public signature; cached datapack must not preserve transient `_source: none` sections when any section failed.
- Produces: `LxrData(mx_script="...")` must affect `mx-data` calls used by `_call_mx_skill()`.

- [ ] **Step 1: Add failing test for partial datapack not cached**

Add a test to `tests/test_lxr_data.py` using a fake cache and monkeypatched section functions. The exact assertion must prove that the first partial datapack is returned but not cached, and the second call recomputes sections.

```python
def test_datapack_does_not_cache_failed_sections(monkeypatch):
    from lxr_data import LxrData

    class FakeCache:
        def __init__(self):
            self.saved = None

        def get(self, endpoint, payload, ttl_seconds):
            return (self.saved is not None), self.saved

        def set(self, endpoint, payload, value):
            self.saved = value

    class FakeClient:
        def __init__(self):
            self.config = {"data_type_ttl_seconds": {}}
            self.cache = FakeCache()

    calls = {"mx_news": 0}
    d = LxrData(client=FakeClient(), verbose=False)

    monkeypatch.setattr("lxr_data._detect_market", lambda code: "cn")
    monkeypatch.setattr("lxr_data._norm_code", lambda code, market=None: "600519")
    monkeypatch.setattr(d, "detect_fs_type", lambda code: "non_financial")
    monkeypatch.setattr(d, "get_financials", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_valuation", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_verification_inputs", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_valuation_percentiles", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_governance", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_majority_shareholders", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "get_revenue_constitution", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "compare_industry_valuation", lambda *a, **k: {"_source": "lixinger"})
    monkeypatch.setattr(d, "mx_data", lambda *a, **k: {"_source": "mx-data", "raw": {"ok": True}})

    def flaky_mx_news(*args, **kwargs):
        calls["mx_news"] += 1
        if calls["mx_news"] == 1:
            raise RuntimeError("temporary timeout")
        return {"_source": "mx-search", "raw": {"ok": True}}

    monkeypatch.setattr(d, "mx_search", flaky_mx_news)

    first = d.get_research_datapack("600519", include_mx=True, ttl_seconds=3600)
    assert first["_source"] == "lixinger+partial-mx"
    assert first["sections"]["mx_news"]["_source"] == "none"
    assert d.client.cache.saved is None

    second = d.get_research_datapack("600519", include_mx=True, ttl_seconds=3600)
    assert second["_source"] == "lixinger+mx"
    assert second["sections"]["mx_news"]["_source"] == "mx-search"
    assert d.client.cache.saved is second
    assert calls["mx_news"] == 2
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest tests/test_lxr_data.py::test_datapack_does_not_cache_failed_sections -q
```

Expected before implementation: FAIL because `get_research_datapack()` currently calls `cache.set()` even when `sections.*._source == "none"`.

- [ ] **Step 3: Implement no-cache-on-partial logic**

In `tools/lxr_data.py`, change the end of `get_research_datapack()` so only fully successful packs are cached. Keep returning partial packs to the caller for transparency.

Use this exact shape:

```python
        pack["_source"] = _datapack_source(pack, include_mx)
        has_failed_section = any(
            isinstance(section, dict)
            and (section.get("_source") in (None, "", "none") or section.get("error"))
            for section in pack.get("sections", {}).values()
        )
        if not has_failed_section:
            self.client.cache.set("datapack/research", cache_key, pack)
        return pack
```

- [ ] **Step 4: Add failing test for `mx_script` override**

Add a test to `tests/test_lxr_data.py` proving `LxrData(mx_script=...)` is honored for `mx-data`.

```python
def test_mx_script_constructor_override_is_used_for_mx_data(tmp_path, monkeypatch):
    from lxr_data import LxrData

    script = tmp_path / "mx_data_fake.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "query = sys.argv[1]\n"
        "out_dir = pathlib.Path(sys.argv[2])\n"
        "out_dir.mkdir(parents=True, exist_ok=True)\n"
        "(out_dir / 'mx_data_fake_raw.json').write_text(json.dumps({'query': query, 'ok': True}), encoding='utf-8')\n",
        encoding="utf-8",
    )

    class FakeCache:
        dir = str(tmp_path / "cache")

        def get(self, endpoint, payload, ttl_seconds):
            return False, None

        def set(self, endpoint, payload, value):
            pass

    class FakeClient:
        config = {"data_type_ttl_seconds": {}}
        cache = FakeCache()

    d = LxrData(client=FakeClient(), mx_script=str(script), verbose=False)
    result = d.call_mx("mx-data", "贵州茅台 最新价", ttl_seconds=0)

    assert result["_source"] == "mx-data"
    assert result["raw"]["ok"] is True
    assert result["raw"]["query"] == "贵州茅台 最新价"
```

- [ ] **Step 5: Run the mx override test**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest tests/test_lxr_data.py::test_mx_script_constructor_override_is_used_for_mx_data -q
```

Expected before implementation: FAIL because `call_mx()` ignores `self.mx_script`.

- [ ] **Step 6: Implement mx-data override**

In `tools/lxr_data.py`, change `call_mx()` script resolution to use `self.mx_script` for `mx-data`.

Use this exact shape:

```python
        script = self.mx_script if skill == "mx-data" else _resolve_mx_script(skill)
```

Keep `mx-search` and `mx-xuangu` on `_resolve_mx_script()` because the constructor only exposes `mx_script` for legacy `mx-data` compatibility.

- [ ] **Step 7: Run targeted tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest tests/test_lxr_data.py -q
```

Expected: all `tests/test_lxr_data.py` tests PASS.

- [ ] **Step 8: Sync Codex script copy**

Run:

```powershell
Copy-Item -LiteralPath tools\lxr_data.py -Destination codex\ai-berkshire\scripts\tools\lxr_data.py -Force
```

- [ ] **Step 9: Commit Task 1**

Run:

```powershell
git add tools/lxr_data.py tests/test_lxr_data.py codex/ai-berkshire/scripts/tools/lxr_data.py
git commit -m "fix(data): 修复数据包失败缓存"
```

Expected: commit succeeds.

---

## Task 2: Fix Windows path blockers

**Files:**

- Modify: `tools/xueqiu_scraper.py`
- Modify: `skills/news-pulse.md`
- Modify: `skills/wechat-article.md`
- Modify: any other `skills/*.md` containing `~/ai-berkshire` or `/tmp`
- Sync: matching files in `codex/ai-berkshire/references/skills/`

**Interfaces:**

- Consumes: existing CLI `python tools/xueqiu_scraper.py --state-path ... --raw-json ...`.
- Produces: default state and raw JSON paths under `tempfile.gettempdir()` on Windows and POSIX.

- [ ] **Step 1: Add tempfile import and default path helpers**

Modify `tools/xueqiu_scraper.py` imports:

```python
import tempfile
```

Add helper functions near argument parsing:

```python
def default_state_path() -> str:
    return str(Path(tempfile.gettempdir()) / "xueqiu_state.json")


def default_raw_json_path(user_id: str) -> str:
    return str(Path(tempfile.gettempdir()) / f"xueqiu_{user_id}_raw.json")
```

- [ ] **Step 2: Replace `/tmp` defaults in `parse_args()` and `main()`**

Change `--state-path` default:

```python
    ap.add_argument("--state-path", type=str, default=default_state_path(),
                    help="登录态缓存文件（默认使用系统临时目录）")
```

Change raw JSON fallback:

```python
    raw_json = args.raw_json or default_raw_json_path(args.user_id)
```

Update module docstring examples to use PowerShell-friendly paths:

```text
python tools/xueqiu_scraper.py --user-id 6784593966 --keywords 茅台 --output "$env:TEMP\xueqiu-out.md"

登录态缓存默认使用系统临时目录，可用 --state-path 覆盖。
```

- [ ] **Step 3: Replace Unix paths in skill docs**

Use PowerShell:

```powershell
rg -n "~/ai-berkshire|/tmp" skills codex\ai-berkshire\references\skills
```

Replace examples as follows:

- `python3 ~/ai-berkshire/tools/financial_rigor.py ...` -> `python tools/financial_rigor.py ...`
- `python3 ~/ai-berkshire/tools/report_audit.py ...` -> `python tools/report_audit.py ...`
- `python3 ~/ai-berkshire/tools/xueqiu_scraper.py ... --output /tmp/dyp-{公司名}.md` -> `python tools/xueqiu_scraper.py ... --output "$env:TEMP\dyp-{公司名}.md"`
- `pdftoppm ... /tmp/page` -> `pdftoppm ... "$env:TEMP\page"`

- [ ] **Step 4: Sync skill docs**

Run:

```powershell
Get-ChildItem -LiteralPath skills -Filter *.md | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination ("codex\ai-berkshire\references\skills\" + $_.Name) -Force
}
```

- [ ] **Step 5: Verify no blockers remain**

Run:

```powershell
rg -n "~/ai-berkshire|/tmp|/usr/bin|wsl.exe|/mnt/c|/home/dragonquix" skills tools codex\ai-berkshire\references\skills
```

Expected: no matches, except explanatory references in global policy files outside this task if intentionally searched beyond `skills tools codex/...`.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add tools/xueqiu_scraper.py skills codex/ai-berkshire/references/skills
git commit -m "fix(windows): 移除阻塞性 Unix 路径"
```

Expected: commit succeeds.

---

## Task 3: Normalize `_source` values across all enhanced skills

**Files:**

- Modify: `skills/bottleneck-hunter.md`
- Modify: `skills/earnings-review.md`
- Modify: any `skills/*.md` containing `_source: 理杏仁` or source label `理杏仁` inside `_source` instructions.
- Sync: matching files under `codex/ai-berkshire/references/skills/`.
- Modify: `tools/verify_channel_capability.py`
- Sync: `codex/ai-berkshire/scripts/tools/verify_channel_capability.py`

**Interfaces:**

- Consumes: canonical source vocabulary from `skills/financial-data.md`.
- Produces: only these machine-readable source values in skill instructions: `lixinger`, `mx-data`, `mx-search`, `mx-xuangu`, `legacy`, `web`, `none`, `lixinger+mx`, `lixinger+partial-mx`.

- [ ] **Step 1: Replace non-canonical `_source` values**

Run:

```powershell
rg -n "_source: 理杏仁|`理杏仁`（结构化|来自理杏仁时标注" skills
```

Apply these replacements:

- `_source: 理杏仁` -> `_source: lixinger`
- `理杏仁（结构化财报/估值）` in a source-value list -> `lixinger（结构化财报/估值）`
- `结构化财报/估值来自理杏仁时标注 _source: 理杏仁` -> `结构化财报/估值来自理杏仁时标注 _source: lixinger`

- [ ] **Step 2: Sync skill docs**

Run:

```powershell
Get-ChildItem -LiteralPath skills -Filter *.md | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination ("codex\ai-berkshire\references\skills\" + $_.Name) -Force
}
```

- [ ] **Step 3: Extend static source validator**

In `tools/verify_channel_capability.py`, add a static scan that fails on non-canonical values and remaining Windows blockers.

Add constants:

```python
BAD_SOURCE_MARKERS = [
    "_source: 理杏仁",
    "`理杏仁`（结构化",
    "标注 `_source: 理杏仁`",
]

WINDOWS_BLOCKERS = [
    "~/ai-berkshire",
    "/tmp",
    "/usr/bin",
    "wsl.exe",
    "/mnt/c",
    "/home/dragonquix",
]
```

Add a function:

```python
def check_global_static_markers() -> int:
    print("\n-- C) 全量静态规范检查 --")
    rc = 0
    roots = [REPO / "skills", REPO / "codex" / "ai-berkshire" / "references" / "skills"]
    for root in roots:
        for path in sorted(root.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(REPO).as_posix()
            for marker in BAD_SOURCE_MARKERS:
                if marker in text:
                    _fail(f"{rel} 含非规范 _source 标记: {marker}")
                    rc |= 1
            for marker in WINDOWS_BLOCKERS:
                if marker in text:
                    _fail(f"{rel} 含 Windows 阻塞路径: {marker}")
                    rc |= 1
    if rc == 0:
        _pass("全量 skill 静态规范检查通过")
    return rc
```

Call it from `main()` after existing `check_skills_source_and_sync()`:

```python
    rc |= check_global_static_markers()
```

- [ ] **Step 4: Run static validator**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
```

Expected: PASS, with no non-canonical `_source` or Windows blocker failures.

- [ ] **Step 5: Sync validator to Codex**

Run:

```powershell
Copy-Item -LiteralPath tools\verify_channel_capability.py -Destination codex\ai-berkshire\scripts\tools\verify_channel_capability.py -Force
```

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add skills codex/ai-berkshire/references/skills tools/verify_channel_capability.py codex/ai-berkshire/scripts/tools/verify_channel_capability.py
git commit -m "fix(skills): 统一来源标注规范"
```

Expected: commit succeeds.

---

## Task 4: Correct capability claims and field-count wording

**Files:**

- Modify: `skills/quality-screen.md`
- Modify: `docs/channel-capability-matrix.md`
- Modify: `docs/plan-skill-enhancement.md`
- Modify: `docs/plan-lixinger-migration.md`
- Sync: `codex/ai-berkshire/references/skills/quality-screen.md`

**Interfaces:**

- Consumes: actual observed commands:
  - `python tools/lxr_data.py financials 600519 --years 5 --source lixinger --quiet` returns `metric_count=23`.
  - `python tools/lxr_data.py financials 601336 --years 5 --source lixinger --quiet` returns `metric_count=57`.
  - `python tools/lxr_data.py financials 00700 --years 5 --source lixinger --quiet` returns `metric_count=22`.
  - `python tools/lxr_data.py industry-deep 601336 --years 5 --quiet` returns `metric_count=128`.
- Produces: docs clearly distinguish API schema capability from currently requested metric set.

- [ ] **Step 1: Fix quality-screen unsupported claim**

In `skills/quality-screen.md`, replace:

```markdown
**已实测支持的 mx-xuangu 条件**：PE、PB、ROE、净利润增速、股息率、毛利率、净利率、资产负债率、FCF、收入增速、行业限定、涨跌幅。未在 `docs/channel-capability-matrix.md` 明确列入实测表的条件（如股价区间、成交量、换手率、市值区间、北向持股）不得写成“已确认支持”；需要使用时先实测，再更新矩阵。
```

with:

```markdown
**已实测支持的 mx-xuangu 条件**：PE、PB、ROE、净利润增速、股息率、毛利率、净利率、资产负债率、FCF、收入增速、行业限定、涨跌幅。未在 `docs/channel-capability-matrix.md` 明确列入实测表的条件（如股价区间、成交量、换手率、市值区间、北向持股）不得写成“已确认支持”；需要使用时先实测，再更新矩阵。
```

- [ ] **Step 2: Add actual metric-count note to capability matrix**

In `docs/channel-capability-matrix.md`, near the endpoint matrix, add:

```markdown
> **字段规模口径说明**：表中的 409/357/227 是理杏仁 API 文档披露的 schema 规模，不代表 `tools/lxr_data.py financials` 当前一次性拉取的指标数。当前 CLI 采用精选指标集：600519 `financials` 实测 `metric_count=23`，601336 `financials` 实测 `metric_count=57`，00700 `financials` 实测 `metric_count=22`；保险 `industry-deep` 实测 `metric_count=128`，用于 EV/NBV/偿付能力等深度字段。
```

- [ ] **Step 3: Update migration plan status**

In `docs/plan-lixinger-migration.md`, replace the header:

```markdown
> **状态**：规划阶段（待审核）
```

with:

```markdown
> **状态**：已实施（P1-P6 核心链路已落地；2026-06-28 终审要求补充修复见 `docs/superpowers/plans/2026-06-28-final-review-fixes.md`）
```

Then add a short status note after the dependency block:

```markdown
> **实现口径说明**：当前 `financials` CLI 拉取精选指标集，不等同于一次性拉取 API schema 全字段；需要全字段审计时应新增专门命令或分批请求，不得把 schema 字段数写成当前 CLI 实际输出字段数。
```

- [ ] **Step 4: Update enhancement plan wording**

In `docs/plan-skill-enhancement.md`, replace claims that conflate schema size with actual CLI output with wording that distinguishes schema and selected metrics:

```markdown
理杏仁 schema 覆盖 409 字段；当前 Skill 通过 `financials` 精选核心指标，并通过 `industry-deep` 补保险/银行/证券深度字段。
```

Apply the same distinction for 357 and 227 field claims.

- [ ] **Step 5: Sync quality-screen Codex reference**

Run:

```powershell
Copy-Item -LiteralPath skills\quality-screen.md -Destination codex\ai-berkshire\references\skills\quality-screen.md -Force
```

- [ ] **Step 6: Verify wording**

Run:

```powershell
rg -n "schema 字段数写成当前 CLI|mx-xuangu 旧条件.*股价区间" docs skills codex\ai-berkshire\references\skills
```

Expected: no stale overclaim matches.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add docs/plan-lixinger-migration.md docs/plan-skill-enhancement.md docs/channel-capability-matrix.md skills/quality-screen.md codex/ai-berkshire/references/skills/quality-screen.md
git commit -m "docs(data): 修正能力边界表述"
```

Expected: commit succeeds.

---

## Task 5: Fix Codex bundle synchronization

**Files:**

- Sync: `codex/ai-berkshire/scripts/tools/report_audit.py`
- Sync: `codex/ai-berkshire/scripts/tools/verify_channel_capability.py`
- Verify: all files under `skills/*.md` and `codex/ai-berkshire/references/skills/*.md`
- Verify: selected tool files under `tools/` and `codex/ai-berkshire/scripts/tools/`

**Interfaces:**

- Produces: SHA256 equality for all intended Codex bundle mirrors.

- [ ] **Step 1: Sync report audit**

Run:

```powershell
Copy-Item -LiteralPath tools\report_audit.py -Destination codex\ai-berkshire\scripts\tools\report_audit.py -Force
```

- [ ] **Step 2: Sync verify_channel_capability**

Run:

```powershell
Copy-Item -LiteralPath tools\verify_channel_capability.py -Destination codex\ai-berkshire\scripts\tools\verify_channel_capability.py -Force
```

- [ ] **Step 3: Run hash comparison**

Run:

```powershell
$pairs = @(
  'lxr_client.py',
  'lxr_cache.py',
  'lxr_data.py',
  'financial_rigor.py',
  'ashare_data.py',
  'report_audit.py',
  'stock_screener.py',
  'verify_channel_capability.py',
  'lxr_config.example.json'
)
foreach ($p in $pairs) {
  $a = "tools\$p"
  $b = "codex\ai-berkshire\scripts\tools\$p"
  $ha = (Get-FileHash -Algorithm SHA256 -LiteralPath $a).Hash
  $hb = (Get-FileHash -Algorithm SHA256 -LiteralPath $b).Hash
  if ($ha -ne $hb) { throw "DIFF $p $ha $hb" }
  "PASS $p"
}
```

Expected: every pair prints `PASS`.

- [ ] **Step 4: Run skill reference hash comparison**

Run:

```powershell
$root = Get-ChildItem -LiteralPath skills -File -Filter *.md | Sort-Object Name | ForEach-Object Name
$codex = Get-ChildItem -LiteralPath codex\ai-berkshire\references\skills -File -Filter *.md | Sort-Object Name | ForEach-Object Name
$diff = Compare-Object $root $codex
if ($diff) { $diff | Format-Table; throw "skill file set mismatch" }
foreach ($p in $root) {
  $a = "skills\$p"
  $b = "codex\ai-berkshire\references\skills\$p"
  $ha = (Get-FileHash -Algorithm SHA256 -LiteralPath $a).Hash
  $hb = (Get-FileHash -Algorithm SHA256 -LiteralPath $b).Hash
  if ($ha -ne $hb) { throw "DIFF $p" }
  "PASS $p"
}
```

Expected: every skill prints `PASS`.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add codex/ai-berkshire/scripts/tools/report_audit.py codex/ai-berkshire/scripts/tools/verify_channel_capability.py codex/ai-berkshire/scripts/tools/lxr_data.py codex/ai-berkshire/scripts/tools/lxr_client.py codex/ai-berkshire/references/skills
git commit -m "chore(codex): 同步 Codex 技能副本"
```

Expected: commit succeeds if there are staged changes. If Task 1-4 already synced all files and there is no diff, skip this commit and record “no-op, already synchronized” in final notes.

---

## Task 6: Fix Lixinger client encoding header

**Files:**

- Modify: `tools/lxr_client.py`
- Modify: `tests/test_lxr_client.py`
- Sync: `codex/ai-berkshire/scripts/tools/lxr_client.py`

**Interfaces:**

- Consumes: existing `LixingerClient._build_request(endpoint, payload) -> urllib.request.Request`.
- Produces: `Accept-Encoding` only advertises encodings the client can decode with stdlib.

- [ ] **Step 1: Add failing header test**

Add to `tests/test_lxr_client.py`:

```python
def test_accept_encoding_only_advertises_supported_codecs(self):
    c = self._client(token="tok")
    req = c._build_request("cn/company", {"token": "tok"})
    enc = req.headers.get("Accept-encoding") or req.headers.get("Accept-Encoding")
    self.assertIn("gzip", enc)
    self.assertIn("deflate", enc)
    self.assertNotIn("br", enc)
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest tests/test_lxr_client.py::TestLixingerClient::test_accept_encoding_only_advertises_supported_codecs -q
```

Expected before implementation: FAIL because header contains `br`.

- [ ] **Step 3: Remove `br` from header**

In `tools/lxr_client.py`, replace:

```python
"Accept-Encoding": "gzip, deflate, br",
```

with:

```python
"Accept-Encoding": "gzip, deflate",
```

- [ ] **Step 4: Run client tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest tests/test_lxr_client.py -q
```

Expected: all client tests PASS.

- [ ] **Step 5: Sync Codex script copy**

Run:

```powershell
Copy-Item -LiteralPath tools\lxr_client.py -Destination codex\ai-berkshire\scripts\tools\lxr_client.py -Force
```

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add tools/lxr_client.py tests/test_lxr_client.py codex/ai-berkshire/scripts/tools/lxr_client.py
git commit -m "fix(lixinger): 修正请求压缩头"
```

Expected: commit succeeds.

---

## Task 7: Final verification and release-gate audit

**Files:**

- No planned source changes unless verification exposes a concrete regression.

**Interfaces:**

- Produces: final verification evidence for no-FAIL准出.

- [ ] **Step 1: Run unit tests**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run channel capability validator**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/verify_channel_capability.py
```

Expected: both commands exit 0.

- [ ] **Step 3: Run fallback-chain smoke test**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import os
from pathlib import Path
from lxr_client import LixingerClient
from lxr_data import LxrData

cfg = {
    "base_url": "https://open.lixinger.com/api/",
    "request": {"timeout_seconds": 10, "max_retries": 0, "min_interval_seconds": 0},
    "cache": {"enabled": False},
    "data_type_ttl_seconds": {"financials": 0, "valuation": 0, "company_list": 0},
}

d = LxrData(client=LixingerClient(config=cfg, token="invalid-token-for-fallback-test"), verbose=True)
res = d.get_financials("600519", years=1, source="auto", name="贵州茅台")
print("first fallback source =", res.get("_source"))
assert res.get("_source") == "mx-data"

fail_script = Path(os.environ["TEMP"]) / "mx_fail_for_final_gate.py"
fail_script.write_text("import sys; print('forced mx failure', file=sys.stderr); sys.exit(1)", encoding="utf-8")
os.environ["MX_DATA_SCRIPT"] = str(fail_script)
try:
    d = LxrData(client=LixingerClient(config=cfg, token="invalid-token-for-fallback-test"), verbose=True)
    res = d.get_financials("600519", years=1, source="auto", name="贵州茅台")
    print("second fallback source =", res.get("_source"))
    assert res.get("_source") == "legacy"
finally:
    fail_script.unlink(missing_ok=True)
'@ | python -
```

Expected: prints `first fallback source = mx-data` and `second fallback source = legacy`.

- [ ] **Step 4: Run three datapack end-to-end checks**

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/lxr_data.py datapack 600519 --years 5 --name 贵州茅台 --quiet | python -c "import sys,json; d=json.load(sys.stdin); s=d['sections']; print(d['_source'], s['financials']['_source'], s['mx_quote']['_source'], s['mx_news']['_source']); assert d['_source']=='lixinger+mx'"
python tools/lxr_data.py datapack 601336 --years 5 --name 新华保险 --quiet | python -c "import sys,json; d=json.load(sys.stdin); s=d['sections']; print(d['_source'], s['financials']['report_type'], bool(s['industry_deep']['deep_summary']['ev']), bool(s['industry_deep']['deep_summary']['nbv'])); assert s['financials']['report_type']=='insurance'; assert s['industry_deep']['deep_summary']['ev']; assert s['industry_deep']['deep_summary']['nbv']"
python tools/lxr_data.py datapack 00700 --years 5 --name 腾讯控股 --quiet | python -c "import sys,json; d=json.load(sys.stdin); s=d['sections']; print(d['_source'], d['market'], s['financials']['_source'], s['mx_quote']['_source'], s['mx_news']['_source']); assert d['market']=='hk'; assert s['financials']['_source']=='lixinger'; assert s['mx_quote']['_source']=='mx-data'; assert s['mx_news']['_source']=='mx-search'"
```

Expected: all assertions pass. If any MX command times out, rerun once with `--ttl 0`; if it still fails, record external service failure and do not cache partial results.

- [ ] **Step 5: Verify no stale blockers**

Run:

```powershell
rg -n "_source: 理杏仁|~/ai-berkshire|/tmp|mx-xuangu 旧条件.*股价区间" skills tools docs codex\ai-berkshire\references\skills
```

Expected: no matches except historical review reports if the search is expanded to `docs/review-*.md`. Do not rewrite historical review reports unless they are presented as current state.

- [ ] **Step 6: Verify Codex sync**

Run the hash comparisons from Task 5 Step 3 and Step 4.

Expected: all mirrored files match.

- [ ] **Step 7: Check working tree**

Run:

```powershell
git status --short
```

Expected: empty.

- [ ] **Step 8: If final verification required a cleanup commit, commit it**

Only if Task 7 produced a source/documentation change:

```powershell
git add <changed-files>
git commit -m "chore(review): 完成终审准出清理"
```

Expected: commit succeeds or no changes are present.

---

## Self-Review Checklist

- [ ] Task 1 covers FAIL: datapack partial cache pollution and mx override inconsistency.
- [ ] Task 2 covers FAIL: Windows-blocking Unix paths in skills and `xueqiu_scraper.py`.
- [ ] Task 3 covers FAIL: non-canonical `_source` values.
- [ ] Task 4 covers FAIL/WARNING: unsupported mx-xuangu claim and field-count overclaim.
- [ ] Task 5 covers FAIL: Codex bundle sync drift.
- [ ] Task 6 covers WARNING: unsupported Brotli advert in `Accept-Encoding`.
- [ ] Task 7 covers final verification, including unit tests, channel validator, fallback chain, and three target datapacks.
- [ ] No task requires WSL or non-Windows paths.
- [ ] No task commits real token/config/cache files.

## Continuation Prompt

Use this prompt in a fresh context:

```text
继续 E:\Repos\Skills\ai-berkshire 的终审修复工作。先读取并严格执行计划文件：

E:\Repos\Skills\ai-berkshire\docs\superpowers\plans\2026-06-28-final-review-fixes.md

当前背景：
- 上一轮独立终审判决为“打回修改”。
- 主要 FAIL：datapack 缓存失败 section、Windows 阻塞路径、_source 非规范值、quality-screen 过度声明、codex 工具副本不同步、文档状态/字段规模表述不一致。
- 计划文件已经落盘并提交；不要重新审查全仓库来替代执行计划。
- 使用 Windows PowerShell，设置 `$env:PYTHONIOENCODING='utf-8'` 后运行 Python/pytest。
- 按计划 Task 1 到 Task 7 串行执行；每个任务完成后运行该任务指定验证并按计划提交。
- 禁止提交 `tools/lxr_config.json`、token、cookies、缓存和 pycache。
- 修改 `skills/*.md` 后同步 `codex/ai-berkshire/references/skills/*.md`；修改 bundle 使用的 `tools/*.py` 后同步 `codex/ai-berkshire/scripts/tools/*.py`。
- 完成前必须运行：`pytest -q`、`python tools/verify_channel_capability.py --quick`、`python tools/verify_channel_capability.py`、fallback-chain smoke test、600519/601336/00700 三条 datapack 验证、Codex hash sync 检查、`git status --short`。

请从读取计划文件开始，使用 superpowers:executing-plans 执行，不要跳步。
```
