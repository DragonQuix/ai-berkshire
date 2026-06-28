# Source Pack 模板

本文件是权限安全多 Agent 架构的资料包模板。适用原则见 `docs/adr/2026-06-28-permission-safe-multi-agent.md`：Team Lead 统一取数、搜索、验算和写文件；角色 Agent 只读分析；缺资料时输出「补数请求」。

## 通用要求

- 每个关键数据必须写清：数值、口径、期间、币种、单位、来源渠道、来源日期。
- 每个来源必须可追溯：标题、链接或文件路径、发布日期、抓取日期、`_source`。
- 每个资料包必须包含反证材料，不得只放支持结论的证据。
- 每个资料包必须列出已知缺口：找不到、未核验、口径冲突、数据过旧。
- 角色 Agent 不得调用 WebSearch/WebFetch/Bash/Write/Edit，不得自行补数；只输出分析、冲突点和补数请求。

## 1. 上市公司深度研究

推荐路径：

- `reports/{公司名}/data-pack.json`
- `reports/{公司名}/source-index.md`

`data-pack.json` 模板：

```json
{
  "meta": {
    "company": "",
    "ticker": "",
    "market": "",
    "generated_at": "YYYY-MM-DD",
    "owner": "Team Lead"
  },
  "financials": {
    "currency": "",
    "unit": "",
    "periods": [],
    "revenue": [],
    "net_income": [],
    "operating_cash_flow": [],
    "free_cash_flow": [],
    "debt": [],
    "equity": [],
    "source_refs": []
  },
  "valuation": {
    "price": null,
    "shares_outstanding": null,
    "market_cap_checked": null,
    "pe": null,
    "pb": null,
    "dividend_yield": null,
    "source_refs": []
  },
  "business_segments": [],
  "management_and_governance": [],
  "industry_and_competition": [],
  "risks_and_counterevidence": [],
  "tool_outputs": [],
  "known_gaps": []
}
```

`source-index.md` 模板：

```markdown
# {公司名} 来源索引

| ref | 来源 | 标题 | 日期 | 链接/路径 | _source | 用途 | 可信度 |
|---|---|---|---|---|---|---|---|
| S1 | 年报 |  |  |  | web | 财务口径核对 | 高 |

## 反证材料

- 

## 已知缺口

- 
```

## 2. 财报分析

推荐路径：

- `reports/{公司名}/{公司名}-{期间}-earnings-source-pack.md`

模板：

```markdown
# {公司名} {期间} 财报 Source Pack

## 基本信息

- 公司：
- 期间：
- 发布日期：
- 报告币种与单位：
- Team Lead 抓取日期：

## 一手材料

| ref | 材料 | 日期 | 链接/路径 | _source | 备注 |
|---|---|---|---|---|---|
| E1 | 财报原文 |  |  | web |  |
| E2 | 业绩会纪要 |  |  | mx-search |  |

## 关键数字

| 指标 | 本期 | 同比 | 环比 | 口径 | ref | 核验状态 |
|---|---:|---:|---:|---|---|---|
| 收入 |  |  |  |  |  |  |
| 归母净利润 |  |  |  |  |  |  |
| 自由现金流 |  |  |  |  |  |  |

## 市场反应

| 指标 | 数值 | 日期 | ref | _source |
|---|---:|---|---|---|
| 发布日涨跌幅 |  |  |  | mx-data |

## 管理层解释

- 

## 反证与风险

- 

## 已知缺口

- 
```

## 3. 未上市公司研究

推荐路径：

- `reports/{公司名}/{公司名}-private-source-pack-{YYYYMMDD}.md`

模板：

```markdown
# {公司名} Private Source Pack

## 研究对象

- 公司：
- 法域/总部：
- 业务边界：
- 研究日期：

## 来源索引

| ref | 来源类型 | 标题 | 日期 | 链接/路径 | _source | 可信度 |
|---|---|---|---|---|---|---|
| P1 | 监管文件 |  |  |  | web | 高 |
| P2 | 融资新闻 |  |  |  | mx-search | 中 |

## 经营与财务拼图

| 主题 | 已知事实 | 估计/推测 | ref | 置信度 |
|---|---|---|---|---|
| 收入规模 |  |  |  |  |
| 用户规模 |  |  |  |  |
| 融资/估值 |  |  |  |  |

## 可比公司锚点

| 公司 | 指标 | 数值 | ref | _source | 可比性限制 |
|---|---|---:|---|---|---|

## 管理层与治理

- 

## 反证与争议

- 

## 已知缺口

- 
```

## 4. 新闻异动

推荐路径：

- `reports/{公司名}/{公司名}-news-source-pack-{YYYYMMDD}.md`

模板：

```markdown
# {公司名} News Source Pack

## 异动摘要

- 公司/标的：
- 观察窗口：
- 股价/成交额/资金流变化：
- Team Lead 取数时间：

## 结构化异动

| 指标 | 数值 | 日期/区间 | ref | _source |
|---|---:|---|---|---|
| 涨跌幅 |  |  |  | mx-data |
| 成交额 |  |  |  | mx-data |

## 事件时间线

| 时间 | 事件 | ref | _source | 可靠性 |
|---|---|---|---|---|

## 四维归因材料

### 公司自身

- 

### 行业/监管

- 

### 竞争格局

- 

### 市场资金/情绪

- 

## 反证材料

- 

## 已知缺口与补数请求

- 
```

## 5. 微信公众号文章

推荐路径：

- `reports/{主题或公司}/article-source-pack-{YYYYMMDD}.md`

模板：

```markdown
# {主题} Article Source Pack

## 文章目标

- 主题：
- 目标读者：
- 核心问题：
- 输出形式：

## 素材索引

| ref | 素材类型 | 标题/说明 | 日期 | 链接/路径 | _source | 可用位置 |
|---|---|---|---|---|---|---|
| A1 | 数据 |  |  |  | lixinger | 图表 |
| A2 | 资讯 |  |  |  | mx-search | 正文 |

## 核心事实卡片

| 事实 | 数值/描述 | ref | 是否已交叉验证 |
|---|---|---|---|

## 图表与配图清单

| 图号 | 内容 | 数据来源 | 文件路径 | 备注 |
|---|---|---|---|---|

## 叙事主线

- 开头钩子：
- 核心冲突：
- 关键证据：
- 反面论据：
- 结尾落点：

## 审稿关注点

- 事实风险：
- 表述风险：
- 读者可能反驳：

## 已知缺口

- 
```

