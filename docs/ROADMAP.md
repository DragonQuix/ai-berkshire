# ai-berkshire 交付路线图

> 当前目标：P0 “普通用户可安装即用”的 Claude Code 版本已发布到 fork；当前只按 P1 反馈驱动修复队列推进真实技能运行反馈。
>
> 本路线图取代旧的功能扩张式 roadmap。旧路线图的问题是不断记录新能力切片，却没有封版目标、阻塞清单、准出门禁和新会话接手协议，导致开发持续前进但交付压力不足。后续所有 agent 必须围绕本文件推进，不得再以“继续优化某个功能”为默认方向。

## 0. 当前判断

- 当前日期：2026-07-01
- 当前分支：`main`
- 当前本地状态：`origin` 指向 fork `https://github.com/DragonQuix/ai-berkshire.git`；P0 Claude Code 安装交付修复已推送到 fork。
- 当前能力状态：核心投研 skill、组合分析工具、报告审计、Codex reference 同步和测试体系已经较完整。
- 当前交付状态：P0 已达到“普通用户可安装即用”的 Claude Code 发布准出标准。
- 当前差距：P0 无剩余阻塞；后续只能从 P1 发布后事项中选择。

## 1. 封版原则

### 1.1 交付定义

“普通用户可安装即用”只承诺以下范围：

- 用户按 README 执行安装命令后，`skills/*.md` 能进入 `~/.claude/commands/`。
- 用户在 Claude Code 中能看到并调用 19 个 slash command。
- 不配置任何私有 token 时，用户仍能运行离线/免费源路径和示例 smoke，不会因为作者本机路径报错。
- 需要理杏仁、妙想、Playwright 的能力必须被清楚标为可选增强，并有降级说明。
- README、install 脚本、skill 文档和测试对“19 个 Skill”保持一致。

### 1.2 冻结规则

在 P0 全部完成前禁止：

- 新增投资研究功能。
- 继续扩展 `portfolio_analyzer` 的再平衡理由、评分、展示口径。
- 新增数据源、行业模型、报告模板或 Codex 专属能力。
- 重构不直接服务安装交付的工具。

允许的改动只限：

- 修复安装失败、路径不可移植、文档误导、凭证/隐私泄漏。
- 增加交付 smoke test 或发布检查。
- 修正文档中与当前实现不一致的内容。

## 2. 新会话接手协议

每个新会话必须先做以下动作，不得跳过：

1. 读取 `docs/ROADMAP.md`。
2. 运行 `git status --short --branch`。
3. 运行 `rg -n --glob '!docs/ROADMAP.md' "C:/Users/admin|C:\\\\Users\\\\admin|/Users/linxuan|~/.claude/projects|-Users-linxuan|18 个|16 clear|lixingren_docs" README.md README_EN.md skills codex/ai-berkshire/references/skills docs install.ps1 install.sh`。
4. 若 P0 未全部完成，从 P0 中选择第一个未完成任务推进；若 P0 已完成，从 P1 反馈驱动修复队列选择第一个未完成任务推进。
5. 每完成一个任务，更新本文件对应状态和相关行动计划文档，运行该任务列出的验证命令，创建原子提交。

如果 P0 全部完成：

1. 运行第 5 节“最终准出门禁”。
2. 若全部通过，进入 P0.7 发布动作。
3. 不再寻找新功能。

如果某个任务发现范围扩大：

- 只能拆成 P0 子任务，不得放入 P1/P2 延后后继续声称可发布。
- 新增任务必须写清阻塞原因、验收标准和验证命令。

## 3. 当前已具备的基线能力

这些能力不再作为近期开发目标，只作为发布基线维护：

- 19 个 Claude Code skill 文件位于 `skills/`。
- Codex 原生 skill 位于 `codex/ai-berkshire/`，并含 `references/skills/` 和 `scripts/tools/`。
- 核心工具覆盖：`financial_rigor.py`、`report_audit.py`、`lxr_data.py`、`md2html.py`、`team_research_outputs.py`、`portfolio_analyzer.py` 等。
- `tools/verify_channel_capability.py --quick` 已能校验 19 个 root/Codex skill reference 同步、静态规范、团队研究样例和 depth profile 同步。
- 全量测试近期验证结果：`python -m pytest -q` 为 `350 passed`。
- install 脚本近期语法验证结果：`install.ps1` PowerShell parse OK，`install.sh` bash syntax OK。

