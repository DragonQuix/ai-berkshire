# 投资研究技能执行复盘与开发反馈（腾讯 deep 档）

- 日期：2026-07-01
- Skill：`/investment-research 腾讯控股 --depth deep`
- 运行环境：Claude Code（Sonnet 4.6，Windows 11 + PowerShell 7.5.4 + Git Bash）
- 运行版本：`1ae451ce`（本次报告 commit）；反馈基线 `20ea36d9`（上一轮泡泡玛特 standard 档复盘）
- 结果分级：`usable-with-warnings`（核心流程跑通，报告准出发布，但容错与可观测性仍有改进空间）
- 产物：`reports/腾讯/腾讯-research-deep-20260701.md`（44 KB / 655 行，LF 行尾，commit `1ae451ce`）
- 抽检准出：30 点 → 25 通过 / 5 警告 / 0 不通过 → 【准出】发布

## 0. 本次反馈的特殊价值

`20ea36d9` 是上一轮作为执行 agent 写的复盘反馈，其后 9 个提交（`ca5b0d2e`→`d0cab458`）是对该反馈的修复落地。本次是**修复后的第二次完整运行**，因此本反馈不仅是新一轮问题记录，更是对上一轮修复的**二次验证证据**：哪些修复真正生效、哪些只修了表象、哪些引入了新边缘情况。这种"反馈 A → 修复 B → 再运行验证 C"的闭环证据链在项目中较罕见，建议编程 agent 把本文件与 `docs/dev-feedback-action-plan.md` 对照阅读。

## 1. 本次运行错误与警告盘点

按发生顺序列出。每项标注：上次反馈是否已记录、本次是否复现、修复是否生效。

| # | 阶段 | 现象 | 根因 | 上次反馈 | 本次状态 |
|---|------|------|------|----------|----------|
| E1 | 数据预处理 | `lxr_data.py datapack` 默认打印 JSON 不落盘，跨模块共享只能 glob 猜文件名 | CLI 无 `-o/--output` | #1 已记录 | ✅ 已修复生效，`-o _tmp_00700_datapack.json` 落盘成功 |
| E2 | 数据预处理 | 理杏仁港股年报 `annuals count: 0`，`date[5:10]=='12-31'` 匹配失败 | 港股返回季度累计数据，需按 `reportType=='annual_report'` 识别 | 未记录（新问题） | 🆕 本次新发现，主 Agent 内联修复 |
| E3 | 数据预处理 | `industry-compare 00700 --no-mx` 输出不含 `alternatives` 与 `note` | `--no-mx` 路径与默认路径输出结构不一致 | #6 部分记录 | ⚠️ 修复在默认路径生效，`--no-mx` 路径未覆盖 |
| E4 | 数据预处理 | exa-1 web_search 返回 `402 credits exceeded` | API Key 额度耗尽 | 未记录（运行时外部因素） | ✅ 按 CLAUDE.md 三 Key 轮换切 exa-2/exa-3 |
| E5 | 定性分析 | Explore Agent 启动失败 `API Error: 400 Claude Desktop 模型路由未配置: deepseek-v4-flash` | 后台 Agent 模型路由未配置 | #8 已记录 | ✅ 降级记录已写入报告附录 A（Fix#8/B1 生效） |
| E6 | 交叉验证 | `cross-validate` 无量级预检，单位错位时输出天文"共识值" | 缺 max/min 量级告警 | #5 已记录 | ✅ 已修复，`max/min>50` 触发告警 |
| E7 | 交叉验证 | `three-scenario --growth 30 15 -5` 算成 3000%/1500%/-500% | 增长率未归一化 | #4 已记录 | ✅ 已修复，二次验证 stderr 警告 + 自动转 0.30/0.15/-0.05 |
| E8 | 抽检准出 | `report_audit verdict` 对 `fetched_value:"2026-07-01"` 崩溃 `float()` | 非数值未安全转换 | #9 已记录 | ✅ 已修复，`_to_numeric()` 生效 |
| E9 | 抽检准出 | `report_audit extract` 把 `-46.5%` 抽成 `46.5%`，verdict 对 `46.5` vs `-46.5` 报 200% | 正则无符号前缀 | #10 已记录 | ✅ 已修复，`_SIGNED_NUM` 含 `[-+]?` |
| E10 | 抽检准出 | `report_audit` 对"14.3亿"返回 `reported_value=14.3, unit=亿`，但 fetched_value 填 1430（百万）时 verdict 报 9900% 偏差 | extract 保留 unit 但 verdict 不做单位归一化 | 未记录 | 🆕 **本次新发现的核心问题**，见 §3.1 |
| E11 | 抽检准出 | `report_audit.py -o` 参数不支持，stdout 含日志头需 Python 切片清洗 JSON | CLI 未实现 `-o` | 未记录 | 🆕 本次新发现，见 §3.2 |
| E12 | 报告执行 | skill 文档要求"所有核心数据表保留「口径/来源」列"，实际 29 个表只有 1 个表头含该列 | 文档要求宽泛，主 Agent 易只在数据摘要节示范 | #11 已记录 | ⚠️ 口径元数据代码层已落地，但报告层执行力不足，见 §3.3 |
| E13 | 抽检准出 | 5 个警告均为已知口径差异（营收 11.27%/IFRS 归母 11.3%/Non-IFRS 归母 3.62%/市值 3.63%/护城河 2.14%），verdict 无"已知口径脚注认可"通道 | verdict 只区分通过/警告/不通过，无 caliber_ack 字段 | #11 部分记录 | 🆕 本次新发现，见 §3.4 |
| E14 | PowerShell 兼容 | `$env:PYTHONIOENCODING='utf-8'` 在 bash 报 `command not found` | PowerShell 语法误用于 bash | 未记录（环境适配） | ✅ 改用 `PYTHONIOENCODING=utf-8 python ...` |

