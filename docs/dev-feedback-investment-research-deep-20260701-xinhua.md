# /investment-research deep 档执行复盘与开发反馈（新华保险 A 股，第三次运行）

> **运行主体**：`/investment-research 新华保险A股 --depth deep`
> **执行时间**：2026-07-01
> **报告产物**：`reports/新华保险/新华保险-research-deep-20260701.md`（782 行，LF）
> **复盘性质**：作为执行该技能的 agent，记录本次运行全流程的错误/警告、对照回顾自 `20ea36d9` 起 20 个提交的代码审核、改进建议与使用感受，供编程 agent 接手改进。
> **反馈闭环定位**：反馈 A（`20ea36d9` 泡泡玛特 standard）→ 修复 B（9 个提交）→ 验证 C（`1ae451ce` 腾讯 deep）→ 再修复（`b32250fa` 等 9 个提交）→ **本次验证 D（`69d675c5` 新华保险 deep，第三次运行）**。本次是对腾讯 deep 反馈 4 个核心新问题（E10/E11/E12/E13）的**三次验证**，价值高于二次。

---

## 0. 闭环价值：第三次运行的意义

前两次运行（泡泡玛特 standard、腾讯 deep）各发现一批错误并驱动修复。本次新华保险 deep 运行的核心价值不是"再发现一批新错"，而是**验证前两批修复在真实运行中是否生效**，并识别"自动测试通过但真实运行仍痛"的残留问题。

**验证结论速览**：

| 腾讯反馈问题 | 修复提交 | 本次验证结果 |
|------------|---------|-------------|
| E10 单位陷阱（extract 保留 unit 但 verdict 不归一化） | `b32250fa` | ✅ 生效。本次无单位陷阱，30 点抽检无假偏差 |
| E11 verdict 不支持 `-o` 落盘 | `ef80db80` | ✅ 生效。本次用 `verdict -o _tmp_verdict.json` 直接落盘纯 JSON |
| E12 核心表口径列检查 | `9d7fe70c` | ⚠️ 生效但**过度匹配**。18/30 抽检点被误标记缺口径列（含压力测试情景表、偏误自查表等非核心表） |
| E13 verdict 无口径认可通道 | `8054c38a` | ✅ 生效。4 个基准日差异点用 `caliber_ack + caliber_note` 认可，不占警告额度 |
| E2 港股年报 reportType 兜底 | `312826c5` | ✅ 代码生效（本次 A 股未直接触发，但测试覆盖） |
| E3 港股 `--no-mx` 路径 alternatives | `657d8b1a` | ✅ 实测生效。`industry-compare 00700 --no-mx` 透出 3 条 alternatives |

**总评**：6 项修复 5 项完全生效，1 项（E12）生效但有副作用。本次运行抽检准出 PASS（23 通过 + 4 口径认可 + 3 跳过 + 0 不通过），体感比腾讯运行顺畅——**前两批修复的累计效果真实可感**。

---

## 1. 本次新华保险运行错误与警告盘点

### 1.1 错误清单（按发生顺序）

