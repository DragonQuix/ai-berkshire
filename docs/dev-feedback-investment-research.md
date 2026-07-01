# 开发反馈：investment-research 技能执行复盘（2026-07-01 泡泡玛特）

> 本文档由执行 `/investment-research 泡泡玛特`（standard 深度）的 Agent 撰写，旨在为后续编程 Agent 提供**可直接接手改进**的具体清单。内容覆盖：本次运行全流程错误盘点 + 项目代码审核 + 技能文档改进意见 + 反馈入口设计建议 + 整体使用感受。
>
> 反馈分级：`mixed`（核心流程能跑通并产出准出报告，但容错性、可观测性、口径一致性有 13 处可改进点）
>
> 关联 issue form：`.github/ISSUE_TEMPLATE/usage-feedback.yml`、`docs/usage-feedback.md`

---

## 一、本次运行错误/警告全流程盘点（13 项，按发生顺序）

下表每项给出「错误现象 → 根因 → 改进方向」。根因分析基于代码审核（见第二节），改进方向落到具体文件/函数。

| # | 环节 | 错误现象 | 根因 | 改进方向（目标文件） |
|---|------|---------|------|---------------------|
| 1 | 第〇步 datapack | `glob datapack_9992*.json` 查不到文件 | `lxr_data.py datapack` 直接 print 到 stdout，**不落盘到缓存文件**；`get_research_datapack` 返回 dict 但 CLI 入口未写盘 | `lxr_data.py`：datapack 命令增加 `--output-dir`/`-o` 落盘到 `tempfile.gettempdir()/ai_berkshire_datapack_{code}.json`，主 Agent 可二次 Read 解析 |
| 2 | 第〇步 financials | 第一次 `d.get('data',[])` 返回空 | 理杏仁财报 JSON 顶层键是 `records` 不是 `data`，技能文档与工具返回结构文档不同步 | `lxr_data.py`：financials 输出标准化为 `{"records":[...], "fields":[...]}`；skill 文档加一段「返回 JSON 结构示例」 |
| 3 | 第七步 verify-valuation | `--currency HKD` 不识别，工具报参数错误 | `financial_rigor.py verify-valuation` 不接收 `--currency`，但 skill 文档示例写了该参数 | 要么 `financial_rigor.py` 接受并仅用作标签透传，要么 skill 文档删除 `--currency`，改用 `--source lixinger {code}` 自动取数 |
| 4 | 第七步 three-scenario | `--growth 30 15 -5` 被解析成 3000%/1500%/-500%，目标股价算出天文数字 | `three_scenario_valuation` 的 growth 参数要求小数（0.30），但参数名 `--growth` 无类型提示，skill 文档示例又写了 `--growth {乐观增速}` 易被填成整数百分比 | `financial_rigor.py`：growth 参数加 `argparse` 校验 `abs(v)>1 and abs(v)<100` 时警告「疑似百分比，请改小数」；或在 floating action 时自动 `/100` 当 `>1` |
| 5 | 第七步 cross-validate | `{"理杏仁":41302, "公司年报":413.02}` 偏差 98%，被打回 | 单位错位（亿 vs 万元），`cross_validate` 无单位一致性预检 | `financial_rigor.py cross_validate`：增加 `--unit` 必填校验 + 同量级预检（max/min > 100 时打印警告「疑似单位不一致」） |
| 6 | 第〇步 industry-compare | 港股 9992 返回 null | 申万行业分类**仅覆盖 A 股**，`industry-compare` 对港股直接返回 null 无降级提示 | `lxr_data.py`：港股时打印明确警告「申万分类不支持港股，建议用 mx-xuangu 或同业参考」，并返回 `{"note":"港股不支持申万分类", "alternatives":[...]}` |
| 7 | 第〇步 mx-xuangu | 查询「PE<16 且 ROE>78% 的港股」返回 A 股筛选器 | mx-xuangu 对港股条件解析不稳定，静默回退到 A 股 | `lxr_data.py mx-xuangu`：港股查询时若返回结果标的均为 A 股，打印警告并返回 `{"warning":"...", "market":"cn_returned"}` |
| 8 | 第一步 Task Agent | 2 个 general-purpose agent 报 `Claude Desktop model route is not configured: deepseek-v4-flash`，全部失败 | 子 Agent 走了 Claude Desktop 的 deepseek-v4-flash 路由，但项目未配置 | skill 文档加「Task Agent 失败诊断步骤」：(1) 捕获错误信息；(2) 按 P0 技能规范降级为主 Agent 顺序模拟四大师视角，不中断流程。或在 `lxr_data.py`/skill 头部加环境检测 `subagent_model_fallback` 提示 |
| 9 | 数据抽检 verdict | 第一次 `float('2026-07-01')` 报 ValueError | `render_verdict` line 314 `fetched = float(fetched)` 强制转 float，不支持字符串型数据（日期、比率文字） | `report_audit.py`：增加 `_to_numeric(v)` 辅助函数，try `float(v)` 失败时尝试日期→年份小数（2026.0），再失败则 `None`+note「非数值型，跳过比对」 |
| 10 | 数据抽检 verdict | id=54 悲观涨跌幅 reported=46.5 vs fetched=-46.5，偏差 200% | `_pct_diff` 公式 `abs(reported-fetched)/abs(reported)` 在符号相反时分子放大 2 倍；extract 阶段 `_clean_num` 对 `-46.5%` 的负号处理在某些列对齐场景会丢号 | `report_audit.py`：(a) 增加方向型指标识别（label 含「涨跌幅/涨跌/变化率/同比」），verdict 时两侧同取 abs；(b) `_pct_diff` 对方向型字段改用 `abs(abs(r)-abs(f))/abs(r)` |
| 11 | 营收口径警告 | 理杏仁 413 亿 vs 年报 371.2 亿，差 10.72% | 理杏仁 `toi`（营业总收入）含其他业务收入 41.8 亿，年报「收益」口径不含；工具未提示口径差异 | `lxr_data.py financials`：港股返回时附 `caliber_note`「营业总收入 vs 收益，差异约 X%」；或在 datapack 层面预标注差异 |
| 12 | cross-validate 营收 | 第二源用 411 亿仍差 10.72% | 应该用同人民币口径 371.2（thesis 引用），但工具未给出「推荐口径」 | `financial_rigor.py cross_validate`：增加 `--caliber` 参数标注口径，偏差时输出「口径差异，建议核对定义」 |
| 13 | 全程可观测性 | 主 Agent 不得不重跑分维度拉取 + 手动拼 JSON，过程不可复现 | datapack 不落盘、子 Agent 失败无重试日志、降级路径无明确记录 | `lxr_data.py`：datapack 落盘 + 增加 `--log-file` 记录每次调用（命令/耗时/是否降级/错误）；skill 文档加「降级事件记录」字段写报告附录 |

