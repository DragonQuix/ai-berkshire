# 投资研究：巴菲特-芒格-段永平-李录 四大师综合分析框架

对 $ARGUMENTS 进行系统化投资研究分析。

## 研究框架

### 深度模式选择

执行前确认研究深度：`--depth lite`（5-10 分钟快速评估）、`--depth standard`（完整研究，默认）或 `--depth deep`（机构级深度）。lite 模式报告文件名加 `-lite` 后缀（如 `腾讯-research-lite-20260629.md`）。本技能三档行为差异详见 `docs/depth-profiles.md`「investment-research」小节。

基于巴菲特、芒格、段永平、李录四位投资大师的方法论，按以下七个模块顺序执行研究：

### 前置步骤：权限安全分工（必须执行）

本 Skill 可使用 Task Agent 辅助定性分析，但所有联网搜索、理杏仁/妙想取数、financial_rigor.py 验算、文件写入和数据抽检必须由主 Agent 执行。Task Agent 只基于主 Agent 注入的数据包、来源索引和资料摘录分析商业模式、竞争格局、管理层、行业 TAM、风险事件等无法编码的维度。若后台 Agent 权限受限，主 Agent 顺序模拟这些分析角色，不中断流程。

### Agent 失败诊断与降级记录（必须执行）

若 TeamCreate、TaskCreate、后台 Agent 启动、等待或读取结果失败，主 Agent 不得把失败当作未发生。遇到 `model route not configured`、`timeout`、`permission denied` 或同类权限/路由/超时错误时，立即降级为「顺序角色模拟」，并在报告附录「Agent 降级记录」中记录：失败 Agent、错误原文摘要、降级方式、影响范围。错误原文摘要只保留必要信息，不写入密钥或本机隐私路径；错误摘要脱敏标准：可保留：模型名、错误码、HTTP 状态、非敏感错误类别，例如 `deepseek-v4-flash 路由未配置`；必须删除：本机绝对路径、token、cookie、账户名、API Key、完整请求头；影响范围需说明哪些角色由主 Agent 模拟、哪些结论因此置信度下降。

### 前置步骤：AI研究偏见自觉（必须执行）

在开始研究前，先评估该公司的"AI可研究性"，识别潜在的数据偏见：

**信息丰富度评级**：
| 等级 | 特征 | AI研究陷阱 | 应对策略 |
|------|------|-----------|---------|
| A级（信息充裕） | 上市多年、券商覆盖多、媒体报道密集 | 共识过强，AI输出趋同于市场定价，alpha有限 | 重点做反面检验：聪明人为什么不买？被忽略的风险是什么？ |
| B级（信息适中） | 上市1-3年、覆盖有限、部分数据需推算 | AI可能用"合理推测"填补空白，看起来完整实则虚假确定性 | 每个推算数据标注置信度，区分"有据推算"和"凭空填充" |
| C级（信息稀缺） | 刚上市/冷门股/新兴市场、几乎无覆盖 | AI会因资料不足而过度保守，误判为"看不清=不好" | 用第一性原理提问（见下方），从有限信息中提取商业本质 |

**C级公司的第一性原理研究法**：
当公开资料不足时，不要试图拼凑出"看起来完整"的报告，而是聚焦以下底层问题：
1. 客户是谁？为什么付钱？有没有替代选择？
2. 复购靠什么驱动？是习惯、锁定、还是持续创造新价值？
3. 竞争对手拿100亿能复制这门生意吗？
4. 管理层做过什么关键决策？这些决策反映了什么判断力和价值观？

**偏见自查清单**（研究全程保持警惕）：
- [ ] 我的"确定性"感受是来自生意本质，还是来自资料数量？
- [ ] 如果把这家公司的资料量减少一半，我的结论会变吗？
- [ ] AI输出的分析是否与市场共识高度雷同？如果是，我的信息优势在哪？
- [ ] 是否存在"公开资料很少但生意本质极好"的可能性被低估了？

