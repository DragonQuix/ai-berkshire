# 财务数据获取与交叉验证规范

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源；同口径结构化双源或理杏仁 vs mx-data 同指标按下方阈值标记差异。**

### 交叉验证阈值（统一，2026-06 修订）

| 场景 | ≤2% | 2%–5% | >5% |
|------|-----|-------|-----|
| **同口径结构化双源**（理杏仁 vs 东财/巨潮/aastocks/macrotrends，字段定义相同） | ✅ 一致，取主源并标注双源 | ⚠️ 标注「数据存在轻微差异」，说明可能原因（汇率/会计口径） | ❌ 标注「数据异常」，须查年报核实 |
| **理杏仁 vs mx-data NLP 同指标**（如 TTM PE，口径已确认相同） | ✅ 静默通过，优先采纳理杏仁 | ⚠️ 注明双源轻微差异，优先理杏仁 | ❌ 标「数据异常」，建议人工核查 |
| **不同口径**（NLP 提取 vs 结构化编码、TTM vs 静态 PE 等） | — | — | **不强行比较**，分别标注口径 |

> 旧版「误差>1%须标记」已废止。`financial_rigor.py cross-validate` 默认容差 2%。

---

## 数据源优先级（自动化三级体系）

自 2026-06 起，A股/港股财务与估值数据改为**自动化三级回退**获取，优先使用理杏仁 API（结构化、含估值分位点、覆盖保险/银行/证券专属报表），失败时回退妙想 Skills，再失败回退免费源。优先级与 `docs/plan-lixinger-migration.md` 一致。**能力边界实测**见 `docs/channel-capability-matrix.md`（E0 准出，含保险 EV/NBV 已确认可用）。

| 顺位 | 来源 | 能力 | 何时用 |
|------|------|------|--------|
| 1（主） | **理杏仁 API** | 结构化财务报表（非金融/保险/银行/证券四类）、估值与历史分位点（1/5/10年）、总股本/市值 | 默认。`--source lixinger` |
| 2（副） | **妙想 Skills** (`mx-data`) | 自然语言查询实时行情、财务、股东信息，输出 Excel/JSON | 理杏仁不可用/缺字段时自动回退 |
| 3（兜底） | **免费源**（东财/巨潮/aastocks/macrotrends 等，见下方表格） | 网页/API 抓取，部分保险报表不可用、GBK 乱码、无分位点 | 前两顺位均失败时兜底 |

### `_source` 字段统一标注（所有 Skill 必遵）

`tools/lxr_data.py` 及妙想 CLI 返回的 JSON **顶层**含 `_source`，报告与 Agent 输出须原样引用：

| `_source` 值 | 含义 | 典型场景 |
|-------------|------|---------|
| `lixinger` | 理杏仁 API 结构化数据 | financials、valuation、governance、quality-metrics |
| `mx-data` | 妙想 mx-data NLP 查询 | 实时行情、公司概况 |
| `mx-search` | 妙想 mx-search 资讯搜索 | 公告、采访、行业新闻 |
| `mx-xuangu` | 妙想 mx-xuangu 条件选股 | quality-screen / industry-funnel 初筛 |
| `lixinger+mx` | 数据包理杏仁+妙想均成功 | datapack（含 mx_quote + mx_news） |
| `lixinger+partial-mx` | 数据包理杏仁成功、妙想部分失败 | datapack 降级 |
| `legacy` | 免费源（东财/巨潮/WebSearch 等） | 第三顺位兜底 |
| `none` | 全部来源失败 | 须标注「数据不可用」，禁止编造 |

复合数据包（`datapack`）顶层 `_source` 反映实际组合；各 `sections.*` 子块保留各自 `_source`。

### CLI 调用方式（推荐）

```bash
# 财报数据（自动按公司类型选择报表：保险/银行/证券/非金融）
python tools/ashare_data.py financials 601336 --source lixinger
python tools/ashare_data.py financials 600519            # 默认走免费源，保持兼容

# 估值 + 历史分位点（理杏仁新增能力）
python tools/ashare_data.py valuation 600519 --source lixinger

# A股龙虎榜（东方财富免费源，经统一入口返回 JSON）
python tools/lxr_data.py lhb 600519 --limit 5 --quiet
python tools/lxr_data.py lhb-detail --trade-id 100357777 --quiet  # 买卖席位明细

# 市值/估值精确验算（自动从理杏仁取股价/股本/EPS/BVPS/分位点）
python tools/financial_rigor.py verify-market-cap 601336 --source lixinger
python tools/financial_rigor.py verify-valuation 600519 --source lixinger
python tools/financial_rigor.py verify-market-cap --price 510 --shares 9.11e9 --reported 4.65e12 --currency HKD  # 手动输入保持兼容
```

### 理杏仁配置

- token 存放于 `tools/lxr_config.json`（已 gitignore，不入库）；模板见 `tools/lxr_config.example.json`。
- 也可用环境变量 `LIXINGER_TOKEN` 覆盖。
- 缓存落盘于 `tempfile.gettempdir()/lxr_cache/`，TTL 按数据类型分级（行情类短、财报类长）。
- 速率限制 1000次/分钟、36次/秒，客户端已内置节流与 429/5xx 指数退避重试。