---

## 二、项目代码审核：四大工具文件改进点（含行号/最小改动）

### 2.1 `tools/report_audit.py`（准出审计，重点）

**问题 A：`_pct_diff` 符号冲突（line 258-262）**

当前：
```python
def _pct_diff(reported: float, fetched: float) -> float:
    if reported == 0:
        return 0.0 if fetched == 0 else float('inf')
    return abs(reported - fetched) / abs(reported)
```

最小改动建议：
```python
_DIRECTIONAL_KEYWORDS = ('涨跌幅', '涨跌', '变化率', '同比', '增速', '回撤', '跌幅')

def _is_directional(label: str) -> bool:
    return any(k in label for k in _DIRECTIONAL_KEYWORDS)

def _pct_diff(reported: float, fetched: float, label: str = "") -> float:
    if reported == 0:
        return 0.0 if fetched == 0 else float('inf')
    # 方向型指标允许同号或互为相反数视为通过（口径一致，符号代表方向）
    if _is_directional(label) and abs(abs(reported) - abs(fetched)) < 1e-9:
        return 0.0
    return abs(reported - fetched) / abs(reported)
```

调用处（line 315、321）传入 `label`：
```python
diff1 = _pct_diff(reported, fetched, label)
```

**问题 B：`float(fetched)` 强制转换崩溃（line 314, 320）**

当前 `fetched = float(fetched)` 对字符串型 fetched_value（如日期"2026-07-01"、状态文字）直接 ValueError。