将信息丰富度评级结果写入报告开头，并在最终结论中注明"AI研究置信度"与"实际投资确定性"的区别。

### 第〇步：数据预处理（双渠道数据包，必须执行）

> 能力边界参见 `docs/channel-capability-matrix.md`（E0 已验证）。A股/港股结构化数据**禁止**先用 WebSearch 拼凑。

**0.1 解析目标**：从 `$ARGUMENTS` 提取公司名与股票代码（A股6位 / 港股5位）。无法确定代码时，先用 `python tools/lxr_data.py` 配合公司搜索或 mx-data 问句解析，再进入批量拉取。

**0.2 一次性拉取数据包**（推荐单命令，TTL 1h 跨模块共享）：

```bash
python tools/lxr_data.py datapack {code} --years 5 -o _tmp_{code}_datapack.json
# 跳过妙想（省日限额）：python tools/lxr_data.py datapack {code} --no-mx -o _tmp_{code}_datapack.json
```

主 Agent 随后读取 `_tmp_{code}_datapack.json`，从 `sections.financials/valuation/verify_inputs/...` 中取数；不要用 `glob datapack_*.json` 猜缓存文件名。若只想看 stdout，可省略 `-o`。财报字段必须同时读取 `sections.financials.caliber_metadata` 或顶层 `caliber_metadata.financials`，保留 `toi=营业总收入`、年报“收益”差异、币种和单位信息。

或按维度分拆（理杏仁为主，妙想补 tick/资讯；单次研究约 5–8 次理杏仁 + 2 次 MX）：

| 维度 | 命令 / 渠道 | `_source` 标注 |
|------|------------|----------------|
| 财报 5 年 | `python tools/lxr_data.py financials {code} --years 5 --source lixinger` | lixinger |
| 估值 + 分位点 | `python tools/lxr_data.py valuation {code} --source lixinger` | lixinger |
| 验算输入 | `python tools/lxr_data.py verify-inputs {code}` | lixinger |
| 行业深度 | `python tools/lxr_data.py industry-deep {code} --years 5` | lixinger |
| 营收构成 | `python tools/lxr_data.py revenue {code} --years 3`（A股） | lixinger |
| 股东 + 治理 | `shareholders --kind majority/num` + `governance --years 2` | lixinger |
| 行业估值对比 | `python tools/lxr_data.py industry-compare {code}`（A股） | lixinger |
| 宏观利率 | `python tools/lxr_data.py macro-debt` + `macro-rates` | lixinger |
| 实时快照 | `python tools/lxr_data.py mx-data "{公司}最新价 涨跌幅 PE PB"` | mx-data |
| 重要资讯 | `python tools/lxr_data.py mx-search "{公司}最新公告 业绩"` | mx-search |

Windows 终端：`$env:PYTHONIOENCODING='utf-8'`；MX 脚本**必须**传 `--output-dir` 或输出目录参数（默认 `/root/.openclaw/...` 在 Windows 不可用）。

**港股行业对比降级**：`industry-compare` 对港股会返回 `note: 申万行业分类仅覆盖A股` 和 `alternatives`；即使使用 `python tools/lxr_data.py industry-compare {code} --no-mx` 省额度路径，也必须保留这组静态替代步骤。港股不要求申万同行分位；改用 `mx-xuangu` 辅助找同业、手工指定同业列表，或选取港股行业龙头 / 主要可比公司后逐一拉取 `valuation` 并说明选择依据。

**0.3 保险 / 银行 / 证券专属字段**（`industry-deep` 自动路由 `report_type`）：

| 类型 | 理杏仁直接获取（E0.4 已验证 601336） | 仍需年报原文的场景 |
|------|--------------------------------------|-------------------|
| 保险 | EV、NBV、核心/综合偿付能力、保险业务收支 | 个别字段 `deep_summary` 为 null；代理人渠道等经营细节 |
| 银行 | 资本充足率、净息差、不良率、拨备覆盖率 | 逐笔不良贷款明细 |
| 证券 | 经纪/投行/资管/自营净收入 | 业务条线口头披露口径核对 |

