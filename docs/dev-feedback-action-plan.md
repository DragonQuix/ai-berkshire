# 技能运行反馈核查与修复方案

本文承接 `docs/dev-feedback-investment-research.md`，但不直接照单执行其中建议。外部 agent 的运行复盘被当作 code review feedback 处理：先复现，再评价，最后形成可由编程 agent 接手的修复队列。

核查日期：2026-07-01

## 1. 总体判断

- `/investment-research` 的四大师框架、数据分级、抽检准出和报告结构没有被这次反馈推翻。
- 问题集中在工具层边界处理：数值解析、单位口径、CLI 参数防呆、datapack 可复用性、降级事件记录。
- 这些问题属于 P1 发布后韧性改进，不是 P0 安装交付阻塞；但其中 `report_audit.py` 崩溃和 `three-scenario` 单位误用会直接影响报告准出，应排在 P1 最前。
- 不能机械采纳“方向型指标一律取绝对值通过”。正确路径是先保留负号，再为“跌幅用正数表示”这类口径提供显式比较模式或人工标注。

## 2. 已核实问题与处置结论

| # | 反馈点 | 核实结论 | 证据 | 处置 |
|---|---|---|---|---|
| 1 | `lxr_data.py datapack` 不落盘 | 确认 | `python tools\lxr_data.py datapack --help` 无 `-o/--output`；CLI 入口只把 dict 交给最终 `print(json.dumps(...))` | P1-A2 增加 `--output/--output-dir` 和日志字段 |
| 2 | financials 顶层 `records` vs `data` | 部分确认 | `get_financials()` 明确返回 `records`；未发现 skill 文档明确承诺 `data` | 补返回结构示例，不新增兼容 `data` 键，避免双事实源 |
| 3 | `verify-valuation --currency` 文档不一致 | 部分确认 | CLI 对 `--currency` 报错；当前 skill 示例中 `--currency` 在 `verify-market-cap` 和 `three-scenario`，未出现在 `verify-valuation` 示例 | 不盲目给 `verify-valuation` 加无意义参数；改为补 CLI/doc 一致性测试 |
| 4 | `three-scenario --growth 30 15 -5` 算成 3000% | 确认 | 复现输出 `3000%/1500%/-500%` 和天文目标价 | P1-A3 增长率归一化或拒绝，必须有 stderr 提示和测试 |
| 5 | `cross-validate` 无量级预检 | 确认 | `41302` vs `413.02` 输出 20,857.51 亿“共识值”，无单位错位提示 | P1-A3 增加 max/min 量级告警，修正“加权中位数”表述 |
| 6 | `industry-compare` 港股 null | 部分确认 | `09992` 返回 `_source: none` 且含 `note: 申万行业分类仅覆盖A股`，并非完全静默，但缺少替代步骤 | P1-B2 增加 alternatives 和 skill 层港股降级说明 |
| 7 | `mx-xuangu` 港股查询返回 A 股 | 未本地确认 | 需要真实 mx 输出样本；当前只能确认 `call_mx()` 返回 `raw/raw_path` | 等拿到脱敏 raw 后再做 schema 检测，先写入 dev-feedback 模板 |
| 8 | Task Agent 路由失败无记录 | 文档缺口确认 | `skills/investment-research.md` 只说可顺序模拟，未要求记录错误原文、降级方式和影响范围 | P1-B1 补 Task Agent 失败诊断和报告附录字段 |
| 9 | `report_audit verdict` 遇日期字符串崩溃 | 确认 | `float('2026-07-01')` 在 `tools/report_audit.py:314` 复现 ValueError | P1-A1 加 `_to_numeric()`；非数值默认 SKIP/WARN，不把日期粗暴转年份 |
| 10 | `report_audit` 正负号处理错误 | 确认且更严重 | verdict 对 `46.5` vs `-46.5` 报 200%；extract 抽取 `-46.5%` 时变成 `46.50%` | P1-A1 先修正 `[-+]?` 抽取，再提供显式绝对幅度比较 |
| 11 | 理杏仁 `toi` vs 年报“收益”口径冲突 | 基本确认但需口径样本 | 工具无 `caliber` 元数据；具体差异需年报/理杏仁字段样本固化 | P1-B3 加口径元数据和报告口径列 |
| 12 | `cross-validate` 缺 `--caliber` | 确认 | CLI 参数无 `--caliber` | P1-A3 加可选 `--caliber`，偏差时输出“口径待核对” |
| 13 | 可观测性不足 | 确认 | datapack 不落盘，Task Agent 降级无固定记录，mx raw 未进入 datapack 汇总 | P1-A2 + P1-B1 解决核心复现链 |

