# 投研团队：四角色并行分析框架

对 $ARGUMENTS 进行团队化投资研究分析。采用权限安全团队模式：Team Lead 统一取数、搜索、验算和写文件；角色 Agent 只基于共享资料包做独立分析。若后台 Agent 因 Claude Code 权限限制无法执行，则由 Team Lead 在同一会话中按角色顺序模拟，流程不得卡死。

## 执行流程

### 第一步：展示团队框架

向用户展示以下团队结构，然后进入数据包准备：

| 角色 | 职责 | 分析框架 |
|------|------|----------|
| **team-lead**（你自己） | 统筹协调、汇总研判、输出最终报告 | 四大师综合框架 |
| **business-analyst** | 商业模式 & 护城河分析 | 段永平视角 |
| **financial-analyst** | 财务报表 & 估值分析 | 巴菲特视角 |
| **industry-researcher** | 行业格局 & 竞争态势 | 芒格视角 |
| **risk-assessor** | 风险评估 & 管理层研判 | 李录视角 |

### 第一步零五：权限安全团队模式（硬约束）

本 Skill 的深度来自**独立视角与互相否证**，不是让后台 Agent 重复搜索。为避免 Claude Code 后台 Agent 无法继承主 Agent 权限导致流程中断，统一采用以下架构：

1. **Team Lead 是唯一有权限执行者**：联网搜索、WebFetch、Bash/Python、理杏仁、妙想、文件写入、报告保存、数据抽检都由 Team Lead 执行。
2. **角色 Agent 只读分析**：后台 Agent 只能读取 Team Lead 注入的 `data-pack`、资料索引、摘录和工具输出；不得自行调用 WebSearch/WebFetch/Bash/Write/Edit。
3. **缺资料不阻塞**：角色 Agent 发现证据不足时，输出「补数请求」而不是自行取数。Team Lead 汇总补数请求后统一补充资料，必要时发起第二轮只读分析。
4. **工具不可用时降级**：如果 Team/Task/后台 Agent 不可用或权限被拒，Team Lead 直接在同一上下文按四个角色逐一产出独立分析，并明确标注为「顺序角色模拟」。
5. **文件协作禁写**：角色 Agent 不写文件、不改报告、不更新任务状态；最终报告、数据包、抽检记录只由 Team Lead 写入。

### 第一步半：AI研究偏见评估

在创建团队前，先向用户展示该公司的"AI可研究性"评估：

**信息丰富度评级**（决定研究策略）：
| 等级 | 特征 | 研究策略调整 |
|------|------|------------|
| A级（信息充裕） | 上市多年、券商覆盖广 | 团队重点放在**反面检验**和**非共识视角**，避免输出与市场一致的"正确的废话" |
| B级（信息适中） | 上市不久、覆盖有限 | 每个Agent的推算数据必须标注置信度，team-lead汇总时标注"数据充分度" |
| C级（信息稀缺） | 冷门/新上市/新兴市场 | 团队转为"第一性原理模式"：不追求报告完整性，聚焦商业本质的几个核心问题 |

**关键提醒**：资料多≠确定性高，资料少≠确定性低。AI能输出的置信度 ≠ 投资的真实确定性。确定性来自商业模式本身，不来自资料数量。

将评级结果告知每个Agent，影响其研究方式。

### 第一步又四分之一：共享数据包（Team 启动前必须执行）

对 A股/港股目标公司，Team Lead **先**拉取一次数据包：

```bash
python tools/lxr_data.py datapack {code} --years 5
```

或分拆拉取（与 `/investment-research` 第〇步相同）：

将 JSON 摘要写入 `reports/{公司名}/data-pack.json`（或团队共享目录），并在创建 Task 时**注入各 Agent description**。美股、未覆盖市场或字段缺失时，由 Team Lead 统一用 WebSearch/WebFetch、SEC/HKEX/巨潮、macrotrends/stockanalysis、mx-search 等补齐，形成 `source-index` 后再分派分析。

**`_source` 标注**（数据包与各 Agent 输出须一致，见 `docs/channel-capability-matrix.md`）：

| 数据块 | `_source` |
|--------|-----------|
| datapack / financials / valuation / governance 等 | `lixinger` |
| mx_quote | `mx-data` |
| mx_news / 竞对资讯 | `mx-search` |

