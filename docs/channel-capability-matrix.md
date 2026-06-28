# 双渠道能力边界矩阵（E0 全验证）

> **验证日期**：2026-06-27  
> **验证环境**：Windows 11 / Python 3.12 / 理杏仁 token + MX_APIKEY 已配置  
> **测试样本**：600519（茅台）、601336（新华保险）、600036（招行）、002594（比亚迪）、00700（腾讯）  
> **验证脚本**：`tools/verify_channel_capability.py`（最小复验）；历史快照 `temp_e0_verify.py` 已删除。

---

## 执行摘要

| 维度 | 结论 | 对技能增强的影响 |
|------|------|----------------|
| **保险 EV/NBV** | ✅ **理杏仁直接获取**（601336 实测有值） | `/investment-research` 保险股可标注「理杏仁直接获取」，走 `industry-deep` |
| **理杏仁 A 股全端点** | ✅ 11/11 通过（5 只样本） | 革命级技能可全面切换理杏仁为主源 |
| **理杏仁港股** | ⚠️ 10/11 通过（股东人数趋势不可用；董事权益变动已修复） | 港股增强可用；筹码趋势用 majority-shareholders，治理走 `governance` |
| **mx-xuangu 筛选** | ✅ 10/10 条件全部通过 | `/quality-screen` 初筛可覆盖全部 7 指标 + 行业限定 |
| **mx-data 港股** | ✅ 行情/财务/股东均可查 | 港股实时快照可走 mx-data，优于文档预期的「弱覆盖」 |
| **mx-search** | ✅ 公告/资讯检索正常 | 全技能资讯层可统一走 mx-search |
| **理杏仁 batch API** | ✅ `stockCodes` 数组 ≤100，`date` 必填 | `/portfolio-review` 批量估值可行 |
| **美股** | ❌ 两渠道均不支持公司级 | 保持 macrotrends + stockanalysis |

---

## E0.4 关键判定：保险 EV/NBV（601336 新华保险）

### 判定结果：**AVAILABLE — 理杏仁直接获取**

| 字段 | API 编码 | 2025-12-31 实测值 | 来源端点 |
|------|----------|-------------------|----------|
| 内含价值 (EV) | `q.bs.ev.t` | 2,878.4 亿元 | `cn/company/fs/insurance` |
| 寿险及健康险 EV | `q.bs.evolahib.t` | 在 `available_metrics` 中 | 同上 |
| 新业务价值 (NBV) | `q.ps.nbv.t` | 98.42 亿元 | 同上 |
| 核心偿付能力充足率 | `q.bs.coresr.t` | 135.11% | 同上 |
| 综合偿付能力充足率 | `q.bs.compsr.t` | 210.47% | 同上 |

**调用方式**（Skill 内统一走 `lxr_data.py`，禁止直调 API）：

```bash
python tools/lxr_data.py industry-deep 601336 --years 5
python tools/lxr_data.py financials 601336 --years 5 --source lixinger
```

`industry-deep` 返回 `deep_summary.ev` / `deep_summary.nbv` / `deep_summary.coresr` 近 3 年序列；`available_metrics` 含 128 个有效指标（含全部 EV/NBV 相关字段）。

**对 `/investment-research` 的增强力度**：保险股 PEV/偿付能力/代理人维度可从「年报原文 + WebFetch 补漏」升级为「理杏仁结构化注入 + mx-search 资讯补充」。EV/NBV **不再**标注「需年报原文」为主路径；年报原文仅作交叉验证。

---

## E0.1 理杏仁端点矩阵（按测试股票）

图例：✅ PASS | ⚠️ 部分可用/有 bug | ❌ 不可用 | — 不适用（A 股专属）

