# AI Berkshire — 项目指令

## 项目概述

双平台（Claude Code + Codex）价值投资研究 Skill 合集。四大师框架：巴菲特、芒格、段永平、李录。
GitHub: xbtlin/ai-berkshire

## 项目结构

```
skills/          — Claude Code 投研命令定义（.md），复制到 ~/.claude/commands/ 使用
codex/           — Codex 原生 Skill 包（SKILL.md + references + scripts）
tools/           — 辅助工具（financial_rigor.py 精确计算）
reports/         — 投资研究报告输出
assets/          — 图片等静态资源
```

## 报告目录结构

所有报告按**公司名**建文件夹，公司相关的所有报告放在对应文件夹内：

```
reports/
├── AI产业研究/              — AI产业链全景研究（置顶）
│   ├── AI五层蛋糕-产业全景研究-20260605.md
│   └── AI五层蛋糕-公众号-20260605.md
├── 腾讯/                    — 腾讯所有研究报告
│   ├── 腾讯-research-20260408.md
│   ├── 腾讯-earnings-2025Q4.md
│   ├── 腾讯-management-20260409.md
│   └── 腾讯-thesis.md
├── 拼多多/                  — 拼多多所有研究报告
├── 泡泡玛特/                — 泡泡玛特所有研究报告
├── 核电-industry-20260409.md — 行业报告放根目录
├── AI算力-funnel-20260509.md  — 漏斗筛选报告放根目录
├── AI-轮动判断-20260509.md    — 主题级综合判断报告放根目录
├── portfolio-latest.md       — 组合报告放根目录
└── 多公司对比-checklist-20260408.md — 多公司报告放根目录
```

## 报告命名规范

| Skill | 文件命名格式 | 示例 |
|------|---------|------|
| /investment-team | `{公司名}/` 目录内含4个视角+最终报告 | `reports/拼多多/最终报告.md` |
| /investment-research | `{公司名}-research-{YYYYMMDD}.md` | `reports/腾讯/腾讯-research-20260408.md` |
| /investment-checklist | `{公司名}-checklist-{YYYYMMDD}.md` | `reports/腾讯/腾讯-checklist-20260408.md` |
| /industry-research | `{行业名}-industry-{YYYYMMDD}.md`（根目录） | `reports/核电-industry-20260409.md` |
| /industry-funnel | `{行业名}-funnel-{YYYYMMDD}.md`（根目录） | `reports/AI算力-funnel-20260509.md` |
| /private-company-research | `{公司名}-private-{YYYYMMDD}.md` | `reports/字节跳动/字节跳动-private-20260408.md` |
| /earnings-review | `{公司名}-earnings-{期间}.md` | `reports/腾讯/腾讯-earnings-2025Q4.md` |
| /earnings-team | `{公司名}/` 目录内含4个大师视角+研究底稿+公众号文章+读者评审 | `reports/腾讯/腾讯-earnings-2025Q4.md`（公众号定稿） |
| /thesis-tracker | `{公司名}-thesis.md`（长期维护） | `reports/腾讯/腾讯-thesis.md` |
| /portfolio-review | `portfolio-latest.md`（根目录，持续更新） | `reports/portfolio-latest.md` |
| /management-deep-dive | `{公司名}-management-{YYYYMMDD}.md` | `reports/腾讯/腾讯-management-20260409.md` |

## /investment-team 文件结构

```
reports/{公司名}/
├── README.md                         — 研究框架概览+核心结论
├── 01-商业模式分析-段永平视角.md
├── 02-财务估值分析-巴菲特视角.md
├── 03-行业竞争分析-芒格视角.md
├── 04-风险管理层评估-李录视角.md
└── 最终报告.md                       — Team Lead 综合报告
```

## 投研分析核心原则（最高优先级）

- **客观、客观、客观**——所有投研分析必须基于事实和数据，严禁主观臆断
- 严格区分"事实"与"观点"：事实用数据支撑，观点必须明确标注为"观点"或"推测"
- **不预设立场**：不预设看多或看空，先摆数据、再推逻辑、最后得结论。结论必须从数据中自然推出
- 禁止使用"我认为"、"我觉得"、"显然"等主观表述，改用"数据显示"、"证据表明"、"根据XX来源"
- **呈现正反两面**：每个核心判断都必须附带反面论据（"但另一方面..."），让读者自己权衡
- 对不确定的事情诚实说"不确定"或"数据不足"，不要用推测填充确定性
- 所有skill（investment-team、investment-research、earnings-review等）在执行时都必须遵守以上原则