| Agent | 注入数据维度 | Agent 专注分析（不取数） |
|-------|-------------|------------------------|
| business-analyst | `revenue` 营收构成 + 业务描述 | 商业模式、护城河定性 |
| financial-analyst | `financials` + `valuation` + 分位点 | 估值判断、安全边际 |
| industry-researcher | `industry-compare` + mx-search 竞对资讯 | 竞争格局、行业趋势 |
| risk-assessor | `governance` + `industry-deep` 风险字段 | 风险、管理层诚信 |

### 第一步又二分之一：结构化产物 Contract（P1 准出要求）

本 Skill 必须遵循 `docs/team-research-output-contract.md`。Team Lead 在启动角色分析前先建立或规划以下产物：

```bash
python tools/team_research_outputs.py {公司名} --ticker {代码} --market {市场}
```

- `reports/{公司名}/data-pack.json`
- `reports/{公司名}/source-index.md`
- `reports/{公司名}/role-briefs/`
- `reports/{公司名}/audit-results.json`
- `reports/{公司名}/最终报告.md` 或 `reports/{公司名}/{公司名}-research-{YYYYMMDD}.md`

脚手架只创建空模板，不代表研究完成；`audit-results.json` 初始应保持 `reject`，直到完成数据抽检并满足准出规则。

准出前执行结构校验：

```bash
python tools/team_research_outputs.py validate reports/{公司名}
```

结构校验通过不等于事实抽检通过；最终发布仍必须满足 `audit-results.json` verdict 为 `pass`。

`audit-results.json.items[*].status` 只能是 `pass`、`fail` 或 `pending`；`claim`、`report_location`、`expected_value` 必须非空；`status` 为 `pass`/`fail` 时 `verified_value` 与 `source_ref` 必须非空且 `source_ref` 在 `source-index.md` 中已定义；`verdict` 为 `pass` 时 `items` 必须非空且全部 `status == pass`，否则结构校验打回。

若最终报告引用未定义来源 ref（即 ref 未出现在 `source-index.md` 的 ref 列），结构校验必须打回，Team Lead 需要补齐来源索引或修正报告引用。

同一规则也适用于 `data-pack.json` 任意层级的 `source_refs` 列表，以及 `audit-results.json.items[*].source_ref` 字段；这些字段不得引用未定义来源 ref。

最终报告中的关键数据必须能追溯到 `data-pack.json` 或 `source-index.md`；角色结论与最终结论冲突时，必须写明 Team Lead 的仲裁理由。

`role-briefs/` 至少包含：

- `business-analyst.md`
- `financial-analyst.md`
- `industry-researcher.md`
- `risk-assessor.md`

每份角色简报必须包含：角色输入范围、核心结论与评分、使用的证据、反面证据、不确定性、补数请求、与其他角色可能冲突的判断。

### 第二步：准备角色任务（不强依赖 TeamCreate）

优先使用 TeamCreate 创建团队，但不得依赖其权限继承能力：
- team_name: `{公司名}-research`（英文小写，如 `meituan-research`）
- agent_type: `team-lead`

若 TeamCreate / TaskCreate 不可用，跳过团队对象，直接按第三步任务定义进行顺序角色模拟。

### 第三步：创建4个任务

使用 TaskCreate 创建以下4个任务（每个都要有 subject、description、activeForm）：

#### 任务1：商业模式分析
- subject: `分析{公司名}商业模式、护城河与用户价值`
- description 包含：
  1. 商业模式本质：核心生意定义、收入结构拆解
  2. 平台/产品飞轮效应如何运转
  3. 护城河分析：品牌/转换成本/网络效应/规模效应/技术壁垒，逐一验证
  4. 用户/客户价值：为各方创造了什么独特价值
  5. 业务矩阵与协同效应
  6. 段永平"好生意"标准评估：差异化、定价权、可持续竞争优势
  7. 仅使用 Team Lead 注入的财报、行业报告、访谈、新闻摘录；缺资料时列出补数请求

