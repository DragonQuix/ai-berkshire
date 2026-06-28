# ADR: 权限安全多 Agent 架构

日期：2026-06-28

## 状态

已采纳。

## 背景

Claude Code 当前存在一个现实限制：后台 Agent 的权限不一定继承主 Agent 的权限，且后台 Agent 触发需要审批的工具调用时，用户可能没有机会批准。

AI Berkshire 过去的团队类 Skill 把“搜索、取数、写文件、分析”都分派给后台 Agent，容易在财报下载、WebSearch、Bash、mx-search、理杏仁、报告保存等步骤卡死，也容易造成数据口径冲突。

## 决策

将 AI Berkshire 的团队类工作流从“后台 Agent 各自取数”重构为：

```text
Team Lead 统一取证 / 验算 / 写入
    -> 角色 Agent 只读分析
    -> Team Lead 综合冲突、补数、定稿
```

## 约束

1. **主 Agent 是唯一权限执行者**：联网、命令、理杏仁、妙想、文件写入、报告保存、抽检和 Git 操作都由 Team Lead 执行。
2. **子 Agent 是只读分析者**：角色 Agent 只读取共享资料包、来源索引、摘录和工具输出，不调用 WebSearch/WebFetch/Bash/Write/Edit。
3. **缺口回传而非自行补数**：角色 Agent 发现资料不足时输出「补数请求」，Team Lead 统一补充资料后再进入第二轮。
4. **并行可选，深度必需**：能并行就并行；权限受限时顺序角色模拟，保留多视角、反证和综合裁判。
5. **文件写入单点化**：所有报告、数据包、审计结果、规划文档只由 Team Lead 写入，避免后台 Agent 写冲突。

## 标准流程

### 资料包准备

Team Lead 根据 Skill 类型建立共享资料包，例如：

| 场景 | 推荐资料包 |
|---|---|
| 上市公司深度研究 | `reports/{公司名}/data-pack.json` + `source-index.md` |
| 财报分析 | `reports/{公司名}/{公司名}-{期间}-earnings-source-pack.md` |
| 未上市公司 | `reports/{公司名}/{公司名}-private-source-pack-{YYYYMMDD}.md` |
| 新闻异动 | `reports/{公司名}/{公司名}-news-source-pack-{YYYYMMDD}.md` |
| 公众号文章 | `reports/.../article-source-pack-{YYYYMMDD}.md` |
| 深度系列 | `reports/{公司名}/《看懂{公司名}》/series-consistency-pack.md` |

资料包至少包含：

- 数据摘要：关键数字、口径、时间、币种、单位。
- 来源索引：标题、链接、日期、来源类型、`_source`。
- 工具输出：`financial_rigor.py`、`lxr_data.py`、mx-data、mx-search 的关键结果。
- 反证材料：负面新闻、竞争压力、管理层争议、数据冲突。
- 已知缺口：找不到、无法验证、口径不一致的信息。

### 只读角色分析

每个角色输出统一结构：

```markdown
## 角色结论

### 核心判断

### 使用的证据

### 反面证据

### 不确定性

### 补数请求

### 评分或置信度
```

### Team Lead 综合

Team Lead 负责合并角色结论、找出角色冲突、仲裁数据口径、补充必要资料、写最终报告并执行数据抽检。

## 已改造范围

| Skill | 新架构 |
|---|---|
| `/investment-team` | Team Lead 建 `data-pack`，4 角色只读分析；权限受限时顺序角色模拟 |
| `/earnings-team` | Team Lead 获取原文和数据；四大师/编辑/读者只读处理 |
| `/private-company-research` | Team Lead 建 `private-source-pack`；6 角色只做拼图分析和补数请求 |
| `/news-pulse` | Team Lead 先拉结构化异动和新闻包；4 角色只做归因 |
| `/wechat-article` | Team Lead 建素材库和图表清单；作者/编辑/读者只写作审稿 |
| `/earnings-review` | 主 Agent 统一获取一手资料和市场反应 |
| `/investment-checklist` | Team Lead 批量建公司数据包；公司角色只读补充判断 |
| `/industry-research` | Team Lead 建行业资料包；市场/环节角色只读复核补漏 |
| `/management-deep-dive` | Team Lead 建定性资料包；四类角色只读分析 |
| `/deep-company-series` | Team Lead 整理路径和关键数字表；只读审读 Agent 输出问题清单 |
| `/investment-research` | Task Agent 只分析主 Agent 注入的数据包 |

## 结果与取舍

- 流程稳定性提高，不再依赖后台 Agent 权限继承。
- 首轮资料包准备更集中，速度可能低于旧式并行搜索。
- 研究深度从“更多搜索线程”转为“统一证据包 + 多视角反证 + 综合裁判”。
- 后续需要模板和静态校验脚本，防止新 Skill 写回旧模式。