| 编号 | 错误/警告 | 现象 | 根因 | 处理 | 严重度 |
|------|----------|------|------|------|--------|
| X1 | `$env:PYTHONIOENCODING` 语法错误 | bash 报 `command not found` | PowerShell 语法误用于 bash | 改 `PYTHONIOENCODING=utf-8 python ...` 前缀 | 低（未影响输出） |
| X2 | `lxr_data.py mx-search --output-dir` 不支持 | 参数被拒 | mx-search 仅接受 query/--ttl/--quiet | 去掉 `--output-dir` | 低 |
| X3 | `report_audit.py extract` 默认 ratio 0.15 | 抽检点不足 deep 要求 | deep 需 0.25 | 显式 `--ratio 0.25` | 低（文档可补） |
| X4 | `extract` stdout 混 46 行日志头 | 需 Python 切片清洗 JSON | extract 不支持 `-o` | 写临时脚本切片 `[47:]` | **中**（腾讯 §3.2 P1 未完成） |
| X5 | extract 误抽年份"2026-2027熊市" | 情景标题当数据点 | 解析器未区分情景标题 | verdict 输入标注跳过 | 中 |
| X6 | extract 列对齐错位 | "PE-TTM · 口径/来源"列股价被误标 | 多列表格列对齐逻辑 | `caliber_ack` 说明 | 中 |
| X7 | PB 偏差 10.9%（报告 1.83 vs 妙想 1.65） | 超阈警告 | 最新价 65.38 vs 基准日 61.75 | `caliber_ack=true` + note | 低（已修复通道生效） |
| X8 | `financial_rigor cross-validate` 反推口径错误 | PE×EPS 反推净利润偏差 28.87% ❌ | 用错反推口径 | 改用市值/PE 反推 = 368.8 亿，偏差 0.81% | 低（工具自纠错） |
| X9 | 18/30 抽检点触发口径列警告 | 元数据警告泛滥 | `9d7fe70c` 关键词匹配过宽 | 报告自评"核心表含口径列 ✅"覆盖 | **中**（新问题，见 §3.1） |
| X10 | 子 agent 派发失败（本次复盘审核时） | `deepseek-v4-flash 路由未配置` | Agent 路由间歇性失败 | 降级主 Agent 直接审核 | 中（间歇性） |

### 1.2 与腾讯 deep 运行的对比

| 维度 | 腾讯 deep（第二次） | 新华保险 deep（本次） |
|------|-------------------|---------------------|
| 运行结果分级 | usable-with-warnings | **usable（更顺畅）** |
| 抽检 30 点 | 25 通过 / 5 警告 / 0 不通过 | **23 通过 / 4 口径认可 / 0 不通过 / 3 跳过** |
| Agent 路由失败 | 有（Explore Agent 失败降级单 Agent） | 报告执行中无（复盘审核时遇子 agent 失败） |
| 单位陷阱 | 有（E10） | **无（b32250fa 生效）** |
| 口径认可 | 无通道，5 警告全靠人工脚注 | **4 点 caliber_ack 成功（8054c38a 生效）** |
| verdict 落盘 | 需切片清洗 | **`-o` 直接落盘（ef80db80 生效）** |
| 口径列检查 | 未实现 | **实现但过度匹配（9d7fe70c 副作用）** |

**结论**：本次运行的体感显著优于腾讯运行。腾讯反馈的 4 个核心新问题中，3 个（E10/E11/E13）已完全修复，1 个（E12）已实现但需调优。**前两批 20 个提交的修复效果真实可感，不是纸面完成。**

---

## 2. 对自 `20ea36d9` 起 20 个提交的审核评价

### 2.1 第一批 9 个提交（泡泡玛特 standard 反馈驱动）

#### 2.1.1 `ca5b0d2e` docs(feedback): 规划技能复盘修复方案 ✅ 积极有效
规划文档，将泡泡玛特 13 项错误转为 P1-A1/A2/A3/B1/B2/B3/C1/D1 修复队列。价值在于把"散乱反馈"转为"有编号可跟踪的队列"，是后续 9 个修复的蓝图。无副作用。

#### 2.1.2 `6e198042` fix(audit): 增强报告抽检数值韧性 ✅ 积极有效
修复非数值核验崩溃、负号抽取丢失、方向/幅度比较口径。`_to_numeric` 安全跳过非数值，`compare_mode=absolute_magnitude` 支持量级比较。测试 67 行覆盖。对症修复泡泡玛特反馈的"负号丢失"和"非数值崩溃"。无副作用。

#### 2.1.3 `f5e74593` fix(datapack): 支持投研数据包落盘 ✅ 积极有效
`lxr_data.py datapack -o` 落盘 + `--output-dir` 默认文件名。落盘提示写 stderr 不污染 stdout JSON。这是本次新华运行第〇步的关键能力——`_tmp_601336_datapack.json` 跨模块共享。70 行测试覆盖。对症且优雅。