**统计**：14 项中 7 项已修复生效（E1/E6/E7/E8/E9 + E4/E14 运行时处理），3 项部分生效或新问题（E3/E12/E13），2 项本次新发现并主 Agent 内联处理（E2/E11），2 项核心新问题待修复（E10/E13）。

## 2. 对 `20ea36d9` 后 9 个提交的审核评价

逐个评价改进是否起到积极有效作用、是否引入新问题或冗余。评价基于本次实际运行触达的代码路径。

### 2.1 `ca5b0d2e` docs(feedback): 规划技能复盘修复方案

- 内容：新增 `docs/dev-feedback-action-plan.md`，把上次反馈 13 项核查后形成 P1 修复队列。
- 评价：**积极有效**。这是难得克制的反馈处理——不是照单全收，而是明确"不直接采纳"3 条（不把日期转年份参与比对、不默认绝对值通过、不强制 `--unit` 必填），给出了正确路径。这种"先复现再评价再修"的纪律避免了过度工程化。
- 改进点：action-plan 未跟踪"修复后二次验证"环节，导致本文件需要手动闭环。建议 action-plan 增加"验证 commit"字段，记录每个 P1 项的二次运行验证证据。

### 2.2 `6e198042` fix(audit): 增强报告抽检数值韧性

- 内容：`_SIGNED_NUM` 引入 `[-+]?` 前缀一致应用到所有正则；`_to_numeric()` 安全转换；`compare_mode="absolute_magnitude"` 显式开关；`abs(val) < 1e15` 防负数过界。
- 评价：**积极有效且设计优雅**。`_SIGNED_NUM` 用一个常量统一升级所有模式，避免了逐处补丁；`compare_mode` 显式开关而非默认绝对值，正符合 action-plan §3 的克制原则。二次验证 E8/E9 通过。
- 改进点：`_to_numeric()` 对"14.3亿"中的"亿"不做单位解析（只剥数字），这是 E10 单位陷阱的根因之一。建议下个版本让 `_to_numeric` 可选返回 `(value, unit)` 元组。

