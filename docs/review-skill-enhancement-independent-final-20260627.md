# Skill 增强独立复审结论与续接交接

> 审核日期：2026-06-27  
> 审核角色：独立审核 Agent  
> 工作区：`E:\Repos\Skills\ai-berkshire`  
> 当前可用分支：`main`  
> 说明：原审查文档曾落在 `feat/enhancement-e4` 的未跟踪文件中。为避免编程 Agent 切分支卡住，本文件在当前 `main` 工作区重新落盘，作为续接依据。  
> 最终判决：**打回修改，需修完 `_source` 全量覆盖后再独立复审**

## 一、结论摘要

上一轮 `/quality-screen` 的核心阻断问题已修复：`share_dilution_5y` 不再缺失，`quality-metrics` 输出含 7 项 checks，`verify_channel_capability.py` 已增强为解析 JSON 并检查有效值，回归验证曾全部通过。

但 `_source` 字段规范仍未做到“所有增强 Skill”全覆盖。重点文件已修复并同步，但以下增强 Skill 中仍有数据源调用只写工具名，未明确要求输出或报告标注对应 `_source` 值，因此需要继续修复。

## 二、两个阻断项专项判定

| 阻断项 | 判定 | 结论 |
|---|---|---|
| `_source` 字段规范 | **FAIL** | 重点文件已修复，但所有增强 Skill 范围仍有残余缺口 |
| `/quality-screen` 精确复核层 | **PASS** | `share_dilution_5y` 不再缺失；missing 语义、准出/降级规则已写清 |

## 三、必须修复项

### F1. `_source` 字段规范仍未全量覆盖

以下文件存在数据源调用，但未明确要求使用 `_source` 字段标注对应来源。根目录与 Codex reference 副本都要同步修改。

| 文件 | 原审行号 | 问题 |
|---|---:|---|
| `skills/news-pulse.md` | 78, 92, 106, 119, 154 | 多处要求先执行 `mx-search`，但未明确要求输出/报告标注 `_source: mx-search`；`mx-data` 实时异动快照也应标注 `_source: mx-data` |
| `codex/ai-berkshire/references/skills/news-pulse.md` | 同上 | Codex 副本需同步 |
| `skills/earnings-review.md` | 42, 44 | `mx-search` 业绩会/券商点评、`mx-data` 市场反应未明确 `_source: mx-search` / `_source: mx-data` |
| `codex/ai-berkshire/references/skills/earnings-review.md` | 同上 | Codex 副本需同步 |
| `skills/bottleneck-hunter.md` | 17 | 供应链中断新闻调用 `mx-search`，但未明确 `_source: mx-search` |
| `codex/ai-berkshire/references/skills/bottleneck-hunter.md` | 同上 | Codex 副本需同步 |

修复要求：

1. 在根目录 `skills/*.md` 中补明确规则，不只写工具名。
2. 同步到 `codex/ai-berkshire/references/skills/*.md`。
3. 保持根目录与 Codex reference 副本哈希一致。
4. 只改与本次修复直接相关的文件。

建议文本：

```markdown
执行 `python tools/lxr_data.py mx-search "..."` 后，相关事件/资讯在报告中必须标注 `_source: mx-search`。
```

```markdown
市场反应来自 `mx-data` 时，报告中必须标注 `_source: mx-data`。
```

## 四、已通过但需防回归

| 项目 | 判定 | 证据 |
|---|---|---|
| `quality-metrics 600132` | PASS | `_source=lixinger`，`share_dilution_5y.value=0.0`，`status=pass`，`result=pass` |
| 五个候选复核 | PASS | `300492`、`600185`、`300972`、`002640`、`600132` 均无 `share_dilution_5y` missing |
| `verify_channel_capability.py` 断言增强 | PASS | 曾检查 `_source`、7 项 key、`share_dilution_5y` 非 missing 且有有效值 |
| Codex Skill 格式 | PASS | UTF-8 模式下 `quick_validate.py` 曾返回 `Skill is valid!` |

## 五、最终验证命令

