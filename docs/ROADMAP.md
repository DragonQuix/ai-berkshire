# ai-berkshire Roadmap

## P0：已完成（2026-06-28）

> 状态：P0 已关闭。后续开发重心转入 P1。以下能力作为当前基线维护，不再把席位画像库持续扩展、更多免费 A 股财务/行情源覆盖、真实题材板块龙虎榜对比列为近期目标。

### 权限安全多 Agent 架构加固
> 2026-06-28 已落地：`docs/source-pack-templates.md` 标准化 5 类 source pack；`tools/verify_multi_agent_permissions.py` 扫描高风险后台 Agent 旧句式；`tools/verify_channel_capability.py --quick` 已覆盖 root/Codex reference SHA256 同步检查（数量随 skill 增减由 `EXPECTED_SKILL_COUNT` 维护，2026-06-29 起 19）。

- 已完成团队类 Skill 的 source pack 模板标准化，覆盖上市公司、财报、未上市公司、新闻异动和公众号文章
- 已新增静态校验脚本，扫描 `skills/*.md` 与 Codex reference 中的高风险后台 Agent 取数/写文件句式
- 已扩展同步校验，覆盖全部 19 个 Skill 的 root/codex reference SHA256 一致性
- 参考 ADR：`docs/adr/2026-06-28-permission-safe-multi-agent.md`

### A股数据源接入
> 2026-06-28 已新增小切片：`tools/ashare_data.py lhb` 与 `tools/lxr_data.py lhb` 接入东方财富龙虎榜免费源；同日继续新增 `lhb-detail`，按 `TRADE_ID` 或 `code + date` 拉取买卖席位明细，并补充 `seat_profile` / `seat_profile_summary` 做席位画像与游资识别。随后新增 `lhb-detail --start-date --end-date` 区间批量筛选，先筛龙虎榜记录再按 `trade_id` 拉详情，并在记录层输出 `seat_amount_summary` 聚合机构/北向/游资/营业部买卖净额、`seat_flow_analysis` 标注资金主导方；区间 payload 追加 `range_flow_summary` 作为多日聚合摘要，追加 `range_seat_profile_summary` 按过滤后记录聚合席位画像、别名净额与 top seats，并内置 `recognition_summary` 汇总可识别席位数量、游资别名数、可识别净额绝对值、游资净额绝对值、可识别主导类型、席位/净额占比和 `top_youzi_seats`，同时输出按游资 alias 聚合并按绝对净额排序的 `youzi_alias_strengths`，作为后续同板块辨识度对比的别名排序基础；继续新增 `lhb-compare`，支持用户给定 2-4 个代码做同区间龙虎榜辨识度排序，复用既有区间模式与过滤条件，`rows` 直接带行级游资辨识标签、共同/独有占比、综合辨识分和排行原因，并支持 `--sort-by youzi_recognition_score` 显式按综合辨识分排序，支持 `--min-recognition-score` 过滤低综合辨识分行并保留 `filtered_out_codes`；继续新增 `lhb-industry-compare`，基于理杏仁申万行业成分自动取锚定股票同板块最多 4 个代码再复用 `lhb-compare`，非 JSON 输出直接展示对比可用性、命中覆盖、领先差距、组合信号、Top 游资横向对比、方向一致性/分歧摘要、共同/独有游资贡献 Top、行级辨识分和标签，并在 `comparison_summary` 汇总命中覆盖、对比可用性、共同游资 alias、alias 覆盖频次、共同游资强度占比、共同游资集中度、每股共同/独有游资贡献度、每股游资辨识来源标签、标签数量/占比汇总、综合辨识度排行、领先代码与第二名分差、每股 Top 游资别名横向对比、共同/独有/方向/集中度组合信号、跨代码 alias 净额强度、同向/分歧方向及方向一致性汇总和领先代码。输出 canonical `_source: legacy` 或 `lixinger+legacy`，详细渠道写入 `source_detail`。

- 已接入东方财富龙虎榜免费源，并经 `lxr_data.py` 统一入口输出 `_source` / `source_detail`
- 已覆盖 A 股龙虎榜列表、买卖席位明细、区间聚合、多股对比、同申万行业对比
- 已保留既有 A 股财务、行情免费源兼容入口
- 冻结项：不继续追踪席位画像库扩展、更多免费 A 股财务/行情源覆盖、真实题材板块龙虎榜对比；如未来重新需要，再从 P1/P2 重新立项

## P1：下一阶段

> 状态：多项已落地。HTML 报告、多档深度模式、多股横向对比、团队研究产物结构升级均已落地；剩余 P1 项与 P2 长期目标待启动。后续优先目标应选择一个能端到端提升投研产物质量的切片，避免同时推进多个方向。

### HTML 报告输出
> 2026-06-29 已落地：新增 `tools/md2html.py`，将 Markdown 投研报告转为单文件自包含 HTML。纯渲染层（`parse_markdown` → AST → `render_html`）与 CLI 拼装层分离，全部可 mock 测试。特性：暗色/浅色双主题一键切换（localStorage 记忆，默认暗色）、左侧导航栏由 H1-H3 自动生成并滚动高亮、表格数值列渲染为内嵌 CSS 条形图（正绿负红、百分比列以 0 为中点）、纯 Python 标准库零外部依赖、输出完全自包含无外链可离线传播。CLI 支持 `--no-sidebar`/`--light`/`--stdin`/`-o` 选项。新增 68 个单元测试（`tests/test_md2html.py`）覆盖解析、渲染、CLI 三层。codex 副本同步至 `codex/ai-berkshire/scripts/tools/`。`EXPECTED_SKILL_COUNT` 不变（19，未新增 skill）。