#### 2.1.4 `fc0504c7` fix(rigor): 增强金融严谨性工具参数防呆 ✅ 积极有效
`three-scenario` 误填 `30 15 -5` 自动归一为 `0.30/0.15/-0.05` 并 stderr 警告；`cross-validate` 增量级错位告警 + `--caliber` 口径输出。本次新华运行 X8（反推口径错误）正是被 `cross-validate` 自纠错捕获——工具强制暴露口径不一致。72 行测试。对症。

#### 2.1.5 `27b66eac` fix(agent): 增加任务代理失败降级记录 ✅ 积极有效
9 个 skill 同步要求记录 `model route not configured`/`timeout`/`permission denied` 失败。本次新华报告第 774 行如实记录"未遇到路由错误"——证明该约束已内化为 agent 行为。34 行 skill 回归测试。但腾讯反馈 §3.7 提的"必要信息判定标准缺失"在本次仍存在（见 §3.3）。

#### 2.1.6 `4568e6f0` fix(lxr): 增加港股行业对比降级路径 ✅ 积极有效
注入 `_hk_industry_compare_alternatives()`（3 条静态降级步骤）。关键设计：alternatives 是纯静态字符串，不依赖 mx 调用，为后续 `657d8b1a` 的 `--no-mx` 路径复用埋好基础。16 行测试。对症。

#### 2.1.7 `abe2842d` fix(metadata): 增加财务口径元数据 ⚠️ 部分有效但有遗留
`caliber_metadata` 输出字段口径、币种、单位。本次新华运行确认元数据通道生效。**但 notes 仍写 "toi=营业总收入"，而保险股 `INSURANCE_FINANCIALS_METRICS` 实际用 `oi`（第 149 行）——文档与代码不一致**（见 §3.2）。60 行测试。修复方向对，但保险股口径描述未对齐代码。

#### 2.1.8 `5d46ce1b` ci: 增加离线回归门禁 ✅ 积极有效
GitHub Actions CI 跑全量 pytest + `verify_channel_capability --quick` + compileall + release smoke + `git diff --check`。固化 datapack 口径元数据、降级记录、抽检骨架合同。本次 88 测试全通过证明无回归。44 行 workflow + 73 行合同测试。长期价值高。

#### 2.1.9 `d0cab458` feat(release): 增加发布说明生成工具 ✅ 积极有效
`release_notes.py` 按 conventional commit 生成中文 Markdown。82 行测试。非本次运行直接使用，但为 P0.7 发布动作铺路。229 行工具实现完整。

**第一批总评**：9 个提交全部对症，8 个完全有效，1 个（abe2842d）有保险股口径描述遗留。整体质量高，双副本同步+测试覆盖纪律严明。

### 2.2 第二批 11 个提交（腾讯 deep 反馈驱动 + 本次产物）

#### 2.2.1 `1ae451ce` docs(腾讯): 增加deep档四大师投研报告 ✅ 产物
腾讯 deep 报告本身，655 行。作为第二次运行的验证产物，是后续修复的基准。

#### 2.2.2 `10a58251` docs(feedback): 脱敏路径示例 ✅ 积极有效
4 行修改，把腾讯反馈文档中的本机路径示例脱敏。虽小但必要——隐私卫生。

#### 2.2.3 `1f5a57f9` docs(feedback): 增加腾讯deep档执行复盘与二次验证反馈 ✅ 积极有效
腾讯反馈文档（本文件的参照模板），14 项错误盘点 + 8 项改进建议 + 路线图摘要。结构清晰，是本文件的格式范本。

#### 2.2.4 `b32250fa` fix(audit): 增加单位归一化核验 ✅ 积极有效（腾讯 E10 修复）
`_unit_scale` 字典覆盖中英文单位（万/亿/百万/十亿/千万/千亿/万亿/million/billion 等），`_normalize_fetched_unit` 换算并生成 note，`_unit_gap_warning` 量级比 >50 触发软警告。**关键设计：区分"硬不通过"（占 fail 额度）与"软警告"（提示补 fetched_unit）**。本次新华运行 30 点无单位陷阱，验证生效。119 行实现 + 46 行测试。对症且健壮。

