# 双渠道 Skill 增强实施独立审核报告

> 审核日期：2026-06-27  
> 审核范围：`docs/plan-skill-enhancement.md` 所定义的 E0-E4 增强规划实施结果  
> 审核角色：独立审核 Agent  
> 最终判决：**打回修改**

## 1. 审核依据

- `docs/plan-skill-enhancement.md`
- `C:/Users/admin/.claude/skills/skill-creator/SKILL.md`
- `CLAUDE.md`
- `docs/channel-capability-matrix.md`
- `docs/plan-lixinger-migration.md`
- 当前分支：`feat/enhancement-e4`

## 2. 实测验证摘要

| 验证项 | 结果 |
|---|---|
| `python -m pytest -q` | PASS，`38 passed` |
| `git status --short --branch` | PASS，工作区干净，当前 `feat/enhancement-e4` |
| `python tools/lxr_data.py industry-deep 601336 --years 3` | PASS，返回 `q.bs.ev.t` 与 `q.ps.nbv.t` |
| 601336 EV/NBV | PASS，2025 EV=2878.4 亿元，NBV=98.42 亿元 |
| 理杏仁 batch API | PASS，`stockCodes=[600519,601336,600036]` 返回 3 条 PE/PB |
| `python tools/lxr_data.py mx-data "腾讯控股近三年净利润 营业收入"` | PASS，返回 2023-2026Q1 财务表 |
| `python tools/lxr_data.py datapack 600519 --years 5 --no-mx` | WARNING，数据可拉取，但顶层 `_source` 错标为 `lixinger+mx` |
| `python tools/lxr_data.py mx-xuangu "ROE大于15%，市盈率小于30的消费股，返回前10只"` | WARNING，初筛可跑，但后续精确 7 指标字段不足 |
| `python tools/financial_rigor.py verify-market-cap 600519 --source lixinger` | PASS，市值偏差约 0.49% |
| `python tools/financial_rigor.py verify-valuation 600519 --source lixinger` | FAIL，股息率口径错误，输出约 0.04% 而非约 4.09% |

## 3. 必修 FAIL 项

### F1. `/quality-screen` 精确 7 指标不可完整执行

状态：FAIL

证据：

- `skills/quality-screen.md:114` 声称 7 指标可从 `financials` 记录本地计算。
- `skills/quality-screen.md:119` 要用资本开支计算 FCF。
- `skills/quality-screen.md:120` 要用利息费用计算利息覆盖。
- `tools/lxr_data.py:79` 起的默认非金融指标集没有资本开支字段，也没有利息费用字段。

影响：

- mx-xuangu 初筛可用，但 Step 2 理杏仁精确复核不能完整算出 7 条硬指标。
- 规划 E1.3 `/quality-screen` 准出标准未满足。

要求：

- 为 `quality-screen` 所需 7 指标补齐可计算字段或新增专用 CLI/脚本。
- 至少覆盖 ROE、FCF、利息覆盖、毛利率、OCF/NI、净利率、股本膨胀。
- 若某些行业不适用，必须明确标注 N/A 与原因。

### F2. `datapack --no-mx` 来源标注错误

状态：FAIL

证据：

- 实测 `python tools/lxr_data.py datapack 600519 --years 5 --no-mx` 没有任何 MX section。
- 顶层仍返回 `_source: "lixinger+mx"`。
- 硬编码位置：
  - `tools/lxr_data.py:1341`
  - `codex/ai-berkshire/scripts/tools/lxr_data.py:1341`

影响：

- 数据来源标注不可信，违反 E0 数据标注规范。

要求：

- `include_mx=False` 时顶层 `_source` 应为 `lixinger`。
- `include_mx=True` 但 MX section 失败时，应准确反映实际来源，例如 `lixinger+partial-mx` 或仅依 section `_source` 判断。

### F3. `financial_rigor.py --source lixinger` 股息率口径错误

状态：FAIL

证据：

- `python tools/lxr_data.py verify-inputs 600519` 返回 `dividend_yield: 0.0409`。
- 该值代表约 4.09%，但 `financial_rigor.py` 又执行 `/100`。
- 相关位置：
  - `tools/financial_rigor.py:467-469`
  - `codex/ai-berkshire/scripts/tools/financial_rigor.py:467-469`

影响：

- `/investment-research` 的估值验算会输出错误股息率。

要求：

