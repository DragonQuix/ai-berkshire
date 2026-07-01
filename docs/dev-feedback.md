# 开发反馈

本页用于收集 agent 或维护者在完整运行某个 AI Berkshire skill 后形成的代码级复盘。它不同于普通使用体验反馈：这里需要能帮助编程 agent 复现、定位和修复问题。

请不要提交 token、cookie、账户标识、真实持仓金额、未脱敏日志或真实本机私有路径。

## 什么时候使用

- 已经完整运行过一个 skill，例如 `/investment-research`、`/portfolio-review`、`/earnings-review`。
- 运行中出现可复现错误、工具崩溃、参数误导、数据口径冲突、降级路径缺失或文档与实现不一致。
- 反馈者能提供至少一个证据：命令、退出码、错误摘要、相关文件/函数、最小复现输入或脱敏 raw 片段。

普通用户只想反馈“有用/不好用/卡在哪里”时，请使用 `docs/usage-feedback.md`。
安装失败、命令不可见或自检不通过时，请使用 `docs/install-feedback.md`。

## 反馈入口

- GitHub issue form：`.github/ISSUE_TEMPLATE/dev-feedback.yml`
- 参考样本：`docs/dev-feedback-investment-research.md`
- 当前核查后的修复方案：`docs/dev-feedback-action-plan.md`

## 最小反馈字段

- Skill 和深度：例如 `/investment-research --depth standard`。
- 运行版本：提交 hash、安装方式、Claude Code/Codex 环境。
- 结果分级：`blocked`、`mixed`、`usable-with-warnings`。
- 错误链：按发生顺序列出阶段、现象、错误摘要和影响。
- 复现证据：命令、退出码、日志片段、脱敏 raw、相关文件和行号。
- 独立评价：哪些建议已验证，哪些只是推测，哪些需要更多样本。
- 最小修复建议：目标文件、测试位置、验收命令。

## Machine-readable JSON 模板

```json
{
  "feedback_version": "1.0",
  "date": "2026-07-01",
  "skill": "investment-research",
  "depth": "standard",
  "runtime": "Claude Code",
  "commit": "unknown",
  "tier": "mixed",
  "errors": [
    {
      "stage": "datapack",
      "symptom": "datapack command printed JSON but no file was created",
      "evidence": "python tools/lxr_data.py datapack --help has no --output option",
      "target_files": ["tools/lxr_data.py", "skills/investment-research.md"],
      "suggested_fix": "add --output and document how the main agent reads the JSON"
    }
  ],
  "degradations": [
    {
      "kind": "agent_route",
      "message": "model route not configured",
      "fallback": "main agent simulated the role sequentially"
    }
  ],
  "caliber_conflicts": [
    {
      "field": "revenue",
      "source_a": "Lixinger toi",
      "source_b": "annual report revenue",
      "decision_needed": "add caliber metadata before strict comparison"
    }
  ],
  "verification_commands": [
    "python -m pytest tests/test_report_audit.py -q"
  ],
  "privacy_checked": true
}
```

## 真实开发反馈记录

```md
- 2026-07-01：`/investment-research 泡泡玛特`；结果 mixed；识别工具容错、口径与可观测性问题；原始反馈见 `docs/dev-feedback-investment-research.md`；核查后方案见 `docs/dev-feedback-action-plan.md`。
```