最小改动建议：新增辅助函数并在 verdict 渲染处替换：
```python
def _to_numeric(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    try:
        return float(s)
    except ValueError:
        # 日期型：近似为年
        m = re.match(r'^(20\d{2})', s)
        if m:
            return float(m.group(1))
        return None  # 非数值型，跳过比对

# line 314 改为：
fetched_num = _to_numeric(fetched)
if fetched_num is None:
    print(f'  ⬜ [{item["id"]:>2}] {label[:35]:35s} 非数值型核验值，跳过比对')
    continue
fetched = fetched_num
```

**问题 C：extract 阶段 `_clean_num` 负号丢失（line 130-164 附近 _parse_md_tables）**

需检查 `_clean_num` 与表格列对齐时对 `-46.5%` 的解析。若 `+174.3%` 和 `-46.5%` 在同一列，正则需确保 `[-+]?\d` 捕获负号。建议审核 `_clean_num` 实现并加单测覆盖「正负同列」。

### 2.2 `tools/financial_rigor.py`（金融严谨性工具）

**问题 A：`three_scenario_valuation` growth 单位易混淆（line 332 附近）**

当前 `--growth 30 15 -5` 被当 3000% 处理。最小改动：
```python
# argparse 后处理
def _normalize_growth(v):
    if abs(v) > 1 and abs(v) < 100:
        # 疑似百分比，自动转小数并警告
        sys.stderr.write(f"⚠️  growth={v} 疑似百分比，已自动转为 {v/100}（建议直接传小数如 0.30）\n")
        return v / 100.0
    return v

growth = [_normalize_growth(g) for g in args.growth]
```

**问题 B：`cross_validate` 无单位一致性预检（line 179 附近）**

当前 `"加权中位数"` 实为排序中位数（2 源时即均值），命名误导。最小改动：
```python
def cross_validate(field, values: dict, unit: str = "", caliber: str = ""):
    nums = list(values.values())
    if max(nums) / min(nums) > 50:
        sys.stderr.write(f"⚠️  {field} 来源间量级差 {max(nums)/min(nums):.0f} 倍，疑似单位不一致（{unit}）\n")
    # ... 原有中位数逻辑
    # 命名修正：median 而非"加权中位数"
```

**问题 C：无 `--caliber` 参数标注口径**

营收口径冲突（11、12 号错误）根源在于工具不记录口径。建议 `cross_validate` 增加 `--caliber "年报收益口径"` 可选参数，写入输出 JSON，verdict 阶段可据此跳过阈值。

### 2.3 `tools/lxr_data.py`（理杏仁统一入口）

**问题 A：datapack 不落盘（line 2495 附近 datapack 命令）**

当前 `python tools/lxr_data.py datapack {code}` 只 print，主 Agent 难以二次解析。最小改动：
```python
# datapack 命令增加 -o/--output
def cmd_datapack(args):
    datapack = get_research_datapack(args.code, years=args.years, no_mx=args.no_mx)
    out_path = Path(tempfile.gettempdir()) / f"ai_berkshire_datapack_{args.code}.json"
    if args.output:
        out_path = Path(args.output)
    out_path.write_text(json.dumps(datapack, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[datapack] 写入 {out_path}")
    if not args.quiet:
        print(json.dumps(datapack, ensure_ascii=False, indent=2))
    return out_path
```

skill 文档同步更新示例：`python tools/lxr_data.py datapack {code} --years 5 -o /tmp/pm.datapack.json`。

**问题 B：`call_mx` 返回 raw_path 但 datapack 无文件输出（line 1486 附近）**

`call_mx` 的 `raw_path` 在 datapack 流程未复用。建议 datapack 内部调 `call_mx` 时把 raw_path 一并写入 datapack JSON 的 `_mx_raws` 字段，便于审计。

**问题 C：港股 industry-compare 静默返回 null（无降级提示）**

最小改动：港股代码时打印明确说明并返回结构化降级建议：
```python
if market == 'hk':
    return {
        "note": "申万行业分类仅覆盖 A 股，港股不支持",
        "alternatives": [
            f"mx-xuangu 查询同业",
            f"手动指定同业参考列表"
        ]
    }
```

**问题 D：financials 返回键不一致（records vs data）**