这些证据只说明代码基线健康，不等于普通用户可安装即用。

## 4. P0：Claude Code 可安装即用发布阻塞清单

P0 未全部完成前，不得发布，不得 push/tag 作为 release。

### P0.1 远端状态收敛

状态：已完成（发布远端已恢复到 fork，最终 push 由 P0.7 执行）

问题：

- 本地 `main` 曾领先 `origin/main` 11 个提交；P0 修复继续推进后，本地仍需要最终 push 才能让普通用户按 README 安装到最新版本。
- 本项目发布远端是 fork `https://github.com/DragonQuix/ai-berkshire.git`；`https://github.com/xbtlin/ai-berkshire.git` 仅作为上游参考仓库。
- 2026-07-01 曾误将 `origin` 对齐到上游 `xbtlin/ai-berkshire` 并尝试 push，结果因当前 GitHub 凭证无上游写权限返回 403；该失败不代表 fork 发布受阻。
- 2026-07-01 已合并上游 `xbtlin/main` 基线到本地 `main`，但普通用户安装入口、install 脚本和发布 smoke 必须统一指向 fork。

必须完成：

- 确认最终发布提交全部在本地 `main`。
- 确认最终发布提交全部在本地 `main`。=> 已确认。
- 确认最终面向普通用户的发布远端：README 默认 clone URL 必须与 fork `DragonQuix/ai-berkshire` 一致。=> 已确认使用 fork。
- 保留已合并的上游基线：已通过 merge commit `<48bdf67>` 合并 `xbtlin/main`，冲突文件保留本地 P0 发布说明，远端新增报告/脚本/Codex 兼容产物已纳入本地。
- 同步修改 README/README_EN/install/release smoke 中的默认 clone URL，避免普通用户按文档安装到上游仓库。=> 已修正为 `DragonQuix/ai-berkshire`。
- 在最终准出门禁通过后，按项目规则 `git fetch origin main` 并确认 `origin/main` 是本地 `main` 祖先，再 push。=> 当前 fork `origin/main` 已是本地 `main` 祖先，最终 push 由 P0.7 执行。
- push 前不得丢失原子提交边界。

验证命令：

```powershell
git status --short --branch
git log -5 --oneline
git remote -v
git fetch origin main
git ls-remote origin HEAD refs/heads/main
git ls-remote https://github.com/xbtlin/ai-berkshire.git HEAD
git rev-list --left-right --count origin/main...main
git merge-base --is-ancestor origin/main main
```

准出标准：

- push 前：工作区干净，本地包含本路线图要求的所有修复，README 默认 clone URL 与实际发布远端一致，且 `origin/main` 是本地 `main` 的祖先。
- push 后：`git status --short --branch` 不再显示本地 ahead（由 P0.7 最终发布动作验证）。

### P0.2 移除作者机器硬编码路径

状态：已完成

问题：

- 多个 skill 仍包含 `C:/Users/admin/.claude/skills/mx-*`。
- `deep-company-series.md` 含 `~/.claude/projects/-Users-linxuan/...` 隐私路径。
- `docs/lixinger-data-guide.md` 含 `C:/Users/admin/Documents/lixingren_docs/offline-docs/`。
- 普通用户安装后没有这些路径，执行流程会卡死或误导。

必须完成：

- 将所有 skill 中的妙想调用统一改为 `python tools/lxr_data.py mx-data ...`、`python tools/lxr_data.py mx-search ...`、`python tools/lxr_data.py mx-xuangu ...`。
- 如需直连外部脚本，只能通过环境变量说明，例如 `MX_DATA_SCRIPT`、`MX_SEARCH_SCRIPT`、`MX_XUANGU_SCRIPT`，不得写作者本机绝对路径。
- 删除或泛化所有个人隐私路径。
- root skill 与 Codex reference 必须同步。

当前已知命中文件：

- `skills/industry-funnel.md`
- `skills/quality-screen.md`
- `skills/management-deep-dive.md`
- `skills/news-pulse.md`
- `skills/portfolio-review.md`
- `skills/thesis-tracker.md`
- `skills/wechat-article.md`
- `skills/deep-company-series.md`
- 对应 `codex/ai-berkshire/references/skills/*.md`
- `docs/lixinger-data-guide.md`

必须新增或扩展测试：