## 3. 不直接采纳的建议

- 不把日期字符串转换成年份后参与数值比对。日期、状态文字、评级文字属于非数值核验，应 `SKIP` 或 `WARN`，否则会制造伪精度。
- 不让所有“涨跌幅/同比/增速”默认按绝对值通过。涨跌幅的符号通常有含义；只有字段或核验结果显式声明 `compare_mode=absolute_magnitude` 时才允许正负同幅通过。
- 不强制 `cross-validate --unit` 立刻变为必填。它会破坏已有调用；先加入无单位时的提示和量级告警，再视反馈提高约束。
- 不在没有 raw 样本前实现 `mx-xuangu` 港股误回 A 股的自动判定。先收集脱敏 raw，再根据稳定 schema 写检测逻辑。

## 4. 修复队列

### P1-A1：`report_audit.py` 数值韧性

状态：已完成（2026-07-01）

目标文件：

- `tools/report_audit.py`
- `codex/ai-berkshire/scripts/tools/report_audit.py`
- `tests/test_report_audit.py`

验收点：

- Markdown 表格中的 `-46.5%` 抽取为 `-46.5`。
- `verdict` 遇到 `fetched_value: "2026-07-01"` 不崩溃，输出非数值跳过或 warning。
- 默认比较保留符号；只有显式 `compare_mode: "absolute_magnitude"` 或后续定义的安全口径才允许正负同幅通过。

验证命令：

```powershell
python -m pytest tests/test_report_audit.py -q
python -m pytest tests/test_skill_output_regressions.py -q
python tools\verify_channel_capability.py --quick
```

### P1-A2：`lxr_data.py datapack` 可复现输出

状态：已完成（2026-07-01）：CLI 已支持 `--output/-o` 与 `--output-dir`；mx section 继续保留 `raw_path`。

目标文件：

- `tools/lxr_data.py`
- `codex/ai-berkshire/scripts/tools/lxr_data.py`
- `skills/investment-research.md`
- `codex/ai-berkshire/references/skills/investment-research.md`
- `tests/test_lxr_data.py`

验收点：

- `python tools/lxr_data.py datapack {code} --years 5 --output _tmp_{code}_datapack.json` 写入 JSON 文件。
- 输出 JSON 中保留 `sections`、`_source`、`_cache`、失败 section 的 `error`。
- 如果包含 mx 调用，datapack 能记录 `raw_path` 或 `_mx_raws`，方便审计。
- skill 文档明确主 Agent 应用 `--output` 后读取 JSON，而不是 glob 猜文件。

验证命令：

```powershell
python -m pytest tests/test_lxr_data.py -q
python tools\release_smoke.py
python tools\verify_channel_capability.py --quick
```

### P1-A3：`financial_rigor.py` 参数防呆与口径提示

状态：已完成（2026-07-01）

目标文件：

- `tools/financial_rigor.py`
- `codex/ai-berkshire/scripts/tools/financial_rigor.py`
- `tests/test_financial_rigor.py`
- `skills/investment-research.md`
- `codex/ai-berkshire/references/skills/investment-research.md`

验收点：

- `three-scenario --growth 30 15 -5` 不再静默输出 3000%/1500%/-500%；应自动转为 `0.30/0.15/-0.05` 并警告，或直接拒绝并提示正确格式。
- `cross-validate` 在 `max(abs(v))/min(abs(v)) > 50` 时提示疑似单位不一致。
- `cross-validate` 增加可选 `--caliber`，输出中保留口径说明。
- “共识值 (加权中位数)”改为“参考中位数”或真实实现加权逻辑，二选一。