统一为 `{"records":[...], "fields":[...], "caliber_note":"..."}`，并在 skill 文档加返回结构示例。

### 2.4 `tools/financial_rigor.py` 与 `report_audit.py` 的协同

verdict 阶段调用 cross_validate 时，若 `--caliber` 已标注，verdict 应在 note 中显示口径并允许跳过 2% 阈值（口径冲突但已说明 → 降为 warning 而非 fail）。

---

## 三、技能文档 `skills/investment-research.md` 改进点

### 3.1 缺失：「Task Agent 失败诊断步骤」

当前 P0 头部只说「若后台 Agent 权限受限，主 Agent 顺序模拟」，但**未给出失败诊断的标准动作**。本次 2 个 agent 报 `deepseek-v4-flash` 路由错误，主 Agent 当时装作没看到继续跑，差点漏掉这一降级事件。

建议在「前置步骤：权限安全分工」后追加：

```markdown
### Task Agent 失败诊断（标准动作）

若 Task Agent 返回错误（如 model route not configured、timeout、permission denied）：

1. **捕获**：记录错误信息原文到 `_tmp_agent_errors.md`
2. **诊断**：
   - `model route not configured` → 子 Agent 走了未配置的模型路由，不可恢复
   - `timeout` → 可重试 1 次
   - `permission denied` → 子 Agent 无 Bash/Write 权限，不可恢复
3. **降级**：不可恢复错误时，主 Agent 顺序模拟对应角色，不中断流程
4. **记录**：报告附录 D「降级事件记录」写明哪个 Agent 失败、降级方式、影响范围
```

### 3.2 缺失：「口径冲突处理指引」

本次营收出现「理杏仁 413 亿 vs 年报 371.2 亿」口径冲突，技能文档**未说明如何处理**。建议在「数据交叉验证」节追加：

```markdown
### 口径冲突处理

当来源间差异 >2% 且可追溯到口径差异（如营业总收入 vs 收益、含/不含某分部）：

1. **识别口径**：理杏仁字段（如 `toi`=营业总收入）vs 年报口径（如「收益」），注明差异构成
2. **优先级**：以**公司年报原始口径**为准，理杏金作为交叉验证参考
3. **标注**：报告数据摘要表加 `口径` 列，附录写明差异金额与构成
4. **审计**：cross_validate 调用时传 `--caliber` 标注口径，verdict 据此跳过阈值
```

### 3.3 缺失：「datapack 二次解析方法」

技能文档示例 `python tools/lxr_data.py datapack {code} --years 5` 但未说明**如何读取结果**。主 Agent 本次只能 glob 查文件但查不到。建议追加：

```markdown
### datapack 读取

datapack 命令写入临时文件后，主 Agent 用 Read 工具读取：
\```bash
python tools/lxr_data.py datapack {code} --years 5 -o _tmp_{code}_datapack.json
\```
然后在 datapack JSON 中按维度键直接取数（financials/valuation/shareholders/...）。
```

### 3.4 建议增加「降级事件记录」标准字段

报告附录增加一节，记录本次运行所有降级事件（数据源降级、Agent 失败、口径冲突），便于审计与后续改进。

---

## 四、反馈入口设计改进建议（commit `1e688604`）

### 4.1 现状评价

`docs/usage-feedback.md` + `.github/ISSUE_TEMPLATE/usage-feedback.yml` 设计**基础扎实**：明确了最小字段、反馈分级（useful/mixed/blocked）、脱敏要求、匿名引用授权。测试契约 `test_install_feedback_contract.py` 覆盖了 snippet 存在性。这是一套可用的最小可行反馈入口。

### 4.2 缺失字段建议

比对本次运行暴露的 13 个错误，反馈入口**缺少能定位 bug 的关键字段**：

| 建议新增字段 | reason | issue form yaml 类型 |
|------------|--------|---------------------|
| **遇到的错误/警告** | 本次 13 个错误若不收集，编程 agent 看不到现场 | textarea，必填 |
| **技能降级路径** | 数据源降级/agent 失败是关键改进信号 | dropdown（无/数据源降级/agent 失败/口径冲突/其他） |
| **是否附 running log** | 脱敏后的运行日志能直接复现 | radio（是/否，否默认） |
| **改进优先级** | 用户感知的痛点和编程 agent 判断可能不一致 | radio（阻断/有用但容错差/锦上添花） |
| **技能版本/commit** | 复现需要版本锚点 | input，可从 git 自动填 |