保险股 PEV = 市值 / EV，EV/NBV **标注「理杏仁直接获取」**；仅当面值缺失或需与年报脚注核对时使用 WebFetch 年报 PDF。

**0.4 数据包注入模板**（写入报告「数据摘要」节，再进入四大师分析）：

```markdown
## 数据摘要（预处理）
| 指标 | 最新值 | 口径/来源 | 币种 | 单位 |
|------|--------|-----------|------|------|
| 市值 / PE-TTM / PB | ... | lixinger | ... | ... |
| PE 历史分位（10年） | ...% | lixinger | ... | ... |
| 营收 / 归母净利润（近5年） | 表 | caliber_metadata：toi=营业总收入；年报“收益”需核对 | CNY/HKD | raw_yuan → 亿元/亿港元 |
| [保险] EV / NBV / 偿付能力 | ... | lixinger / industry-deep | ... | ... |
| 前十大股东（最新） | 表 | lixinger | ... | ... |
| 高管/大股东增减持（2年） | 表 | lixinger | ... | ... |
| 实时价 / 涨跌幅 | ... | mx-data | ... | ... |
```

凡含理杏仁 / 妙想取数或核心财务字段（PE/PB/营收/归母净利润/市值/现金流等）的数据表，必须保留「口径/来源」列；纯历史趋势表或定性对比表可省。`cross-validate --caliber` 的口径说明应与 `caliber_metadata` 保持一致；如工具提示「口径待核对」，先解释口径差异再决定是否纳入抽检通过。

**0.5 Agent 分工调整**：结构化数字由数据包提供；Task Agent **仅**负责竞争格局、商业模式定性、管理层履历、行业 TAM、风险事件等**无法编码**的维度。禁止 3 个 Agent 并行重复拉取财报、调用 WebSearch/WebFetch/Bash 或写文件。缺资料时输出补数请求，由主 Agent 统一补齐。

### 第一步：数据收集

> **数据源规范**：参见 `skills/financial-data.md`。理杏仁第1顺位 → 妙想第2顺位 → 免费源第3顺位（兜底）。
> - 美股：macrotrends（主）+ stockanalysis（副）
> - 港股：aastocks（主）+ macrotrends ADR（副）
> - A股：东方财富（主）+ 巨潮资讯（副）
>
> **A股/港股结构化数据优先用理杏仁 CLI**（避免免费源 GBK 乱码、保险报表缺失、无估值分位点）：
> ```
> python tools/lxr_data.py financials 601336 --years 5 --source lixinger   # 财报（自动判定保险/银行/证券/非金融）
> python tools/lxr_data.py valuation 600519 --source lixinger              # 估值 + 历史分位点
> python tools/lxr_data.py industry-deep 601336 --years 5                  # 行业深度（保险EV/NBV/偿付能力、银行资本充足率/净息差、证券经纪/投行/资管）
> python tools/lxr_data.py revenue 600519 --years 3                        # 营收构成（分产品/分地区）
> python tools/lxr_data.py governance 601336 --years 2                     # 公司治理（高管/大股东增减持）
> python tools/lxr_data.py shareholders 600519 --kind majority             # 前十大股东/股东人数/基金持股
> ```
> **保险股研究特别说明**：EV（内含价值）、NBV（新业务价值）、偿付能力充足率、营运利润均已由
> `industry-deep` 直接返回（如 601336 2025 EV=2878亿/NBV=98亿），**不再依赖 WebFetch 抓年报补漏**。
> 仅当理杏仁字段为空（如个别公司不披露营运利润）或需历史口径核对时，再回到年报原文。

数据包（第〇步）已覆盖 1、2、9 的结构化部分。以下**非结构化**信息由主 Agent 补充进资料包（优先 mx-search，降级 WebSearch），再交给只读分析角色使用：