- 在 Markdown 基础上增加 HTML 报告格式
- 支持暗色模式、导航栏、图表可视化
- 提升报告传播性和阅读体验

### 多档深度模式
> 2026-06-29 已落地：新增 `docs/depth-profiles.md`（三档定义表 + 通用杠杆表 + 8 个核心技能各 lite/standard/deep 行为矩阵），codex 副本同步至 `codex/ai-berkshire/references/depth-profiles.md`（SHA256 一致）。8 个核心技能（investment-research/earnings-review/industry-research/investment-team/earnings-team/quality-screen/industry-funnel/compare）头部加"深度模式选择"小节，采用纯引用形态指向中心文档对应小节（DRY，单一事实源，不重复速览表）。`verify_channel_capability.py` 新增 `check_depth_profile_sync()` 校验 root/codex 的 depth-profiles.md SHA256 一致（--quick 即执行）。CLAUDE.md 与 AGENTS.md 同步追加"多档深度模式"小节（两文件逐字一致），约定 `--depth lite|standard|deep` 参数与 lite 报告加 `-lite` 后缀。codex/ai-berkshire/SKILL.md 追加深度模式引用行（保留原有工作流指引）。`EXPECTED_SKILL_COUNT` 不变（19，深度模式是现有 skill 的参数化，不新增 skill 文件）。本次重新落地规避了上次被 revert 撤销方案的 3 个缺陷：A) CLAUDE.md 改动原子化、不与双平台化捆绑且同步 AGENTS.md；B) codex SKILL.md 追加而非替换原有指引；C) skill 头部纯引用避免与中心文档内容重复漂移。

- `lite`：5分钟速判，快速给出估值区间和核心结论
- `standard`：当前默认模式，完整多Agent研究
- `deep`：增加更多交叉验证和历史类比，机构级深度

### 多股横向对比
> 2026-06-29 已落地：新增 `tools/lxr_data.py compare` 子命令与 `/compare` skill（root+codex）。`compare` 复用 `get_financials` + `get_valuation`（理杏仁首选自动降级），把 2-4 只股票对齐到最新公共年报期，输出 8 财务 + 5 估值维度的对比矩阵（★领先标记、越低/越高越好方向、平局提示、`_source` 来源标注）与综合领先摘要；纯计算层（`align_compare_dimensions` / `build_compare_matrix` / `pick_compare_leader` / `render_compare_markdown`）与 CLI 拼装层分离，全部可 mock 测试。`/compare` skill 固化"工具只覆盖结构化维度、护城河/管理层/确定性由分析者裁决、结构化领先不等于投资结论、便宜背后有代价、跨期防统计幻觉"等约束，对齐 AGENTS.md 核心原则。`verify_channel_capability.py` 的 `EXPECTED_SKILL_COUNT` 同步 18→19。

- 支持 2-4 只股票同维度横向对决
- 同行业公司估值对标
- 输出对比矩阵和择优建议

### 团队研究产物结构升级
> 2026-06-28 已启动第一切片：新增 `docs/team-research-output-contract.md`，将团队研究必需产物、关键数据溯源、角色冲突仲裁与准出规则固化为可测试 contract，并要求 `/investment-team` 遵循。同日继续新增 `tools/team_research_outputs.py`，可初始化 `data-pack.json`、`source-index.md`、`role-briefs/`、`audit-results.json` 和 `最终报告.md` 空模板；`audit-results.json` 初始 `verdict` 为 `reject`，防止未抽检即发布。随后追加 `validate` 子命令，用于准出前检查必需产物、JSON 结构、最终报告溯源/仲裁小节、未定义来源 ref，并继续覆盖 `data-pack.json.source_refs` 与 `audit-results.json.items[*].source_ref`。
>
> 2026-06-28 继续推进第二切片（抽检闭环）：`tools/team_research_outputs.py` 新增 `audit-extract` 子命令，从最终报告采样（复用 `tools/report_audit.py` 的抽取与采样逻辑）直接生成 `audit-results.json.items[*]` 的 contract 结构（`status=pending`、`verdict` 重置为 `reject`），打通 `report_audit` 输出与 contract 格式之间需要手工翻译的鸿沟；`validate` 同步强化为校验 `items[*].status` 取值（`pass`/`fail`/`pending`）、必填字段、`pass`/`fail` 项须携带 `verified_value` 与 `source_ref`、`verdict` 为 `pass` 时 `items` 非空且全部 `status==pass`。`docs/team-research-output-contract.md` 与 `skills/investment-team.md`（root+codex）已固化抽检闭环流程。
>
> 2026-06-29 推进第三切片（role-briefs 内容校验）：`validate` 强化检查每份 `role-briefs/` 简报是否含全部 7 个必需小节标题（角色输入范围、核心结论与评分、使用的证据、反面证据、不确定性、补数请求、与其他角色可能冲突的判断），缺失即记入 `invalid_files` 打回，防止缺反面证据或不确定性小节的角色简报蒙混准出；校验只保证小节齐全，不替代 Team Lead 的内容质量判断。`docs/team-research-output-contract.md` 与 `skills/investment-team.md`（root+codex）同步固化。期间还修复独立审核发现的缺陷：`source_ref` 非标准格式绕过准出校验、`from report_audit import` 破坏包式导入、role-brief 标题子串匹配被三级标题/正文/代码块绕过。

