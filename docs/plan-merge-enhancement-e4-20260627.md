# 合并 feat/enhancement-e4 到 main 的执行计划

> 起草日期：2026-06-27
> 工作区：`E:\Repos\Skills\ai-berkshire`
> 当前 main 顶端：`f9083e0`（F1 修复：`_source` 字段规范全量覆盖，已推送 origin/main）
> 目标分支：`feat/enhancement-e4`（实现 `lxr_data.py` 的 `mx-xuangu` / `quality-metrics` 子命令）
> 执行者：有 git/python 权限的 Agent（本会话 shell 挂起，无法亲自执行）

## 一、背景

F1 修复已合并到 main 并推送（commit `f9083e0`）。段 2 验证在 main 必 FAIL：

```
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet
```

两条均报 `invalid choice`——`lxr_data.py` 子命令表止于 `industry-compare`。这两个子命令的实现在 `feat/enhancement-e4`，需合并到 main 才能让段 2 转通过。

## 二、合并前侦察（必须先跑，结果决定后续策略）

```powershell
cd E:\Repos\Skills\ai-berkshire
git fetch origin

# 1) e4 分支存在性与领先/落后关系
git branch -a --list "*enhancement-e4*"
git log --oneline --left-right --graph main...origin/feat/enhancement-e4 | head -n 40

# 2) e4 相对 main 改了哪些文件（冲突面）
git diff --stat main..origin/feat/enhancement-e4
git diff --name-status main..origin/feat/enhancement-e4

# 3) verify_channel_capability.py 在 e4 是否已存在（add/add 冲突预判）
git cat-file -e origin/feat/enhancement-e4:tools/verify_channel_capability.py 2>&1
git ls-tree origin/feat/enhancement-e4 -- tools/verify_channel_capability.py

# 4) 6 个 skill 文件在 e4 是否也改过（三路合并冲突预判）
git diff --name-only main..origin/feat/enhancement-e4 -- `
  skills/news-pulse.md skills/earnings-review.md skills/bottleneck-hunter.md `
  codex/ai-berkshire/references/skills/news-pulse.md `
  codex/ai-berkshire/references/skills/earnings-review.md `
  codex/ai-berkshire/references/skills/bottleneck-hunter.md

# 5) e4 端真实 quality-metrics JSON key 名（对齐 EXPECTED_CHECK_KEYS 的依据）
git show origin/feat/enhancement-e4:tools/lxr_data.py | `
  Select-String -Pattern "quality-metrics|share_dilution_5y|roe_10y_avg|fcf_5y_cum|interest_coverage|gross_margin_long|ocf_to_ni_5y|net_margin_long" -Context 0,2 | head -n 80

# 6) e4 端 lxr_data.py 子命令全貌（确认 mx-xuangu/quality-metrics 已加）
git show origin/feat/enhancement-e4:tools/lxr_data.py | Select-String "add_parser" | head -n 40
```

## 三、合并策略

默认采用 **`git merge --no-ff origin/feat/enhancement-e4`**，保留合并提交，便于追溯与回滚。

若侦察显示 e4 仅 1-2 提交且与 main 无并行开发，可改用 rebase；但 e4 已 push 到 origin，rebase 需 force-push，风险更高，**不推荐**。

## 四、冲突预判与解决策略

### 冲突高概率 1：`tools/verify_channel_capability.py`（add/add）

- **main 端**（commit `f9083e0`）：含 B 类静态校验（`_source` 覆盖 + 根/Codex SHA256 同步）；A 类 quality-metrics JSON 有效值断言的 `EXPECTED_CHECK_KEYS` 可能与 e4 真实 key 不一致
- **e4 端**：可能有另一份同名脚本，对齐了真实 quality-metrics JSON key
- **解决策略**：**不要简单 `--ours` 或 `--theirs`**。以 e4 版本为基底，手工移植 main 端的 B 类校验段：
  - `TARGETS` 列表
  - `check_source_coverage()`
  - `check_sync()`
  - `check_skills_source_and_sync()`
  - `--quick` 入口分支
- A 类断言的 `EXPECTED_CHECK_KEYS` 用侦察第 5 项查到的真实 key 替换，**不得沿用 main 端可能过时的 key 名**

### 冲突高概率 2：6 个 skill 文件（若 e4 也改过）

- **main 端**：补了 `_source` 标注条款（`_source: mx-search` / `mx-data` / `web` / `理杏仁`）
- **e4 端**：可能有其它增强（新数据调用段落）
- **解决策略**：保留两端改动。main 的 `_source` 标注必须留下；e4 新增段落若含数据源调用，也需补 `_source` 标注。冲突多为上下文相邻行，手工合并。
- **合并后必须再次校验根/Codex 副本 SHA256 一致**（`python tools/verify_channel_capability.py --quick` 的 B 类会自动检查）

### 低风险：`tools/lxr_data.py`

- e4 加了 `mx-xuangu` / `quality-metrics` 子命令，main 未动此文件 → 应自动合并无冲突

## 五、合并执行

```powershell
# 确保 main 最新
git checkout main
git pull --rebase origin main

# 合并 e4（保留合并提交）
git merge --no-ff origin/feat/enhancement-e4 -m "合并 feat/enhancement-e4：lxr_data.py 新增 mx-xuangu/quality-metrics 子命令"

# 若遇冲突，按第四章策略解决；解完逐个 git add
git status --short
# 全部 add 后完成合并提交
git commit
```

## 六、合并后验证（必须全绿才算完成）

```powershell
$env:PYTHONIOENCODING='utf-8'

# 1) 段 2 转通过（合并核心目标）
python tools/lxr_data.py mx-xuangu "ROE>15% PE<30 消费股" --ttl 0
python tools/lxr_data.py quality-metrics 600132 --years 5 --quiet

# 2) A 类有效值断言（需对齐真实 key 后通过）
python tools/verify_channel_capability.py

# 3) B 类静态校验不应回归
python tools/verify_channel_capability.py --quick

# 4) 回归
python -m compileall -q tools codex/ai-berkshire/scripts/tools
python -m pytest -q
$env:PYTHONUTF8='1'
python "$env:USERPROFILE\.claude\skills\skill-creator\scripts\quick_validate.py" codex\ai-berkshire

# 5) 状态确认
git status --short --branch
```

### 合并后断言清单

- `mx-xuangu` / `quality-metrics` 子命令可执行（不再 `invalid choice`）
- `quality-metrics 600132` 输出含：`_source=lixinger`、7 项 checks、`share_dilution_5y` 非 missing 且 value 为有效数值、`result/status=pass`
- `verify_channel_capability.py`（full）A+B 全绿
- `verify_channel_capability.py --quick` B 类不回归（6 文件 `_source` 覆盖 + 根/Codex SHA256 同步一致）
- `pytest` 不回归（基线 38 passed）
- Codex Skill 格式仍 `valid`

## 七、推送与回滚

```powershell
# 验证全绿后推送
git push origin main

# 若合并后验证失败、且合并提交未 push：
git reset --hard f9083e0   # 回到合并前 main 顶端

# 若已 push，用 git revert <merge-commit> 而非 reset
```

## 八、关键约束

1. **不切分支到 e4 长期停留**：在 main 上 merge e4，不在 e4 上操作
2. **冲突解决优先采信 e4 的 quality-metrics 实现**，再保留 main 的 `_source`/同步静态校验段
3. **不得谎称验证通过**：每条验证命令必须实际执行并贴真实输出；任一关键验证失败不得声称完成
4. **不得擅自 force-push**：除非用户明确同意
5. **只改与合并直接相关的文件**：不顺手重构无关代码