### 2.3 `f5e74593` fix(datapack): 支持投研数据包落盘

- 内容：新增 `_write_json_output` 和 `_datapack_output_path`，CLI 增加 `-o/--output` 和 `--output-dir`，二者互斥校验。
- 评价：**积极有效**。`--output` 与 `--output-dir` 互斥校验避免了误用；`newline="\n"` 保证 LF 行尾；`os.makedirs(exist_ok=True)` 自动建目录。本次正是用 `-o` 落盘的，E1 修复确认。
- 改进点：stderr 输出 `[datapack] 写入 <path>` 是好习惯，但主 Agent 用 `$(cat file)` 读 JSON 时若路径含空格或中文会出问题（本次未触发）。建议文档示例显式用双引号包裹路径。

### 2.4 `fc0504c7` fix(rigor): 增强金融严谨性工具参数防呆

- 内容：`cross_validate` 增加 `caliber` 参数、量级告警 `max/min>50`、`magnitude_warning` 返回字段；`three_scenario` 增加 `_normalize_growth_inputs` 自动归一化 + stderr 警告；"共识值(加权中位数)"改为"参考中位数"。
- 评价：**积极有效**。量级告警正中上次反馈 #5 的场景；growth 归一化带 stderr 警告而非静默修正，保留了可审计性。二次验证 E7 通过（stderr 含警告、不再 3000%）。
- 改进点：量级告警阈值 `>50` 是硬编码。本次腾讯营收 7518 vs 理杏仁 8365 差 11%，不触发；但若单位错位 100x 会触发。阈值合理，但建议暴露为 CLI 参数 `--magnitude-threshold` 供特殊场景调整。

### 2.5 `27b66eac` fix(agent): 增加任务代理失败降级记录

- 内容：9 个团队型 skill 同步增加"Agent 失败诊断与降级记录（必须执行）"小节，明确 `model route not configured`/`timeout`/`permission denied` 三类错误的处理，要求报告附录记录失败 Agent/错误原文/降级方式/影响范围。
- 评价：**积极有效且覆盖广**。同步覆盖 9 个 skill（investment-team/earnings-team/industry-research 等）而非只改 investment-research，避免了局部修复。本次报告附录 A 完整记录了 Explore Agent 和 exa-1 两项降级（见 §1 E5），Fix#8/B1 实际生效。
- 改进点：错误原文摘要"只保留必要信息，不写入密钥或本机隐私路径"是好的隐私原则，但没有给出"必要信息"的判定标准。建议补一个示例：`deepseek-v4-flash 路由未配置` 是可保留的模型名，`<本机用户目录>\...` 是必须删除的路径。

### 2.6 `4568e6f0` fix(lxr): 增加港股行业对比降级路径

- 内容：`_hk_industry_compare_alternatives()` 返回 3 条替代路径（mx-xuangu/手工同业/港股龙头），在 `industry` 子块和顶层都透出 `note`+`alternatives`。
- 评价：**默认路径积极有效，但 `--no-mx` 路径未覆盖**。二次验证：`industry-compare 00700`（默认）完整输出 alternatives 与 note，但加 `--no-mx` 时输出为空（见 §1 E3）。skill 文档第〇步示例正是 `--no-mx` 省额度路径，主 Agent 按文档示例走就会拿不到 alternatives。
- 改进点：`--no-mx` 路径应在港股分支同样透出 alternatives（该字段不依赖 mx，是纯静态字符串列表）。这是一个**修复未覆盖到文档推荐路径**的盲点。

### 2.7 `abe2842d` fix(metadata): 增加财务口径元数据