- 在 `tests/test_skill_output_regressions.py` 或新增发布检查测试中扫描 README、skills、Codex references 和关键 docs，禁止出现作者机器路径。

验证命令：

```powershell
rg -n --glob '!docs/ROADMAP.md' "C:/Users/admin|C:\\Users\\admin|/Users/linxuan|~/.claude/projects|-Users-linxuan|lixingren_docs" README.md README_EN.md skills codex/ai-berkshire/references/skills docs
python -m pytest tests/test_skill_output_regressions.py -q
python tools\verify_channel_capability.py --quick
```

准出标准：

- 上述 `rg` 对发布面文件无命中。
- 相关测试通过。

### P0.3 明确外部数据依赖与降级合同

状态：已完成

问题：

- 用户不一定有理杏仁 token、妙想 skills、Playwright 或私有数据源。
- 当前文档对“核心可用”和“增强可用”的边界不够清晰。

必须完成：

- README 新增“数据源与可选依赖”小节。
- 明确三层能力：
  - 核心离线能力：无需 token，可运行工具、样例、报告框架、组合分析、HTML 转换、审计工具。
  - 免费/公开源能力：东方财富等免费源可用，但可能受网络和站点变化影响。
  - 私有增强能力：理杏仁 `LIXINGER_TOKEN`、妙想 mx 系列、Playwright 雪球爬虫，均为可选。
- 明确无 token 时如何处理：不报“安装失败”，只降级或提示用户补配置。
- 更新 `tools/lxr_config.example.json` 的引用说明，不要求用户提交真实 token。

验证命令：

```powershell
rg -n "LIXINGER_TOKEN|MX_DATA_SCRIPT|MX_SEARCH_SCRIPT|MX_XUANGU_SCRIPT|可选|降级|无需 token" README.md skills/financial-data.md docs/lixinger-data-guide.md
python -m pytest tests/test_skill_output_regressions.py -q
```

准出标准：

- 普通用户能从 README 判断：哪些功能安装后即可用，哪些需要额外凭证。

### P0.4 安装脚本和 README 对齐

状态：已完成

问题：

- README 当前写“18 个 Skill”，实际为 19 个。
- README 写“检查前置条件（git, python, claude）”，但安装脚本当前主要检查 git/python。
- 手动安装说明只说复制 `skills/*.md`，但很多命令依赖仓库内 `tools/` 和 `docs/`。

必须完成：

- README、README_EN、install 输出、测试常量都统一为 19 个 skill。
- 明确 `claude` CLI 是推荐前置条件还是硬性前置条件；若是硬性，脚本检查；若不是，README 不写“脚本检查 claude”。
- 手动安装说明必须写清：复制 `skills/*.md` 只安装命令定义；若要工具链可用，必须保留仓库目录并在命令中从仓库根目录运行，或使用安装脚本。
- 安装脚本的 `--help`、成功输出和 README 示例保持一致。

验证命令：

```powershell
rg -n --glob '!docs/ROADMAP.md' "18 个|16 clear|19 个|claude" README.md README_EN.md install.ps1 install.sh tests tools
$tokens = $null; $errors = $null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'install.ps1'), [ref]$tokens, [ref]$errors) > $null; if ($errors.Count) { $errors; exit 1 }
bash -n install.sh
python -m pytest tests/test_skill_output_regressions.py -q
```

准出标准：

- 文档和脚本不再出现错误数量。
- 安装前置条件描述与脚本行为一致。

### P0.5 干净安装 smoke test

状态：已完成

问题：

- 当前验证多发生在开发工作区，未证明普通用户从干净目录安装后可用。

必须完成：

- 新增一个发布 smoke 测试脚本，推荐路径：`tools/release_smoke.py`。
- smoke 至少验证：
  - `skills/*.md` 数量为 19。
  - `install.ps1` 可解析。
  - `install.sh` 可 `bash -n`。
  - `tools/lxr_config.json` 未被 Git 跟踪。
  - 发布面文件无作者机器路径。
  - 核心样例可运行：`portfolio_analyzer.py analyze examples/portfolio-holdings.sample.json --format json`。
  - README 中的安装命令和 skill 数量与实际一致。
- 如果实现临时 HOME 安装测试，必须只写入临时目录，不污染真实 `~/.claude`。

验证命令：

```powershell
python tools\release_smoke.py
python -m pytest tests/test_release_smoke.py -q
```

准出标准：