| 端点 / 能力 | 600519 茅台 | 601336 新华保险 | 600036 招行 | 002594 比亚迪 | 00700 腾讯 |
|------------|------------|----------------|------------|--------------|-----------|
| `financials` 财报 | ✅ non_financial | ✅ **insurance** | ✅ bank | ✅ non_financial | ✅ non_financial（schema 227 字段；当前精选指标集） |
| `valuation` 估值 | ✅ | ✅ insurance 类型 | ✅ bank 类型 | ✅ | ✅ |
| `verify-inputs` 验算输入 | ✅ | ✅ | ✅ | ✅ | ✅ |
| `kline` 日K线 | ✅ | ✅ | ✅ | ✅ | ✅ 前复权 |
| `shareholders --kind majority` | ✅ | ✅ | ✅ | ✅ | ✅ latest-shareholders |
| `shareholders --kind num` 股东人数 | ✅ | ✅ | ✅ | ✅ | ❌ `_source=none` |
| `percentiles` 估值分位矩阵 | ✅ 6×8 | ✅ | ✅ | ✅ | ✅ |
| `governance` 增减持 | ✅ | ✅ | ✅ | ✅ | ✅ 董事权益变动 hot 端点 |
| `revenue` 营收构成 | ✅ | ✅ | ✅ | ✅ | — |
| `industry-deep` 行业深度 | ✅ | ✅ **含 EV/NBV** | ✅ 资本充足率等 | ✅ | — |
| `industry-compare` 行业估值对比 | ✅ | ✅ 保险申万二级 | ✅ | ✅ | — |
| `macro-debt` 国债收益率 | ✅ | ✅ | ✅ | ✅ | ✅ |
| `macro-rates` 利率 | ✅ | ✅ | ✅ | ✅ | ✅ |
| `index-val` 指数估值 | ✅ 000300 | ✅ | ✅ | ✅ | ✅ HSI |

> **字段规模口径说明**：表中的 409/357/227 是理杏仁 API 文档披露的 schema 规模，不代表 `tools/lxr_data.py financials` 当前一次性拉取的指标数。当前 CLI 采用精选指标集：600519 `financials` 实测 `metric_count=23`，601336 `financials` 实测 `metric_count=57`，00700 `financials` 实测 `metric_count=22`；保险 `industry-deep` 实测 `metric_count=128`，用于 EV/NBV/偿付能力等深度字段。

### A 股类型自动路由（实测）

| 代码 | 自动判定 `report_type` | 字段规模 |
|------|------------------------|----------|
| 600519 | non_financial | 409 |
| 601336 | **insurance** | 357（有效拉取 128/请求） |
| 600036 | bank | 357 |
| 002594 | non_financial | 409 |

---

## E0.2 mx-xuangu 财务筛选条件验证

> 调用格式：`python mx_xuangu.py "<条件>" --output-dir %TEMP%\mx_skills`  
> ⚠️ Windows 必须用 `--output-dir`，不能传位置参数。

| 筛选条件 | 测试问句 | 结果 | 返回行数 |
|----------|----------|------|----------|
| PE | 市盈率小于20的A股，返回前5只 | ✅ | 5 |
| PB | 市净率小于2的A股，返回前5只 | ✅ | 5 |
| ROE | 净资产收益率大于15%的A股，返回前5只 | ✅ | 5 |
| 净利润增速 | 净利润同比增长大于0的A股，返回前5只 | ✅ | 5 |
| 股息率 | 股息率大于3%的A股，返回前5只 | ✅ | 5 |
| **毛利率** | 毛利率大于40%的A股，返回前5只 | ✅ | 5 |
| **净利率** | 净利率大于20%的A股，返回前5只 | ✅ | 5 |
| **资产负债率** | 资产负债率小于50%的A股，返回前5只 | ✅ | 5 |
| **FCF** | 自由现金流大于0的A股，返回前5只 | ✅ | 5 |
| **收入增速** | 营业收入同比增长大于10%的A股，返回前5只 | ✅ | 5 |
| 行业限定 | 白酒行业市盈率小于30的股票，返回前5只 | ✅ | 5 |
| 涨跌幅 | 今日涨幅大于2%的A股，返回前5只 | ✅ | 5 |

**结论**：规划文档中标注为「待验证」的毛利率/净利率/资产负债率/FCF/收入增速 **全部可用**。`/quality-screen` 可优先 mx-xuangu 初筛；理杏仁 batch 作为精确复核层，而非唯一补数路径。