- 内容：`FINANCIAL_FIELD_CALIBERS` 字典定义 5 个字段口径（toi=营业总收入等）；`_financial_caliber_metadata()` 注入 currency/unit/unit_note；datapack 顶层汇总 `caliber_metadata.financials`；`cross-validate --caliber` 输出口径冲突提示；skill 文档要求核心数据表保留「口径/来源 / 币种 / 单位」列。
- 评价：**代码层积极有效，报告层执行力不足**。datapack 确实携带了 caliber_metadata（本次报告中脚注说明了理杏仁 toi 8365 vs 腾讯年报 7518 的 11.27% 口径差异）。但 skill 文档要求"所有核心数据表保留口径列"，本次 29 个数据表只有 1 个含该列（见 §1 E12）。这是"文档说了但没机制强制"的典型。
- 改进点：见 §3.3，建议 report_audit 增加"口径列覆盖率"检查。

### 2.8 `5d46ce1b` ci: 增加离线回归门禁

- 内容：新增 `.github/workflows/ci.yml`，PR/push 触发离线门禁（pytest + verify_channel_capability + compileall + release_smoke + git diff --check）；新增 `investment_research_smoke` fixture（datapack + 报告骨架）；新增 `test_ci_and_fixture_contract.py` 防 CI 退化。
- 评价：**积极有效且设计正确**。CI 不依赖理杏仁 token/Playwright/secrets，纯离线门禁，符合"普通用户可安装即用"的封版原则。fixture 固化预录 datapack 作为后续 smoke 基线，是把 P1 修复转为长期回归的正确做法。
- 改进点：fixture 的 `expected_report_skeleton.md` 只有 28 行，覆盖的口径列/降级记录/抽检字段较浅。建议下一个 fixture 加入"含理杏仁字段的数据表必须带口径列"的正样本，强化 E12 的回归。

### 2.9 `d0cab458` feat(release): 增加发布说明生成工具

- 内容：新增 `tools/release_notes.py`（229 行），按 conventional commit 类型分组生成中文 Markdown release notes，支持 `--from/--to/--title/--output/--max-count`；新增 `test_release_notes.py`；release_smoke 增加 dry run 检查。
- 评价：**积极有效**。`CATEGORY_BY_TYPE` 把 type 映射到中文分组（功能/修复/CI/文档/测试/工程维护），`GIT_FIELD_SEPARATOR=\x1f` 用 ASCII unit separator 避免 commit message 含 `|` 或换行干扰解析，是稳健的工程选择。
- 改进点：与本次 investment-research 运行无直接关系，但 release notes 的 commit 摘要来自 `git log --format=%s`，若 commit message 含中文逗号或全角符号，分组正则 `CONVENTIONAL_RE` 仍能解析（type 是英文前缀）。无问题。

### 2.10 `1ae451ce` docs(腾讯): 增加deep档四大师投研报告（本次产出）

- 评价：本次运行产物，非工具改进。但作为"修复后运行"的载体，其附录 A 降级记录、脚注口径说明、抽检 30 点准出，间接验证了上述修复的端到端有效性。

**9 个提交总评**：全部起到积极有效作用，无冗余、无退化。设计上保持了"克制修复"的纪律（不默认绝对值、不强制必填、不静默修正）。但存在 3 个**覆盖盲点**：`--no-mx` 路径未透 alternatives（§2.6）、口径列报告层执行力不足（§2.7）、verdict 无已知口径认可通道（§3.4）。

## 3. 技能与代码值得改进的地方

### 3.1 【高优】report_audit 单位陷阱：extract 保留 unit 但 verdict 不归一化

**问题**：`extract_data_points` 对"14.3亿MAU"返回 `reported_value=14.3, unit='亿'`，unit 字段在模板里。但 verdict 的 `fetched_value` 是裸数字，核验者填 1430（百万）还是 14.3（亿）还是 1.43（十亿）全靠自觉。本次我就填成了 1430，触发 9900% 假偏差，差点导致报告被打回（实际报告数据正确）。

