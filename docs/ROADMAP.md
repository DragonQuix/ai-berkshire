# ai-berkshire Roadmap

## P0：近期（1-2个月）

### 权限安全多 Agent 架构后续加固
> 2026-06-28 已落地：`docs/source-pack-templates.md` 标准化 5 类 source pack；`tools/verify_multi_agent_permissions.py` 扫描高风险后台 Agent 旧句式；`tools/verify_channel_capability.py --quick` 已覆盖 18 个 root/Codex reference SHA256 同步检查。

- 将团队类 Skill 的 source pack 模板标准化，覆盖上市公司、财报、未上市公司、新闻异动和公众号文章
- 新增静态校验脚本，扫描 `skills/*.md` 与 Codex reference 中的高风险后台 Agent 取数/写文件句式
- 扩展同步校验，覆盖全部 18 个 Skill 的 root/codex reference SHA256 一致性
- 参考 ADR：`docs/adr/2026-06-28-permission-safe-multi-agent.md`

### A股数据源接入
> 2026-06-28 已新增小切片：`tools/ashare_data.py lhb` 与 `tools/lxr_data.py lhb` 接入东方财富龙虎榜免费源；同日继续新增 `lhb-detail`，按 `TRADE_ID` 或 `code + date` 拉取买卖席位明细，并补充 `seat_profile` / `seat_profile_summary` 做席位画像与游资识别。随后新增 `lhb-detail --start-date --end-date` 区间批量筛选，先筛龙虎榜记录再按 `trade_id` 拉详情，并在记录层输出 `seat_amount_summary` 聚合机构/北向/游资/营业部买卖净额、`seat_flow_analysis` 标注资金主导方；区间 payload 追加 `range_flow_summary` 作为多日聚合摘要，追加 `range_seat_profile_summary` 按过滤后记录聚合席位画像、别名净额与 top seats，并内置 `recognition_summary` 汇总可识别席位数量、游资别名数、可识别净额绝对值、游资净额绝对值、可识别主导类型、席位/净额占比和 `top_youzi_seats`，作为后续同板块辨识度对比的排序基础；同时支持 `--dominant-type` / `--dominant-direction` / `--youzi-alias` / `--min-dominant-net` 过滤。输出 canonical `_source: legacy`，详细渠道写入 `source_detail`。

- 接入 akshare、东方财富等免费数据源
- 覆盖 A 股财务数据、行情、龙虎榜
- 龙虎榜下一步：席位画像库持续扩展、同板块龙虎榜辨识度对比
- 现有 Skill 无需改动，数据层扩展即可

## P1：中期（3-6个月）

### HTML 报告输出
- 在 Markdown 基础上增加 HTML 报告格式
- 支持暗色模式、导航栏、图表可视化
- 提升报告传播性和阅读体验

### 多档深度模式
- `lite`：5分钟速判，快速给出估值区间和核心结论
- `standard`：当前默认模式，完整多Agent研究
- `deep`：增加更多交叉验证和历史类比，机构级深度

### 多股横向对比
- 支持 2-4 只股票同维度横向对决
- 同行业公司估值对标
- 输出对比矩阵和择优建议

### 团队研究产物结构升级
- 默认生成 `data-pack.json`、`source-index.md`、`role-briefs/`、`audit-results.json` 与最终报告
- 最终报告中的关键数据能追溯到资料包或来源索引
- 角色结论与最终结论冲突时，必须写明 Team Lead 的仲裁理由

## P2：长期（6个月+）

### 测试覆盖
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