1. 收入结构：**分产品叙事**（理杏仁 `revenue` 已有则直接引用）；缺省再搜
2. ~~财务指标~~ → 已由 `financials` + `industry-deep` 提供
3. 竞争格局：市场份额、主要竞争对手对比
4. 商业模式与护城河：核心竞争优势来源
5. 技术能力：核心技术栈、研发投入
6. 管理层：创始人/CEO履历、**持股比例以理杏仁 `shareholders`/`governance` 为准**，履历与决策用 mx-search
7. 行业前景：TAM（总可寻址市场）、增长预测
8. 风险因素：地缘政治、监管、供应链等（mx-search 监管公告 + 理杏仁 `inquiry`/`measures` 如有）
9. ~~当前估值~~ → 已由 `valuation` + `verify-inputs` 提供；PEV/PEG 用工具验算
10. 多空双方核心论点

#### 数据交叉验证（必须执行，使用金融严谨性工具）

数据收集完成后，**必须调用 `tools/financial_rigor.py` 对关键数据进行程序化验证**，杜绝LLM心算误差。

**必须验证的数据点**：
- 总股本（从交易所、Yahoo Finance、StockAnalysis 等至少2个源确认）
- 当前股价和市值（**手动计算 股价×总股本 并与报告市值对比，防止单位错误**）
- 最近财年收入和净利润（从公司年报+至少1个第三方源确认）
- 现金储备和净现金（现金+短期投资-总债务，注意口径差异）
- 管理层持股比例（区分经济权益和投票权，注意AB股结构）

**强制验证步骤（使用Bash调用工具）**：

Step 1 — 市值验算（精确十进制，非浮点）：
```bash
python tools/financial_rigor.py verify-market-cap \
  --price {股价} --shares {总股本} --reported {报告市值} --currency {币种}
```

Step 2 — 关键数据多源交叉验证：
```bash
python tools/financial_rigor.py cross-validate \
  --field {字段名} --values '{"来源1": 数值, "来源2": 数值}' --unit {单位} \
  --caliber "{口径说明，如年报收益口径/理杏仁营业总收入口径}"
```
对收入、净利润、现金储备分别执行。若工具提示“疑似单位不一致”，必须回到来源核对单位、币种或小数点后再写入报告。

Step 3 — 估值指标精确验算（PE/PB/ROE/FCF Yield 等）：
```bash
python tools/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产} --fcf-per-share {每股FCF} --dividend {每股股息}
```

**验证规则**：
1. 每个关键数据点至少2个独立来源
2. 发现来源间有差异时，优先采用公司年报/交易所数据，并注明差异原因
3. **所有涉及计算的数据必须通过工具验算，禁止LLM心算**
4. 工具输出结果直接嵌入报告附录"关键数据交叉验证记录"
5. 如果工具报告 ❌ 偏差过大，必须排查原因后才能继续分析

**常见错误防范**：
- 市值单位：港币亿 vs 人民币亿 vs 美元亿，容易漏写/多写一个零
- FCF口径：不同来源对资本支出的定义可能不同（是否含租赁、收购等）
- 债务口径：是否包含经营租赁负债
- 持股比例：AB股公司的经济权益 ≠ 投票权

### 第二步：生意本质分析 — 段永平"对的生意"

分析要点：
- 用一句话定义这门生意的本质
- 收入结构拆解（图表）
- 5年盈利能力趋势（图表）
- 商业模式画布：一次性销售 vs 订阅/复购？硬件 vs 软件 vs 平台？
- 生态粘性/客户锁定强度
- 毛利率水平与同行对比，解释为什么高/低
- 经营杠杆分析
- **段永平式追问**：这门生意好在哪？如果只能用一句话描述，是什么？

### 第三步：护城河评估 — 巴菲特"经济护城河"

逐一验证五类护城河：

| 护城河类型 | 验证方法 |
|-----------|---------|
| 品牌/定价权 | 是否能在不损失销量的情况下提价？ |
| 转换成本 | 客户迁移到竞品的成本有多高？ |
| 网络效应 | 用户越多产品越好吗？ |
| 规模效应 | 规模带来的成本优势有多大？ |
| 技术/专利壁垒 | 技术领先几年？能否被复制？ |

