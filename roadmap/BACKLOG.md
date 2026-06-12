# Backlog

Ideas and improvements not yet scheduled. See `docs/ROADMAP.md` for the broader prioritized backlog (P1-P5).

Items here are concrete enough to become a work item but not yet started.

## Ideas

| Idea | Why It Matters | Added |
|------|---------------|-------|
| Summarize node: consolidate 4 LLM calls into 1 | Summarize makes 4 separate cheap LLM calls (response summary, turn compression, conversation compression, engagement summary) — all post-Reply so not latency-impacting, but worth exploring whether one smarter call returning all 4 outputs would be cheaper/better. | 2026-03-12 |
| Repo-wide lint/type debt | 368 pre-existing mypy strict errors + widespread ruff violations (surfaced by A1's gates; A1 added zero). Gate going forward: touched files fully clean, mypy at exact baseline parity per feature (error total on a clean run is the metric). Paying the debt down is unscheduled. | 2026-06-11 |
| Derive `get_subdomain_registry()` from `subdomains` | The protocol declares subdomain→tables twice (typed `subdomains` property + dict-shaped `get_subdomain_registry()`, both abstract). Defaulting the dict one to derive from the typed one drops an abstract member — one less method for new domains. Protocol-surface compat decision (freeze-test abstract-set change), NOT doc debt — too big for X2. Surfaced by A3. | 2026-06-12 |

## Promoted

| Idea | Promoted To | Date |
|------|-------------|------|
| Reply continuity guidance override | `roadmap/active/0312-reply-continuity-override/` | 2026-03-12 |
| Summarize node prompt template alignment | `roadmap/active/0312-summarize-template-alignment/` | 2026-03-12 |
| Safe calculator tool (`calculate`) | `roadmap/active/0312-calculate-tool/` | 2026-03-12 |