完成记录：

- `three-scenario` 对绝对值大于 1 的 growth 输入按百分数误填处理，自动除以 100，并向 stderr 写出格式警告。
- `cross-validate` 返回并输出量级告警，支持 `--caliber` 传入口径说明，最终参考值统一用“参考中位数”表述。
- root 工具、Codex bundled 副本、root skill 与 Codex reference 已同步。

验证命令：

```powershell
python -m pytest tests/test_financial_rigor.py -q
python -m pytest tests/test_skill_output_regressions.py -q
python tools\verify_channel_capability.py --quick
```

### P1-B1：Task Agent 失败诊断与降级记录

状态：已完成（2026-07-01）

目标文件：

- `skills/investment-research.md`
- `codex/ai-berkshire/references/skills/investment-research.md`
- 相关团队型 skill 如发现同类表述也一并同步
- `tests/test_skill_output_regressions.py`

验收点：

- 明确 `model route not configured`、`timeout`、`permission denied` 的处理策略。
- 要求报告附录记录：失败 agent、错误原文摘要、降级方式、影响范围。
- 主 Agent 顺序模拟不再“装作没有失败”，而是可审计地继续。

完成记录：

- `investment-research` 增加 Task Agent 失败诊断与报告附录记录要求。
- 同步覆盖含后台 Agent/顺序模拟句式的团队型入口：`investment-team`、`earnings-team`、`industry-research`、`investment-checklist`、`management-deep-dive`、`news-pulse`、`private-company-research`、`wechat-article`、`deep-company-series`。
- 测试固定检查三类错误、失败 Agent、错误原文摘要、降级方式、影响范围和「顺序角色模拟」标注，避免后续文档回退为 silent fallback。

验证命令：

```powershell
python -m pytest tests/test_skill_output_regressions.py -q
python tools\verify_channel_capability.py --quick
```

### P1-B2：港股行业对比降级说明

状态：已完成（2026-07-01）

目标文件：

- `tools/lxr_data.py`
- `codex/ai-berkshire/scripts/tools/lxr_data.py`
- `skills/investment-research.md`
- `codex/ai-berkshire/references/skills/investment-research.md`
- `tests/test_lxr_data.py`

验收点：

- 港股 `industry-compare` 返回 `note` 同时包含 `alternatives`，例如 mx-xuangu 同业、手工指定同业、行业龙头列表。
- skill 文档在港股路径中不再要求申万同行分位，而是转为同业手工列表或 mx 辅助。

完成记录：

- `compare_industry_valuation()` 在港股/非 A 股申万不适用时，将 `note` 与 `alternatives` 透出到顶层结果，并在 `industry` 子块保留同一组替代路径。
- alternatives 覆盖 `mx-xuangu` 辅助筛选、手工指定同业列表、港股行业龙头/主要可比公司三条路径。
- `investment-research` 明确“港股行业对比降级”，D2 行业水位不要求申万同行分位。

验证命令：

```powershell
python -m pytest tests/test_lxr_data.py -q
python tools\verify_channel_capability.py --quick
```

### P1-B3：财务口径元数据

状态：已完成（2026-07-01）

目标文件：

- `tools/lxr_data.py`
- `tools/financial_rigor.py`
- `skills/financial-data.md`
- `skills/investment-research.md`
- Codex reference 同步文件

验收点：

- financials/datapack 能表达字段口径，例如 `toi=营业总收入`、年报“收益”口径、币种和单位。
- `cross-validate --caliber` 输出口径冲突提示，避免把已解释的口径差异当作普通数据错误。
- 报告数据表要求增加“口径/来源”列。

完成记录：