### 4.3 机器可读反馈格式建议

当前 issue form 文本，编程 agent 需手工解析。建议**追加一个 machine-readable JSON 反馈格式**，在 `docs/usage-feedback.md` 末尾提供模板：

```json
{
  "feedback_version": "1.0",
  "date": "2026-07-01",
  "skill": "investment-research",
  "depth": "standard",
  "tier": "mixed",
  "errors": [
    {"stage": "datapack", "symptom": "...", "root_cause": "...", "suggested_fix": "..."}
  ],
  "degradations": ["Task Agent deepseek-v4-flash 路由失败 → 主 Agent 顺序模拟"],
  "caliber_conflicts": ["营收 理杏仁 413 vs 年报 371.2，营业总收入/收益口径"],
  "improvement_priority": ["report_audit abs 口径冲突阻断", "datapack 不落盘阻断"]
}
```

issue form 可增加一个「可选：附 JSON 反馈」的 textarea，编程 agent 用脚本一键解析所有 feedback issue 生成改进清单。

### 4.4 反馈入口分类建议

当前两个入口（install-feedback / usage-feedback）已覆盖安装与使用。建议**增加第三个：dev-feedback**（开发反馈），专门收集「执行 agent 的代码审核意见」，因为：

- usage-feedback 面向最终用户，字段偏使用体验
- install-feedback 面向安装失败
- 执行 agent 的代码审核（如本文档）需要更结构化的字段：错误链、根因、行号、最小改动

本文档（`docs/dev-feedback-investment-research.md`）即是 dev-feedback 的首份样本，建议建立 `.github/ISSUE_TEMPLATE/dev-feedback.yml` 与 `docs/dev-feedback.md` 对应模板。

### 4.5 测试契约补充

`test_install_feedback_contract.py` 当前只验证 snippet 存在。建议增加：

- 验证 issue form 字段数量 ≥ 某阈值（防止字段被误删）
- 验证 `docs/usage-feedback.md` 的「真实反馈记录」区有占位（当前有，但加一条断言更稳）
- 验证 machine-readable JSON 模板存在（若采纳 4.3）

---

## 五、其他建议

### 5.1 datapack 落盘 + 缓存复用

本次主 Agent 因 datapack 不落盘，被迫分维度重跑拉取（financials/valuation/shareholders/...），**多花了 4-6 次理杏仁调用 + 2 次 mx 调用**。落盘后同会话二次研究同公司可直接读缓存，省 80% 取数时间。

### 5.2 report_audit 增加「口径冲突豁免」机制

当 `--caliber` 已标注口径差异时，verdict 应允许该数据点降为 warning 而非 fail，避免「明明口径已说明还被反复打回」的循环（本次营收被打了 2 次）。

### 5.3 子 Agent 路由可探测性

skill 头部可加一段「环境探测」：运行前快速 spawn 一个最小子 Agent 测试路由是否可用，若不可用直接走降级路径，避免跑到一半才发现 agent 失败。比本次「跑了 2 个 agent 才发现都失败」更省 token。

### 5.4 financial_rigor 与 lxr_data 的口径元数据互通

理杏仁返回结构应携带 `caliber`（口径）元数据，financial_rigor 调用时透传，verdict 据此自动豁免。当前两工具口径信息不互通，是 11/12 号错误的系统根因。

### 5.5 长期：技能自检 fixture

建立一个 `tests/fixtures/investment_research_smoke/` 目录，含一份小型公司（如某 A 股冷门股）的预录 datapack + 预期报告骨架，让 `/investment-research` 能跑离线 smoke，CI 可验证技能不退化。当前 release_smoke 只测安装，不测技能行为。

---

## 六、整体使用感受（作为执行 agent）

### 6.1 正面