**根因**：extract 输出 unit，但 verdict 比较时丢弃了 unit 上下文，没有单位归一化层。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`、`tests/test_report_audit.py`
- extract 模板 JSON 每项增加 `report_unit` 字段（从已解析的 unit 复制）
- verdict 要求核验者填 `fetched_unit`，若 `fetched_unit != report_unit` 且二者属于已知换算关系（亿/百万/万/十亿/亿港元），自动归一化后再 `pct_diff`
- 无 `fetched_unit` 时，若 `max(abs)/min(abs) > 50`，输出"疑似单位不一致，请核对 fetched_unit"而非直接判不通过
- 测试：构造"14.3亿" vs fetched 1430（百万）case，期望 verdict 归一化后 0% 偏差通过

**验收命令**：`python -m pytest tests/test_report_audit.py -q`

### 3.2 【高优】report_audit.py CLI 缺 `-o/--output`，stdout 含日志头需清洗

**问题**：`report_audit.py verdict` 不支持 `-o`，主 Agent 只能 `$(cat filled.json)` 传 `--results`，但 stdout 混了日志头与 ANSI 颜色码，需要 Python 字符串切片清洗才能拿到纯净 JSON。本次我重定向 stdout 后又用 Python 切片才解决。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`
- verdict 增加 `-o/--output` 写 JSON 到文件，stdout 只打印人类可读摘要
- 或新增 `--json` 旗标，stdout 纯 JSON 无日志头
- 参考 `lxr_data.py datapack -o` 的 `_write_json_output` 实现，保持一致

**验收命令**：`python tools/report_audit.py verdict --results "$(cat filled.json)" --report xxx.md -o _tmp_verdict.json` 应直接落盘纯净 JSON。

### 3.3 【中优】口径列报告层执行力：skill 要求"所有核心数据表"但实际只有 1/29

**问题**：`abe2842d` 让 skill 文档要求"所有核心数据表保留「口径/来源 / 币种 / 单位」列"，但本次 29 个数据表只有"数据摘要"节 1 个表头含该列。文档要求宽泛，主 Agent 在信息量大的 deep 档容易只做示范。

**根因**：文档要求是"软约束"，无机器检查。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`skills/investment-research.md`
- report_audit extract 识别"含理杏仁字段的数据表"（表头或附近出现 PE/PB/营收/归母 等关键词），检查该表头是否含「口径」或「来源」列，缺失时在 verdict 输出 warning（不阻塞准出，但提示）
- skill 文档把"所有核心数据表"细化为"凡含理杏仁/妙想取数的表必须带口径列，纯历史趋势表可省"
- 测试：构造一个含理杏仁字段但无口径列的表，期望 warning

**验收命令**：`python -m pytest tests/test_report_audit.py -q`

### 3.4 【中优】verdict 缺"已知口径认可"通道，5 个警告全靠人工脚注

**问题**：本次 5 个警告（营收 11.27%、IFRS 归母 11.3%、Non-IFRS 归母 3.62%、市值 3.63%、护城河 2.14%）全是已知口径差异，已在报告脚注说明，但 verdict 仍把它们列为警告，主 Agent 需在反馈中人工解释"这些是口径差异非错误"。verdict 没有"已认可口径"字段让核验者标注 `caliber_ack: true` 后降级为通过。

**最小修复建议**：
- 目标文件：`tools/report_audit.py`、`codex/ai-berkshire/scripts/tools/report_audit.py`、`tests/test_report_audit.py`
- results JSON 每项支持可选 `caliber_ack: true` + `caliber_note: "理杏仁toi vs 年报抵销口径，已脚注"`
- verdict 遇到 `caliber_ack: true` 时，偏差超阈但不再列为"不通过"，改为"口径认可"单独计数，最终摘要区分"通过/口径认可/警告/不通过"
- 防滥用：`caliber_ack` 必须配 `caliber_note`，空 note 不认可

**验收命令**：`python -m pytest tests/test_report_audit.py -q`

### 3.5 【中优】港股 industry-compare `--no-mx` 路径未透 alternatives

