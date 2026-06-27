# 理杏仁 API 取数升级规划（含妙想分工）

> **状态**：规划阶段（待审核）  
> **创建日期**：2026-06-27  
> **依赖**：
> - 理杏仁 Open API v1.22.25（文档快照 2026-05-15）
> - 东方财富妙想 Skills Hub API（`mkapi2.dfcfs.com`，已集成在 uzi-skill v3.13.0）  
> **API Key**：理杏仁 token + 妙想 MX_APIKEY 均已在本机配置，可直接用于开发测试  

---

## 目录

1. [取数功能遍历与取代分析](#1-取数功能遍历与取代分析)
2. [理杏仁 × 妙想：三条管道与分工](#2-理杏仁--妙想三条管道与分工)
3. [源头项目兼容性设计](#3-源头项目兼容性设计)
4. [架构设计](#4-架构设计)
5. [分阶段实施计划](#5-分阶段实施计划)
6. [风险评估与缓解](#6-风险评估与缓解)
7. [附录：理杏仁 API 能力速查](#7-附录理杏仁-api-能力速查)

---

## 1. 取数功能遍历与取代分析

### 1.1 自动化脚本工具

#### 1.1.1 `tools/ashare_data.py` — A 股数据工具 ⭐ 最高优先级

| # | 功能 | 当前来源 | 当前 API | 理杏仁替代 | 可行性 |
|---|------|---------|---------|-----------|--------|
| 1 | **每日行情与估值** (quote) | 腾讯行情 | `qt.gtimg.cn/q=sh601336` | `cn/company/fundamental/non_financial` (sp/mc/pe_ttm/pb) + `cn/company/candlestick` (最新日K线) | ✅ **日频数据完全取代**；⚠️ 日内实时 tick（当前价/涨跌幅/成交额）理杏仁不提供，仍保留腾讯行情补充 |
| 2 | **核心财务** (financials) | 东方财富 DataCenter | `datacenter.eastmoney.com/securities/api/data/get` | `cn/company/fs/{non_financial\|bank\|insurance\|security}` — 按财报类型自动选择 | ✅ **完全取代**（数据更精确，字段更多） |
| 3 | **估值指标** (valuation) | 腾讯行情 | `qt.gtimg.cn/q=sh601336` | `cn/company/fundamental/non_financial` — PE-TTM/PB/PS-TTM/股息率/市值/分位点 | ✅ **完全取代**（增加历史分位点） |
| 4 | **股票搜索** (search) | 东方财富搜索 | `searchadapter.eastmoney.com/api/suggest/get` | `cn/company` — 获取全量A股列表后本地搜索（内存级，毫秒延迟） | ⚠️ **可取代**（需本地实现搜索逻辑） |

**取代收益**：
- 腾讯行情 API 返回 GBK 编码，解码不稳定 → 理杏仁返回 UTF-8 JSON
- 东方财富保险行业报表不可用（9501错误）→ 理杏仁有 `insurance` 专用财报类型（357字段）
- 一次 API 调用可同时获取每日估值 + 历史分位点（而非多次调用）
- 支持 5 种金融行业类型的财报自动适配
- ⚠️ 日内实时数据（当前价、涨跌幅、换手率）理杏仁不提供，腾讯行情仍作为 tick 级数据补充

**注意事项**：
- 腾讯 API 无需鉴权、零依赖 → 理杏仁需 token
- 理杏仁每分钟 1000 次限制，需添加本地缓存（1分钟内重复查询走缓存）
- 理杏仁 fundamental 端点的 sp（股价）是上一交易日收盘价，非实时价

---

#### 1.1.2 `tools/morningstar_fair_value.py` — 美股公允价值筛选

| # | 功能 | 当前来源 | 理杏仁替代 | 可行性 |
|---|------|---------|-----------|--------|
| 5 | 美股公允价值筛选 | Morningstar Screener API | ❌ 理杏仁**不支持美股公司级数据**（仅指数级） | ❌ **无法取代** |

**结论**：保留现有 Morningstar API。理杏仁可补充美股指数估值数据作为参考。

---

#### 1.1.3 `tools/momentum_backtest.py` — 美股动量回测

| # | 功能 | 当前来源 | 理杏仁替代 | 可行性 |
|---|------|---------|-----------|--------|
| 6 | 美股日线数据（NVDA/AMD/MU） | Yahoo Finance Chart API | ❌ 不支持美股公司级 | ❌ **无法取代** |

**结论**：保留 Yahoo Finance。理杏仁可提供 `us/index/candlestick` 作为美股大盘指数对照。

---

#### 1.1.4 `tools/stock_screener.py` — 多市场动量扫描

| # | 功能 | 当前来源 | 理杏仁替代 | 可行性 |
|---|------|---------|-----------|--------|
| 7 | 美股日线数据 | Yahoo Finance | ❌ 不支持美股公司级 | ❌ **无法取代** |
| 8 | 港股日线数据 | Yahoo Finance | `hk/company/candlestick` — 含量/价/换手率，支持复权 | ✅ **完全取代港股部分** |
| 9 | A股日线数据 | （未实现，注释标注"需要不同数据源"） | `cn/company/candlestick` — 含量/价/换手率，支持 4 种复权 | ✅ **新增强大** |

**取代收益（港股+A股部分）**：
- 港股 watchlist 批量获取 K 线，单次 API 调用支持多股票
- A 股动量扫描从未实现（因为 YF 不支持 A 股），理杏仁可直接填补

---

#### 1.1.5 `tools/momentum_backtest_v2.py` — 动量回测 v2

| # | 功能 | 当前来源 | 理杏仁替代 | 可行性 |
|---|------|---------|-----------|--------|
| 10 | 美股价格数据 | 硬编码数组 + 本地 JSON | ❌ 不支持美股公司级 | ❌ **无法取代** |

**结论**：v2 已放弃实时抓取，转为本地数据。保持不变。

---

#### 1.1.6 `tools/xueqiu_scraper.py` — 雪球内容爬虫

| # | 功能 | 当前来源 | 理杏仁替代 | 可行性 |
|---|------|---------|-----------|--------|
| 11 | 雪球用户时间线 | 雪球 API（Playwright） | ❌ 理杏仁不提供社交/社区内容 | ❌ **无法取代** |

**结论**：保留现有雪球爬虫。

---

### 1.2 数据获取规范文档

#### 1.2.1 `skills/financial-data.md` — 财务数据获取规范

| # | 市场 | 当前主源 | 当前副源 | 理杏仁替代方案 | 可行性 |
|---|------|---------|---------|--------------|--------|
| 12 | **A股** | eastmoney.com | cninfo.com.cn | `cn/company/fs/*`（主源）+ `cn/company/fundamental/*`（估值） — 理杏仁取代两个源 | ✅ **完全取代** |
| 13 | **港股** | aastocks.com | macrotrends ADR | `hk/company/fs/*`（主源）+ `hk/company/fundamental/*`（估值） — 理杏仁取代两个源 | ✅ **完全取代** |
| 14 | **美股** | macrotrends.net | stockanalysis.com | ❌ 不支持美股公司级 | ❌ **保留现有** |

**新规范设计**：将 financial-data.md 改造为三级数据源体系：
```
优先级 1（首选）：理杏仁 API（A股+港股全覆盖）
优先级 2（后备）：现有数据源（东方财富/腾讯/aastocks/macrotrends）
优先级 3（人工）：年报PDF/交易所原文
```

---

### 1.3 验证/审计工具

#### 1.3.1 `tools/report_audit.py` — 报告数据抽检

| # | 功能 | 当前核验源 | 理杏仁替代 | 可行性 |
|---|------|----------|-----------|--------|
| 15 | A股数据抽检 | eastmoney + cninfo | `cn/company/fs/*` + `cn/company/fundamental/*` | ✅ **新增为首选核验源** |
| 16 | 港股数据抽检 | aastocks + macrotrends | `hk/company/fs/*` + `hk/company/fundamental/*` | ✅ **新增为首选核验源** |
| 17 | 美股数据抽检 | macrotrends + stockanalysis | ❌ 不支持 | ❌ **保留现有** |

---

#### 1.3.2 `tools/financial_rigor.py` — 金融严谨性工具

| # | 功能 | 当前模式 | 理杏仁集成 | 可行性 |
|---|------|---------|-----------|--------|
| 18 | 市值验算 | 手动传参 | 自动从理杏仁获取总股本+股价验算 | ✅ **新增自动化模式** |
| 19 | 多源交叉验证 | 手动传参 | 理杏仁数据作为第二源参与交叉验证 | ✅ **增强验证能力** |
| 20 | 估值指标验算 | 手动传参 | 从理杏仁获取 PE/PB/ROE/FCF 等自动验算 | ✅ **新增自动化模式** |
| 21 | 三情景估值 | 手动传参 | 理杏仁历史分位点数据用于情景参数设定 | ✅ **增强参数合理性** |

---

### 1.4 Skills 中新增取数能力（当前不存在，理杏仁可提供）

以下数据当前项目**无自动化取数渠道**（部分可通过 WebSearch/WebFetch 手动获取但效率低），理杏仁可填补空白：

| # | 新增能力 | 理杏仁 API | 应用场景 |
|---|---------|-----------|---------|
| 22 | **保险行业财务报表**（357字段） | `cn/company/fs/insurance` | investment-research 对保险公司的深度分析。⚠️ **需验证**：内含价值(EV)和新业务价值(NBV)属于精算披露而非通用会计准则科目，可能不在标准财务报表中。若理杏仁 insurance 报表不含 EV/NBV，这些仍需从年报原文获取 |
| 23 | **银行行业财务报表** | `cn/company/fs/bank` | 银行股研究 |
| 24 | **证券行业财务报表** | `cn/company/fs/security` | 券商股研究 |
| 25 | **A股前十大股东** | `cn/company/majority-shareholders` | 股东结构分析 |
| 26 | **A股股东人数变化** | `cn/company/shareholders-num` | 筹码集中度分析 |
| 27 | **A股营收构成**（分产品/分地区） | `cn/company/operation-revenue-constitution` | 分部估值分析 |
| 28 | **A股分红记录** | `cn/company/dividend` | 股息率历史分析 |
| 29 | **港股前十大股东** | `hk/company/latest-shareholders` | 港股股东分析 |
| 30 | **估值历史分位点**（PE/PB 的上市以来/10年/5年/3年分位） | `cn/company/fundamental/non_financial`（统计指标） | 估值合理性判断 |
| 31 | **A股高管增减持** | `cn/company/senior-executive-shares-change` | 管理层信心信号 |
| 32 | **A股融资融券** | `cn/company/margin-trading-and-securities-lending` | 市场情绪指标 |
| 33 | **A股陆股通持仓** | `cn/company/mutual-market` | 外资流向跟踪 |
| 34 | **A股龙虎榜** | `cn/company/trading-abnormal` | 游资行为分析 |
| 35 | **宏观经济数据**（利率/CPI/PMI/社融等） | `macro/*`（36个API） | 宏观背景分析 |
| 36 | **大盘指数估值**（沪深300/恒生 PE/PB分位） | `cn/index/fundamental` + `hk/index/fundamental` | 市场整体估值判断 |
| 37 | **行业估值数据** | `cn/industry/fs/*` + `cn/industry/fundamental/*` | 行业相对估值 |

---

### 1.5 取代可行性汇总

```
总取数功能数：37（含现有18 + 新增19）
  ✅ 完全可取代：15（40.5%）
     — ashare_data.py 全部4个功能
     — financial-data.md A股+港股 2个数据源
     — stock_screener.py 港股+A股 2个功能
     — report_audit.py A股+港股 2个核验源
     — financial_rigor.py 5个增强功能

  ❌ 无法取代：6（16.2%）
     — 美股公司级数据 x4（morningstar_fair_value, momentum_backtest, stock_screener美股, momentum_backtest_v2）
     — 雪球社区内容 x1（xueqiu_scraper）
     — report_audit美股核验 x1

  🆕 新增能力：16（43.2%）
     — 保险/银行/证券专项财报、股东分析、估值分位、宏观数据等
```

**结论**：理杏仁可取代约 **71%（15/21）** 的非美股非社交取数功能，同时新增 16 项当前无自动化取数渠道的数据能力。

---

## 2. 理杏仁 × 妙想：三条管道与分工

> **核心原则：理杏仁第一顺位，妙想第二顺位。**
>
> 理杏仁提供结构化、可编码、可回测的精确金融数据，是量化分析和投资研究的首选数据源。
> 妙想提供 NLP 便捷查询、实时行情、金融资讯和选股筛选，作为辅助数据源和特定场景（资讯/筛选/模拟交易）的唯一来源。
> 现有免费源（腾讯/东财/Yahoo）作为兜底后备，在理杏仁和妙想均不可用时启用。
>
> **优先级链**：`理杏仁 → 妙想 → 现有免费源 → 人工(WebSearch/年报)`

### 2.1 三条管道总览

| 管道 | 顺位 | 覆盖市场 | 强项 | 弱项 | 失效时动作 |
|------|------|---------|------|------|-----------|
| **理杏仁** Open API | **第 1 顺位** | A股 + 港股 + 美股指数 + 宏观 | 结构化精确数据（409字段）、估值分位点、金融专属报表、宏观36端点 | 不支持美股公司级、无NLP、无tick行情 | → 降级到妙想 |
| **妙想 6 技能** | **第 2 顺位** | A股（全线）+ 港股（数据+搜索）+ 美股（搜索） | NLP自然语言、实时tick行情、金融资讯、多条件选股、模拟交易 | 非结构化返回、无分位点、港股弱于A股 | → 降级到免费源 |
| **现有免费源**（腾讯/东财/Yahoo/Morningstar） | **第 3 顺位**（兜底） | A股 + 港股 + 美股 | 免费、美股全覆盖、无需token | 反爬风险、GBK编码、保险报表不可用 | → 降级到人工 |

### 2.2 理杏仁 vs 妙想 6 技能：完整分工矩阵

> **关键纠正**：之前基于 `uzi-skill` 中的 `mx_api.py`（仅暴露了 `query` + `news_search` + `fetch_snapshot` + `resolve_entity` 四个精简接口）评估妙想能力，严重低估了其覆盖范围。安装完整 6 个技能后，发现 **mx-data 几乎覆盖了理杏仁的所有数据维度**（区别在于精度而非覆盖度），而 mx-xuangu 提供了理杏仁不具备的筛选能力。

#### 2.2.1 数据维度逐一对比

| 数据维度 | 理杏仁 | mx-data | mx-search | mx-xuangu | 首选 | 理由 |
|---------|--------|---------|-----------|-----------|------|------|
| **结构化财报**（利润表/BS/CF） | ✅ 409字段，5种财报类型，精确编码 | ✅ NLP查询，"近三年净利润 营业收入" | ❌ | ❌ | **理杏仁** | 精度差异：理杏仁返回 `ps.npatoshopc=11.63元`，mx-data 返回自然语言表格。量化分析必须精确编码 |
| **保险/银行/证券专属财报** | ✅ insurance/bank/security 各300+字段 | ⚠️ NLP可查，但保险字段可能不全 | ❌ | ❌ | **理杏仁** | 保险EV/NBV等精算概念，NLP不一定能准确理解 |
| **历史K线**（日/周/月） | ✅ 最多10年，4种复权 | ✅ "近一年每个交易日开盘价收盘价成交量" | ❌ | ❌ | **理杏仁** | 理杏仁返回标准化OHLCV数组；mx-data 返回Excel表格。回测用理杏仁更方便 |
| **实时行情**（tick级） | ❌ 仅日频收盘估值 | ✅ "最新价、涨跌幅、主力资金流向" | ❌ | ❌ | **mx-data** | 理杏仁不提供tick数据。mx-data是唯一tick来源 |
| **估值指标**（PE/PB/PS） | ✅ 当前值 + 分位点 | ✅ 当前值（NLP查询） | ❌ | ✅ 可作为筛选条件 | **两者互补** | 当前值：mx-data方便；分位点：理杏仁独有 |
| **估值分位点**（6时间维×8统计） | ✅ 独有 | ❌ 不提供 | ❌ | ❌ | **理杏仁唯一** | 这是区分"便宜"和"价值陷阱"的关键 |
| **股东结构**（前十大/基金持股） | ✅ 结构化，含变动历史 | ✅ "贵州茅台十大股东" | ❌ | ❌ | **两者互补** | 理杏仁有变动历史；mx-data当前快照 |
| **股东人数变化** | ✅ 含变化比例 | ⚠️ 不确定 | ❌ | ❌ | **理杏仁** | |
| **高管增减持** | ✅ 详细记录 | ⚠️ 不确定 | ❌ | ❌ | **理杏仁** | |
| **大股东增减持** | ✅ 含均价 | ⚠️ 不确定 | ❌ | ❌ | **理杏仁** | |
| **营收构成**（分产品/地区） | ✅ 结构化 | ⚠️ NLP可能返回 | ❌ | ❌ | **理杏仁** | |
| **公司概况**（董事长/主营/注册资本） | ✅ profile API | ✅ "董事长是谁 总股本多少" | ❌ | ❌ | **mx-data** | 更方便，自然语言即可 |
| **板块/指数行情** | ✅ 含分位点 | ✅ "沪深300最新点位 涨跌幅" | ❌ | ✅ "白酒板块成分股" | **两者互补** | mx-data 用来看点位；理杏仁用来看分位 |
| **行业成分股** | ✅ 3种行业分类 | ❌ | ❌ | ✅ "白酒板块成分股" | **mx-xuangu** | 理杏仁有行业但需API调用；mx-xuangu更直观 |
| **宏观数据**（利率/CPI/PMI） | ✅ 36个API | ⚠️ 不确定覆盖面 | ❌ | ❌ | **理杏仁** | 36个专用端点覆盖面极广 |
| **融资融券/陆股通** | ✅ 结构化 | ✅ "主力资金流向" | ❌ | ❌ | **两者互补** | 不同角度 |
| **龙虎榜** | ✅ 结构化 | ⚠️ 不确定 | ❌ | ❌ | **理杏仁** | |
| **分红记录** | ✅ 含除权日/到账日 | ⚠️ 不确定 | ❌ | ❌ | **理杏仁** | |
| **新闻/公告/研报** | ❌ | ❌ | ✅ 金融信源智能筛选 | ❌ | **mx-search** | **唯一来源**，替代WebSearch |
| **多条件选股** | ❌ | ❌ | ❌ | ✅ "PE<20且ROE>15%且股息率>3%的银行股" | **mx-xuangu** | **独有能力** |
| **股票名称模糊搜索** | ❌ | ✅ 内建NLP | ✅ 内建NLP | ✅ 内建NLP | **mx-*** | 所有mx技能天然支持 |
| **模拟交易** | ❌ | ❌ | ❌ | ❌ | **mx-moni** | 独立工作流 |
| **社区运营** | ❌ | ❌ | ❌ | ❌ | **mx-poster** | 独立工作流 |
| **自选股管理** | ❌ | ❌ | ❌ | ❌ | **mx-zixuan** | 独立工作流 |

#### 2.2.2 核心结论：精度 vs 便捷

```
mx-data ≈ 理杏仁 在"覆盖范围"上（大部分维度两者都能查到）
理杏仁 ≫ mx-data 在"数据精度"上（结构化编码 vs NLP解释）
mx-data ≫ 理杏仁 在"查询便捷性"上（自然语言 vs API参数）
mx-xuangu = 独特能力（选股筛选，两者都不提供）
mx-search = 独特能力（金融资讯搜索，两者都不提供）
```

**使用规则**：
- 需要精确数值、历史序列、分位点、回测 → **理杏仁**
- 需要快速查询、自然语言、实时行情、即席探索 → **mx-data**
- 需要资讯研究、事件归因、政策解读 → **mx-search**
- 需要全市场筛选、条件选股 → **mx-xuangu**
- 关键数据交叉验证 → 理杏仁 + mx-data 双重取值比对

### 2.3 回退链设计（理杏仁 → 妙想 → 免费源）

所有取数操作遵循统一的降级链。如果理杏仁可用，优先使用理杏仁；理杏仁不可用时降级到妙想；再不可用降级到免费源。

```
═══════════════════════════════════════════════════════════
                    统一优先级链
═══════════════════════════════════════════════════════════

取数操作
  │
  ├─ 第1顺位：理杏仁 API ─── 成功 → 返回（标注 source: lixinger）
  │   │
  │   └─ 失败（超时/429/token过期）
  │       │
  │       └─ 第2顺位：妙想 skill ─── 成功 → 返回（标注 source: mx-*）
  │           │
  │           └─ 失败
  │               │
  │               └─ 第3顺位：现有免费源 ─── 成功 → 返回（标注 source: legacy）
  │                   │
  │                   └─ 失败 → 返回错误 + 提示人工获取
  │
  └─ 例外场景（妙想独有能力，理杏仁不提供）：
      ├─ 📰 金融资讯/新闻/公告  → mx-search 直接调用（无降级必要）
      ├─ 🔍 多条件选股筛选      → mx-xuangu 直接调用
      ├─ 💰 模拟交易            → mx-moni 直接调用
      ├─ 📝 社区内容运营        → mx-poster 直接调用
      └─ 📋 自选股管理          → mx-zixuan 直接调用
```

**各场景路由详表**：

| 场景 | 第1顺位 | 第2顺位 | 第3顺位 | 备注 |
|------|--------|--------|--------|------|
| 结构化财报（非金融） | 理杏仁 `cn/company/fs/non_financial` | mx-data NLP 查询 | 东财 DataCenter | 理杏仁精度最高 |
| 保险/银行/证券财报 | 理杏仁 `cn/company/fs/insurance` | mx-data NLP（可能不全） | — | mx-data 保险字段覆盖未知 |
| 历史 K 线 | 理杏仁 `cn/company/candlestick` | mx-data "近N年交易日数据" | 腾讯 qt.gtimg.cn | 理杏仁返回数组，回测方便 |
| 实时行情（tick） | mx-data "最新价 涨跌幅 资金流向" | 腾讯 qt.gtimg.cn | — | **mx-data 是此处第1顺位**（理杏仁不提供 tick） |
| 估值分位点 | 理杏仁（独有） | — | 手工（mx-data取历史+自行排序） | 无降级方案 |
| 股东结构 + 变化 | 理杏仁 `majority-shareholders` | mx-data "十大股东" | — | 理杏仁有变动历史 |
| 公司概况 | 理杏仁 `company/profile` | mx-data "董事长 总股本" | 东财 F10 | |
| 宏观数据 | 理杏仁 `macro/*` | mx-search 宏观解读 | WebSearch | |
| 行业/指数估值 | 理杏仁 `index/fundamental` | mx-data "沪深300最新点位" | 腾讯行情 | |
| 龙虎榜/两融/陆股通 | 理杏仁 | mx-data（部分） | 东财 data 子域 | |
| 金融资讯/公告/研报 | mx-search | WebSearch | — | **mx-search 独有** |
| 多条件选股 | mx-xuangu | 理杏仁手动筛选 | WebSearch | **mx-xuangu 独有** |

### 2.4 交叉验证设计

对于关键估值数据（PE/PB/市值），最多可有 4 条管道同时取值交叉验证：

```
理杏仁 fundamental → PE_ttm_a（精确编码，最可信）
mx-data NLP查询   → PE_ttm_b（东方财富底层，实时性可能更高）
腾讯 qt            → PE_ttm_c（免费，实时tick）
现有东财 DataCenter → PE_ttm_d（备用）

采纳优先级：理杏仁 > mx-data > 腾讯 > 东财DataCenter
差异阈值：max(P) - min(P) / median > 1% → 标记为"多源差异"，调查原因
```

### 2.5 妙想的两层存在形式

妙想在本系统中以**两层**形式存在：

| 层级 | 位置 | 形式 | 用途 |
|------|------|------|------|
| **Claude Code Skill 层** | `~/.claude/skills/mx-*/` | 6 个独立 SKILL.md + Python 脚本 | 通过 `/mx-data`、`/mx-search` 等 slash 命令交互式调用 |
| **uzi-skill SDK 层** | `~/.claude/local-plugins/uzi-skill/` | `mx_api.py` Python客户端 | 被 `stock-deep-analyzer` 插件以代码方式集成，走并行竞速数据管道 |

**对 ai-berkshire 的影响**：
- ai-berkshire 的 Skills（如 investment-research）可以通过 Bash 调用 mx-* 的 Python 脚本获取数据
- mx-* 脚本的输出格式（Excel/CSV/JSON）可以直接被后续分析流程消费
- 无需依赖 uzi-skill，两个层级可以独立使用

---

## 3. 源头项目兼容性设计

### 3.1 核心原则

```
源头仓库: xbtlin/ai-berkshire（GitHub）
本仓库:   （fork，不向上游贡献代码，但可能抓取上游更新）
```

**兼容性要求**：
1. 新增理杏仁模块作为**可选增强**，不修改/删除现有工具的核心逻辑
2. 现有工具的 CLI 接口保持不变，上游更新可直接合并
3. 理杏仁功能通过独立模块和配置文件注入，不与现有代码耦合

### 3.2 文件隔离策略

```
现有文件（保持兼容）:
  tools/ashare_data.py          → 不修改核心逻辑，仅新增 --source lixinger 选项
  tools/financial_rigor.py      → 不修改现有函数签名，新增 lixinger_* wrapper
  tools/report_audit.py         → 不修改（理杏仁数据通过新增的核验函数注入，无需改动 report_audit.py 本身）
  skills/financial-data.md      → 不删除现有内容，新增"理杏仁优先"章节
  CLAUDE.md                     → 不修改

新增文件（独立模块，不干扰上游）:
  tools/lxr_client.py           → 理杏仁 API 客户端（核心模块）
  tools/lxr_data.py             → 面向 Skill 的高级数据接口
  tools/lxr_config.json         → API 配置（token 不提交 git）
  tools/lxr_config.example.json → 配置模板（可提交）
  tools/lxr_cache.py            → 本地缓存层（降低 API 调用频率）
  tests/test_lxr_client.py      → 单元测试
```

**Git 策略**：
- `lxr_config.json` → `.gitignore` 中排除（含 API token）
- `lxr_config.example.json` → 提交（模板，token 字段留空）
- 新文件独立存放，上游合并时可 `git cherry-pick` 选择性地保留

**codex/ 副本目录**：项目存在 `codex/ai-berkshire/scripts/tools/`（与 `tools/` 并行）。现有 `ashare_data.py` 等工具在此有副本。新增的 `lxr_*` 模块也应在 `codex/` 目录放置副本，保持与现有工具副本策略一致。在阶段 6 的 P6.3 中执行。

### 3.3 接口设计：数据源抽象层

所有理杏仁新增功能通过统一抽象层暴露，Skills 不直接调用 API：

```
                     ┌──────────────────┐
 Skills / CLI 调用    │  lxr_data.py     │  ← 面向业务的简洁接口
                     │  get_financials() │
                     │  get_valuation()  │
                     │  get_shareholders│
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                      │  lxr_client.py   │  ← 通用 HTTP 客户端
                      │  post(endpoint)  │     处理 token/错误/限流/重试
                      └────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                      │  lxr_cache.py     │  ← 本地缓存
                      │  (TTL 60s)        │     减少重复 API 调用
                      └──────────────────┘
```

**数据源选择逻辑**（每个取数操作的回退链）：

```
1. 理杏仁 API  →  成功 → 返回
2. 理杏仁 API  →  失败 → 打印警告 → fallback 到原有数据源
3. 原有数据源  →  成功 → 返回（标注数据来源）
4. 原有数据源  →  失败 → 返回错误 + 数据缺失标记
```

### 3.4 上游合并冲突预案

| 场景 | 风险评估 | 处理方案 |
|------|---------|---------|
| 上游更新 `ashare_data.py` | 低 — 我们仅新增 `--source` 选项，不改变核心函数 | `git merge` 自动合并或手动合并新功能 |
| 上游更新 `financial-data.md` | 低 — 我们仅在末尾追加"理杏仁优先"章节 | 手动合并 |
| 上游新增数据源工具 | 低 — 我们的新文件独立存放 | 无冲突 |
| 上游删除/重构 `ashare_data.py` | 中 — 如果上游完全移除 | 评估是否仍需要，fork 保留或迁移到 lxr 模块 |
| 上游将工具迁移到 `codex/` 子目录 | 低 | 关注上游动向，同步调整 |

---

## 4. 架构设计

### 4.1 模块关系图（三条管道）

```
                         ┌──────────────────────────────────┐
                         │          Skills (.md files)        │
                         │  investment-research / earnings   │
                         │  quality-screen / thesis-tracker  │
                         └──────────────┬───────────────────┘
                                        │ 通过 Bash 调用
                         ┌──────────────▼───────────────────┐
                         │  lxr_data.py  (高级数据接口)       │
                         │  - get_company_financials()      │
                         │  - get_valuation_with_percentile │
                         │  - get_shareholder_structure()   │
                         │  - get_industry_comparison()      │
                         │  - search_news() → 妙想 mx-search│
                         └──────┬────────┬──────────────────┘
                                │        │
         ┌──────────────────────┤        ├──────────────────┐
         │ 第1顺位 (优先)        │        │  第2顺位 (降级)    │
         ▼                      │        ▼                  │
  ┌──────────────┐              │  ┌──────────────────────┐ │
  │ 理杏仁         │              │  │ 妙想 6 Skills         │ │
  │ lxr_client.py │              │  │ mx-data (NLP查询)     │ │
  │ ● 结构化财报   │              │  │ mx-search (资讯)      │ │
  │ ● 估值分位点   │              │  │ mx-xuangu (选股)      │ │
  │ ● 金融专属报表 │              │  │ mx-moni (模拟交易)    │ │
  │ ● 股东/治理    │              │  │ mx-poster (社区)      │ │
  │ ● 宏观/指数    │              │  │ mx-zixuan (自选)      │ │
  └──────┬───────┘              │  └──────────┬───────────┘ │
         │                      │             │              │
         │      失败降级 ────────┼────────────►│              │
         │                      │             │              │
         │             失败降级 ─┼─────────────┼──────┐       │
         │                      │             │      ▼       │
         │                      │  第3顺位 (兜底)             │
         │                      │  腾讯 / 东财 / Yahoo        │
         │                      └────────────────────────────┘
         │
         └─────────── 成功 → 返回 (标注 source: lixinger) ──────►
                     失败 → 降级第2顺位 → 返回 (标注 source: mx-*)
                     失败 → 降级第3顺位 → 返回 (标注 source: legacy)
```
          ├─ tools/financial_rigor.py (新增 lxr_* wrapper)  │
          ├─ tools/report_audit.py  (保留)                  │
          ├─ tools/stock_screener.py (港股/A股新增 lixinger) │
          ├─ tools/morningstar_fair_value.py (保留, 美股)    │
          ├─ tools/xueqiu_scraper.py (保留, 社区内容)        │
          └─ 腾讯 qt / 东财 / Yahoo (保留作为三层 fallback)  │
```

### 4.2 数据源回退链（理杏仁 → 妙想 → 免费源）

```python
# lxr_data.py 中的回退逻辑（概念）

def get_financials(code: str, years: int) -> dict:
    """
    统一取数入口，遵循 理杏仁 → 妙想 → 免费源 降级链。
    返回 dict 中必含 `_source` 字段标注实际来源。
    """

    # 第 1 顺位：理杏仁
    try:
        result = _get_from_lixinger(code, years)
        result["_source"] = "lixinger"
        return result
    except LixingerError as e:
        print(f"[降级] 理杏仁不可用 ({e}) → 尝试妙想")

    # 第 2 顺位：妙想 mx-data
    try:
        result = _get_from_mx_data(code, years)
        result["_source"] = "mx-data"
        return result
    except MXError as e:
        print(f"[降级] 妙想不可用 ({e}) → 尝试免费源")

    # 第 3 顺位：现有免费源（兜底）
    try:
        result = _get_from_legacy_source(code, years)
        result["_source"] = "legacy"
        return result
    except LegacyError as e:
        print(f"[错误] 全部数据源不可用: {e}")
        return {"error": str(e), "_source": "none"}
```

**例外路由**（妙想独有能力，不经过理杏仁）：

```python
def search_financial_news(query: str) -> dict:
    """金融资讯搜索 — 妙想独有，直接调用 mx-search"""
    return _call_mx_skill("mx-search", query)

def screen_stocks(conditions: str) -> dict:
    """多条件选股 — 妙想独有，直接调用 mx-xuangu"""
    return _call_mx_skill("mx-xuangu", conditions)
```

### 4.3 缓存策略

| 数据类型 | TTL | 理由 |
|---------|-----|------|
| 实时行情（股价/PE/PB） | 60 秒（仅日频估值用，非日内 tick） | 日频估值每日更新一次，60s 足以去重 |
| K 线历史数据 | 1 小时 | 日线数据当天不变 |
| 财务报表数据 | 24 小时 | 财报发布频率低（季度/年度） |
| 股东信息 | 24 小时 | 报告期末数据，不经常变 |
| 公司基础信息 | 7 天 | 极少变更 |
| **全量公司列表** | **7 天** | 每日新增 IPO 1-2 家，7 天刷新合理 |
| 估值分位点 | 1 小时 | 每日收盘后更新一次 |
| 指数/行业数据 | 1 小时 | 每日收盘后更新 |

**缓存实现**：本地 JSON 文件，路径使用 `tempfile.gettempdir() / "lxr_cache"`（Windows 兼容），零外部依赖。

---

## 5. 分阶段实施计划

### 阶段 1：核心 API 客户端（预估 3-4 小时）

> **分支策略**：在独立分支 `feat/lixinger-p1` 上开发，准出通过后合并到 main。

**目标**：建立可工作的理杏仁 API 调用基础设施，包含缓存、回退和配置管理。

| 序号 | 任务 | 产出 | 测试方式 |
|------|------|------|---------|
| P1.1 | 创建 `tools/lxr_client.py` | HTTP POST 客户端，处理 token/限流/重试/错误 | 对 `cn/company/fs/non_financial` 发真实请求验证 |
| P1.2 | 创建 `tools/lxr_cache.py` | TTL 磁盘缓存层，使用 `tempfile.gettempdir()` 跨平台路径 | 连续两次相同请求，验证第二次走缓存 |
| P1.3 | 创建 `tools/lxr_config.json` + `tools/lxr_config.example.json` | 配置文件，token 已填入；example 模板 token 留空 | 确认 `.gitignore` 排除 `lxr_config.json` 但不排除 example |
| P1.4 | 实现三阶回退链 | `lxr_data.py` 中实现 `理杏仁 → 妙想 mx-data → 免费源` 降级逻辑 | 故意用错误 token 触发理杏仁失败，验证自动降级到妙想；再模拟妙想失败，验证降级到免费源 |
| P1.5 | 更新 `.gitignore` | 添加 `tools/lxr_config.json`，添加缓存目录 | 确认 git status 不显示 config 文件 |

**阶段 1 准出标准**：
- [ ] `lxr_client.py` 能成功获取 贵州茅台(600519) 近5年财务数据
- [ ] 缓存命中时响应时间 < 10ms
- [ ] 模拟 429 限流，验证自动重试机制

---

### 阶段 2：A 股数据全面替换（预估 3-4 小时）

**目标**：让 `ashare_data.py` 同等功能通过理杏仁运行，且数据质量更高。

| 序号 | 任务 | 产出 | 兼容性措施 |
|------|------|------|-----------|
| P2.1 | 创建 `tools/lxr_data.py` — `get_financials()` | A 股财务数据接口，支持 5 种财报类型自动适配 | 独立模块，不修改 `ashare_data.py` |
| P2.2 | 创建 `tools/lxr_data.py` — `get_valuation()` | A 股估值数据 + 历史分位点 | 新增能力，现有工具不具备 |
| P2.3 | 为 `ashare_data.py` 新增 `--source lixinger` | 让现有工具可选择理杏仁数据源 | 默认仍走东方财富/腾讯（`--source default`），不破现有行为 |
| P2.4 | 为 `financial_rigor.py` 新增 `--source lixinger` | 自动从理杏仁获取数据验算 | 独立参数，不影响现有 `--price/--shares/--reported` 手动模式 |
| P2.5 | 更新 `skills/financial-data.md` | 新增"理杏仁优先"章节，定义三级数据源 | 不删除现有内容，追加在新章节 |

| P2.6 | 运行阶段验证脚本 | 对 600519 和 601336 分别运行 `lxr_data.py` 输出对比 | 现有数据与理杏仁数据偏差 < 0.5% |

**阶段 2 准出标准**：
- [ ] `ashare_data.py financials 601336 --source lixinger` 输出与现有数据一致（偏差 < 0.5%）
- [ ] `financial_rigor.py verify-market-cap 601336 --source lixinger` 自动验算通过
- [ ] 对保险股（601336）能正确获取 `insurance` 类型报表，字段数 > 50

---

### 阶段 3：港股数据替换 + 新增能力（预估 2-3 小时）

> **分支策略**：在 `feat/lixinger-p3` 上开发，基于 P2 合并后的 main。

**目标**：港股取数切换到理杏仁，并新增当前不具备的数据维度。

| 序号 | 任务 | 产出 |
|------|------|------|
| P3.1 | `lxr_data.py` — 港股财务数据接口 | `hk/company/fs/*` 封装 |
| P3.2 | `lxr_data.py` — 港股估值 + K 线 | `hk/company/fundamental` + `hk/company/candlestick` |
| P3.3 | 为 `stock_screener.py` 新增 `--source lixinger` | 港股 watchlist 动量扫描改用理杏仁 |
| P3.4 | `lxr_data.py` — 股东分析模块 | `majority-shareholders` + `shareholders-num` + `fund-shareholders`（A股+港股同步完成） |
| P3.5 | `lxr_data.py` — 估值分位点模块 | PE/PB/PS 的 6 个时间维度 × 8 种统计指标 |
| P3.6 | 运行阶段验证脚本 | 对比腾讯(00700.HK)理杏仁数据 vs Yahoo Finance 数据 |

**阶段 3 准出标准**：
- [ ] 能获取 腾讯(00700.HK) 近5年财务数据
- [ ] 港股 watchlist 动量扫描输出与现有 Yahoo Finance 结果一致
- [ ] 估值分位点查询对 600519 返回正确的历史分位数据

---

### 阶段 4：深度集成 + 保险/金融专属（预估 2 小时）

> **分支策略**：在 `feat/lixinger-p4` 上开发。

**目标**：利用理杏仁保险/银行/证券专属报表，解决本次 601336 研究中遇到的数据盲区。

| 序号 | 任务 | 产出 |
|------|------|------|
| P4.1 | **首先验证**：调用 `cn/company/fs/insurance` 对 601336 获取全量字段列表，确认 EV/NBV 是否包含 | 字段清单。若 EV/NBV 不在标准财报中，标注"仍需年报原文"，不在此模块处理 |
| P4.2 | `lxr_data.py` — 保险行业专项模块 | 基于 P4.1 验证结果，封装保险可获取的全部财务指标 |
| P4.3 | `lxr_data.py` — 银行/证券行业专项模块 | 银行（357字段）/证券（303字段）专属财务指标 |
| P4.4 | `lxr_data.py` — 营收构成模块 | `operation-revenue-constitution` 分产品/分地区收入 |
| P4.5 | `lxr_data.py` — 公司治理模块 | 高管增减持 + 大股东增减持（股东数据已在 P3.4 完成） |
| P4.6 | 运行阶段验证脚本 | 对 601336 验证保险报表完整性和治理数据准确性 |

**阶段 4 准出标准**：
- [ ] 对 601336 能列出保险行业财务报表全部可用字段（预期 > 100）
- [ ] 明确标注 EV/NBV 是否在理杏仁 insurance 报表中
- [ ] `investment-research` Skill 执行保险股研究时不再完全依赖 WebFetch 补漏

---

### 阶段 5：宏观与指数数据（预估 1-2 小时）

> **分支策略**：在 `feat/lixinger-p5` 上开发。

**目标**：为投资研究提供宏观背景和行业估值参照系。

| 序号 | 任务 | 产出 |
|------|------|------|
| P5.1 | `lxr_data.py` — 宏观模块 | GDP/CPI/利率/汇率/社融等核心宏观指标 |
| P5.2 | `lxr_data.py` — 指数估值模块 | 沪深300/恒生指数 PE/PB 分位点 |
| P5.3 | `lxr_data.py` — 行业对比模块 | 同行估值对比（PEV 等保险行业特有指标） |
| P5.4 | 运行阶段验证脚本 | 对比理杏仁宏观数据 vs 公开数据源（如人民银行/统计局）|

**阶段 5 准出标准**：
- [ ] 能获取当前 10 年期国债收益率并用于利差分析
- [ ] 能一键输出目标公司所在行业（申万二级）的估值对比表

---

### 阶段 6：文档与收尾（预估 1 小时）

> **分支策略**：在 `feat/lixinger-p6` 上开发。此为收尾阶段，不涉及核心逻辑变更。

| 序号 | 任务 | 产出 |
|------|------|------|
| P6.1 | 更新 CLAUDE.md 项目指令 | 标注理杏仁为 A 股/港股首选数据源（自动化取数），保留现有源为后备 |
| P6.2 | 编写 `tools/lxr_data.py --help` 和 Skill 调用示例 | 供 Claude Code Skills 使用的参考文档 |
| P6.3 | 检查 `codex/ai-berkshire/scripts/tools/` 目录 | 确认新增的 `lxr_*` 模块是否需要同步副本到 codex/ 目录（与现有 ashare_data.py 的副本策略一致） |

---

### 总预估时间

| 阶段 | 预估时间 | 累计 |
|------|---------|------|
| 阶段 1：核心客户端 + 缓存 + 回退 | 3-4h | 4h |
| 阶段 2：A 股替换 + 自动验证 | 3-4h | 8h |
| 阶段 3：港股 + 股东 + 分位点 | 2-3h | 11h |
| 阶段 4：保险/金融专属 + EV/NBV 验证 | 2-3h | 14h |
| 阶段 5：宏观 + 指数 + 行业对比 | 1-2h | 16h |
| 阶段 6：文档收尾 + codex 同步 | 1h | 17h |
| **总计** | **12-17h** | — |

### 分支与回滚策略

```
每个阶段在独立 feature 分支上开发：
  feat/lixinger-p1 → 准出通过 → merge to main
  feat/lixinger-p2 → 基于 main（含 P1）→ 准出通过 → merge to main
  feat/lixinger-p3 → 基于 main（含 P1+P2）→ 准出通过 → merge to main
  ...

回滚方案：
  - 单阶段回退：git revert 该阶段的 merge commit
  - 完全回退：git revert 所有 lixinger merge commit，系统回到纯原有数据源
  - 由于新模块是独立文件 + 现有工具仅新增可选参数（默认行为不变），
    即使不回滚，将 --source lixinger 参数去掉即可回到原有模式
```

---

## 6. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 理杏仁 API 服务中断 | 低 | 高 — 所有依赖理杏仁的功能不可用 | 每个取数操作保留 fallback 到原有数据源 |
| API 版本升级导致接口不兼容 | 中 | 中 — 需要更新 `lxr_client.py` | 文档中维护 `reference/` 对比，每次使用前检查更新日志 |
| Token 泄露 | 低 | 高 — 他人可能消耗你的 API 额度 | `.gitignore` 排除 `lxr_config.json`；CI 中不执行理杏仁相关测试 |
| 速率限制触发（429） | 中 | 低 — 请求被延迟 | 内置指数退避重试（1s→2s→4s→8s）+ 本地缓存减少调用 |
| 理杏仁数据与现有源不一致 | 中 | 中 — 结果矛盾 | `financial_rigor.py` 交叉验证时自动标记差异 > 1% 的数据 |
| 上游项目更新冲突 | 低 | 低 — 新文件独立存放 | 阶段性 `git cherry-pick` 上游更新 |
| 理杏仁 API 将来收费模式变化 | 低 | 高 — 可能影响可用性 | 保留现有免费数据源作为长期 fallback |
| 理杏仁字段语义与现有数据源不一致 | 中 | 中 — "净利润"等看似相同的字段可能因口径不同产生偏差 | `financial_rigor.py` 交叉验证时自动标注差异；文档中维护字段映射表 |
| Windows Python 环境兼容性 | 中 | 低 — 如 subprocess/curl 路径问题 | 新模块统一使用 `urllib.request`（纯 Python），避免 shell 调用；缓存路径使用 `tempfile` |
| 理杏仁 token 有效期 | 低 | 高 — token 过期导致全部取数失败 | P1.1 客户端启动时验证 token 有效性，失败时给出明确提示"请更新 token" |
| 全量 A 股列表数据量大 | 低 | 低 — `cn/company` 可能返回数千条 | 本地缓存 7 天；分页拉取；内存中搜索足够快 |

---

## 7. 附录：理杏仁 API 能力速查

### 7.1 关键 API 清单（本次规划涉及）

```
基础信息:
  cn/company                    — A股公司列表
  hk/company                    — 港股公司列表
  cn/company/profile            — 公司概况（董事长/总经理/注册资本等）

行情数据:
  cn/company/candlestick        — A股日K线（4种复权）
  hk/company/candlestick        — 港股日K线

财务数据:
  cn/company/fs/non_financial   — A股非金融财报（409字段）
  cn/company/fs/insurance       — A股保险财报（357字段）
  cn/company/fs/bank            — A股银行财报（357字段）
  cn/company/fs/security        — A股证券财报（303字段）
  hk/company/fs/non_financial   — 港股非金融财报（227字段）
  hk/company/fs/insurance       — 港股保险财报（198字段）

估值数据:
  cn/company/fundamental/non_financial — A股估值（53指标+历史分位）
  hk/company/fundamental/non_financial — 港股估值（35指标）

股东与治理:
  cn/company/majority-shareholders     — 前十大股东
  cn/company/shareholders-num          — 股东人数变化
  cn/company/senior-executive-shares-change — 高管增减持
  cn/company/major-shareholders-shares-change — 大股东增减持

指数与行业:
  cn/index/fundamental           — A股指数估值
  cn/industry/fs/sw/*            — 申万行业财务数据
  hk/index/fundamental           — 港股指数估值

宏观:
  macro/national-debt            — 国债收益率（中美）
  macro/interest-rates           — Shibor/LPR/MLF等67个利率指标
  macro/price-index              — CPI/PPI/PMI
  macro/gdp                      — GDP
  macro/money-supply             — M0/M1/M2
  macro/currency-exchange-rate   — 汇率
```

### 7.2 技术约束

| 约束 | 值 |
|------|-----|
| 请求方式 | 全部 POST (Content-Type: application/json) |
| 认证 | `token` 参数（每个请求必传） |
| 速率限制 | 1000次/分钟, 36次/秒 |
| 时间跨度上限 | 单次查询最多 10 年 |
| 多股票指标上限 | 批次查询最多 48 指标/股 |
| 单股票指标上限 | 单股查询最多 36 或 128 指标 |
| Accept-Encoding | 必须包含 `gzip` |

---

*规划文件版本：v1.0*  
*下一步：用户审核后，按阶段顺序执行实施*