- 明确 `dyr` 口径：若理杏仁返回小数收益率 `0.0409`，每股股息应为 `price * dyr`，不是 `price * dyr / 100`。
- 增加回归测试，验证 600519 股息率输出约 4.09%。

### F4. 交叉验证阈值未统一到规划 §4.3 的 2%

状态：FAIL

证据：

- `docs/plan-skill-enhancement.md:403-419` 要求 NLP 源与结构化源交叉验证阈值为 2%。
- `skills/investment-research.md:328` 已写 2%。
- 仍保留旧 1% 规则：
  - `skills/financial-data.md:3`
  - `skills/financial-data.md:89-90`
  - `codex/ai-berkshire/SKILL.md:16`
  - `skills/investment-research.md:315-316`
  - `skills/investment-team.md:135`
  - `skills/earnings-review.md:55`

影响：

- 同一项目对数据差异阈值给出冲突规则，执行 Agent 会误判。

要求：

- 统一规则：
  - 同口径结构化来源可保留严格阈值。
  - 理杏仁 vs mx-data NLP 同指标按 2% / 5% 分层。
  - 不同口径不强行比较，需说明口径差异。
- 同步 `skills/` 与 `codex/ai-berkshire/references/skills/`。

### F5. E2-E4 多个增强技能没有统一 `_source` 字段

状态：FAIL

证据：

- E0 矩阵定义了统一数据标注规范：
  - `docs/channel-capability-matrix.md:188-193`
- 多个增强技能只写“来源/理杏仁/mx-search”，未统一 `_source` 字段，例如：
  - `skills/portfolio-review.md:39-50`
  - `skills/thesis-tracker.md:38-48`
  - `skills/investment-team.md:34-50`
  - `skills/industry-funnel.md:41-55`
  - `skills/industry-research.md:20-24`
  - `skills/investment-checklist.md:31-41`

影响：

- E2-E4 “每个增强技能是否标注数据来源（_source 字段）”未通过。

要求：

- 对所有增强技能补充统一 `_source` 标注模板。
- 同步 Claude slash-command 文件和 Codex reference 副本。

### F6. 硬编码 token 字符串

状态：FAIL

证据：

- `tools/ashare_data.py:275`
- `codex/ai-berkshire/scripts/tools/ashare_data.py:275`

影响：

- 安全扫描不通过。
- 即使该 token 是东方财富公开查询参数，也不应以真实 token 形态硬编码在源码里。

要求：

- 移除或解释为非敏感公开参数并改名避免误报。
- 若确需保留，至少加注释说明其不是认证密钥；更好方案是封装为常量并命名为 `EASTMONEY_SEARCH_TOKEN_PUBLIC` 或改为配置。

## 4. WARNING 项

### W1. E0 原始验证脚本已删除

状态：WARNING

证据：

- `docs/channel-capability-matrix.md` 声明验证脚本 `temp_e0_verify.py` 已删除。

影响：

- 文档有结果快照，我也复验了关键项，但完整复现证据不如保留脚本可靠。

建议：

- 保留最小复验脚本或把复验命令固化为 `tools/verify_channel_capability.py`。

### W2. `docs/channel-capability-matrix.md` 港股治理状态自相矛盾

状态：WARNING

证据：

- `docs/channel-capability-matrix.md:16` 写“治理增减持待修”。
- `docs/channel-capability-matrix.md:163` 写港股 governance 已修复。
- `docs/channel-capability-matrix.md:178` 又写 management-deep-dive 港股治理暂降级 WebSearch。

实测：

- `python tools/lxr_data.py governance 00700 --years 2` 可返回 `_source: lixinger`，端点为 `hk/company/hot/director_equity_change`。
- `python tools/lxr_data.py shareholders 00700 --kind num --years 2` 返回 `_source: none`，港股股东人数趋势不可用。
- `python tools/lxr_data.py shareholders 00700 --kind majority --years 2` 可返回 9 条。

建议：

- 矩阵修订为：港股董事权益变动端点已修复；港股股东人数趋势仍不可用；港股股东结构用 `latest-shareholders`。

### W3. mx-xuangu 筛选全集没有显式列“确认不支持”

状态：WARNING

证据：

- 已列支持 PE/PB/ROE/净利润增速/股息率/毛利率/净利率/资产负债率/FCF/收入增速/行业限定/涨跌幅。
- 但审核清单要求“确认支持 + 确认不支持”。

建议：

- 若当前测试项全部支持，应明确写“本轮测试项中未发现确认不支持项；未测项不得推断支持”。