分析护城河趋势：过去5年变宽还是变窄？未来5年预判。

**巴菲特式追问**：10年后这条护城河还在吗？什么能摧毁它？

### 第四步：逆向思考与风险清单 — 芒格"反过来想"

- 列出"这家公司可能失败的所有路径"（表格：路径/概率/影响程度）
- 历史类比：找到历史上处于相似位置的公司，结局如何？
- 跨学科分析：用网络效应理论、技术采纳曲线、竞争博弈等模型交叉验证
- 偏误自查：叙事偏差、锚定效应、幸存者偏差
- 收集空方核心论点

**芒格式追问**：我最可能在哪里犯错？聪明人为什么会不买/做空这家公司？

### 第五步：管理层评估 — 段永平"对的人" + 巴菲特"管理层诚信"

- CEO/创始人关键决策复盘（表格：时间/决策/结果/评分）
- 资本配置能力：研发回报率、并购成功率、回购时机
- 股东利益一致性：管理层持股、薪酬结构、减持记录
- 组织能力：团队稳定性、关键人才风险
- 企业文化特征

**段永平式追问**：如果CEO退休，这家公司还能保持竞争力吗？

### 第六步：行业与文明趋势 — 李录"文明演进框架"

- 判断所在行业是否处于"文明级范式转移"
- 历史技术革命类比（蒸汽机/电力/互联网/AI）
- TAM增长曲线与天花板分析
- 公司在产业价值链中的位置
- 技术路线风险
- 客户/供应商集中度分析

**李录式追问**：站在20年后回看，这家公司是"这个时代的标准石油"还是"昙花一现的3Com"？

### 第七步：估值与安全边际 — 巴菲特"内在价值" + 段永平"对的价格"

#### 估值四维坐标（必须填写）

| 维度 | 问题 | 取数 | `_source` |
|------|------|------|-----------|
| D1 自身水位 | PE 处于自身历史什么分位？ | `percentiles` + `valuation` 的 PE-TTM 分位点 | lixinger |
| D2 行业水位 | A股：PE 处于申万同业什么位置；港股：不要求申万同行分位，改用港股行业对比降级路径 | `industry-compare` 对比表；港股用 mx-xuangu / 手工指定同业 / 港股行业龙头可比公司 | lixinger / mx-xuangu |
| D3 全市场位置 | 全市场多少家更便宜且质量不输？ | mx-xuangu「PE低于{本公司PE}且ROE大于{本公司ROE}%的A股」 | mx-xuangu |
| D4 利率环境 | 10Y 国债收益率下当前 PE 合理吗？ | `macro-debt` 最新 10Y + 与历史 ERP 直觉对照 | lixinger |

写入报告估值节前的「四维坐标表」，四维度结论综合后再做三情景 DCF/PE 估值。

- 当前市场定价（关键估值指标表格）—— **必须通过工具验算**
- 反向DCF：当前股价隐含了什么增长预期？
- 三情景估值 —— **必须通过工具精确计算，禁止心算**：
```bash
python tools/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {总股本亿} \
  --growth {乐观增速} {中性增速} {悲观增速} \
  --pe {乐观PE} {中性PE} {悲观PE} --years 3 --currency {币种}
```
`--growth` 推荐使用小数格式（例如 `0.30 0.15 -0.05`）。若误填 `30 15 -5`，工具会自动转为 `0.30/0.15/-0.05` 并在 stderr 警告；报告中必须保留最终使用口径。
- 与自身历史估值对比
- 与同行估值对比

**段永平式追问**：如果股市明天关闭5年，你愿意以这个价格持有吗？

### 第八步：综合决策备忘录

汇总表格：

| 维度 | 结论 | 信心度 |
|------|------|--------|
| 生意质量（段永平） | | |
| 护城河（巴菲特） | | |
| 管理层（段永平+巴菲特） | | |
| 最大风险（芒格） | | |
| 文明趋势（李录） | | |
| 估值（巴菲特+段永平） | | |