- `lxr_data.py financials` 新增 `caliber_metadata`，记录理杏仁字段口径（如 `toi=营业总收入`）、年报“收益”口径提醒、币种和原始单位。
- `datapack` 汇总 `sections.financials.caliber_metadata` 到顶层 `caliber_metadata.financials`，方便报告和审计链路复用。
- `cross-validate --caliber` 在来源偏差未通过时输出「口径待核对」，返回结果保留 `caliber_warning`。
- `financial-data` 与 `investment-research` 文档要求核心数据表保留「口径/来源 / 币种 / 单位」，root skill 与 Codex reference 已同步。

验证命令：

```powershell
python -m pytest tests/test_financial_rigor.py tests/test_lxr_data.py -q
python tools\verify_channel_capability.py --quick
```

### P1-C1：离线 fixture 与 CI 回归门禁

状态：已完成（2026-07-01）

目标文件：

- `.github/workflows/ci.yml`
- `tests/test_ci_and_fixture_contract.py`
- `tests/fixtures/investment_research_smoke/datapack.json`
- `tests/fixtures/investment_research_smoke/expected_report_skeleton.md`
- `docs/ROADMAP.md`
- `docs/dev-feedback-action-plan.md`

验收点：

- GitHub Actions 在 `pull_request` 和 `main` push 上运行离线门禁：全量 pytest、`verify_channel_capability --quick`、compileall、release smoke、`git diff --check`。
- CI 不依赖理杏仁 token、私有 `tools/lxr_config.json`、Playwright 或 GitHub secrets。
- `tests/fixtures/investment_research_smoke/` 固化一份预录 datapack 与报告骨架，覆盖 `caliber_metadata`、`口径/来源`、币种、单位、Task Agent 降级记录和抽检字段。

完成记录：

- 新增 `.github/workflows/ci.yml`，把本地 P0/P1 关键门禁转为 PR/push 自动检查。
- 新增 `tests/test_ci_and_fixture_contract.py`，防止 CI workflow 被删减为只跑局部测试，也防止 investment-research 离线 fixture 退化。
- 新增 `investment_research_smoke` fixture，作为后续技能行为 smoke 的离线输入基线。

验证命令：

```powershell
python -m pytest tests/test_ci_and_fixture_contract.py -q
python -m pytest -q
python tools\verify_channel_capability.py --quick
python tools\release_smoke.py
```

### P1-D1：release notes 自动生成

状态：已完成（2026-07-01）

目标文件：

- `tools/release_notes.py`
- `tools/release_smoke.py`
- `tests/test_release_notes.py`
- `tests/test_release_smoke.py`
- `docs/release-notes.md`
- `docs/ROADMAP.md`
- `docs/dev-feedback-action-plan.md`

验收点：

- 默认用 `origin/main..HEAD` 生成 Markdown 发布说明，不联网、不依赖私有配置。
- 按 conventional commit 类型分组，保留 scope 和中文提交摘要。
- 支持 `--from`、`--to`、`--title`、`--output/-o`、`--max-count`。
- release smoke 覆盖 dry run，避免发布说明工具退化。

完成记录：

- 新增 `tools/release_notes.py`，输出中文 Markdown release notes。
- 新增 `tests/test_release_notes.py` 覆盖分组、解析和 `--output` 落盘。
- `tools/release_smoke.py` 增加 `release notes dry run` 检查。
- `docs/release-notes.md` 记录维护者生成草稿的使用流程。

验证命令：

```powershell
python -m pytest tests/test_release_notes.py tests/test_release_smoke.py -q
python tools\release_smoke.py
```

### P1-E1：`report_audit` 单位归一化

状态：已完成（2026-07-01）

来源反馈：

- `docs/dev-feedback-investment-research-deep-20260701.md` §3.1。
- `extract_data_points` 对"14.3亿MAU"能保留 `unit: 亿`，但 verdict 的 `fetched_value` 是裸数字；核验者填 `1430`（百万）时会触发 9900% 假偏差。

目标文件：

- `tools/report_audit.py`
- `codex/ai-berkshire/scripts/tools/report_audit.py`
- `tests/test_report_audit.py`
- `docs/ROADMAP.md`
- `docs/dev-feedback-action-plan.md`

验收点：