### W4. Codex 包顶层规则仍有旧 1% 阈值

状态：WARNING

证据：

- `codex/ai-berkshire/SKILL.md:16`

建议：

- 与 `skills/financial-data.md` 统一，不要让 Codex 入口和引用文件冲突。

## 5. 四项特别关注追踪

| 特别关注 | 判定 |
|---|---|
| EV/NBV | PASS，E0 与 `/investment-research` 均标注为理杏仁获取 |
| mx-xuangu 定位 | PASS/WARNING，仍定位为初筛，理杏仁为精确复核；但精确复核字段不全导致 `/quality-screen` 整体 FAIL |
| news-pulse 架构 | PASS，4 Agent 并行保留，每个 Agent 内部优先 `mx-search` |
| 港股覆盖描述 | WARNING，227 vs 409 的量化描述存在；但 E0 矩阵对港股治理状态前后矛盾 |

## 6. 修复优先级建议

1. 修复 `financial_rigor.py` 股息率口径并加测试。
2. 修复 `datapack` 顶层 `_source` 逻辑并同步 Codex 副本。
3. 补齐 `/quality-screen` 精确 7 指标计算链，必要时新增专用命令或脚本。
4. 统一 2%/5% 交叉验证策略，移除旧 1% 冲突描述。
5. 全量补 `_source` 标注模板，保持 `skills/` 与 `codex/ai-berkshire/references/skills/` 内容一致。
6. 处理硬编码 token 扫描问题。
7. 修订 `docs/channel-capability-matrix.md` 的港股治理与不支持项描述。
8. 重新运行实测命令与 `pytest`。

## 7. 续接提示词

将下面提示词复制给下一个 Agent：

```text
你在 E:\Repos\Skills\ai-berkshire 项目中继续修复“双渠道 Skill 增强实施独立审核”发现的问题。

必读文件：
- E:\Repos\Skills\ai-berkshire\docs\review-skill-enhancement-20260627.md
- E:\Repos\Skills\ai-berkshire\docs\plan-skill-enhancement.md
- E:\Repos\Skills\ai-berkshire\docs\channel-capability-matrix.md
- E:\Repos\Skills\ai-berkshire\CLAUDE.md

当前分支应为 feat/enhancement-e4。先执行：
cd E:\Repos\Skills\ai-berkshire
$env:PYTHONIOENCODING='utf-8'
git status --short --branch

目标：修复 review-skill-enhancement-20260627.md 中所有 FAIL 和 WARNING，重点包括：
1. 修复 tools/financial_rigor.py 与 codex/ai-berkshire/scripts/tools/financial_rigor.py 的理杏仁股息率口径错误；增加回归测试，600519 输出应约 4.09% 而不是 0.04%。
2. 修复 tools/lxr_data.py 与 codex/ai-berkshire/scripts/tools/lxr_data.py 的 datapack 顶层 _source：--no-mx 时不能返回 lixinger+mx。
3. 修复 /quality-screen 精确 7 指标计算链：补齐 FCF、利息覆盖等字段或新增专用计算脚本/CLI；确保 “ROE>15% PE<30 消费股” 能完成 mx-xuangu 初筛 + 理杏仁精确复核。
4. 统一交叉验证阈值：理杏仁 vs mx-data NLP 同指标按 2%/5% 分层；修正所有仍写 1% 的冲突规则。
5. 为所有增强技能补齐统一 _source 标注，保持 skills/*.md 与 codex/ai-berkshire/references/skills/*.md 完全同步。
6. 处理 tools/ashare_data.py 与 codex 副本中硬编码 token 扫描问题。
7. 修订 docs/channel-capability-matrix.md：港股董事权益变动已修复；港股股东人数趋势不可用；mx-xuangu 本轮测试项未发现确认不支持项，未测项不得推断支持。

验收必须亲自运行并报告：
- python -m pytest -q
- python tools/lxr_data.py industry-deep 601336 --years 3
- python tools/lxr_data.py datapack 600519 --years 5 --no-mx
- python tools/lxr_data.py mx-xuangu "ROE大于15%，市盈率小于30的消费股，返回前10只"
- python tools/financial_rigor.py verify-valuation 600519 --source lixinger
- git status --short --branch

要求：
- 用 PowerShell / Windows 路径，不使用 WSL。
- 不要重写无关文件，不要删除历史报告。
- 修改后同步 Codex 副本。
- 最终给出每个审核问题的 PASS/FAIL 状态和证据。
```