- 一条命令能给出发布是否可交付的明确 PASS/FAIL。

### P0.6 Claude Code 快速使用闭环

状态：已完成

问题：

- 用户安装后需要知道如何确认安装成功，以及如何跑第一个不依赖私有 token 的用例。

必须完成：

- README 新增“安装后自检”。
- 自检必须包含：
  - 检查 `~/.claude/commands` 下有 19 个命令。
  - 在仓库根目录运行 portfolio 示例命令。
  - 在 Claude Code 中调用一个轻量命令，例如 `/dyp-ask` 或 `/portfolio-review` 的最小输入。
- 明确如果 Claude Code 看不到命令，应新开 Claude Code 会话或检查 `~/.claude/commands`。

验证命令：

```powershell
rg -n "安装后自检|19 个|portfolio-holdings.sample.json|~/.claude/commands|/dyp-ask|/portfolio-review" README.md README_EN.md
```

准出标准：

- 新用户不用读源码即可完成安装验证。

### P0.7 最终发布动作

状态：已完成（已推送到 fork `origin/main`）

前置条件：

- P0.1-P0.6 全部完成。
- 第 5 节最终准出门禁全部通过。

必须完成：

- 更新发布日志，写清本次 release 面向 Claude Code 普通用户安装使用。
- 创建最终原子提交。
- 按项目规则执行 `git pull --rebase origin main`。
- push 到 `origin main`。
- 如需要 tag，使用明确 tag，例如 `v0.9.0-claude-code-installable`。

完成记录：

- 2026-07-01 已重新运行最终准出门禁，全部通过。
- 已按项目规则执行 `git pull --rebase origin main`；该命令因 rebase 展开旧提交并在历史文件上冲突。为保留 P0 原子提交和 merge commit `<48bdf67>`，已中止 rebase。
- 已用 `git rev-list --left-right --count origin/main...main` -> `0 52` 和 `git merge-base --is-ancestor origin/main main` -> 通过，证明 fork 远端无新增提交且可 fast-forward。
- 已执行 `git push --progress --porcelain origin main`；fork `DragonQuix/main` 从 `92e3ccd3` 更新到 `b35df6db`。

验证命令：

```powershell
git status --short --branch
git log -5 --oneline
git push --progress --porcelain origin main
```

准出标准：

- 远端可通过 README 命令安装到同一版本。
- `git status --short --branch` 不再显示本地 ahead。

## 5. 最终准出门禁

发布前必须逐条运行并记录结果：

```powershell
git status --short --branch
python -m pytest -q
python tools\verify_channel_capability.py --quick
python -m compileall -q tools codex\ai-berkshire\scripts\tools
python tools\release_smoke.py
git diff --check
```

如果 `git diff --check` 只有 Windows 行尾提示且退出码为 0，可通过；若出现 trailing whitespace 或 conflict marker，必须修复。

发布面路径扫描必须无命中：

```powershell
rg -n --glob '!docs/ROADMAP.md' "C:/Users/admin|C:\\Users\\admin|/Users/linxuan|~/.claude/projects|-Users-linxuan|lixingren_docs|18 个|16 clear" README.md README_EN.md skills codex/ai-berkshire/references/skills docs install.ps1 install.sh
```

最近本地准出门禁记录：

- 2026-07-01：本地 `main` 在 `fc2940c9` 通过最终准出门禁；验证：`git status --short --branch` -> `main...origin/main [ahead 22]`；`python -m pytest -q` -> 363 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`python -m compileall -q tools codex\ai-berkshire\scripts\tools` -> 通过；`python tools\release_smoke.py` -> PASS release smoke；`git diff --check` -> 通过；发布面路径扫描 -> 无命中。该记录只证明当时本地状态可发布，后续已继续处理 P0.1 远端收敛。

## 6. P1：发布后再做的事

P1 只能在 P0 发布完成后启动。

- Codex 包安装体验继续优化。
- 增加真实用户安装反馈案例。
- 增加更多报告样例。
- 继续扩展组合级分析、估值模型或数据源。
- 增加 GitHub Actions CI。
- 做 release notes 自动生成。
- 按真实技能运行反馈收敛工具容错性、可观测性和口径元数据，优先处理会阻断报告准出的缺陷。

P1 不得回填到 P0 之前作为“顺手优化”。

P1 反馈驱动修复队列（按 `docs/dev-feedback-action-plan.md` 执行）：

