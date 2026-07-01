# Release notes 自动生成

`tools/release_notes.py` 用本地 Git 提交生成 Markdown 发布说明，默认范围为 `origin/main..HEAD`，不联网、不读取私有 token，也不写入仓库文件，除非显式传 `--output`。

## 常用命令

```powershell
python tools\release_notes.py
python tools\release_notes.py --from origin/main --to HEAD --title "P1 本地待发布变更"
python tools\release_notes.py --from origin/main --to HEAD --output docs\release-notes-draft.md
```

## 分组规则

工具按 conventional commit 前缀分组：

- `feat` -> 功能
- `fix` -> 修复
- `ci` / `build` -> CI / 发布工程
- `docs` -> 文档
- `test` -> 测试
- `chore` / `refactor` / `perf` / `style` -> 工程维护
- 其他提交 -> 其他

提交标题建议继续使用项目约定的中文 conventional commit，例如：

```text
fix(metadata): 增加财务口径元数据
ci: 增加离线回归门禁
docs(feedback): 增加技能执行复盘
```

## 发布前使用方式

1. 本地完成 P1 任务并通过验证。
2. 运行 `python tools\release_notes.py --from origin/main --to HEAD --output docs\release-notes-draft.md` 生成草稿。
3. 人工审阅草稿，必要时改写为面向用户的 release notes。
4. 草稿文件默认不要求提交；正式发布说明应按当次发布策略写入 GitHub Release 或指定文档。

`tools/release_smoke.py` 已包含 release notes dry run，确保该工具在发布门禁中不会退化。