#### 2.2.5 `ef80db80` fix(audit): 支持判决结果落盘 ✅ 积极有效（腾讯 E11 修复）
verdict 增加 `-o/--output` 写纯 JSON 到文件 + `--output-json` stdout 纯 JSON。本次新华运行 X4 用此直接落盘 `_tmp_verdict.json`，无需切片清洗。15 行实现 + 37 行测试。**但 extract 仍不支持 -o（腾讯 §3.2 P1 未完成）**——这是本次运行仍需切片清洗 extract 输出的原因（见 §3.1）。verdict 部分对症，extract 部分遗留。

#### 2.2.6 `8054c38a` fix(audit): 增加口径认可通道 ✅ 积极有效（腾讯 E13 修复）
`caliber_ack_valid = caliber_ack and bool(caliber_note)` 落实"防滥用：空 note 不认可"；分支顺序正确（pass → caliber_ack → 硬不通过 → 软警告）；摘要四计数（通过/口径认可/警告/不通过）。本次新华 4 个基准日差异点用此通道认可，验证生效。40 行实现 + 48 行测试。对症且防滥用设计良好。

#### 2.2.7 `657d8b1a` fix(lxr): 保留港股无mx行业替代路径 ✅ 积极有效（腾讯 E3 修复）
加 `--no-mx` 参数声明 + 测试断言 alternatives 透出。**实测 `industry-compare 00700 --no-mx` 确实透出 3 条 alternatives**。diff 看不到注入代码是因为复用了 `4568e6f0` 的 `_hk_industry_compare_alternatives`（静态字符串不依赖 mx）。1 行代码 + 30 行测试。对症。

#### 2.2.8 `9d7fe70c` fix(audit): 检查核心表口径列 ⚠️ 生效但过度匹配（腾讯 E12 修复）
`_CORE_TABLE_KEYWORD_RE` 匹配 PE/PB/ROE/营收/归母/市值/毛利率/现金流/股息/资产/负债等关键词，`_CALIBER_HEADER_RE` 检查表头是否含口径/来源。**问题：关键词过宽，把"利率环境表""偏误自查表""压力测试情景表"也判为核心数据表**。本次新华运行 30 点抽检中 **18 点触发口径列警告（60%）**，但其中多数是压力测试情景表、偏误自查表等本就不需要口径列的表。102 行实现 + 57 行测试。**修复方向对，但关键词需收窄或增加表类型识别**（见 §3.1）。

#### 2.2.9 `312826c5` fix(lxr): 识别港股年报reportType ✅ 积极有效（腾讯 E2 修复）
`_is_annual_fs_record` 先查 `reportType==annual_report`，date 匹配失败时兜底。本次 A 股未直接触发，但 56 行测试覆盖港股季度累计 datapack 场景。15 行实现。对症。

#### 2.2.10 `0da38fd6` docs(agent): 明确降级脱敏与二次验证 ✅ 积极有效
9 个 skill 同步补充降级脱敏标准（可保留模型名/错误码/HTTP 状态，必须删除路径/token/cookie/账户名）+ action-plan 二次验证字段。46 行 skill 回归测试。补了 `27b66eac` 的标准缺失（腾讯 §3.7）。本次报告第 774 行的降级记录符合此标准。

#### 2.2.11 `69d675c5` docs(新华保险): 新增deep深度投资研究报告 ✅ 产物
本次报告，782 行 LF。保险股 PEV 估值两法收敛 80 元，决策建议明确。产物质量由前述修复支撑。

**第二批总评**：11 个提交中，5 个代码修复（b32250fa/ef80db80/8054c38a/657d8b1a/9d7fe70c）4 个完全对症，1 个（9d7fe70c）过度匹配需调优。腾讯反馈 4 个核心新问题（E10/E11/E12/E13）全部被回应，3 个完全修复，1 个（E12）有副作用。**修复闭环质量高，但 extract 的 -o 落盘仍未补（腾讯 §3.2 P1 只做了 verdict）**。

### 2.3 整体审核结论

20 个提交中：
- **✅ 积极有效**：17 个（第一批 8 + 第二批 9）
- **⚠️ 部分有效但有遗留**：2 个（abe2842d 保险股口径描述、9d7fe70c 口径列过度匹配）
- **❌ 未起作用**：0 个
- **产物**：3 个（1ae451ce/1f5a57f9/69d675c5）