- verdict 支持 `report_unit` / `fetched_unit`，能把 `1430 百万` 归一为 `14.30 亿` 后比较。
- 无 `fetched_unit` 且 `reported_value` 与 `fetched_value` 量级差超过 50 倍时，不直接打回，而是输出「疑似单位不一致，请补 fetched_unit」并降为 warning。
- extract JSON 模板带 `report_unit`、`fetched_unit`、`fetched_unit2`，提示核验者保留单位。

完成记录：

- 新增常见数量单位换算表，覆盖 `亿`、`万亿`、`百万`、`million/M`、`billion/B`、`trillion/T` 等。
- verdict 在比较前将核验值归一到报告单位，并在输出 detail 中保留「单位换算」说明。
- root 工具与 Codex bundled 副本已同步。

验证命令：

```powershell
python -m pytest tests/test_report_audit.py -q
python tools\verify_channel_capability.py --quick
```

### P1-E2：`report_audit verdict` 可复现输出

状态：已完成（2026-07-01）

来源反馈：

- `docs/dev-feedback-investment-research-deep-20260701.md` §3.2。
- `report_audit.py verdict` 只把 JSON 结果混在 stdout 人类日志之后输出，主 Agent 需要清洗日志头和 ANSI 颜色码才能拿到可机器解析结果。

目标文件：

- `tools/report_audit.py`
- `codex/ai-berkshire/scripts/tools/report_audit.py`
- `tests/test_report_audit.py`
- `docs/ROADMAP.md`
- `docs/dev-feedback-action-plan.md`

验收点：

- `python tools/report_audit.py verdict --results ... -o _tmp_verdict.json` 直接写入纯 JSON 判决文件。
- stdout 继续保留人类可读准出/打回摘要，stderr 只写落盘提示。
- 输出文件使用 UTF-8 和 LF 行尾，便于后续 Agent/CI 直接读取。

完成记录：

- verdict CLI 新增 `-o/--output`。
- 新增 `_write_json_output()`，自动创建父目录并写出 UTF-8/LF JSON。
- `tests/test_report_audit.py` 覆盖 `-o` 落盘、JSON 可解析和 verdict 字段。
- root 工具与 Codex bundled 副本已同步。

验证命令：

```powershell
python -m pytest tests/test_report_audit.py -q
python tools\verify_channel_capability.py --quick
```

### P1-E3：`report_audit verdict` 口径认可通道

状态：已完成（2026-07-01）

来源反馈：

- `docs/dev-feedback-investment-research-deep-20260701.md` §3.4。
- 已知口径差异已经在报告脚注解释时，`report_audit verdict` 仍把超阈值差异列为警告或失败，主 Agent 需要额外人工说明。

目标文件：

- `tools/report_audit.py`
- `codex/ai-berkshire/scripts/tools/report_audit.py`
- `tests/test_report_audit.py`
- `skills/investment-research.md`
- `codex/ai-berkshire/references/skills/investment-research.md`
- `docs/ROADMAP.md`
- `docs/dev-feedback-action-plan.md`

验收点：

- results JSON 每项支持可选 `caliber_ack: true` 与非空 `caliber_note`。
- 超阈值差异在 `caliber_ack` 有效时不计入警告或失败，而是进入单独的「口径认可」计数。
- 空 `caliber_note` 不认可，避免滥用。
- verdict 输出 JSON 保留 `caliber_ack_count` 与 `caliber_ack_items`，便于 Agent/CI 后续读取。

完成记录：

- `render_verdict()` 新增 `caliber_ack_items` 分类，摘要区分「通过/口径认可/警告/不通过」。
- extract JSON 模板新增 `caliber_ack` 与 `caliber_note` 字段提示。
- `/investment-research` 抽检流程要求超阈值口径差异必须在报告中解释，并在 JSON 中填写 `caliber_ack` + `caliber_note`。
- root 工具、Codex bundled 副本、root skill 与 Codex reference 已同步。

验证命令：

```powershell
python -m pytest tests/test_report_audit.py -q
python tools\verify_channel_capability.py --quick
```

## 5. 反馈入口动作

本次已将“执行 agent 的代码级复盘”从普通 `usage-feedback` 中分离，新增：