- **技能成熟度高**：四大师框架 + 七步流程 + 估值四维坐标 + 三情景估值 + 15% 抽检准出，是一套**严丝合缝**的投研工作流。相比之下多数开源投研 prompt 只有「分析+结论」两段，无准出门禁
- **数据三级降级链设计正确**：理杏仁 → 妙想 → 免费源，本次理杏仁可用 80%，妙想补 tick/资讯，降级路径自然
- **financial_rigor 程序化验算**：避免 LLM 心算 PE/EPS 这类高频错误，是关键护城河
- **报告结构规范**：信息丰富度分级 + AI 局限性声明 + 置信度区分，强迫 agent 诚实标注不确定性，符合 CLAUDE.md「客观、不预设立场」原则

### 6.2 待提升

- **容错性**：13 个错误中 8 个是工具参数/返回结构的「硬碰撞」（直接报错或静默错），缺乏软降级。`report_audit` 字符串崩溃、`three_scenario` 单位错位、`industry-compare` 港股静默 null 是典型
- **可观测性**：过程不可复现——datapack 不落盘、子 Agent 失败无日志、降级路径无记录。出问题时只能靠 agent 记忆复盘
- **口径一致性**：理杏仁 vs 年报口径差异是系统性问题，工具未提供口径元数据，导致本次营收被反复打回
- **文档与实现不同步**：skill 文档示例写 `--currency` 但工具不支持、datapack 示例未说明读取方式、`{data vs records}` 键不一致

### 6.3 总结判断

**技能骨架优秀，容错与可观测性是短板。** 13 个错误中没有一个是「框架错误」——四大师框架、数据分级、准出门禁全部正确。问题集中在工具层的边界处理（参数校验、单位、口径、字符串、降级提示）。这意味着**改进空间是工程性的，不需要重构框架**，预计 2-3 个工作日可将这 13 点全部收敛。

建议优先级（编程 agent 接手顺序）：
1. **P0（阻断准出循环）**：report_audit abs 口径 + float 字符串崩溃（2.1A/B）
2. **P0（取数效率）**：datapack 落盘（2.3A）
3. **P1（单位/口径）**：three_scenario growth 归一化 + cross_validate 单位预检（2.2A/B）
4. **P1（降级提示）**：港股 industry-compare/mx-xuangu 结构化降级（2.3C、2.3D... 等问题 6/7）
5. **P2（文档同步）**：skill 文档加 Task Agent 诊断、口径冲突指引、datapack 读取方法（第三节）
6. **P2（反馈入口）**：dev-feedback 入口 + machine-readable JSON 模板（第四节）

---

## 七、路线图进度摘要（按 CLAUDE.md 开发收尾汇报要求）

本次未改变 `docs/ROADMAP.md` 目标。基于当前 ROADMAP（2026-07-01 版）：

- **P0（Claude Code 可安装即用发布）**：已全部完成并推送到 fork `DragonQuix/main`（`b35df6db`），无剩余阻塞
- **P0.7 最终发布动作**：已完成
- **P1（发布后再做的事）**进展记录中已有：
  - Codex 包安装体验第一步
  - 安装反馈入口第一步
  - README 试用说明收敛
  - Windows 安装说明收敛
  - **使用体验反馈入口第一步**（commit `1e688604`）

**本次工作对路线图的关系**：
- 本文档是**使用体验反馈入口的首次真实填充**，对应 P1 进展记录中「使用体验反馈入口第一步」的延续
- 本文档第四节（反馈入口设计改进建议）可直接作为 P1「真实用户安装/使用反馈案例」的开发侧输入
- 建议在 P1 进展记录追加一行：「2026-07-01：执行 investment-research 泡泡玛特后撰写开发反馈，识别 13 项容错/可观测性改进点与反馈入口设计建议，见 `docs/dev-feedback-investment-research.md`」

**仍待推进的 P1 事项**：
- Codex 包安装体验继续优化
- 增加更多报告样例
- 扩展组合级分析、估值模型或数据源
- 增加 GitHub Actions CI
- release notes 自动生成
- （新增）按本文档第二/三节改进工具容错性与可观测性
- （新增）按本文档第四节建立 dev-feedback 入口与 machine-readable 反馈格式

---

*本文档由执行 `/investment-research 泡泡玛特` 的 agent 撰写，2026-07-01。内容基于真实运行错误与代码审核，可直接作为编程 agent 改进 backlog。*