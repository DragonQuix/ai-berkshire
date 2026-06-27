# 财务数据获取与交叉验证规范

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源，误差>1%须标记。**

---

## 数据源优先级（自动化三级体系）

自 2026-06 起，A股/港股财务与估值数据改为**自动化三级回退**获取，优先使用理杏仁 API（结构化、含估值分位点、覆盖保险/银行/证券专属报表），失败时回退妙想 Skills，再失败回退免费源。优先级与 `docs/plan-lixinger-migration.md` 一致。

| 顺位 | 来源 | 能力 | 何时用 |
|------|------|------|--------|
| 1（主） | **理杏仁 API** | 结构化财务报表（非金融/保险/银行/证券四类）、估值与历史分位点（1/5/10年）、总股本/市值 | 默认。`--source lixinger` |
| 2（副） | **妙想 Skills** (`mx-data`) | 自然语言查询实时行情、财务、股东信息，输出 Excel/JSON | 理杏仁不可用/缺字段时自动回退 |
| 3（兜底） | **免费源**（东财/巨潮/aastocks/macrotrends 等，见下方表格） | 网页/API 抓取，部分保险报表不可用、GBK 乱码、无分位点 | 前两顺位均失败时兜底 |

### CLI 调用方式（推荐）

```bash
# 财报数据（自动按公司类型选择报表：保险/银行/证券/非金融）
python tools/ashare_data.py financials 601336 --source lixinger
python tools/ashare_data.py financials 600519            # 默认走免费源，保持兼容

# 估值 + 历史分位点（理杏仁新增能力）
python tools/ashare_data.py valuation 600519 --source lixinger

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
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差 | 处理方式 |
|------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

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
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） |