## 数据获取优先级（自动化三级体系）

A股/港股结构化财务与估值数据采用**三级自动降级链**，详细规范见 `skills/financial-data.md`：

1. **理杏仁 API（第1顺位，首选）**——`tools/lxr_data.py` 统一入口，自动判定市场(A股cn/港股hk)与报表类型(非金融/保险/银行/证券)。
   - 财报/估值/估值分位点、K线、股东、行业深度(EV/NBV/偿付能力/资本充足率)、营收构成、公司治理、宏观(国债10y/利率)、指数估值、申万行业对比，均一站取数。
   - token 置于 `tools/lxr_config.json`（不提交 git，example 模板提交）；缓存路径用 `tempfile.gettempdir()`。codex 副本同步至 `codex/ai-berkshire/scripts/tools/`。
2. **妙想 Skills（第2顺位）**——`mx-data/mx-search/mx-xuangu` 等自然语言查询，理杏仁字段缺失或需实时资讯时降级。
3. **免费源（第3顺位，兜底）**——东方财富/巨潮/aastocks/Yahoo/Morningstar，理杏仁+妙想均失效时使用。

现有 CLI（`ashare_data.py`/`financial_rigor.py`/`stock_screener.py`）通过 `--source lixinger` 切换，默认行为不变，去掉参数即回到原模式。保险/银行/证券专属报表、估值分位点为理杏仁独有能力，免费源无法提供。

## 报告语言与风格

- 所有报告使用**中文**
- 风格：直接、犀利、不说废话
- 数据必须标注来源，关键数据至少2个来源交叉验证
- 估计值必须注明"估计"
- 评分使用★符号（★1-5），不含半星
- 穿插巴菲特/芒格/段永平/李录的语录点评

## GitHub 操作

- 本地克隆路径：`~/ai-berkshire/`
- 远程仓库：`https://github.com/xbtlin/ai-berkshire.git`
- 推送前先 `git pull --rebase origin main`（远程经常有新提交）
- commit message 用中文，描述清楚改了什么
- 不要推送中间过程文件（如 data_collection.md），只推最终报告

## 常用命令

```bash
# 推送报告到GitHub
cd ~/ai-berkshire
git add reports/xxx.md
git commit -m "添加xxx报告"
git pull --rebase origin main
git push origin main
```

## 注意事项

- 市值必须手算校验：股价 × 总股本，与报告市值对比
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE等指标用 tools/financial_rigor.py 精确计算
- 报告写完后主动询问是否推送到GitHub

## 多档深度模式

核心分析技能（investment-research、earnings-review、industry-research、investment-team、earnings-team、quality-screen、industry-funnel、compare）支持三档研究深度，用户可通过 `--depth lite|standard|deep` 参数选择：

- **`--depth lite`**：5-10 分钟快速评估，适合初步扫描或已有持仓巡检。合并或跳过非核心环节，仅保留核心判断和估值区间。报告文件名加 `-lite` 后缀（如 `腾讯-research-lite-20260629.md`）。
- **`--depth standard`**：完整研究流程（默认）。当前各技能的默认行为不变。
- **`--depth deep`**：45-90+ 分钟机构级深度。追加交叉验证轮次、历史类比、压力测试、额外 Agent，抽检比率提升至 25%。

档位行为全景与各技能三档差异矩阵参见 `docs/depth-profiles.md`。各技能头部"深度模式选择"小节仅引用该文档对应小节，不重复速览表（单一事实源）。

## 开发收尾汇报

- 每次项目开发工作完成后，最终回复必须补充一段路线图进度摘要。
- 摘要至少说明：本次工作推进了 `docs/ROADMAP.md` 中哪些目标、当前已完成哪些能力、还有哪些路线图目标或后续工作尚未完成。
- 若本次工作没有直接改变路线图，也要明确说明“本次未改变路线图目标”，并基于当前 `docs/ROADMAP.md` 简要列出仍待推进的事项。