#### 任务2：财务与估值分析
- subject: `分析{公司名}财务数据、盈利能力与估值`
- description 包含：
  1. 近3-5年营收、净利润、经营利润趋势
  2. 盈利能力指标：ROE、ROA、毛利率、经营利润率
  3. 现金流分析：经营性现金流、自由现金流、资本开支
  4. 资产负债表健康度：现金储备、负债率、流动性
  5. 估值分析：PE/PS/PB/EV等，与历史及同业对比
  6. 安全边际评估：内在价值 vs 当前股价
  7. **金融严谨性验证（禁止心算）**：Team Lead 必须在分派前或汇总时调用工具；financial-analyst 只解读工具输出，缺输出则提出补算请求
     - 市值验算：`python tools/financial_rigor.py verify-market-cap --price {价格} --shares {股本} --reported {报告市值} --currency {币种}`
     - 估值验算：`python tools/financial_rigor.py verify-valuation --price {价格} --eps {EPS} --bvps {每股净资产}`
     - 关键数据交叉验证：`python tools/financial_rigor.py cross-validate --field {字段} --values '{JSON}' --unit {单位}`
     - 三情景估值：`python tools/financial_rigor.py three-scenario --price {价格} --eps {EPS} --shares {股本亿} --growth {乐观} {中性} {悲观} --pe {乐观PE} {中性PE} {悲观PE}`
     - 将工具输出结果直接嵌入报告中作为验证记录

#### 任务3：行业与竞争分析
- subject: `分析{行业}行业格局与{公司名}竞争态势`
- description 包含：
  1. 行业规模与增长：市场规模、增速、渗透率
  2. 竞争格局：主要对手市场份额、竞争策略对比
  3. 核心竞争者威胁评估：逐个分析主要竞争对手
  4. 各细分赛道格局
  5. 行业趋势：技术变革、政策影响、新进入者
  6. 产业链分析：上中下游价值分配
  7. 仅使用 Team Lead 注入的行业数据和竞争动态；缺资料时列出补数请求

#### 任务4：风险与管理层评估
- subject: `评估{公司名}投资风险与管理层质量`
- description 包含：
  1. 管理层评估：CEO能力圈、诚信度、战略眼光、资本配置能力、历史决策质量
  2. 监管风险：当前及潜在监管影响
  3. 竞争风险：各竞争对手威胁程度评估
  4. 业务风险：新业务亏损、扩张不确定性
  5. 宏观风险：经济周期、行业周期影响
  6. 治理结构：股权结构、关联交易、股东回报政策
  7. 长期确定性：10年后公司会怎样？什么可能颠覆其商业模式？
  8. 仅使用 Team Lead 注入的监管动态、管理层言论和治理数据；缺资料时列出补数请求

### 第四步：启动4个只读分析 Agent

如果当前平台允许后台 Agent 正常运行，使用 Task 工具启动4个只读分析 Agent；能并行就并行，不能并行就顺序执行。不要为了并行牺牲权限稳定性。

每个Agent的配置：
- `subagent_type`: `general-purpose`
- `run_in_background`: `true`
- `team_name`: 对应团队名
- `name`: 对应角色名（business-analyst / financial-analyst / industry-researcher / risk-assessor）

每个Agent的prompt模板：

```
你是{公司名}投研团队中的"{角色中文名}"，负责从{大师名}投资视角分析{公司名}。

请完成任务 #{任务编号}：{任务subject}

具体要求：
{任务description的内容}

**研究方法**：
- 只使用 Team Lead 提供的共享资料包、资料索引和工具输出，不调用 WebSearch/WebFetch/Bash/Write/Edit
- **财务数据必须来自 Team Lead 提供的两个独立来源或交叉验证结果**，按 `skills/financial-data.md` 交叉验证阈值（同口径 ≤2% / 2–5% 标注差异 / >5% 异常）解读
- 确保数据准确，关键数据标注来源；如果资料不足，明确列出「补数请求」
- 分析要深入，不流于表面

**输出要求**：
- 报告要详尽，使用Markdown表格呈现关键数据
- 每个分析维度要有明确结论和评分
- 报告末尾要有该维度的总体结论
- 单独列出：`使用的证据`、`反面证据`、`不确定性`、`补数请求`

**完成后**：
直接把完整分析报告返回给 Team Lead；不要写文件，不要调用平台任务状态或跨 Agent 消息工具，除非当前平台明确支持且不触发权限问题。
```

### 第五步：接收报告并跟踪进度

- 向用户展示进度表（哪些角色已完成、哪些仍在研究中）
- 每收到一份报告，更新进度并展示该报告的核心要点（3-5条）
- 等待全部4份报告到齐；如有补数请求，Team Lead 统一补数后再补一轮只读分析

### 第六步：关闭团队成员

仅当实际创建了持久团队对象时，清理或关闭团队成员；普通 Task/顺序角色模拟无需发送关闭消息。

