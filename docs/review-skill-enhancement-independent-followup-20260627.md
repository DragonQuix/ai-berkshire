# 双渠道 Skill 增强独立复审结论（修复前交接）

> 审核日期：2026-06-27  
> 审核角色：独立审核 Agent  
> 审核对象：`docs/plan-skill-enhancement.md` E0-E4 增强实施结果  
> 当前分支：`feat/enhancement-e4`  
> 最终判决：**打回修改**  

## 一、结论摘要

核心数据通道已经可用，E0 关键能力复验通过，`investment-research`、`management-deep-dive`、`quality-screen`、`news-pulse` 的主要架构问题基本修正。

但仍有两类问题必须修复后才能准出：

1. 多个增强后的 Skill 没有按验收标准统一使用 `_source` 字段标注数据来源。
2. `/quality-screen` 的理杏仁精确复核层虽然可运行，但实测 5 个候选全部缺失 `share_dilution_5y`，导致 7 指标结果不完整。

## 二、已执行验证命令

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/lxr_data.py industry-deep 601336 --years 3
python tools/lxr_data.py datapack 600519 --years 5 --name 贵州茅台
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 300492 --years 5 --quiet
python tools/lxr_data.py quality-metrics 600185 --years 5 --quiet
python tools/lxr_data.py quality-metrics 300972 --years 5 --quiet
python tools/lxr_data.py quality-metrics 002640 --years 5 --quiet
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
python tools/lxr_data.py mx-data "腾讯控股近三年净利润 营业收入" --ttl 0
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
git status --short --branch
```

关键结果：

| 验证项 | 结果 |
|---|---|
| `verify_channel_capability.py --quick` | PASS，5/5 |
| `industry-deep 601336` | PASS，`q.bs.ev.t` 与 `q.ps.nbv.t` 存在 |
| `datapack 600519` | PASS，返回理杏仁 + MX 数据 |
| `mx-xuangu "ROE>15% PE<30 消费股"` | PASS，返回 5 个候选 |
| 5 个候选逐只 `quality-metrics` | WARNING，均缺 `share_dilution_5y` |
| 港股 mx-data 腾讯财务 | PASS，返回 2023-2026Q1 表 |
| `compileall` | PASS |
| `pytest` | PASS，44 passed |
| `git status` | PASS，工作区干净 |

## 三、逐项审核结果

| 项目 | 判定 | 说明 |
|---|---|---|
| E0 能力矩阵产出 | PASS | `docs/channel-capability-matrix.md` 存在，关键命令复验通过 |
| EV/NBV 是否在理杏仁 insurance 报表中 | PASS | 实测 `q.bs.ev.t`、`q.ps.nbv.t` 存在 |
| mx-xuangu 条件全集 | PASS | 支持项已列出，未测项也列为“勿假设支持” |
| 港股 mx-data 覆盖度 | PASS | 实测腾讯控股财务查询成功 |
| batch API 范围 | PASS | 实测 `stockCodes` 数组返回 600519/601336 |
| `/investment-research` 数据预处理 | PASS | `skills/investment-research.md:35-61` 已新增数据包流程 |
| `/investment-research` EV/NBV 标注 | PASS | `skills/investment-research.md:67-73` 标注“理杏仁直接获取” |
| `/management-deep-dive` 定量数据层 | PASS | `skills/management-deep-dive.md:25-55` 已新增治理、股东、估值等定量层 |
| `/quality-screen` 三级筛选 | PASS | `skills/quality-screen.md:86-139` 已改为 mx-xuangu → 理杏仁 → 本地精筛 |
| 未支持指标处理 | PASS | E0 后确认 10/10 支持，理杏仁作为精确复核层 |
| 每个增强技能 `_source` 标注 | FAIL | 多个增强技能只写“来源/理杏仁/mx-search”，未统一 `_source` 字段 |
| 向后兼容 | PASS | `pytest` 44 passed；Codex references 与根 `skills/*.md` 哈希一致 |
| MX 日限额估算 | PASS | `investment-research`、`portfolio-review` 和规划中有合理估算 |
| `/investment-research 600519` 实测 | PASS/WARNING | 数据包完整可用；slash command 本身不是 CLI，未生成最终报告文件 |
| `/quality-screen "ROE>15% PE<30 消费股"` 实测 | WARNING | 初筛成功，精确复核可跑；但 5 个候选均缺 `share_dilution_5y` |
| Git 工作区干净 | PASS | `git status` 干净 |
| 每阶段独立分支 | PASS | `feat/enhancement-e0` 到 `feat/enhancement-e4` 均存在 |
| 安全漏洞检查 | WARNING | 未发现真实 token 泄露；`financial_rigor.py` 有受限 `eval`，当前有字符白名单，低风险 |

## 四、必须修复项

### F1. 多个增强技能未使用 `_source` 字段

验收标准要求“每个增强技能是否标注数据来源（`_source` 字段）”。当前部分文件只写“来源”或只提到工具名，没有统一 `_source` 字段。

需要修复的文件：

| 文件 | 位置 | 问题 |
|---|---:|---|
| `skills/dyp-ask.md` | 5 | 使用 `mx-search`，但未要求输出 `_source: mx-search` |
| `skills/earnings-team.md` | 27-32 | 使用理杏仁和 `mx-search`，但没有 `_source` 字段规范 |
| `skills/management-deep-dive.md` | 47-53 | 表头为“来源”，应改为 `_source` 或同时保留 `_source` |
| `skills/private-company-research.md` | 41 | 新增 mx-search/理杏仁补充，但未要求 `_source` |
| `skills/wechat-article.md` | 36-40 | 只写“标注来源”，未规定 `_source` |
| `skills/financial-data.md` | 19-24 | 三级数据源规范中应补统一 `_source` 标注表 |

同步要求：

1. 根目录 `skills/*.md` 改完后，同步 `codex/ai-berkshire/references/skills/*.md`。
2. 保持 Codex references 与根 `skills` 对应文件内容一致。
3. 修完后用哈希或 diff 检查同步一致性。

### F2. `/quality-screen` 精确复核层 7 指标不完整

实际命令：

```powershell
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 300492 --years 5 --quiet
python tools/lxr_data.py quality-metrics 600185 --years 5 --quiet
python tools/lxr_data.py quality-metrics 300972 --years 5 --quiet
python tools/lxr_data.py quality-metrics 002640 --years 5 --quiet
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
```

结果：

| 候选 | 结果 | 问题 |
|---|---|---|
| 300492 华图山鼎 | fail | `share_dilution_5y` missing |
| 600185 珠免集团 | fail | `share_dilution_5y` missing |
| 300972 万辰集团 | fail | `share_dilution_5y` missing |
| 002640 跨境通 | fail | `share_dilution_5y` missing |
| 600132 重庆啤酒 | incomplete | `share_dilution_5y` missing |

需要修复或明确降级：

1. 优先修复 `tools/lxr_data.py quality-metrics` 中 `share_dilution_5y` 的取值逻辑，确认 `q.bs.tsc.t` 在近 5 年年报中是否实际可用。
2. 如果理杏仁该字段对部分股票不可得，`skills/quality-screen.md` 必须明确该项可能为 `missing`，并定义最终筛选的准出/降级规则。
3. 不要只让 `verify_channel_capability.py` 检查 key 是否存在；应增加至少一个断言，验证 7 项中预期可得项有有效值，或明确允许 `share_dilution_5y` 为 `missing` 时的结果语义。
4. 同步修改 Codex 副本 `codex/ai-berkshire/scripts/tools/lxr_data.py` 和 `codex/ai-berkshire/references/skills/quality-screen.md`。

### W1. `financial_rigor.py calc` 使用受限 `eval`

位置：

| 文件 | 行 | 说明 |
|---|---:|---|
| `tools/financial_rigor.py` | 288-305 | 先做字符白名单，再 `eval(expr, {"__builtins__": {}}, {})` |
| `codex/ai-berkshire/scripts/tools/financial_rigor.py` | 288-305 | 同步副本 |

当前风险较低，因为只允许数字、算术符号、括号、空格和科学计数法字符，且禁用 builtins。不是本次准出阻断项，但后续最好改为 AST 安全表达式求值。

## 五、4 项特别关注结论

| 特别关注项 | 判定 | 结论 |
|---|---|---|
| EV/NBV 标注 | PASS | 已按 E0 结果标注“理杏仁直接获取” |
| mx-xuangu 定位 | PASS | 已定位为初筛，理杏仁为精确复核 |
| news-pulse 架构 | PASS | `skills/news-pulse.md:70-133` 保留 4 Agent 并行，并在各 Agent 内部优先 `mx-search` |
| 港股覆盖描述 | PASS | 文档保留 227 vs A 股 409 字段的量化差异，未夸大 |

## 六、建议修复顺序

1. 修复 `_source` 字段规范缺口，先改根 `skills/*.md`，再同步 Codex references。
2. 修复或正式降级 `/quality-screen` 的 `share_dilution_5y` 缺失语义。
3. 增强 `tools/verify_channel_capability.py` 对 `quality-metrics` 的断言。
4. 同步 `tools/` 与 `codex/ai-berkshire/scripts/tools/`。
5. 运行验证命令。

建议最终验证命令：

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
git status --short --branch
```

## 七、续接提示词

```text
你是接续工作的编程 Agent，工作区是 E:\Repos\Skills\ai-berkshire，当前任务是修复独立复审发现的问题并完成验证。请先读取：

1. E:\Repos\Skills\ai-berkshire\docs\review-skill-enhancement-independent-followup-20260627.md
2. E:\Repos\Skills\ai-berkshire\docs\plan-skill-enhancement.md
3. E:\Repos\Skills\ai-berkshire\docs\channel-capability-matrix.md
4. E:\Repos\Skills\ai-berkshire\CLAUDE.md

必须修复的阻断项：

1. 多个增强后的 Skill 未按验收标准统一使用 `_source` 字段标注数据来源。重点检查并修复：
   - skills/dyp-ask.md
   - skills/earnings-team.md
   - skills/management-deep-dive.md
   - skills/private-company-research.md
   - skills/wechat-article.md
   - skills/financial-data.md

2. `/quality-screen` 精确复核层实测 5 个候选全部缺失 `share_dilution_5y`。请优先调查 `tools/lxr_data.py quality-metrics` 中 `q.bs.tsc.t` 的取值逻辑，能修就修；若理杏仁对部分股票无法提供，则在 `skills/quality-screen.md` 中明确该项可能 missing，并定义最终筛选准出/降级规则。同步增强 `tools/verify_channel_capability.py`，不要只检查 key 是否存在。

同步要求：

- 根目录 `skills/*.md` 修改后，必须同步到 `codex/ai-berkshire/references/skills/*.md`。
- `tools/*.py` 修改后，若 Codex 包中有对应副本，必须同步到 `codex/ai-berkshire/scripts/tools/*.py`。
- 保持工作区只改与本次修复直接相关的文件。

最终验证必须运行并报告结果：

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
git status --short --branch
```

完成后给出：改动摘要、验证证据、仍存风险。如果关键验证失败，不要声称完成。
```