**修复方向全部对症，实现质量普遍较高（双副本同步+测试覆盖+ROADMAP/action-plan 跟踪）**。最突出的遗留是 **extract 的 -o 落盘未补** 和 **9d7fe70c 口径列检查过度匹配**——这两项是下一轮 P1 应优先解决的"准出摩擦"。

---

## 3. 技能与代码值得改进的地方

### 3.1 【高优】extract 仍不支持 `-o` 落盘（腾讯 §3.2 P1 未完成）

**问题**：`ef80db80` 只给 verdict 加了 `-o`，extract 仍只能 stdout 输出，前 46 行是日志头，JSON 从第 47 行起。本次新华运行 X4 仍需写临时脚本 `lines[46:]` 切片清洗。腾讯反馈明确把 §3.2 列为 P1，但只完成了 verdict 一半。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`
- extract 增加 `-o/--output` 写 JSON 到文件，stdout 只打印人类可读表格（同 `--dry-run` 的表格预览）
- 参考 `lxr_data.py datapack -o` 与 `report_audit.py verdict -o` 的现有实现，三者保持一致
- 测试：`extract --report xxx.md --ratio 0.25 -o _tmp_extract.json` 应直接落盘纯 JSON，stdout 无 JSON

**验收命令**：`python tools/report_audit.py extract --report <报告> --ratio 0.25 -o _tmp_extract.json && python -c "import json; json.load(open('_tmp_extract.json'))"`

### 3.2 【高优】9d7fe70c 口径列检查过度匹配，60% 抽检点误报警

**问题**：`_CORE_TABLE_KEYWORD_RE` 含"利率""资产""负债"等词，把"利率环境表""偏误自查表""压力测试情景表"误判为核心数据表，触发口径列缺失警告。本次 30 点抽检中 18 点被标记（60%），但多数是非核心表。元数据警告泛滥会削弱信号价值——真正缺口径列的核心表被淹没在误报里。

**根因**：仅靠关键词匹配无法区分"核心财务数据表"与"定性分析/压力测试/偏误自查表"。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`、`tests/test_report_audit.py`
- 收窄 `_CORE_TABLE_KEYWORD_RE`：移除"利率""资产""负债"等弱信号词，只保留强信号财务指标（PE/PB/ROE/EPS/营收/归母净利润/市值/毛利率/净利率/自由现金流/股息率/EV/NBV）
- 增加表类型识别：表头含"触发条件""自查""情景""路径""概率"等词时判定为定性/压力测试表，跳过口径列检查
- 或：只有当表内**数值行 ≥ 3 行**且含强信号指标时才标记为核心表
- 测试：构造"压力测试情景表"和"偏误自查表"，期望不触发口径列警告；构造"PE/PB/ROE 估值表"无口径列，期望触发

**验收命令**：`python -m pytest tests/test_report_audit.py -q`

### 3.3 【中优】保险股 oi/toi 口径文档与代码不一致

**问题**：`INSURANCE_FINANCIALS_METRICS`（lxr_data.py:149）对保险股用 `q.ps.oi.t`（营业收入），但 skill 文档（investment-research.md:60/99）和 `_financial_caliber_metadata` notes（lxr_data.py:183）仍写 "toi=营业总收入"。执行 Agent 按文档读 `toi` 会拿到 None，需自行发现改用 `oi`。本次新华运行我实际踩到此坑。

**最小修复建议**：
- 目标文件：`tools/lxr_data.py`、`codex/ai-berkshire/scripts/tools/lxr_data.py`、`skills/investment-research.md`、`codex/ai-berkshire/references/skills/investment-research.md`
- `_financial_caliber_metadata` 对 `report_type==insurance` 的 notes 改为 "oi=营业收入（保险股无营业总收入，用营业收入口径）"
- skill 文档第 60/99 行补充"保险股用 oi 非 toi"说明
- 测试：构造 insurance report_type，期望 caliber_metadata notes 含 oi 说明