### 交叉验证基准（理杏仁已对齐）

理杏仁年报核心指标与东方财富 DataCenter 已做偏差验证：**600519 / 601336 近3年归母净利润、EPS 偏差 0.00%**（≤0.5% 准出通过）。理杏仁在此基础上额外提供东财缺失的**保险/银行/证券专属报表**与**估值历史分位点**。

---

## 手动交叉验证来源（兜底/对照，第三顺位）

> 当自动化链路不可用、或需要原始一手数据核对时，按下方来源手动取数。下方表格仍作为第三顺位兜底与人工对照基准保留。

### 美股（PDD、腾讯ADR、网易ADR等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **macrotrends** | macrotrends.net/stocks/charts/{ticker} | 直接访问，无需注册 |
| 2（副） | **stockanalysis** | stockanalysis.com/stocks/{ticker}/financials | 直接访问，无需注册 |
| 原始一手 | SEC EDGAR | sec.gov/cgi-bin/browse-edgar | 10-K / 10-Q 原文 |

### 港股（腾讯0700、网易9999、美团3690等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **aastocks** | aastocks.com/tc/stocks/analysis/company-fundamental | 直接访问 |
| 2（副） | **macrotrends**（ADR代码） | 腾讯用TCEHY，网易用NTES | 直接访问 |
| 原始一手 | HKEX披露易 | hkexnews.hk | 年报PDF |

### A股（三七互娱、吉比特等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **东方财富** | eastmoney.com → 搜股票代码 → 财务报表 | 直接访问 |
| 2（副） | **巨潮资讯** | cninfo.com.cn | 原始年报/季报PDF |

---

## 执行规范

### 第一步：获取数据

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

### 第二步：误差计算与标记

```
误差率 = |来源1数值 - 来源2数值| / 参考中位数 × 100%
```

按上文「交叉验证阈值」三档处理；**禁止**对口径不同的来源强行计算误差。

### 第三步：数据呈现格式

每个关键数据必须按以下格式标注：

```
收入：1,239亿元 ✅
  - macrotrends: 1,241亿元
  - stockanalysis: 1,237亿元
  - 误差: 0.3%
```

差异示例：
```
净利润：245亿元 ⚠️ 数据存在差异
  - macrotrends: 245亿元（GAAP）
  - stockanalysis: 278亿元（Non-GAAP）
  - 误差: 13.5% — 原因：会计口径不同（GAAP vs Non-GAAP）
```

---

## 常见差异原因（不一定是数据错误）

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元换算时间点不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

---

## 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 快速索引

> 自动化链路：A股/港股统一经 `--source lixinger` 走理杏仁→妙想→免费源三级回退；下表"主要来源"为该场景首选用法，"备用来源"为手动对照。

| 场景 | 主要来源 | 备用来源 |
|------|---------|---------|
| PDD / 拼多多 | macrotrends.net/stocks/charts/PDD | stockanalysis.com/stocks/pdd |
| 腾讯 | macrotrends.net/stocks/charts/TCEHY | aastocks（0700.HK） |
| 网易 | macrotrends.net/stocks/charts/NTES | aastocks（9999.HK） |
| 三七互娱 | `ashare_data.py ... --source lixinger`（理杏仁） | eastmoney.com（002555） |
| 吉比特 | `ashare_data.py ... --source lixinger`（理杏仁） | eastmoney.com（603444） |
| 保险/银行/证券 | `ashare_data.py ... --source lixinger`（理杏仁专属报表） | 妙想 mx-data / 巨潮年报PDF |
| 保险EV/NBV/偿付能力 | `lxr_data.py industry-deep 601336` | 巨潮年报PDF |
| 营收构成(分产品/地区) | `lxr_data.py revenue 600519` | 年报附注 |
| 高管/大股东增减持 | `lxr_data.py governance 601336` | 巨潮公告 |
| 10年期国债收益率(利差基准) | `lxr_data.py macro-debt --area cn` | 人民银行/中债网 |
| LPR/Shibor/MLF利率 | `lxr_data.py macro-rates --area cn` | 人民银行 |
| 指数估值(沪深300/恒生PE/PB分位) | `lxr_data.py index-val 000300 --market cn` | aastocks / mx-data |
| 申万二级行业估值对比 | `lxr_data.py industry-compare 600519` | mx-data "白酒板块估值" |
| A股龙虎榜明细 | `lxr_data.py lhb 600519 --limit 5`（东方财富免费源，`_source: legacy`） | 理杏仁 `trading-abnormal` |
| A股龙虎榜买卖席位 | `lxr_data.py lhb-detail --trade-id 100357777` 或 `lhb-detail 000004 --date 2026-06-26`（`source_detail: legacy:ashare_data/lhb-detail`） | 东方财富网页明细页 |
| **投研数据包（推荐）** | `lxr_data.py datapack 600519 --years 5`（TTL 1h） | 分拆 CLI |
| **去劣 7 指标精算** | `lxr_data.py quality-metrics 600519 --years 10` | 手算 financials |
| 妙想资讯搜索 | `lxr_data.py mx-search "{公司} 最新公告"` | 直调 mx_search.py |
| 妙想智能选股 | `lxr_data.py mx-xuangu "ROE>15%的A股"` | 直调 mx_xuangu.py |
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） |