### 第七步：汇总最终报告

综合4份分析报告，输出以下结构的最终报告：

---

#### 1. 一句话结论
> 用一段话（50-100字）概括是否值得投资及核心逻辑

#### 2. 四维评分总表
| 维度 | 框架 | 评分(1-5星) | 核心判断 |
|------|------|------------|----------|

综合评分：X / 5

#### 3. 核心数据速览
关键财务和经营指标表格（近2年对比）

#### 4. 各维度分析摘要
每个维度摘取3-5条最重要的发现

#### 5. 投资论点（Bull vs Bear）
- 🟢 看多逻辑（5-7条）
- 🔴 看空逻辑（5-7条）

#### 6. 巴菲特买入前Checklist
| # | 检查项 | 通过? | 说明 |
10个核心检查项，逐一评估

#### 7. 最终投资建议
- 定性判断表（生意质量/管理层/估值/时机）
- 分层操作建议表（激进型/稳健型/保守型 → 建议+价格区间）
- 关键催化剂（加仓信号/减仓信号各3-5条）

#### 8. 总结段落
100-200字的最终总结

#### 9. 关键数据溯源
列出最终报告关键财务、估值、行业、治理和风险数据对应的 `data-pack.json` 字段或 `source-index.md` ref。

#### 10. 角色冲突与 Team Lead 仲裁
列出四个角色之间或角色结论与最终结论之间的关键冲突；如存在冲突，写明 Team Lead 的仲裁理由、采纳依据和残余不确定性；如无实质冲突，明确写“未发现影响最终结论的角色冲突”。

---

### 第八步：保存报告

将完整最终报告写入 `reports/{公司名}/{公司名}-research-{YYYYMMDD}.md`；若使用 `/investment-team` 的目录化输出，也可保存为 `reports/{公司名}/最终报告.md`。同时保存或更新 `data-pack.json`、`source-index.md`、`role-briefs/` 和 `audit-results.json`。

### 第九步：数据抽检（准出流程）

最终报告写完后，用 `team_research_outputs.py audit-extract` 从报告中采样生成 contract 格式抽检清单，直接写入 `audit-results.json`：

```bash
# Step 1 — 从最终报告采样生成 contract 格式抽检清单（复用 report_audit 抽取）
python tools/team_research_outputs.py audit-extract reports/{公司名} \
  --ratio 0.15 --seed 42

# Step 2 — 对 audit-results.json.items 每项从可靠信源取数（参见 skills/financial-data.md），
#          填入 verified_value 与 source_ref，并把 status 改为 pass/fail

# Step 3 — 准出结构校验
python tools/team_research_outputs.py validate reports/{公司名}
```

`audit-extract` 复用 `tools/report_audit.py` 的抽取与采样逻辑，但直接产出 `audit-results.json.items[*]` 的 contract 结构（`status=pending`），并把 `verdict` 重置为 `reject`；不需要再用 `report_audit.py extract/verdict` 手工翻译格式。

**【准出】** `validate` 通过且 `audit-results.json` verdict 改为 `pass`（全部 item `status==pass`）→ 报告可发布；**【打回】** 有 `fail` item 或 `validate` 不通过 → 修正后重审。

### 第十步：清理团队

如果创建了平台团队对象，使用对应清理工具释放团队资源；否则跳过。

## 重要注意事项

1. **优先权限安全，再追求并行速度**——Agent 可并行只读分析，但取数、搜索、写文件必须由 Team Lead 统一执行
2. **Agent 的价值是独立视角**——不是重复搜索，而是基于同一证据包给出不同框架下的判断、反证和不确定性
3. **数据准确性**——Team Lead 负责最新数据和关键数据交叉验证，Agent 负责指出证据缺口
4. **结论要明确**——不回避给出买入/观望/回避建议和具体价格区间
5. **所有分析必须有数据支撑**——附数据来源
6. **允许顺序角色模拟**——后台权限受限时，不要阻塞流程；按四个角色顺序完成同等分析
7. **反偏见意识**——team-lead在汇总时必须评估：各Agent的分析是否受限于资料充裕度？是否与市场共识过度趋同？最终报告需包含"信息丰富度评级"和"AI研究局限性声明"
8. **信息稀缺时的诚实原则**——宁可在报告中留白标注"数据不足"，也不要用推测填满框架伪装确定性
