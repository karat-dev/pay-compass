# AGENTS.md

## Token-saving rules for agents

1. Model by task: fast standard model by default. Use a strong model only for migrations, payments, auth, prod. No Max Mode unless needed.
2. One task = one agent = one PR. More than 5 continuations or one run over 15M tokens: close the agent and start a new one with a short summary.
3. Read only the files named in the task. If context reaches 30M tokens, stop and rethink the approach.
4. At most 2-3 agents per repo at once. Dependent PRs go one after another; no PR cascades.
5. If a task needs more than 3 PRs, stop and ask the owner.
6. Fix your own CI failures at most 2 times, then stop and report.
7. Reviewers read only the PR diff. Exception: a project-wide audit is its own task: one agent, planned pass (structure first, then modules), split into 2-3 parts with separate reports if large.
8. Finished agents are archived, not continued.
9. Minor changes (texts, styles, tests; no DB, payments, auth or prod env) may be merged by the agent when CI is green. Merges to main in risky areas and prod migrations need the owner's explicit OK.
10. Budget: $20/month; per-agent on-demand cap $1-3.
11. Spend report Tue/Fri/Sun (Sunday = weekly total): spent, remaining, new daily guide = remaining / remaining days. Overspend is allowed; the guide is recalculated.
12. Alarm when a day uses more than 2x the daily guide or one agent dominates spend.
13. Recurring reports and checks run via scripts or cheap models.