**问题**：`4568e6f0` 在默认路径透出 alternatives，但 `--no-mx` 路径输出为空。skill 文档第〇步示例恰是 `--no-mx` 省额度路径，主 Agent 按文档走会拿不到港股降级提示。

**最小修复建议**：
- 目标文件：`tools/lxr_data.py`、`codex/ai-berkshire/scripts/tools/lxr_data.py`、`tests/test_lxr_data.py`
- `--no-mx` 路径的港股分支同样注入 `_hk_industry_compare_alternatives()`（该字段是纯静态字符串，不依赖 mx）
- 测试：`industry-compare 00700 --no-mx` 期望输出含 alternatives

**验收命令**：`python -m pytest tests/test_lxr_data.py -q`

### 3.6 【低优】港股年报识别：理杏仁返回季度累计数据，date 匹配失败

**问题**：理杏仁港股年报 `date[5:10]=='12-31'` 匹配失败，`annuals count: 0`。实际港股返回季度累计数据，需按 `reportType=='annual_report'` 识别。本次主 Agent 内联修复后提取 6 年年报成功。

**最小修复建议**：
- 目标文件：`tools/lxr_data.py`、`codex/ai-berkshire/scripts/tools/lxr_data.py`、`tests/test_lxr_data.py`
- 港股 financials 解析增加 `reportType=='annual_report'` 兜底识别，date 匹配失败时按 reportType 兜底
- 测试：构造港股季度累计 datapack，期望 annuals 提取非空

**验收命令**：`python -m pytest tests/test_lxr_data.py -q`

### 3.7 【低优】Agent 失败降级记录的"必要信息"判定标准缺失

**问题**：`27b66eac` 要求"错误原文摘要只保留必要信息，不写入密钥或本机隐私路径"，但未给判定标准。本次我保留 `deepseek-v4-flash 路由未配置`（模型名），删除了路径。其他 agent 可能标准不一致。

**最小修复建议**：
- 目标文件：`skills/investment-research.md` 及 8 个同步 skill
- 补示例：可保留 = 模型名/错误码/HTTP 状态；必须删除 = 本机绝对路径/token/cookie/账户名
- 测试：`test_skill_output_regressions.py` 增加正样本检查

### 3.8 【低优】action-plan 缺"二次验证"跟踪字段

**问题**：`dev-feedback-action-plan.md` 每个 P1 项有"状态：已完成"但无"二次运行验证证据"字段，导致修复闭环靠人工回忆。

**最小修复建议**：
- 目标文件：`docs/dev-feedback-action-plan.md`
- 每个已完成项增加"二次验证"字段，链接到验证运行的反馈文件（如 P1-A3 → 本文件 §1 E7）
- 鼓励每次完整运行后回填该字段，形成修复-验证证据链

## 4. 整体使用感受

### 4.1 技能骨架优秀

四大师七模块框架（段永平生意/巴菲特护城河/芒格逆向/李录文明）+ 数据三级降级链 + financial_rigor 精确十进制 + report_audit 25% 抽检准出，这套骨架在 deep 档下经受住了机构级深度的考验。5 情景 + 蒙特卡洛敏感度 + 3 情景量化压力测试 + 5 历史类比 + 终局推演，产出了一份自洽可审计的 655 行报告。**骨架是这套技能最大的资产，不需要推翻。**

### 4.2 容错与可观测性是短板，但上一轮修复已显著改善

上一轮反馈后，datapack 落盘、Agent 降级记录、数值韧性、口径元数据、CI 门禁这 5 项核心改进全部生效。本次运行的体感比上一轮顺畅很多——最关键的进步是 **"装作没发生"被"可审计降级"取代**（附录 A 透明记录了 Explore Agent 失败）。这是项目质量文化的实质提升。

### 4.3 剩余短板集中在 report_audit 的单位与口径处理

本次最大的摩擦点不是工具崩溃（那些已修），而是 **report_audit 的单位归一化与口径认可**（§3.1/§3.4）。这两项不修，每次 deep 档都会在抽检环节浪费 15-30 分钟处理假偏差和人工解释口径差异。这是下一轮 P1 应优先解决的"准出摩擦"。