最终决策表格：

| 策略 | 建议 |
|------|------|
| 空仓者 | |
| 持仓者 | |
| 卖出信号 | |
| 加仓信号 | |

四位大师的模拟点评（用引用格式）。

## 输出要求

1. 所有分析必须有数据支撑，附数据来源
2. 使用 Markdown 表格呈现关键数据
3. 每个模块末尾必须有对应大师的"追问"
4. 最终将完整报告写入 `reports/{公司名}/{公司名}-research-{YYYYMMDD}.md`，例如 `reports/腾讯/腾讯-research-20260629.md`
5. 结论要明确，不回避给出买入/观望/回避的建议
6. 估值部分必须给出具体的价格区间
7. **报告开头**必须包含"信息丰富度评级"（A/B/C）和"AI研究局限性声明"
8. **报告结尾**必须区分"AI分析置信度"与"投资确定性"——前者取决于资料量，后者取决于生意本质。明确告知读者：本报告的哪些结论基于充分数据，哪些基于有限信息的推理
9. 如果公司属于C级（信息稀缺），报告末尾必须列出"需要一手验证的问题清单"——建议读者通过田野调查、产品体验、供应链访谈等方式补充AI的盲区

## 数据抽检（准出流程）

报告写入文件后，**必须**执行数据抽检，通过后方可发布：

**Step 1 — 提取抽检清单（15%随机抽样）：**
```bash
python tools/report_audit.py extract \
  --report <报告文件路径>
```
输出 JSON 模板，每项含 `fetched_value`（待填）。

**Step 2 — 取数核验：**
对清单中每个数据点，按 `skills/financial-data.md` 规范从可靠信源取数
（美股：macrotrends+stockanalysis；港股：aastocks+macrotrends；A股：东方财富+巨潮资讯），
填入 `fetched_value` / `fetched_unit` / `fetched_source` / `fetched_value2` / `fetched_unit2` / `fetched_source2`。若超阈值差异已经在报告脚注或「口径/来源」列中解释，必须同时填 `caliber_ack: true` 与非空 `caliber_note`；空说明不得视为口径认可。

**Step 3 — 输出判决：**
```bash
python tools/report_audit.py verdict \
  --results '<填好的JSON>' \
  --report <报告文件名> \
  -o _tmp_verdict.json
```

- **【准出】**：所有抽检点按 `skills/financial-data.md` 交叉验证阈值通过（同口径结构化双源 ≤2%），或超阈值口径差异已用 `caliber_ack` + `caliber_note` 认可 → 报告可发布
- **【打回】**：任意抽检点超阈且无有效口径说明，或口径冲突未在报告中解释 → 修正后重新抽检
- **【元数据警告】**：若 verdict 输出「核心数据表缺少口径/来源列」，不直接打回，但必须在发布前回补表头或在报告脚注说明豁免理由。

## 数据源配置（增强后）

| 优先级 | 渠道 | 适用场景 | 日限额 |
|--------|------|----------|--------|
| 1 | 理杏仁 `tools/lxr_data.py` | A股/港股财报、估值分位、股东、治理、宏观、行业对比 | ~144k/天 |
| 2 | mx-data | 实时 tick、NLP 即席查数、港股行情快照 | 150/天 |
| 2 | mx-search | 公告、研报、新闻、管理层采访 | 150/天 |
| 3 | 免费源 | 理杏仁+妙想均失败时（见 `skills/financial-data.md`） | — |
| 3 | 年报 PDF / WebFetch | 保险经营细节核对、口径脚注 | — |

**交叉验证**（可选，出稿前一次）：理杏仁 vs mx-data 同一指标（如 PE-TTM）差异 >2% 标注双源；>5% 标「数据异常」人工核查。NLP 源与结构化源口径不同则不强行对比。

**美股**：理杏仁/妙想均无公司级数据，保持 macrotrends + stockanalysis，本预处理步骤跳过。
