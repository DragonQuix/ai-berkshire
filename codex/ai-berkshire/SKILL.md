---
name: ai-berkshire
description: AI Berkshire value-investing research workflows for Codex. Use when the user asks for company investment research, earnings review, portfolio review, industry research, quality screening, valuation checks, management deep dives, Buffett/Munger/Duan Yongping/Li Lu style analysis, or explicitly mentions AI Berkshire slash commands such as /investment-research, /investment-team, /earnings-review, /industry-funnel, /portfolio-review, /news-pulse, /dyp-ask.
---

# AI Berkshire for Codex

Use this skill to run AI Berkshire's value-investing research workflows in Codex while preserving the original Claude Code slash-command prompts as references.

## Core rules

- Keep analysis objective: separate facts from opinions, cite sources, show both positive and negative evidence, and say "数据不足" when evidence is incomplete.
- Do not pre-decide bullish or bearish conclusions. Gather data first, reason second, conclude last.
- Use Chinese for final reports unless the user explicitly requests another language.
- For current market data, earnings, news, prices, filings, management changes, or regulations, verify with live sources before writing conclusions.
- For key financial numbers, require at least two independent sources when feasible. If sources differ by more than 1%, flag the mismatch.
- Never rely on LLM mental math for market cap, PE, valuation, or scenario analysis. Use the bundled Python tools or equivalent exact calculations.

## Workflow selection

If the user names a slash command, use the matching reference file. If not, infer the closest workflow:

| User intent | Reference file |
| --- | --- |
| Deep listed-company research | `references/skills/investment-research.md` |
| Multi-role investment team analysis | `references/skills/investment-team.md` |
| Buffett-style pre-buy checklist | `references/skills/investment-checklist.md` |
| Earnings or annual-report review | `references/skills/earnings-review.md` |
| Earnings team plus publishable article | `references/skills/earnings-team.md` |
| Management or founder deep dive | `references/skills/management-deep-dive.md` |
| Private-company research | `references/skills/private-company-research.md` |
| Industry map or full industry research | `references/skills/industry-research.md` |
| Industry funnel screening | `references/skills/industry-funnel.md` |
| Quality screen / eliminate weak companies | `references/skills/quality-screen.md` |
| Portfolio review | `references/skills/portfolio-review.md` |
| Thesis tracking | `references/skills/thesis-tracker.md` |
| News or stock-price move diagnosis | `references/skills/news-pulse.md` |
| Duan Yongping style Q&A | `references/skills/dyp-ask.md` |
| Financial data sourcing rules | `references/skills/financial-data.md` |
| Public-account article rewrite | `references/skills/wechat-article.md` |
| Long company article series | `references/skills/deep-company-series.md` |
| Bottleneck / scarcity map | `references/skills/bottleneck-hunter.md` |

Read only the selected reference file first. Read `references/skills/financial-data.md` when the workflow requires financial data sourcing or cross-validation.

## Codex adaptation

The reference files were originally written as Claude Code slash commands. Apply these translations in Codex:

- Treat `$ARGUMENTS` as the user's company, ticker, industry, period, portfolio, or question.
- Treat Claude Code `Task` / `Team` instructions as a role decomposition pattern. Use Codex subagents only when available and useful; otherwise perform the roles sequentially and label each role's findings.
- Treat Bash snippets as examples. On Windows, prefer `python`; on macOS/Linux, prefer `python3` when available.
- Replace `~/ai-berkshire/tools/...` with the bundled tools under `scripts/tools/...` or with the repository's `tools/...` when working inside an AI Berkshire checkout.
- Preserve report naming and directory rules from the repository `AGENTS.md` when the current workspace is AI Berkshire.

## Tooling

Bundled deterministic tools live under `scripts/tools/`:

- `financial_rigor.py`: market cap, valuation, cross-source checks, scenario math.
- `report_audit.py`: report quality and data-source audit.
- `stock_screener.py`: structured screening helpers.
- `morningstar_fair_value.py`: Morningstar fair-value data helper when configured.
- `ashare_data.py`: A-share data helper.

Before finalizing a report that contains valuation or market-cap math, run the relevant `financial_rigor.py` command or an equivalent exact calculation and include the verification result or a concise summary.

## Output standards

- Lead with the conclusion, then evidence, then uncertainties and risks.
- Mark facts, estimates, assumptions, and opinions clearly.
- Include source links for web-derived facts.
- Use `★1-5` ratings where the selected workflow calls for scoring.
- For generated reports in this repository, save to `reports/` using the naming rules in `AGENTS.md`.
