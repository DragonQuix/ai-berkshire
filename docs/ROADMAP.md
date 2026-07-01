# ai-berkshire 交付路线图

> 当前唯一目标：交付一个“普通用户可安装即用”的 Claude Code 版本。
>
> 本路线图取代旧的功能扩张式 roadmap。旧路线图的问题是不断记录新能力切片，却没有封版目标、阻塞清单、准出门禁和新会话接手协议，导致开发持续前进但交付压力不足。后续所有 agent 必须围绕本文件推进，不得再以“继续优化某个功能”为默认方向。

## 0. 当前判断

- 当前日期：2026-07-01
- 当前分支：`main`
- 当前本地状态：本地曾验证为 `main...origin/main [ahead 11]`，说明 GitHub 用户通过默认安装脚本还拿不到最近 11 个提交。
- 当前能力状态：核心投研 skill、组合分析工具、报告审计、Codex reference 同步和测试体系已经较完整。
- 当前交付状态：不建议直接对普通 Claude Code 用户发布；可以内部 beta 使用。
- 当前差距：主要是发布工程和安装链路，估计最小可交付还需 0.5-1 天，稳妥公开交付需 2-3 天。

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
4. 从 P0 中选择第一个未完成任务推进。
5. 每完成一个任务，更新本文件对应 checkbox 和“发布日志”，运行该任务列出的验证命令，创建原子提交。

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

状态：未完成

问题：

- 本地 `main` 曾领先 `origin/main` 11 个提交。用户通过 README 默认 `git clone https://github.com/xbtlin/ai-berkshire.git` 只能拿到远端版本。

必须完成：

- 确认最终发布提交全部在本地 `main`。
- 在最终准出门禁通过后，按项目规则 `git pull --rebase origin main`，解决冲突后再 push。
- push 前不得丢失原子提交边界。

验证命令：

```powershell
git status --short --branch
git log -5 --oneline
```

准出标准：

- push 前：工作区干净，且本地包含本路线图要求的所有修复。
- push 后：`git status --short --branch` 不再显示本地 ahead。

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

状态：未完成

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

状态：未完成

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

状态：未完成

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

状态：未完成

前置条件：

- P0.1-P0.6 全部完成。
- 第 5 节最终准出门禁全部通过。

必须完成：

- 更新发布日志，写清本次 release 面向 Claude Code 普通用户安装使用。
- 创建最终原子提交。
- 按项目规则执行 `git pull --rebase origin main`。
- push 到 `origin main`。
- 如需要 tag，使用明确 tag，例如 `v0.9.0-claude-code-installable`。

验证命令：

```powershell
git status --short --branch
git log -5 --oneline
```

准出标准：

- 远端可通过 README 命令安装到同一版本。

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

## 6. P1：发布后再做的事

P1 只能在 P0 发布完成后启动。

- Codex 包安装体验继续优化。
- 增加真实用户安装反馈案例。
- 增加更多报告样例。
- 继续扩展组合级分析、估值模型或数据源。
- 增加 GitHub Actions CI。
- 做 release notes 自动生成。

P1 不得回填到 P0 之前作为“顺手优化”。

## 7. 发布日志

每个完成 P0 任务的会话必须追加一条记录，格式固定：

```md
- YYYY-MM-DD：完成 P0.x，提交 `<hash>`；验证：`命令` -> `关键结果`；剩余阻塞：P0.y、P0.z。
```

当前记录：

- 2026-07-01：重写路线图为 Claude Code 可安装即用交付路线图；旧功能扩张式路线图停止作为执行依据；P0 阻塞清单成为唯一推进入口。
- 2026-07-01：完成 P0.2，提交 `<a1ae8e83>`；验证：`rg -n --glob '!docs/ROADMAP.md' "C:/Users/admin|C:\\Users\\admin|/Users/linxuan|~/.claude/projects|-Users-linxuan|lixingren_docs" README.md README_EN.md skills codex/ai-berkshire/references/skills docs` -> 无命中；`python -m pytest tests/test_skill_output_regressions.py -q` -> 25 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`git diff --check` -> 通过；剩余阻塞：P0.1、P0.3、P0.4、P0.5、P0.6、P0.7。
- 2026-07-01：完成 P0.3，提交 `<22530ff>`；验证：`rg -n "LIXINGER_TOKEN|MX_DATA_SCRIPT|MX_SEARCH_SCRIPT|MX_XUANGU_SCRIPT|可选|降级|无需 token" README.md skills/financial-data.md docs/lixinger-data-guide.md` -> 命中 README、financial-data、lixinger-data-guide；`python -m pytest tests/test_skill_output_regressions.py -q` -> 28 passed；`python tools\verify_channel_capability.py --quick` -> 全部通过；`git diff --check` -> 通过；剩余阻塞：P0.1、P0.4、P0.5、P0.6、P0.7。
