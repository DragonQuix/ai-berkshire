# 安装反馈记录

本页用于收集“普通用户可安装即用”的真实反馈。提交反馈时不要包含
token、cookie、账户标识、真实本机私有路径或未脱敏日志。

## 反馈入口

- GitHub issue form：`.github/ISSUE_TEMPLATE/install-feedback.yml`
- README 安装后自检：`README.md` / `README_EN.md`

## 最小反馈字段

- 平台：Windows PowerShell、macOS/Linux shell、WSL 或其他兼容层。
- 工具版本：OS、git、python、Claude Code、Codex App。
- 安装命令：完整命令，但必须脱敏本地隐私路径。
- Claude Code 自检：`~/.claude/commands` 下是否有 19 个 `.md` 命令。
- 离线样例：`python tools/portfolio_analyzer.py analyze examples/portfolio-holdings.sample.json --format json` 是否成功。
- Codex 自检：新会话或重启 Codex App 后是否能发现 `ai-berkshire` skill。
- 失败日志：只贴关键错误，移除 token、cookie、账户标识和私有路径。

## 反馈分级

- `pass`：安装、自检、离线样例和 Codex 发现均通过。
- `partial`：Claude Code 或离线样例通过，但 Codex 发现、可选依赖或平台细节有问题。
- `fail`：安装脚本失败、命令数量不对、离线样例不可运行，或文档步骤无法复现。

## 真实反馈记录

暂未收集外部真实用户反馈。收到反馈后按以下格式追加，避免写入任何隐私信息：

```md
- YYYY-MM-DD：平台；安装方式；结果 pass/partial/fail；关键现象；修复或后续动作；关联 issue。
```
