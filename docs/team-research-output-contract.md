# 团队研究产物结构 Contract

本 contract 适用于 `/investment-team` 的 P1 团队研究产物结构升级。目标是让 Team Lead 输出的最终报告可追溯、可审计、可解释，而不是只生成一份不可复核的 Markdown 报告。

## 适用范围

- 适用 Skill：`/investment-team`
- 适用输出目录：`reports/{公司名}/`
- 权限边界：Team Lead 统一取数、验算、写文件和抽检；角色 Agent 只读分析，不写文件、不自行联网、不自行补数。

## 必需产物

一次完整团队研究至少生成以下文件或目录：

| 产物 | 路径 | 责任人 | 用途 |
|---|---|---|---|
| 资料包 | `reports/{公司名}/data-pack.json` | Team Lead | 保存结构化财务、估值、业务、治理、行业、风险与工具输出 |
| 来源索引 | `reports/{公司名}/source-index.md` | Team Lead | 记录每个来源的 ref、标题、日期、链接/路径、`_source`、用途和可信度 |
| 角色简报 | `reports/{公司名}/role-briefs/` | Team Lead | 保存四个角色的只读输入摘要、角色结论、反面证据、不确定性和补数请求 |
| 抽检结果 | `reports/{公司名}/audit-results.json` | Team Lead | 保存最终报告关键数据抽检清单、核验结果、准出/打回判决 |
| 最终报告 | `reports/{公司名}/最终报告.md` 或 `{公司名}-research-{YYYYMMDD}.md` | Team Lead | 综合结论、四维评分、关键数据、投资建议和仲裁理由 |

Team Lead 可用脚手架工具初始化上述产物：

```bash
python tools/team_research_outputs.py {公司名} --ticker {代码} --market {市场}
```

脚手架只创建空模板，不代表研究完成；`audit-results.json` 初始 `verdict` 为 `reject`，必须完成抽检后才能改为 `pass`。

## `data-pack.json` 最小结构

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
    "source_refs": []
  },
  "valuation": {
    "price": null,
    "market_cap_checked": null,
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

## `source-index.md` 最小结构

`source-index.md` 必须包含来源表、反证材料和已知缺口：

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

## `role-briefs/` 最小结构

`role-briefs/` 下至少包含四份角色简报：

- `business-analyst.md`
- `financial-analyst.md`
- `industry-researcher.md`
- `risk-assessor.md`

每份角色简报必须包含：

- 角色输入范围：可使用的 `data-pack.json` 字段和 `source-index.md` ref
- 核心结论与评分
- 使用的证据
- 反面证据
- 不确定性
- 补数请求
- 与其他角色可能冲突的判断

## `audit-results.json` 最小结构

```json
{
  "report": "reports/{公司名}/最终报告.md",
  "generated_at": "YYYY-MM-DD",
  "sample_ratio": 0.15,
  "items": [
    {
      "claim": "",
      "report_location": "",
      "source_ref": "",
      "expected_value": "",
      "verified_value": "",
      "status": "pass",
      "note": ""
    }
  ],
  "verdict": "pass"
}
```

`verdict` 只能是 `pass` 或 `reject`。出现关键数据无来源、口径冲突未解释、抽检失败未修正时，必须写 `reject`，不得发布最终报告。

## 关键数据溯源

最终报告中的关键数据必须能追溯到 `data-pack.json` 或 `source-index.md`：

- 财务与估值数字：引用 `data-pack.json` 字段，并标注来源 ref。
- 行业、竞争、治理与风险事实：引用 `source-index.md` ref。
- 工具验算结果：引用 `data-pack.json.tool_outputs` 或在报告中嵌入命令输出摘要。
- 估计值：必须标注“估计”、口径、假设和来源限制。

建议在最终报告的关键表格中增加 `来源/ref` 列。若不适合逐行展示，应在章节末尾集中列出“本节来源 ref”。

## 冲突仲裁

角色结论与最终结论冲突时，Team Lead 必须写明冲突仲裁：

- 冲突双方：哪两个角色或哪类证据发生冲突。
- 冲突内容：结论、口径、时间范围或风险权重的差异。
- 仲裁依据：优先级为一手资料、结构化数据、工具验算、可交叉验证来源、角色推理。
- Team Lead 的仲裁理由：为什么采纳某一方，为什么没有采纳另一方。
- 残余不确定性：仲裁后仍不能确定的事项。

最终报告至少包含一个“角色冲突与 Team Lead 仲裁”小节；如本次研究没有实质冲突，也必须明确写“未发现影响最终结论的角色冲突”，并说明检查范围。

## 准出规则

最终报告准出前必须满足：

- 必需产物均已生成或明确说明为何不适用。
- `data-pack.json` 与 `source-index.md` 中的来源 ref 可被最终报告引用。
- `role-briefs/` 中四个角色均有独立结论、反面证据和不确定性。
- `audit-results.json` verdict 为 `pass`。
- 最终报告包含关键数据溯源和冲突仲裁小节。