编程 Agent 修复后必须亲自运行：

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
$env:PYTHONUTF8='1'
python C:\Users\admin\.claude\skills\skill-creator\scripts\quick_validate.py codex\ai-berkshire
git status --short --branch
```

另外用哈希或 diff 证明以下根/Codex reference 对同步一致：

- `news-pulse.md`
- `earnings-review.md`
- `bottleneck-hunter.md`

## 六、给编程 Agent 的续接提示词

````text
你是接续工作的编程 Agent，工作区是 E:\Repos\Skills\ai-berkshire。不要切换分支；直接在当前工作区继续。请先读取：

1. E:\Repos\Skills\ai-berkshire\docs\review-skill-enhancement-independent-final-20260627.md
2. E:\Repos\Skills\ai-berkshire\docs\plan-skill-enhancement.md
3. E:\Repos\Skills\ai-berkshire\CLAUDE.md
4. C:\Users\admin\.claude\skills\skill-creator\SKILL.md

必须修复所有独立审核发现的问题，重点是 `_source` 字段规范未全量覆盖：

- 修复 `skills/news-pulse.md`：所有 `mx-search` 侦察任务必须明确要求输出/报告标注 `_source: mx-search`；`mx-data` 实时异动快照如用于报告，必须标注 `_source: mx-data`。
- 修复 `skills/earnings-review.md`：业绩会/券商点评来自 `mx-search` 时标注 `_source: mx-search`；市场反应来自 `mx-data` 时标注 `_source: mx-data`。
- 修复 `skills/bottleneck-hunter.md`：供应链中断新闻来自 `mx-search` 时标注 `_source: mx-search`。
- 同步对应 Codex reference 副本：
  - `codex/ai-berkshire/references/skills/news-pulse.md`
  - `codex/ai-berkshire/references/skills/earnings-review.md`
  - `codex/ai-berkshire/references/skills/bottleneck-hunter.md`

只改与本次修复直接相关的文件。根目录 `skills/*.md` 与对应 Codex reference 必须内容一致。

最终验证必须亲自运行并报告结果：

```powershell
$env:PYTHONIOENCODING='utf-8'
python tools/verify_channel_capability.py --quick
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
$env:PYTHONUTF8='1'
python C:\Users\admin\.claude\skills\skill-creator\scripts\quick_validate.py codex\ai-berkshire
git status --short --branch
```

另外用哈希或 diff 证明 `news-pulse.md`、`earnings-review.md`、`bottleneck-hunter.md` 的根/Codex reference 副本同步一致。若任一关键验证失败，不得声称完成。
````

## 七、给新会话独立评审 Agent 的提示词

````text
你是一个独立审核 Agent。你的任务是对编程 Agent 修复后的结果进行独立、严格复审。你只负责审查，不负责编写代码。

工作区：E:\Repos\Skills\ai-berkshire

请先读取：

1. E:\Repos\Skills\ai-berkshire\docs\review-skill-enhancement-independent-final-20260627.md
2. E:\Repos\Skills\ai-berkshire\docs\plan-skill-enhancement.md
3. E:\Repos\Skills\ai-berkshire\CLAUDE.md
4. C:\Users\admin\.claude\skills\skill-creator\SKILL.md

重点复审：

1. `_source` 字段规范全量覆盖
   - 重点检查：
     - skills/news-pulse.md
     - skills/earnings-review.md
     - skills/bottleneck-hunter.md
   - 检查这些文件中的 `mx-search`、`mx-data`、`mx-xuangu`、理杏仁/`lixinger` 数据调用是否都明确要求在输出或报告中标注对应 `_source` 字段。
   - 检查对应 Codex reference 副本是否同步。
   - 扩大抽查所有增强 Skill，确认不存在新的“调用数据源但未明确 `_source`”缺口。

2. `/quality-screen` 不要回归
   - 实测：
     $env:PYTHONIOENCODING='utf-8'
     python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
     python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
   - 判定 `share_dilution_5y` 是否仍非 missing，且 `_source: lixinger`、7 项 checks 完整。
   - 检查 `tools/verify_channel_capability.py` 是否仍包含有效值断言，而不是退回只检查 key 存在。

3. 回归验证
   - 必须亲自运行：
     $env:PYTHONIOENCODING='utf-8'
     python tools/verify_channel_capability.py --quick
     python -m compileall -q tools codex/ai-berkshire/scripts/tools
     python -m pytest -q
     $env:PYTHONUTF8='1'
     python C:\Users\admin\.claude\skills\skill-creator\scripts\quick_validate.py codex\ai-berkshire
     git status --short --branch

4. 安全与一致性
   - 检查是否有真实 token/API key 泄露。
   - 检查是否引入危险 shell 拼接、命令注入或不必要的 `shell=True`。
   - 检查 Codex Skill 格式是否符合 `skill-creator` 规范。
   - 检查工作区是否干净，或仅有预期修复变更。

输出格式：

- 逐项给出 PASS / FAIL / WARNING。
- FAIL 必须附文件路径和行号。
- 对 `_source` 全量覆盖和 `/quality-screen` 不回归分别给出专门判定。
- 给出最终判决：准出 / 打回修改 / 有条件准出。
- 列出你亲自运行过的命令和关键结果。
- 不要相信编程 Agent 的自述，所有结论必须基于文件内容和实际执行结果。
````