- `docs/dev-feedback.md`
- `.github/ISSUE_TEMPLATE/dev-feedback.yml`

使用边界：

- 普通用户说“好不好用、卡在哪里”继续用 `docs/usage-feedback.md`。
- 安装失败继续用 `docs/install-feedback.md`。
- agent 或维护者能提供错误链、命令输出、源码位置、最小复现和修复建议时，使用 `docs/dev-feedback.md`。

后续可以在收集到多个 dev-feedback 后，增加脚本把 machine-readable JSON 汇总成 P1 backlog。

## 6. 建议执行顺序

1. 先做 P1-A1，解决报告准出工具会崩溃和负号丢失的问题。
2. 再做 P1-A2，让完整投研数据包可落盘复现。
3. 再做 P1-A3，降低三情景估值和交叉验证的误用概率。
4. 然后做 P1-B1/B2/B3，把 skill 文档和口径/降级元数据补齐。
5. 最后做离线 fixture 和 CI，把这些问题变成长期回归测试。=> 已完成 P1-C1。

## 7. 二次运行验证证据（2026-07-01 腾讯 deep 档）

`20ea36d9` 后的修复经 `1ae451ce` 运行二次验证，结果记录于 `docs/dev-feedback-investment-research-deep-20260701.md`：

| 修复项 | 二次验证结论 | 证据 |
|--------|------------|------|
| P1-A1 report_audit 数值韧性 | ✅ 生效 | E8/E9 不再崩溃，`_to_numeric` 与 `_SIGNED_NUM` 生效 |
| P1-A2 datapack 落盘 | ✅ 生效 | `-o _tmp_00700_datapack.json` 落盘成功 |
| P1-A3 rigor 参数防呆 | ✅ 生效 | `--growth 30 15 -5` 自动转 0.30/0.15/-0.05 + stderr 警告；`--caliber` 与量级告警可用 |
| P1-B1 Agent 降级记录 | ✅ 生效 | 报告附录 A 完整记录 Explore Agent 与 exa-1 两项降级 |
| P1-B2 港股行业对比降级 | ⚠️ 默认路径生效，`--no-mx` 路径未覆盖 | `industry-compare 00700` 含 alternatives；`--no-mx` 输出为空 |
| P1-B3 财务口径元数据 | ⚠️ 代码层生效，报告层执行力不足 | caliber_metadata 进入 datapack；但 29 个数据表仅 1 个含口径列 |
| P1-C1 离线 CI 门禁 | ✅ 生效 | fixture 与 workflow 就位 |
| P1-D1 release notes | ✅ 生效 | 与本次运行无直接关系，工具可用 |

## 8. 下一轮 P1 反馈驱动修复候选（来自腾讯 deep 档）

按准出摩擦优先级排序，详见 `docs/dev-feedback-investment-research-deep-20260701.md` §3 与 §5：

- **P1-E1**：`report_audit` 单位归一化（§3.1）——extract 保留 unit 但 verdict 不归一化，fetched_value 单位错配触发 9900% 假偏差。目标 `tools/report_audit.py`，加 `report_unit`/`fetched_unit` 字段与已知换算归一化。=> 已完成。
- **P1-E2**：`report_audit` CLI `-o/--output`（§3.2）——verdict stdout 混日志头需清洗。参考 `lxr_data.py datapack -o`。=> 已完成。
- **P1-E3**：`report_audit` verdict `caliber_ack` 通道（§3.4）——已知口径差异占警告额度，缺认可通道。=> 已完成。
- **P2-E4**：港股 `--no-mx` 路径透 alternatives（§3.5）——文档示例路径的覆盖盲点。
- **P2-E5**：口径列覆盖率检查（§3.3）——让"所有核心数据表"从软约束变机器检查。
- **P2-E6**：港股年报 `reportType` 兜底（§3.6）——本次主 Agent 内联修复，应固化。
- **P3-E7/E8**：Agent 降级"必要信息"标准示例（§3.7）、action-plan 二次验证字段（§3.8，本节已示范）。