- P1-A1：`report_audit.py` 数值韧性，修复非数值核验崩溃、负号抽取丢失和方向/幅度比较口径。=> 已完成。
- P1-A2：`lxr_data.py datapack` 可复现输出，支持落盘、复用和降级/mx raw 记录。=> 已完成 `--output/-o` 与 `--output-dir` 落盘；mx raw 路径保留在各 mx section。
- P1-A3：`financial_rigor.py` 参数防呆，处理三情景增长率误填、交叉验证量级错位和口径说明。=> 已完成。
- P1-B1：Task Agent 失败诊断与降级记录，避免子 agent 路由失败被无声吞掉。=> 已完成。
- P1-B2：港股行业对比降级说明，给出申万不适用时的替代路径。=> 已完成。
- P1-B3：财务口径元数据，把理杏仁字段口径、年报口径、币种和单位传到报告与审计环节。

P1 进展记录：

- 2026-07-01：Codex 包安装体验第一步，`tools/release_smoke.py` 增加 Codex package contract，检查 `codex/ai-berkshire/SKILL.md`、19 个 reference、关键 bundled tools、禁止私有 `lxr_config.json` 进入 Codex 包，并校验 `scripts/tools/*.py` 与 root `tools/*.py` 同步。
- 2026-07-01：安装反馈入口第一步，新增 `.github/ISSUE_TEMPLATE/install-feedback.yml`、`docs/install-feedback.md` 和 README/README_EN 入口，用于收集普通用户安装、自检、Codex 发现和脱敏失败日志。
- 2026-07-01：最终用户试用前 README 收敛，README/README_EN 顶部补充“项目能做什么/首次试用建议”，安装后自检改为核对 19 个 AI Berkshire 命令名，避免已有其他 Claude Code 命令时误判目录总数。
- 2026-07-01：Windows 安装说明收敛，README/README_EN 明确 `install.ps1` 应使用 PowerShell 7 `pwsh` 执行，避免 Windows PowerShell 5.1 按 ANSI 误读 UTF-8 脚本。
- 2026-07-01：使用体验反馈入口第一步，新增 `.github/ISSUE_TEMPLATE/usage-feedback.yml`、`docs/usage-feedback.md` 和 README/README_EN 入口，用于收集命令使用场景、脱敏输入、结果体验、卡点、改进建议和匿名引用授权。
- 2026-07-01：完成 `/investment-research 泡泡玛特` 运行复盘的独立核查，确认 `report_audit`、`financial_rigor`、`lxr_data datapack`、Task Agent 降级记录和口径元数据的 P1 修复队列，见 `docs/dev-feedback-action-plan.md`。
- 2026-07-01：开发反馈入口第一步，新增 `.github/ISSUE_TEMPLATE/dev-feedback.yml`、`docs/dev-feedback.md` 和 README/README_EN 入口，用于收集执行 agent 的错误链、复现证据、源码位置、技术评价和 machine-readable JSON。
- 2026-07-01：完成 P1-A1 `report_audit.py` 数值韧性修复，保留表格正负号、非数值核验值安全跳过、默认保留符号比较，并支持显式 `compare_mode=absolute_magnitude`；root 工具与 Codex bundled 副本已同步。
- 2026-07-01：完成 P1-A2 `lxr_data.py datapack` 可复现输出，datapack CLI 支持 `--output/-o` 指定文件和 `--output-dir` 默认文件名，stdout 保持 JSON，落盘提示写 stderr；`investment-research` 文档改为主 Agent 读取 `_tmp_{code}_datapack.json`。
- 2026-07-01：完成 P1-A3 `financial_rigor.py` 参数防呆与口径提示，`three-scenario` 对误填百分数增长率自动归一并写 stderr 警告，`cross-validate` 增加量级错位告警、`--caliber` 口径输出，并把“加权中位数”文案改为“参考中位数”；root 工具、Codex bundled 副本和 `investment-research` 文档已同步。
- 2026-07-01：完成 P1-B1 Task Agent 失败诊断与降级记录，`investment-research` 及 9 个团队型/多 Agent skill 均要求记录 `model route not configured`、`timeout`、`permission denied` 等失败，降级为「顺序角色模拟」时必须在报告或素材附录写入失败 Agent、错误原文摘要、降级方式和影响范围；root skill 与 Codex reference 已同步。
- 2026-07-01：完成 P1-B2 港股行业对比降级说明，`industry-compare` 对港股返回 `note` 与 `alternatives`，提示申万行业分类仅覆盖 A 股，并给出 `mx-xuangu`、手工指定同业、港股行业龙头/主要可比公司三条替代路径；`investment-research` D2 行业水位不再要求港股申万同行分位，root 工具、Codex bundled 副本和 skill reference 已同步。

