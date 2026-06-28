# 理杏仁数据接口使用指南

> 面向 Claude Code / Codex Skills 的结构化数据取数参考。统一入口：`tools/lxr_data.py`。
> 优先级：**理杏仁 → 妙想 → 免费源**（自动降级）。规范见 `skills/financial-data.md`。

## 一、环境配置

- Token：填写 `tools/lxr_config.json`（不提交 git），模板见 `tools/lxr_config.example.json`。
 也可用环境变量 `LIXINGER_TOKEN`。codex 副本目录 `codex/ai-berkshire/scripts/tools/`。
- 妙想脚本路径：默认 `~/.claude/skills/mx-data/mx_data.py`（codex 自动回退 `~/.codex/skills/...`），
 可用 `MX_DATA_SCRIPT` 覆盖。
- 缓存：自动落盘 `tempfile.gettempdir()`，财报/估值等 TTL 见各方法。
- Windows 中文输出：`$env:PYTHONIOENCODING='utf-8'`。

## 二、CLI 命令速查（`python tools/lxr_data.py <command>`）

### 公司财务与估值
| 命令 | 说明 | 示例 |
|------|------|------|
| `financials <code> [--years N] [--source lixinger]` | 年度财报（自动判定保险/银行/证券/非金融） | `financials 601336 --years 5` |
| `valuation <code> [--source lixinger]` | 估值 + 历史分位点（PE/PB/PS/股息率） | `valuation 600519` |
| `percentiles <code> [--report-type T]` | 估值分位全矩阵 4指标×6维度×8统计量 | `percentiles 600519` |
| `verify-inputs <code>` | 验算输入（总股本/EPS/BVPS/市值，取最近年报） | `verify-inputs 601336` |

### 行情与股东
| 命令 | 说明 | 示例 |
|------|------|------|
| `kline <code> [--days N] [--adjust qfq]` | 前复权K线（A股/港股） | `kline 00700 --days 120` |
| `shareholders <code> --kind {majority,num,fund}` | 前十大股东/股东人数/基金持股 | `shareholders 600519 --kind majority` |
| `lhb [code] [--limit N]` | A股龙虎榜明细（东方财富免费源，`_source: legacy`） | `lhb 600519 --limit 5` |
| `lhb-detail [code] --date YYYY-MM-DD` / `--trade-id ID` / `--start-date YYYY-MM-DD --end-date YYYY-MM-DD` | A股龙虎榜买卖席位明细；区间模式先筛龙虎榜记录再按 `trade_id` 批量拉详情，并输出 `range_flow_summary`；可用 `--dominant-type` / `--dominant-direction` 过滤资金主导方，用 `--youzi-alias` 过滤指定游资/活跃席位，或用 `--min-dominant-net` 过滤主导资金绝对净额下限；席位含 `seat_category`、`seat_profile`，记录含 `seat_profile_summary` / `seat_amount_summary` / `seat_flow_analysis`；`source_detail: legacy:ashare_data/lhb-detail` | `lhb-detail 000004 --start-date 2026-06-01 --end-date 2026-06-26 --min-dominant-net 500000` |

### 行业深度与治理（阶段4）
| 命令 | 说明 | 示例 |
|------|------|------|
| `industry-deep <code> [--years N]` | 保险EV/NBV/偿付能力、银行资本充足率/净息差、证券经纪/投行/资管 | `industry-deep 601336` |
| `revenue <code> [--years N]` | 营收构成（分产品/分地区，dataList） | `revenue 600519 --years 3` |
| `governance <code> [--years N]` | 高管/大股东增减持（A股）；港股董事权益变动 | `governance 601336` |

### 宏观、指数与行业对比（阶段5）
| 命令 | 说明 | 示例 |
|------|------|------|
| `macro-debt [--area cn|us] [--years N]` | 国债收益率（含10年期，利差基准） | `macro-debt --area cn` |
| `macro-rates [--area cn|hk|us]` | LPR/Shibor/MLF 等利率（取最新非空值） | `macro-rates --area cn` |
| `index-val <code> [--market cn|hk]` | 指数估值 PE/PB/PS/股息率 当前值+10年分位+点位 | `index-val 000300 --market cn` |
| `industry-compare <code> [--source sw_2021] [--level two]` | 申万二级行业归属 + 公司vs行业估值对比表 | `industry-compare 600519` |

常用指数代码：沪深300=`000300`、上证50=`000016`、中证500=`000905`、恒生指数=`HSI`、恒生科技=`HSTECH`。

## 三、Python 调用示例

```python
import sys; sys.path.insert(0, "tools")
from lxr_data import LxrData
d = LxrData(verbose=False)

# 保险深度（EV/NBV/偿付能力，附 deep_summary 近3年值）
ins = d.get_industry_deep("601336", years=5)
print(ins["deep_summary"]["ev"])   # [{date,value}, ...]

# 10年期国债收益率（利差分析）
print(d.get_bond_yield_10y(area="cn")["yield_10y"])

# 申万二级行业估值对比表
cmp = d.compare_industry_valuation("600519", level="two")
for row in cmp["comparison"]["table"]:
    print(row["metric"], "行业", row["industry_cv"], row["industry_cvpos"],
          "公司", row["company_cv"], row["company_cvpos"])
```

## 四、Skill 集成建议

- `/investment-research`：第一步数据收集优先 `financials`/`valuation`/`industry-deep`/`revenue`/`governance`，
 保险股 EV/NBV/偿付能力不再依赖 WebFetch 抓年报补漏。
- `/industry-research`：用 `index-val` 看大盘估值分位、`industry-compare` 看申万二级行业相对估值、
 `macro-debt`/`macro-rates` 提供宏观背景与利差。
- `/earnings-review`：`financials` + `industry-deep` 提供同口径财报与行业专属指标。
- `/investment-checklist`：`verify-inputs` 自动取数后交 `financial_rigor.py` 程序化验算。

## 五、降级与回退

- 理杏仁请求失败（限流/字段缺失）自动降级到妙想 `mx-data`，再降级到免费源 `ashare_data.py` 等。
- 关闭理杏仁：CLI 去掉 `--source lixinger` 即回原模式；Python 层 `get_financials(code, source="legacy")`。
- 完全回退：`git revert` 各 `feat/lixinger-pX` 的 merge commit。

## 六、字段与端点索引

完整 API 文档见 `C:/Users/admin/Documents/lixingren_docs/offline-docs/`：
- `AGENT-INDEX.md`：248 端点入口索引。
- `pages/<market>/<resource>.md`：各端点详细字段目录。
关键端点：`cn|hk/company/fs/{non_financial,insurance,bank,security}`、`cn|hk/company/fundamental/*`、
`cn|hk/company/candlestick`、`cn|hk/index/fundamental`、`cn/industry/fundamental/sw_2021`、
`macro/national-debt`、`macro/interest-rates`。
