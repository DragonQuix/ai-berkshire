# 使用体验反馈

本页用于收集用户在 Claude Code 或 Codex 中实际使用 AI Berkshire 后的体验、卡点和经验。
请不要提交真实持仓金额、账户标识、token、cookie、未脱敏日志或真实本机私有路径。

## 反馈入口

- GitHub issue form：`.github/ISSUE_TEMPLATE/usage-feedback.yml`
- 安装失败、命令不可见或自检不通过：请优先使用 `.github/ISSUE_TEMPLATE/install-feedback.yml`

## 最小反馈字段

- 使用场景：公司研究、财报解读、组合复盘、行业研究、管理层分析、新闻脉冲、文章改写等。
- 使用命令：例如 `/dyp-ask`、`/portfolio-review`、`/investment-research`。
- 脱敏输入：贴简化后的 prompt，用比例或匿名样例替代真实账户和敏感数据。
- 结果体验：哪些地方有帮助，哪些地方太啰嗦、不清楚、不可执行或缺少依据。
- 卡点：命令可见性、数据源、报告结构、术语、速度、幻觉、缺少反面证据等。
- 期望改进：希望新增的说明、样例、命令行为或报告结构。
- 匿名引用授权：是否允许把反馈整理进 README 或 docs 作为用户案例。

## 反馈分级

- `useful`：输出能直接辅助研究、复盘或下一步决策。
- `mixed`：部分有帮助，但仍需要大量人工重写、补数据或纠偏。
- `blocked`：命令能启动，但流程结果无法用于当前任务。

## 真实反馈记录

暂未收集外部真实用户使用反馈。收到反馈后按以下格式追加，避免写入任何隐私信息：

```md
- YYYY-MM-DD：场景；命令；结果 useful/mixed/blocked；关键体验；期望改进；是否可匿名引用；关联 issue。
```