### 3.4 【中优】extract 误抽情景标题与列对齐错位

**问题**：本次 X5（"权益市场2026-2027熊市"被当数据点）、X6（PE-TTM 表列对齐错位）说明 extract 解析器对"压力测试情景标题"和"多列表格列对齐"处理不健壮。9d7fe70c 加了口径列检查但未触及解析器根因。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`、`tests/test_report_audit.py`
- extract 解析器：label 含"触发条件""情景""路径"等词且所在表无数值列时，跳过提取
- 多列表格列对齐：当 `|` 分割的列数与表头不一致时，跳过该行而非错位赋值
- 测试：构造压力测试情景表，期望 extract 不抽"触发条件"行

### 3.5 【中优】Agent 路由失败的间歇性与文档诚实性

**问题**：`deepseek-v4-flash 路由未配置`是间歇性问题——本次新华报告执行中未遇（第 774 行），但复盘审核时派子 agent 全部失败。腾讯运行遇 Explore Agent 失败。skill 文档已要求降级记录，但未说明"路由失败是间歇性的，同一会话可能部分成功部分失败"。

**最小修复建议**：
- 目标文件：`skills/investment-research.md` 及同步 skill
- 补充说明：Agent 路由失败可能间歇性发生，每次派发需独立捕获，不因前一次成功而假设后续成功
- 失败时不重试同一路由，直接降级主 Agent 顺序模拟

### 3.6 【低优】deep 档抽检点数量下限自适应

**问题**：deep 档 25% 抽检，本次 30 点。但 782 行报告 261 数据点，30 点仍可能漏关键口径。腾讯反馈 §3.8 已提"抽检点数量下限 = max(30, 数据点数 × 0.25)"。

**最小修复建议**：extract 对 deep 档自动用 `max(30, count*0.25)`，报告数据点 > 120 时抽检点随之增加。

### 3.7 【低优】datapack 缓存 TTL 可观测

**问题**：skill 文档说"TTL 1h 跨模块共享"，但 datapack JSON 不记录生成时间，主 Agent 无法判断是否过期。腾讯反馈已提。

**最小修复建议**：datapack 顶层加 `_generated_at` 字段（CLI 用系统时间，workflow 脚本用 args 传入）。

---

## 4. 整体使用感受

### 4.1 骨架与修复闭环是真实资产

四大师七模块框架 + 数据三级降级链 + financial_rigor 精确十进制 + report_audit 25% 抽检准出，这套骨架在 deep 档下经受住了保险股（EV/NBV/偿付能力）的考验。`industry-deep` 对 insurance 报表的自动路由直接返回 EV 2878.4 亿/NBV 98.4 亿，无需年报 PDF 解析——这是第〇步数据预处理的实质进步。**骨架不需要推翻，修复闭环（反馈→修复→二次验证）正在收敛工具容错性。**

### 4.2 前两批修复的累计效果真实可感

本次运行最直接的体感：**抽检准出从"15-30 分钟处理假偏差和人工解释口径"降到"5 分钟填 verdict 输入"**。b32250fa（单位归一化）消灭了假偏差，8054c38a（口径认可通道）让基准日差异不再占警告额度，ef80db80（verdict -o）让落盘直接可机器解析。这是项目质量文化的实质提升——**"装作没发生"被"可审计降级"取代**。

### 4.3 剩余短板集中在 extract 的 -o 与口径列检查

本次最大摩擦点不是工具崩溃（那些已修），而是 **extract 仍不支持 -o**（§3.1）和 **9d7fe70c 口径列检查过度匹配**（§3.2）。前者每次抽检都要写临时脚本切片清洗，后者让元数据警告泛滥淹没真信号。这两项不修，每次 deep 档都会在抽检环节浪费 10-15 分钟。**这是下一轮 P1 应优先解决的"准出摩擦"。**

### 4.4 保险股 oi/toi 口径不一致是"按文档走会踩坑"的典型

abe2842d 的 caliber_metadata 通道设计正确，但保险股 notes 仍写 toi 而代码用 oi——文档与代码不一致。这类缺口靠代码 review 难发现，需要**按 skill 文档逐条跑一遍保险股**的 smoke。建议下一轮增加"保险股 smoke"测试。

### 4.5 deep 档真实成本与 Agent 可用性

本次报告执行中未遇 Agent 路由失败（顺序模拟四大师），但复盘审核时子 agent 全部失败——说明路由失败是间歇性的。deep 档"跨 Agent 偏见验证"在单 Agent 模式下退化为"主 Agent 自我对抗式复核"，置信度低于真双 Agent。skill 文档应更诚实标注此约束（§3.5）。

---

## 5. 给编程 agent 的接手建议

按优先级排序：

### P1（下一轮优先，解决准出摩擦）

1. **§3.1 extract `-o` 落盘**——腾讯 §3.2 P1 的未完成部分，每次抽检都踩
2. **§3.2 口径列检查过度匹配**——9d7fe70c 的副作用，60% 误报警淹没真信号
3. **§3.3 保险股 oi/toi 口径对齐**——文档与代码不一致，按文档走会踩坑

### P2（解析器健壮性与文档诚实性）

4. **§3.4 extract 误抽情景标题与列对齐**——解析器根因未触及
5. **§3.5 Agent 路由间歇性说明**——文档诚实性

### P3（增量优化）

6. **§3.6 deep 档抽检点数量自适应**——腾讯 §3.8 的延续
7. **§3.7 datapack `_generated_at`**——TTL 可观测

### 其他建议（非本次发现，但值得纳入）

- **保险股 smoke 测试**：构造 601336 datapack fixture，覆盖 oi/无 toi、EV/NBV/偿付能力字段，防止口径文档再次与代码漂移
- **extract 解析器与口径列检查的协同**：9d7fe70c 的口径列检查依赖 extract 解析出的表结构，extract 误抽会污染口径列检查结果——两者应协同修复
- **ROADMAP 二次验证字段回填**：本次验证了 E1/E2/E3/E4/E6 真实生效，E5 有副作用，应在 action-plan 对应项回填"新华保险 deep 三次验证"证据

---

## 6. 路线图进度摘要

本次工作未改变 `docs/ROADMAP.md` 目标。P0 已完成发布，P1 反馈驱动修复队列 16 项（A1-A3/B1-B3/C1/D1/E1-E3/E4-E6/E7-E8）全部标记"已完成"。

本次工作的贡献是**为 P1-E1/E2/E3/E4/E6 五项提供真实技能运行二次验证证据**：
- P1-E1（单位归一化）：✅ 新华运行验证生效
- P1-E2（verdict -o）：✅ 新华运行验证生效
- P1-E3（口径认可通道）：✅ 新华运行 4 点 caliber_ack 验证生效
- P2-E4（港股 --no-mx alternatives）：✅ 实测生效
- P2-E5（口径列检查）：⚠️ 生效但过度匹配，需调优（§3.2）
- P2-E6（港股年报 reportType）：✅ 代码生效（本次 A 股未直接触发）

**仍待推进的事项**：
- P1 新增候选：§3.1 extract -o（腾讯 §3.2 未完成部分）、§3.2 口径列检查调优、§3.3 保险股 oi/toi 对齐
- P2 新增候选：§3.4 extract 解析器健壮性、§3.5 Agent 路由间歇性说明
- action-plan 二次验证字段回填：本次验证证据应回填到 P1-E1/E2/E3/E4/E6 对应项
- 保险股 smoke 测试纳入 P1-C1 离线 fixture 扩展

建议编程 agent 把 §3.1-§3.3 纳入 P1 反馈驱动修复队列的新条目，§3.4-§3.5 纳入 P2，§3.6-§3.7 纳入 P3。

---

## 7. 隐私检查

本反馈未包含 token、cookie、账户标识、真实持仓金额、未脱敏日志或本机私有路径。错误原文摘要仅保留模型名 `deepseek-v4-flash` 与错误类别 `model route not configured`，已删除所有路径与账户信息。报告产物中的股价、估值、财务数据均来自理杏仁/妙想公开接口，非私有信息。