### 4.4 deep 档真实成本提示

本次因 Explore Agent 路由失败降级为单 Agent，deep 档"跨 Agent 偏见验证"未完整执行。这不是技能设计缺陷，而是 Agent 可用性依赖。但技能文档应更诚实地标注：**deep 档的质量保障上限受 Agent 可用性约束**，单 Agent 模式下"双 Agent 偏见验证"退化为"主 Agent 自我对抗式复核"，置信度低于真双 Agent。本次报告已在附录 A 如实标注。

### 4.5 文档与代码的一致性仍有缺口

`--no-mx` 路径的 alternatives 缺失（§3.5）是"文档示例走的路径恰好是修复未覆盖的路径"的典型。这类缺口靠代码 review 难发现，需要**按文档示例逐条跑一遍**的 smoke。建议下一轮增加"文档示例路径 smoke"测试。

## 5. 给编程 agent 的接手建议

按优先级排序，建议按 P1→P2 顺序接手：

### P1（下一轮优先，解决准出摩擦）

1. **§3.1 report_audit 单位归一化**——本次最痛的点，每次抽检都会踩
2. **§3.2 report_audit CLI `-o`**——与 §3.1 配套，让 verdict 输出可机器解析
3. **§3.4 verdict caliber_ack 通道**——让已知口径差异不再占用警告额度

### P2（覆盖盲点与执行力）

4. **§3.5 港股 `--no-mx` 路径 alternatives**——文档示例路径的覆盖盲点
5. **§3.3 口径列覆盖率检查**——让"所有核心数据表"从软约束变机器检查
6. **§3.6 港股年报 reportType 兜底**——本次主 Agent 内联修复，应固化

### P3（文档与流程）

7. **§3.7 Agent 降级"必要信息"标准**——补示例
8. **§3.8 action-plan 二次验证字段**——闭环证据链

### 其他建议（非本次发现，但值得纳入）

- **deep 档 Agent 可用性兜底**：当 Explore/Team Agent 路由失败时，skill 文档应明确"单 Agent 模式下哪些 deep 档环节必须降级标注置信度"，目前只说"顺序模拟"，未说"哪些结论因此置信度下降"。本次我自己标注了，但应文档化。
- **report_audit 抽检点数量自适应**：deep 档 25% 抽检 + 全部双源，本次 30 点。但 deep 档报告长，30 点仍可能漏掉关键口径差异。建议 deep 档抽检点数量下限 = max(30, 报告数据点数 × 0.25)。
- **financial_rigor 量级告警阈值可配**：`>50` 硬编码，建议 `--magnitude-threshold` 参数。
- **datapack 缓存 TTL 可观测**：skill 文档说"TTL 1h 跨模块共享"，但 datapack JSON 不记录生成时间，主 Agent 无法判断是否过期。建议 datapack 顶层加 `_generated_at` 字段（用 args 传入时间戳，避免 `Date.now()` 在 workflow 脚本里不可用的问题——这是 workflow 脚本的约束，CLI 不受影响）。

## 6. 路线图进度摘要

本次未改变 `docs/ROADMAP.md` 目标。P0 已完成发布，P1 的 A1/A2/A3/B1/B2/B3/C1/D1 全部已完成。本次工作属 P1 "按真实技能运行反馈收敛工具容错性"的延续——提供修复后的二次验证证据，并识别下一轮 P1 候选（§3.1-§3.6）。建议编程 agent 把 §3.1-§3.4 纳入 P1 反馈驱动修复队列的新条目，§3.5-§3.8 纳入 P2。

## 7. 隐私检查

本反馈未包含 token、cookie、账户标识、真实持仓金额、未脱敏日志或本机私有路径。错误原文摘要仅保留模型名 `deepseek-v4-flash` 与 HTTP 状态 `402`，已删除所有路径与账户信息。