- 默认生成 `data-pack.json`、`source-index.md`、`role-briefs/`、`audit-results.json` 与最终报告
- 最终报告中的关键数据能追溯到资料包或来源索引
- 角色结论与最终结论冲突时，必须写明 Team Lead 的仲裁理由
- `audit-results.json` 抽检清单可由 `audit-extract` 从最终报告自动生成，`validate` 把关 item 结构与 verdict/status 一致性
- 每份 role-brief 含全部 7 个必需小节标题，`validate` 缺失即打回

## P2：长期（6个月+）

### 测试覆盖
> 2026-06-29 已启动第一切片：`financial_rigor.py` 回归测试从 2 个扩展到 14 个，覆盖股息率口径、市值偏差阈值、估值比率、交叉验证、Benford 小样本/异常分布、`calc` 安全白名单，以及 Windows GBK stdio 下 CLI 不因 emoji 输出触发 `UnicodeEncodeError` 的回归场景。同日修复 `financial_rigor.py` CLI 入口的 stdout/stderr UTF-8 重配，并同步 Codex 工具副本。
>
> 2026-06-29 继续推进第二切片：新增 `tests/test_skill_output_regressions.py`，锁定 12 个报告类 Skill 的输出路径、报告命名、数据抽检/估值验算关键命令，并同时覆盖 root skill 与 Codex reference。同步修正 6 个旧输出路径漂移：`investment-research`、`earnings-review`、`industry-research`、`investment-checklist`、`management-deep-dive`、`thesis-tracker` 不再指向 `~/...` 或 reports 根目录旧格式，统一回到 `AGENTS.md` 约定的 `reports/` 公司目录或行业根目录命名规范。
>
> 2026-06-29 继续推进第三切片：新增 `tests/test_report_audit.py`，直接覆盖 `report_audit.py` 的 Markdown 表格/KV 数据点抽取、抽样比例/种子/行号排序、准出/打回/警告判决、CLI extract/verdict 退出码和 root/Codex 工具副本同步。期间修复两个准出链路缺陷：CLI 在 Windows GBK stdio 下输出中文/emoji 会乱码或触发 `UnicodeEncodeError`，以及单一核验来源超出 2% 容差时被误判为警告并返回 exit 0；现在单来源超阈值会打回并返回非 0，双来源一过一不过才保留为警告。

- 为核心工具（financial_rigor.py 等）增加单元测试
- 为 Skill 输出增加回归测试
- 确保迭代不破坏已有功能