## 7. 发布日志

每个完成 P0 任务的会话必须追加一条记录，格式固定：

```md
- YYYY-MM-DD：完成 P0.x，提交 `<hash>`；验证：`命令` -> `关键结果`；剩余阻塞：P0.y、P0.z。
```

当前记录：

- 2026-07-01：重写路线图为 Claude Code 可安装即用交付路线图；旧功能扩张式路线图停止作为执行依据；P0 阻塞清单成为唯一推进入口。
- 2026-07-01：完成 P0.2，提交 `<a1ae8e83>`；验证：`rg -n --glob '!docs/ROADMAP.md' "C:/Users/admin|C:\\Users\\admin|/Users/linxuan|~/.claude/projects|-Users-linxuan|lixingren_docs" README.md README_EN.md skills codex/ai-berkshire/references/skills docs` -> 无命中；`python -m pytest tests/test_skill_output_regressions.py -q` -> 25 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`git diff --check` -> 通过；剩余阻塞：P0.1、P0.3、P0.4、P0.5、P0.6、P0.7。
- 2026-07-01：完成 P0.3，提交 `<22530ff>`；验证：`rg -n "LIXINGER_TOKEN|MX_DATA_SCRIPT|MX_SEARCH_SCRIPT|MX_XUANGU_SCRIPT|可选|降级|无需 token" README.md skills/financial-data.md docs/lixinger-data-guide.md` -> 命中 README、financial-data、lixinger-data-guide；`python -m pytest tests/test_skill_output_regressions.py -q` -> 28 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`git diff --check` -> 通过；剩余阻塞：P0.1、P0.4、P0.5、P0.6、P0.7。
- 2026-07-01：完成 P0.4，提交 `<641bf4a>`；验证：`rg -n --glob '!docs/ROADMAP.md' "18 个|16 clear|19 个|claude" README.md README_EN.md install.ps1 install.sh tests tools` -> 仅命中 19 个与 claude 预期说明，无旧错误数量；PowerShell 解析 `install.ps1` -> 通过；`bash -n install.sh` -> 通过；`python -m pytest tests/test_skill_output_regressions.py -q` -> 33 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`git diff --check` -> 通过；剩余阻塞：P0.1、P0.5、P0.6、P0.7。
- 2026-07-01：完成 P0.5，提交 `<5a72772>`；验证：`python tools\release_smoke.py` -> PASS release smoke；`python -m pytest tests/test_release_smoke.py -q` -> 2 passed；剩余阻塞：P0.1、P0.6、P0.7。
- 2026-07-01：完成 P0.6，提交 `<06e86a9>`；验证：`rg -n "安装后自检|19 个|portfolio-holdings.sample.json|~/.claude/commands|/dyp-ask|/portfolio-review" README.md README_EN.md` -> 命中安装后自检、19 个命令、portfolio 样例、Claude Code 轻量命令和排障提示；`python -m pytest tests/test_skill_output_regressions.py -q` -> 35 passed；剩余阻塞：P0.1、P0.7。
- 2026-07-01：完成 P0.1 上游基线合并，提交 `<48bdf67>`；验证：`git rev-list --left-right --count origin/main...main` -> `0 201`（当时 origin 指向上游）；`git merge-base --is-ancestor origin/main main` -> 通过；`python -m pytest -q` -> 363 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`python tools\release_smoke.py` -> PASS release smoke；剩余阻塞：P0.7。
- 2026-07-01：完成 P0.7 fork 发布，提交 `<b35df6db>`；验证：`git status --short --branch` -> `main...origin/main [ahead 52]`（push 前）；`python -m pytest -q` -> 363 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`python -m compileall -q tools codex\ai-berkshire\scripts\tools scripts` -> 通过；`python tools\release_smoke.py` -> PASS release smoke；`git diff --check` -> 通过；发布面路径扫描 -> 无命中；`git push --progress --porcelain origin main` -> `92e3ccd3..b35df6db` 推送到 `DragonQuix/main`；剩余阻塞：无。
