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

- 为核心工具（financial_rigor.py 等）增加单元测试
- 为 Skill 输出增加回归测试
- 确保迭代不破坏已有功能

### 组合级分析
- 持仓组合健康度评估
- 行业/地域集中度分析
- 相关性风险检测

### 权限安全架构回归样例
- 用腾讯、新华保险、拼多多、AI算力等历史案例验证新架构不会降低证据密度
- 至少一个样例展示“补数请求 -> Team Lead 补资料 -> 第二轮分析”的闭环