### 组合级分析
> 2026-06-29 已启动第一切片：新增 `tools/portfolio_analyzer.py`，提供离线组合结构诊断。工具接受 JSON 持仓，自动归一化百分数/小数权重，输出 `overall_health`、`concentration`、`exposures`、`risk_flags` 与 `correlation_risks`，覆盖非现金持仓数、现金占比、第一大/前三大持仓、HHI/有效持仓数、行业/地域/货币/主题暴露和基于同业/同地区/同货币/共同主题的相关性风险。`/portfolio-review` 已加入该工具作为组合层面分析底稿，Codex 工具副本与 reference 同步，并新增回归测试锁定 CLI、Markdown/JSON 输出和双平台同步。
>
> 2026-06-29 继续推进第二切片：`portfolio_analyzer` 新增 `stress_tests`，按持仓行业、地域、货币与主题标签估算全球衰退、中美/地缘风险、利率飙升和 AI Capex 下行四类结构化压力情景，输出组合影响、风险等级和前三大拖累项；渲染层拆分为 `tools/portfolio_render.py`，压力测试计算拆分为 `tools/portfolio_stress.py`，保持单文件规模约束。`/portfolio-review` 已要求报告引用 `stress_tests`，并新增回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-29 继续推进第三切片：`portfolio_analyzer` 新增 `opportunity_cost`，读取持仓级 `expected_return` 与 `conviction`，计算 `risk_adjusted_return = expected_return × conviction`，按风险调整后预期年化排序，并输出低于 4% 现金门槛的持仓、最弱持仓与缺失输入列表；机会成本计算拆分为 `tools/portfolio_opportunity.py`，Markdown 报告新增“机会成本”章节。`/portfolio-review` 已要求输入和报告引用 `opportunity_cost`，并继续用回归测试锁定 root/Codex 同步。
>
> 2026-06-29 继续推进第四切片：新增 `examples/portfolio-holdings.sample.json`，作为 `portfolio_analyzer` 和 `/portfolio-review` 的最小可运行样例；样例包含结构诊断、压力测试和机会成本所需字段，并同步到 Codex 包内。新增 smoke test 直接用样例跑 CLI 的 Markdown/JSON 输出，防止后续字段契约漂移。
>
> 2026-06-30 继续推进第五切片：`portfolio_analyzer` 新增 `rebalance_suggestions`，将机会成本、第一大持仓集中度和现金缓冲转成机械再平衡建议，输出首要动作、逐项 action/priority/current_weight/suggested_weight/reason；计算逻辑拆分为 `tools/portfolio_rebalance.py`，Markdown 报告新增“再平衡建议”章节，`/portfolio-review` 已要求报告引用该字段并明确机械建议不替代个股估值和最终交易判断。新增回归测试锁定 JSON 字段、Markdown 章节和 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第六切片：`portfolio_analyzer analyze` 新增 `--cash-hurdle` 参数，支持用小数或百分数覆盖默认 4% 现金门槛；`analyze_portfolio()` 同步开放 `cash_hurdle` 入参，机会成本排序和 `rebalance_suggestions` 共用该门槛，便于在利率环境变化时调整“不如现金”的判断标准。`/portfolio-review` 已补充参数用法，回归测试锁定 CLI/API 行为和技能文档契约。
>
> 2026-06-30 继续推进第七切片：`portfolio_analyzer` 新增 `allocation_drift`，支持持仓输入可选 `target_weight`、`min_weight`、`max_weight`，输出目标仓位偏离、上下限状态、需关注列表和最大偏离项；计算逻辑拆分为 `tools/portfolio_allocation.py`，Markdown 报告新增“目标仓位偏离”章节。`/portfolio-review` 已补充目标仓位字段说明，回归测试锁定 JSON 字段、Markdown 章节、技能契约和 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第八切片：`allocation_drift` 新增目标调仓测算，输出 `buy_to_target`、`sell_to_target`、`turnover_to_target` 与 `unmatched_cash_delta`，用于估算回到目标仓位需要的买入/卖出规模和理论换手率；Markdown “目标仓位偏离”章节同步展示理论换手率和目标买卖合计，`/portfolio-review` 已要求引用 `allocation_drift.turnover_to_target`。
>
> 2026-06-30 继续推进第九切片：`allocation_drift` 新增目标仓位覆盖度诊断，输出 `target_weight_sum`、`target_gap_to_full_allocation`、`targeted_current_weight` 与 `untargeted_current_weight`，用于识别目标仓位是否只覆盖部分组合或目标权重合计偏离 100%；Markdown “目标仓位偏离”章节同步展示目标仓位合计、未分配目标和已/未设目标持仓当前占比，`/portfolio-review` 已要求引用 `allocation_drift.target_weight_sum`。
>
> 2026-06-30 继续推进第十切片：`rebalance_suggestions` 接入 `allocation_drift`，在机会成本之后、集中度之前优先输出目标仓位/上下限偏离对应的机械加减仓动作（`trim_to_target` / `add_to_target`），避免“诊断发现目标偏离但调仓建议只看集中度”的断层；`/portfolio-review` 已同步要求再平衡建议引用目标仓位偏离。
>
> 2026-06-30 继续推进第十一切片：`allocation_drift` 新增回到约束区间的最小调仓测算，逐项输出 `adjustment_to_band`，聚合输出 `buy_to_band`、`sell_to_band`、`turnover_to_band` 与 `unmatched_band_cash_delta`；该口径优先用于只有 `min_weight` / `max_weight`、没有 `target_weight` 的持仓，保留既有 `turnover_to_target` 精确回到目标仓位语义。Markdown 报告和 `/portfolio-review` 已要求展示 `allocation_drift.turnover_to_band`。
>
> 2026-06-30 继续推进第十二切片：组合输入解析拆分为 `tools/portfolio_input.py`，并新增目标仓位约束一致性校验；`min_weight > max_weight`、`target_weight < min_weight`、`target_weight > max_weight` 会在分析前直接打回，避免自相矛盾的约束进入 `allocation_drift` 和 `rebalance_suggestions`。
>
> 2026-06-30 继续推进第十三切片：`portfolio_input.as_ratio()` 新增比例上限校验，`target_weight` / `min_weight` / `max_weight` 与 CLI `--cash-hurdle` 换算后不得超过 100%；输入 `150` 这类超过 100% 的比例会在进入组合分析前直接打回。
>
> 2026-06-30 继续推进第十四切片：`portfolio_input` 新增持仓 `weight` 上限校验，单项权重不得超过 100%；此前 `target_weight` / `min_weight` / `max_weight` 已被限制在 0-100%，本切片补齐原始持仓权重字段的同类输入卫生，避免 `weight=150` 被归一化后静默进入组合诊断。`/portfolio-review` 已同步说明 `weight` 必须大于 0 且不得超过 100%，并继续用回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第十五切片：修复 `portfolio_opportunity` 中显式 `conviction=0` 被 `or 1.0` 误当成缺省 100% 置信度的问题；现在只有缺省 `conviction` 才按 100% 处理，显式 0 会保留为 0%，避免机会成本和再平衡建议高估低置信度持仓。`/portfolio-review` 已同步说明该口径，并用回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第十六切片：`portfolio_opportunity` 拆分 `expected_return` 与 `conviction` 的比例解析，保留预期收益超过 100% 的表达能力，但将 `conviction` 严格限制在 0-100%；输入 `conviction=150` 会在机会成本计算前直接打回，避免风险调整后收益被不可能的置信度放大。`/portfolio-review` 已同步说明 `conviction` 不得超过 100%，并用回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第十七切片：`portfolio_analyzer analyze` 对输入校验类 `ValueError` 改为输出简洁 `错误: ...` 并返回 exit 2，不再把 Python traceback 暴露给报告使用者；无效持仓字段、JSON 结构错误和 `--cash-hurdle` 越界都走同一 CLI 错误出口。新增回归测试锁定无效 `conviction` 不出现 `Traceback`，并继续同步 Codex 工具副本。
>
> 2026-06-30 继续推进第十八切片：`portfolio_analyzer analyze` 对输入文件读取失败追加友好错误，缺失文件或无法读取时输出 `错误: 无法读取输入文件 ...` 并返回 exit 2，不再暴露 Python traceback；新增回归测试锁定缺失文件路径、无 traceback 和 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第十九切片：`portfolio_analyzer analyze` 对 malformed JSON 追加友好解析错误，输出 `错误: 输入 JSON 解析失败 ... 第 N 行第 M 列` 并返回 exit 2，不再只暴露 Python `JSONDecodeError` 英文信息；新增回归测试锁定损坏 JSON 文件路径、行列提示、无 traceback 和 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第二十切片：`portfolio_analyzer analyze` 对 JSON 语法合法但结构不符合契约的输入追加文件上下文，输出 `错误: 输入 JSON 结构错误 <path>: 必须是持仓数组，或包含 holdings 数组的对象` 并返回 exit 2；新增回归测试锁定错误文件路径、结构错误前缀、无 traceback 和 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第二十一切片：`portfolio_analyzer analyze` 对合法 JSON 但持仓字段不符合契约的输入追加文件上下文，输出 `错误: 输入持仓字段错误 <path>: ...` 并返回 exit 2；`--cash-hurdle` 等 CLI 参数错误仍保持参数级提示，不混入文件路径。新增回归测试锁定字段错误路径、错误前缀、无 traceback，并同步 `/portfolio-review` 文档契约与 Codex 工具副本。
>
> 2026-06-30 继续推进第二十二切片：`portfolio_input.as_ratio()` 从“必须大于 0”调整为“不可为负数且不得超过 100%”，使 `target_weight` / `min_weight` / `max_weight` 可显式填 0，对应清仓目标或 0% 约束边界；`portfolio_analyzer analyze --cash-hurdle 0` 也可用于零现金门槛场景。持仓 `weight` 仍必须大于 0，避免空仓位进入归一化。新增回归测试锁定 0% 目标/上下限和 CLI 零现金门槛，并同步 `/portfolio-review` 文档契约与 Codex 工具副本。
>
> 2026-06-30 继续推进第二十三切片：`allocation_drift` 新增 `target_allocation_status`，按目标仓位合计识别 `under_allocated` / `fully_allocated` / `over_allocated` / `not_configured`，避免报告只展示 `target_gap_to_full_allocation` 负数而缺少语义；Markdown “目标仓位偏离”章节同步展示中文目标覆盖状态，`/portfolio-review` 已要求引用该字段。
>
> 2026-06-30 继续推进第二十四切片：Markdown “目标仓位偏离”章节对 `over_allocated` 不再显示负的“未分配目标”，改为用正数展示“目标超配”，`under_allocated` 继续展示“未分配目标”；`/portfolio-review` 已同步固化该展示口径，防止报告使用负数缺口表达目标超配。
>
> 2026-06-30 继续推进第二十五切片：Markdown “目标仓位偏离”章节对 `not_configured` 不再显示“未分配目标：100.0%”，改为显示“目标差额：未配置”，避免把没有设置目标仓位误读成仍有 100% 目标待分配；`/portfolio-review` 已同步固化该展示口径。
>
> 2026-06-30 继续推进第二十六切片：Markdown “目标仓位偏离”明细表状态列从内部枚举 `overweight` / `underweight` / `within_band` 改为中文“超配 / 低配 / 约束内”，JSON 结构字段保持不变；`/portfolio-review` 已同步要求报告状态列使用中文。
>
> 2026-06-30 继续推进第二十七切片：Markdown “再平衡建议”动作列从内部枚举 `reduce_or_exit` / `trim_to_limit` / `raise_cash` / `fill_inputs` 等改为中文动作（减仓/清仓、下调至集中度上限、提高现金、补齐输入等），JSON 结构字段保持不变；`/portfolio-review` 已同步要求报告动作列使用中文。
>
> 2026-06-30 继续推进第二十八切片：Markdown “再平衡建议”优先级列从内部枚举 `high` / `medium` / `low` 改为中文“高 / 中 / 低”，并同步默认无建议行的“维持观察”动作中文化；JSON 结构字段保持不变，`/portfolio-review` 已同步要求优先级列和动作列均使用中文。
>
> 2026-06-30 继续推进第二十九切片：Markdown “相关性风险”“压力测试”和“风险提示”中的风险等级从内部枚举 `high` / `medium` / `low` 改为中文“高 / 中 / 低”；JSON 中的 `risk_level` / `level` 字段保持不变，`/portfolio-review` 已同步要求风险等级展示中文化。
>
> 2026-06-30 继续推进第三十切片：Markdown “相关性风险”驱动因素列从内部枚举 `same_industry` / `same_region` / `same_currency` / `shared_theme:*` 改为中文“同行业 / 同地区 / 同货币 / 共同主题：*”；JSON 中的 `drivers` 字段保持不变，`/portfolio-review` 已同步要求相关性驱动因素展示中文化。
>
> 2026-06-30 继续推进第三十一切片：Markdown “机会成本”章节显式展示 `opportunity_cost.weakest_holding` 对应的“最弱持仓”和风险调整后收益，避免读者只能从排序表末行推断；JSON 结构字段保持不变，`/portfolio-review` 已同步要求机会成本段展示最弱持仓。
>
> 2026-06-30 继续推进第三十二切片：Markdown “机会成本”章节的“低于现金门槛”列表从只展示名称升级为同时展示每个持仓的风险调整后收益，便于直接判断低于门槛的幅度；JSON 结构字段保持不变，`/portfolio-review` 已同步要求该列表展示风险调整后收益。
>
> 2026-06-30 继续推进第三十三切片：`portfolio_opportunity` 放开 `expected_return` 的负数输入，用于表达看跌或论文破产场景；`-5` 与 `-0.05` 均会解析为 -5%，并继续参与机会成本排序、低于现金门槛列表和最弱持仓判断。`conviction` 仍严格限制在 0-100%，`--cash-hurdle` 仍不可为负且不得超过 100%。`/portfolio-review` 已同步说明负预期收益口径，并用回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第三十四切片：`portfolio_opportunity` 对 `expected_return` 与 `conviction` 的非数字输入追加字段级中文错误，统一返回 `标的.字段 必须是数字`，CLI 继续包装为 `错误: 输入持仓字段错误 <path>: ...` 且不暴露 Python 原生 `could not convert string` 或 traceback。`/portfolio-review` 已同步说明该输入卫生契约，并用回归测试锁定 API 与 CLI 行为及 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第三十五切片：`rebalance_suggestions` 的补输入建议原因与 `opportunity_cost` 口径对齐；缺少 `expected_return` 的持仓会触发 `fill_inputs`，提示“缺少 expected_return，无法纳入机会成本排序”，而缺省 `conviction` 按 100% 处理、不再被误写为缺失字段。`/portfolio-review` 已同步说明缺省 `conviction` 不视为缺失输入，并用回归测试锁定 root/Codex 工具副本同步。
>
> 2026-06-30 继续推进第三十六切片：Markdown “机会成本”章节对缺少 `expected_return` 的持仓显式加上 `数据不足：缺少预期收益输入：...`，与 `/portfolio-review` 的诚实留白原则对齐，避免只写“缺少预期收益输入”而没有数据不足标记。JSON 结构字段保持不变，Codex 工具副本同步，并用回归测试锁定该展示口径。
>
> 2026-06-30 继续推进第三十七切片：Markdown “压力测试”章节补齐 `risk_level=severe` 的中文展示，输出“严重”而不是内部枚举 `severe`；JSON 结构字段保持不变，`/portfolio-review` 已同步要求风险等级展示为“严重 / 高 / 中 / 低”，并用回归测试锁定该展示口径。
>
> 2026-06-30 继续推进第三十八切片：`overall_health` 接入 `stress_tests`，当任一压力情景风险等级为 `severe` 时，整体健康度直接降为“问题严重”，避免报告一边显示严重压力测试、一边仍给出“需要调整”的低估判断。`/portfolio-review` 已同步说明该联动口径，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第三十九切片：`overall_health` 新增 `drivers` 与动态 `summary`，把整体健康度评级的触发原因显式输出，覆盖严重压力测试、单一暴露、相关性风险和集中度判断；Markdown 顶部同步展示“健康度依据”，避免读者只看到评级而看不到为什么被降级。`/portfolio-review` 已同步要求引用该依据，Codex 工具副本同步，并用回归测试锁定 JSON 与 Markdown 两层输出。
>
> 2026-06-30 继续推进第四十切片：`overall_health` 新增 `primary_driver`，把 `drivers` 中优先级最高的风险提炼为“当前最大风险”；Markdown 顶部同步展示该字段，直接对齐 `/portfolio-review` 结论必须回答“当前最大风险是什么”的准出要求。Codex 工具副本同步，并用回归测试锁定 JSON 与 Markdown 输出。
>
> 2026-06-30 继续推进第四十一切片：Markdown 顶部新增“最应该做的一件事”，直接引用 `rebalance_suggestions.primary_action`，让组合报告开头同时回答健康度、当前最大风险和首要动作三项结论问题。`/portfolio-review` 已同步该准出要求，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十二切片：`portfolio_analyzer` 新增 `executive_summary`，把 `overall_health.rating`、`overall_health.primary_driver`、`rebalance_suggestions.primary_action` 与 `overall_health.summary` 汇总为 JSON 层首屏结论契约；Markdown 顶部改为从 `executive_summary` 渲染整体健康度、当前最大风险、最应该做的一件事和健康度依据，避免 JSON 消费者与报告展示各自拼字段造成漂移。`/portfolio-review` 已同步要求引用该字段，Codex 工具副本同步，并用回归测试锁定 JSON 与 Markdown 两层输出。
>
> 2026-06-30 继续推进第四十三切片：`executive_summary` 新增 `action_method`，把 `rebalance_suggestions.method` 提升到首屏摘要契约；Markdown 顶部同步展示“首要动作口径”，明确机械再平衡建议不替代个股研究或最终交易判断，避免读者只看到“最应该做的一件事”而误读为直接交易指令。`/portfolio-review` 已同步要求展示该字段，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十四切片：`executive_summary` 新增 `data_gap_summary`，把 `opportunity_cost.missing_inputs` 中缺少 `expected_return` 的持仓前置到首屏摘要；Markdown 顶部同步展示“数据缺口”，即使首屏已经给出健康度、最大风险和首要动作，也会明确提示哪些持仓缺少预期收益输入，避免机会成本排序和机械建议被误读为完整数据基础上的结论。`/portfolio-review` 已同步要求引用该字段，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十五切片：`overall_health` 接入 `opportunity_cost.below_cash_hurdle`，当任一持仓风险调整后收益低于现金门槛时，整体健康度至少降为“需要调整”，并在 `drivers` / `primary_driver` / `summary` 中写入“机会成本：X 低于现金门槛”；修复此前结构分散组合可能显示“良好”但首要动作却建议减仓的首屏矛盾。`/portfolio-review` 已同步说明该降级口径，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十六切片：`overall_health` 接入 `opportunity_cost.missing_inputs`，当组合结构、暴露、相关性与压力测试均未触发更强风险，但缺少 `expected_return` 时，整体健康度标为“数据不足”，并在 `drivers` / `primary_driver` / `summary` 中写入“数据缺口：缺少预期收益输入：X”；避免首屏一边提示数据缺口，一边把组合评为“良好”。`/portfolio-review` 已同步说明该数据不足口径，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十七切片：`rebalance_suggestions` 增加低配缺输入冲突消解；当持仓低于目标仓位或下限但缺少 `expected_return` 时，不再直接输出 `add_to_target` 加仓建议，而是先输出 `fill_inputs`，且同一标的不重复出现在再平衡表中。避免机械目标仓位建议绕过机会成本数据缺口。`/portfolio-review` 已同步说明“低配但缺预期收益先补输入、不直接加仓”的口径，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十八切片：`portfolio_input` 增加持仓名称唯一性校验；同一组合输入内出现重复 `name` 会在分析前直接打回，避免 `opportunity_cost.missing_inputs`、`rebalance_suggestions`、权重映射和 Markdown 明细表把两个持仓混成同一标的。`/portfolio-review` 已同步说明 `name` 必须唯一，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第四十九切片：`portfolio_input` 增加非空 `code` 唯一性校验；不同 `name` 若填写同一股票代码会在分析前直接打回，避免名称伪装成多标的但实际代码相同，导致集中度、机会成本和再平衡建议身份混淆。`/portfolio-review` 已同步说明非空 `code` 必须唯一，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-06-30 继续推进第五十切片：`portfolio_analyzer` 新增 `valuation_sanity` 估值水位张力校验，闭合"`percentiles` 已取但未回流约束机会成本"的端到端断层。新增可选输入字段 `pe_percentile`（自身 PE 历史分位点，0-100%，缺省不校验，复用 `_optional_ratio` 口径），新增纯计算层 `tools/portfolio_valuation_sanity.py`，检测两类张力：高估高预期（PE 分位 ≥ 80% 且预期年化 ≥ 15%，风险信号，触发整体健康度降级）与低估低预期（PE 分位 ≤ 20% 且预期年化 ≤ 4%，机会信号，不降级健康度）。张力通过 `overall_health.drivers` / `primary_driver` 输出并触发至少"需要调整"降级，`executive_summary.valuation_sanity_summary` 前置标注存在张力的持仓，Markdown 新增"估值水位张力"小节（类型列中文"高估高预期 / 低估低预期"，不暴露 `high_valuation_high_return` / `low_valuation_low_return` 枚举）并紧随"机会成本"之后。`/portfolio-review` 已同步说明 `pe_percentile` 用法、张力检测阈值与"张力提示不替代个股估值判断，分析者需结合 D1/D2 人工裁决"口径，Codex 工具副本与样例同步，并用回归测试锁定 9 个新增场景与 root/Codex 副本同步。
>
> 2026-06-30 继续推进第五十一切片：`rebalance_suggestions` 接入 `valuation_sanity` 的高估高预期张力，避免目标仓位偏离和现金缓冲继续把高估张力标的作为机械加仓对象。低配但存在 `high_valuation_high_return` 的持仓不再输出 `add_to_target`，改为 `review_valuation_tension`，提示先复核 PE 分位与 `expected_return`；现金偏高时的 `deploy_cash_review` 会跳过高估高预期候选，优先研究无张力的高收益持仓，若所有候选都有高估张力则输出复核估值张力动作。Markdown 再平衡表新增中文动作“复核估值张力”，不暴露内部枚举。`/portfolio-review` 已同步说明该软门禁口径，Codex 工具副本同步，并用回归测试锁定低配门禁、现金部署候选过滤和 Markdown 中文化。
>
> 2026-06-30 继续推进第五十二切片：`rebalance_suggestions` 继续接入 `valuation_sanity` 的低估低预期张力，避免 PE 处于低估区但主观预期低于现金门槛的标的被机械建议直接减仓/清仓。低于现金门槛且存在 `low_valuation_low_return` 的持仓不再输出 `reduce_or_exit`，改为 `review_valuation_tension`，提示先复核估值水位与 `expected_return` 是否过低；普通低于现金门槛且无低估张力的持仓仍保持减仓/清仓建议。`/portfolio-review` 已同步说明该软门禁口径，Codex 工具副本同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十三切片：`rebalance_suggestions.primary_action` 补齐 `review_exposure` 的中文语义，单一暴露风险作为唯一机械建议时，首屏动作从泛化的“复核 X”改为“复核 X 单一暴露”，与再平衡明细表“复核暴露”保持一致，避免组合报告开头丢失风险类型。Codex 工具副本同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十四切片：`rebalance_suggestions.method` 补齐单一暴露作为机械建议驱动，首屏“首要动作口径”从只列机会成本、目标仓位、集中度、估值水位张力和现金缓冲，扩展为同时说明单一暴露，避免 `review_exposure` 动作有结论但没有方法口径。`/portfolio-review` 同步固化“复核暴露”动作及 `review_exposure` 枚举禁曝，Codex 工具副本与 skill reference 同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十五切片：`rebalance_suggestions` 的 `review_exposure` 从“取第一个风险提示”改为按风险等级与暴露权重选择最严重的单一暴露；当行业 55% 与主题 80% 同时超阈值时，机械建议优先复核 80% 主题暴露，避免类别遍历顺序压过真实风险强度。`/portfolio-review` 同步固化该选择口径，Codex 工具副本与 skill reference 同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十六切片：`review_exposure` 的建议优先级不再固定为 `low`，而是跟随被选中单一暴露的 `risk_flags.level`；中等暴露显示中优先级，高风险暴露显示高优先级，避免再平衡表低估 70%+ 单一暴露的处理紧迫性。`/portfolio-review` 同步固化该口径，Codex 工具副本与 skill reference 同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十七切片：`review_exposure.reason` 直接引用被选中 `risk_flags.message`，在再平衡明细中展示“X 暴露达到 Y%”，避免报告只提示单一暴露偏高却不说明偏高到多少。`/portfolio-review` 同步要求复核理由展示具体暴露比例，Codex 工具副本与 skill reference 同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十八切片：`rebalance_suggestions` 的现金缓冲类建议理由补齐当前现金占比与触发阈值；现金过低时展示“现金 X% 低于 3%”，现金过高部署或复核估值张力时展示“现金 X% 高于 35%”，避免再平衡表只说现金偏高/偏低却不给触发依据。`/portfolio-review` 同步要求现金缓冲理由展示当前现金占比与阈值，Codex 工具副本与 skill reference 同步，并用回归测试锁定。
>
> 2026-07-01 继续推进第五十九切片：`trim_to_limit.reason` 补齐第一大持仓当前占比；集中度机械建议从只展示“超过 40% 上限”，改为展示“第一大持仓 X% 超过 40% 集中度上限”，避免再平衡表给出下调动作但不说明触发幅度。`/portfolio-review` 同步要求集中度理由展示第一大持仓占比与上限，Codex 工具副本与 skill reference 同步，并用回归测试锁定。