**口径注意**：mx-xuangu 的 PE 等指标为 NLP 解析口径，与理杏仁 TTM 可能有 2–5% 偏差；交叉验证阈值按规划 2%（NLP 源放宽）。

**本轮测试未发现确认不支持项**：上表 10 项 + 行业限定 + 涨跌幅均已实测通过。**未测条件不得推断支持**（如市值区间、换手率、北向持股等）。

**未测 / 勿假设支持**：市值绝对值区间、换手率、陆股通持股、自定义公式组合、港股全市场批量（以个股降级为准）。

---

## E0.3 mx-data 港股覆盖度（00700 腾讯）

| 查询类型 | 测试问句 | 结果 | 备注 |
|----------|----------|------|------|
| 实时行情 | 腾讯控股最新价 涨跌幅 市盈率 市净率 | ✅ | 返回近 5 日 PE/PB/收盘价/涨跌幅 |
| 财务数据 | 腾讯控股近三年净利润 营业收入 | ✅ | 含 2023–2025 年报 + 2026 一季报 |
| 股东信息 | 腾讯控股十大股东 | ⚠️ | 有数据但格式为拼接字符串，非结构化前十 |

**结论**：港股 **行情 + 财务** 覆盖优于规划预期（原标注「弱于 A 股」）。股东结构建议仍以理杏仁 `latest-shareholders` 为主，mx-data 作补充。

### mx-data A 股快照（600519）

| 查询 | 结果 |
|------|------|
| 贵州茅台最新价 涨跌幅 PE PB | ✅ 与理杏仁估值量级一致（PE ~17.66） |

### mx-search 资讯（601336）

| 查询 | 结果 |
|------|------|
| 新华保险最新公告 | ✅ 返回 15 条，含公告类型与日期 |

---

## E0.5 理杏仁 Batch API

| 端点 | 测试 payload | 结果 |
|------|-------------|------|
| `cn/company/fundamental/non_financial` | `stockCodes: [600519, 601336, 600036]`, `date: 2026-06-26`, `metricsList: [pe_ttm, pb, mc]` | ✅ 返回 3 条 |
| `cn/company/fs/non_financial` | `stockCodes: [600519, 601336, 600036]`, `date: 2025-12-31`, `metricsList: [q.ps.np.t, q.ps.oi.t]` | ✅ 返回 3 条 |

**约束**：
- `stockCodes` 长度 1–100
- 必须传 `date` 或 `startDate`+`endDate`（**不支持** `date: latest` 字符串）
- 多股时 `metricsList` ≤48 项；单股 ≤36 项（基本面）/ ≤128 项（财报）

**对 `/portfolio-review` 的影响**：5–15 只持仓 1–2 次 API 可完成批量估值更新。

---

## 确认不存在的能力（勿在增强中使用）

| 能力 | 原因 |
|------|------|
| 理杏仁美股公司级财报/估值 | 仅支持美股指数 |
| mx-moni 实盘交易 | 模拟交易 only |
| 理杏仁日内 tick | 仅日频收盘价 |
| 港股股东人数趋势 | 理杏仁无对应端点（00700 实测 `_source=none`） |

---

## 待修复项（不阻塞 E1，但需在后续阶段处理）

| 问题 | 影响技能 | 建议 | 状态 |
|------|----------|------|------|
| ~~`get_governance` 港股缺 `sortName`/`sortOrder`~~ | management-deep-dive, news-pulse | 改用 `hk/company/hot/director_equity_change` 正确 payload（`stockCodes`+`metricsList`） | ✅ 已修复 `lxr_data.py` |
| mx 脚本 Windows 默认输出路径 | 全部 MX 技能 | Skill 文档统一写 `--output-dir %TEMP%\mx_skills` | ✅ 已在技能中注明 |
| `client.post` vs `post_raw` batch 测试误判 | 无用户影响 | 内部测试用 `post_raw` + 正确 date | 文档已说明 |
| 港股股东人数趋势 | shareholders-num | 理杏仁无端点，标注降级 | 已知限制 |

---

## 技能增强力度修订（基于 E0 实测）

| 技能 | 原规划 | E0 后修订 |
|------|--------|-----------|
| `/investment-research` 保险 EV/NBV | ⚠️ 待验证 | ✅ **理杏仁直接获取**，增强力度从「受限」升为「完整」 |
| `/quality-screen` mx-xuangu 覆盖 | ⚠️ 5 项待验证 | ✅ **10/10 条件可用**，Step 2 理杏仁补数降为「精确复核」 |
| `/portfolio-review` batch | 待验证 | ✅ 已确认 |
| 港股 mx-data | ⚠️ 弱覆盖 | ✅ 行情+财务可用，股东结构化仍靠理杏仁 |
| `/management-deep-dive` 港股治理 | 未测 | ✅ 理杏仁 `governance` 董事权益变动可用；股东人数趋势仍不可用 |

---

## 数据标注规范（增强后统一）

报告与 Skill 输出中的数据来源标注：

| 标注 | 含义 |
|------|------|
| `_source: lixinger` | 理杏仁 API，经 `lxr_data.py` |
| `_source: mx-data` | 妙想金融数据 |
| `_source: mx-search` | 妙想资讯搜索 |
| `_source: mx-xuangu` | 妙想智能选股 |
| `_source: legacy` | 东方财富/腾讯/aastocks 等免费源；详细渠道写入 `source_detail`，如 `eastmoney:lhb` / `eastmoney:lhb-detail` |
| `需年报原文` | 仅作交叉验证，非主路径（保险 EV/NBV **已移出此类**） |

---

## 验证命令速查（复现 E0）

```powershell
$env:PYTHONIOENCODING='utf-8'

# 保险 EV/NBV（E0.4 关键）
python tools/lxr_data.py industry-deep 601336 --years 3

# 理杏仁全能力抽检
python tools/lxr_data.py financials 600519 --years 3 --source lixinger
python tools/lxr_data.py industry-compare 601336

# 东方财富龙虎榜免费源
python tools/lxr_data.py lhb 000004 --limit 1
python tools/lxr_data.py lhb-detail --trade-id 100357777
python tools/lxr_data.py lhb-detail 000004 --start-date 2026-06-01 --end-date 2026-06-26 --list-limit 20
python tools/lxr_data.py lhb-detail 000004 --start-date 2026-06-01 --end-date 2026-06-26 --dominant-type youzi --dominant-direction net_buy
python tools/lxr_data.py lhb-detail 000004 --start-date 2026-06-01 --end-date 2026-06-26 --youzi-alias 拉萨天团
python tools/lxr_data.py lhb-detail 000004 --start-date 2026-06-01 --end-date 2026-06-26 --min-dominant-net 500000

# Batch API
cd tools; python -c "from lxr_client import LixingerClient; import json; c=LixingerClient(); print(json.dumps(c.post_raw('cn/company/fundamental/non_financial', {'stockCodes':['600519','601336'],'date':'2026-06-26','metricsList':['pe_ttm','pb']})['data'], ensure_ascii=False))"

# mx-xuangu（注意 --output-dir）
python C:\Users\admin\.claude\skills\mx-xuangu\mx_xuangu.py "ROE大于15%的A股，返回前5只" --output-dir $env:TEMP\mx_skills

# mx-data 港股
python C:\Users\admin\.claude\skills\mx-data\mx_data.py "腾讯控股近三年净利润 营业收入" $env:TEMP\mx_skills
```

`lhb-detail` 记录中的 `buy_seats` / `sell_seats` 已包含 `seat_category` 与 `seat_profile`；记录层包含 `seat_profile_summary`、`seat_amount_summary` 与 `seat_flow_analysis`，用于区分机构、北向、普通营业部与已知游资/活跃席位，按类型聚合买入/卖出/净额，并标注资金主导方。区间模式额外返回 `range_flow_summary`，汇总多日主导类型、方向、类型净额和游资别名，并可用 `--dominant-type` / `--dominant-direction` / `--youzi-alias` / `--min-dominant-net` 过滤记录。

---

*本矩阵为 `docs/plan-skill-enhancement.md` E0 阶段准出产物。验证通过后按 E1→E2→E3→E4 顺序实施技能增强。*