- 持仓组合健康度评估
- 行业/地域集中度分析
- 相关性风险检测
- 机会成本（含负预期收益、字段级输入错误、缺失输入建议与数据不足展示，并纳入整体健康度降级/数据不足判断）、压力测试、目标仓位偏离、目标调仓测算、目标覆盖度、机械再平衡建议（含低配缺输入冲突消解、高估高预期加仓软门禁、低估低预期减仓软门禁、集中度理由展示第一大持仓占比与上限、现金缓冲理由展示当前占比与阈值、单一暴露首要动作与动作口径语义化、按风险等级与暴露权重选择复核对象、复核暴露优先级跟随风险等级、复核暴露理由展示具体比例）、首屏结论摘要、动作口径与数据缺口、可配置现金门槛、持仓名称/代码唯一性校验、估值水位张力校验（PE 分位与预期收益的张力，含不替代人工裁决口径）

### 权限安全架构回归样例
> 2026-06-29 已启动第一切片：新增 `examples/team-research-regression/tencent-supplement-loop/`，构造腾讯团队研究回归样例，覆盖 `data-pack.json`、`source-index.md`、四份 `role-briefs/`、`audit-results.json`、`最终报告.md` 与 `supplement-loop.md`。样例明确展示“角色只读提出补数请求 -> Team Lead 补 S3 资料 -> 第二轮分析修正结论 -> Team Lead 仲裁并抽检准出”的闭环，且 `audit-results.json.verdict=pass`、抽检项均绑定已定义 ref。同步到 Codex 包内，并新增回归测试验证样例可通过 `team_research_outputs.validate` 且 root/Codex 样例逐文件一致。
>
> 2026-06-29 继续推进第二切片：`tools/verify_channel_capability.py --quick` 接入 `examples/team-research-regression/*` 自动校验，逐个样例调用 `team_research_outputs.validate`，并递归比对 root/Codex 样例目录文件列表与内容，防止补数闭环样例失效或双平台漂移。
>
> 2026-06-30 继续推进第三切片：新增 `examples/team-research-regression/pinduoduo-conflict-arbitration/`，覆盖“商业角色强调低价心智 vs 风险角色强调价格竞争 -> Team Lead 补 S3 -> 最终报告双边保留并仲裁”的角色冲突样例。样例包含完整 `data-pack.json`、`source-index.md`、四份 `role-briefs/`、`audit-results.json`、`最终报告.md` 与 `supplement-loop.md`，`audit-results.json.verdict=pass` 且抽检项绑定 S1/S3/E1；同步到 Codex 包内，并新增回归测试验证样例可通过 `team_research_outputs.validate` 且 root/Codex 逐文件一致。

- 用腾讯、新华保险、拼多多、AI算力等历史案例验证新架构不会降低证据密度
- 至少一个样例展示“补数请求 -> Team Lead 补资料 -> 第二轮分析”的闭环
- 至少一个样例展示“角色冲突 -> Team Lead 补资料 -> 仲裁写入最终报告”的闭环
