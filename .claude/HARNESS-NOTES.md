# Harness Design Notes

> 2026-06-10. Why the alfred-core Claude harness looks the way it does. Source: deep trace
> of `c:\Projects\landscaping`'s harness (20 skills, 10 path-glob rules, PITFALLS agent,
> derived PORTFOLIO) — a mature team-scale setup that is deliberately overkill here.
> This repo is a solo-maintained monorepo for a PyPI library; the harness is sized for that.

## What landscaping taught (load-bearing ideas)

1. **PLAN as verifiable contract.** Their Capability Map cites grep-verified live symbols
   (docs are "discovery aids, never the contract"); code review Pass A mechanically gates on
   adherence; deviations must amend the plan in the same diff. Kills silent reinvention and
   plan/code drift.
2. **PITFALLS.md as a self-improving immune system.** Themed patterns with grep-checkable
   Checks and dated incidents, gated by a 5-condition graduation rule. `/bug-report`
   backward-walks each bug to the artifact that should have caught it. The only mechanism
   in their harness that makes the loop learn.
3. **Derived artifacts beat hand-maintained ones.** Their hand-edited HANDOFF_SUMMARY
   drifted constantly and was killed for a PORTFOLIO regenerated from folder structure + git.
4. **One canonical source per topic**, declared in a table in CLAUDE.md.
5. **Path-glob rules** auto-load conventions so nobody has to remember them.

And what they deleted — the strongest signal:
- **All 7 subagents** (6 were thin 1:1 wrappers around skills; one was lifted into a skill +
  always-loaded invariants). Agents that wrap a skill are dead weight.
- **6+ skills culled across two redesigns** in two months. Skills accrete faster than they
  earn their keep; prune deliberately.
- **Every parallel mirror drifted** (Codex AGENTS.md, `.agents/` skills copy). Don't keep
  copies you won't automate.

## What this repo adopted

| Adopted | Where |
|---------|-------|
| PITFALLS.md + Graduation Rule, seeded from System Boundaries | `.claude/PITFALLS.md` |
| Read-pitfalls-first + add-before-SUMMARY, in the execute stage | `/pm` workflow 3 |
| Reuse Map (live symbol + path, grep-verified) in PLAN template | `/pm` PLAN template |
| Definition of Done in PLAN template | `/pm` PLAN template |
| Plan-adherence check before SUMMARY (deviations are mandatory rows) | `/pm` workflow 3 |
| PITFALLS freshness pruning per release | `/doc-review` Tier 4 |
| Canonical Sources table | `CLAUDE.md` |

Already in place before this pass (independently matching their patterns):
- `/pm` status is **derived** from `roadmap/active/` folder contents — same insight as PORTFOLIO.
- `injection-map.md` is the capability index, and `/doc-review` is its refresh mechanism —
  the sync loop landscaping had to retrofit with `/capabilities-refresh`.
- 4-tier `/doc-review` propagation is stronger than their post-phase doc pass.

## Deliberately skipped (and the trigger that would revisit)

| Skipped | Why | Revisit if |
|---------|-----|------------|
| Subagent definitions | Their own history: wrappers died | A task needs genuinely different tools/permissions |
| `/orient` session-start skill | Solo + trunk-based; `git status` suffices | Second contributor or parallel-Claude sessions |
| `/code-review` as separate skill | Pass-A-lite folded into `/pm` execute | Diffs grow beyond what one adherence pass covers |
| capabilities-bootstrap/refresh | injection-map.md + `/doc-review` already cover it | Codebase outgrows one navigable injection map |
| Path-glob rule files | No recurring per-path mistake yet | Same template/test mistake recurs — likely first: `src/alfred/prompts/templates/**` |
| BRD funnel, PORTFOLIO, triage, audit | Team/non-engineer/app-surface pressures absent here | — |
| AGENTS.md or any mirror | Mirrors drift; single harness only | — |

## Standing guidance

- New skills must earn their place: a skill that just restates a doc is a pointer, not a skill.
- Inventory-style content (counts, file lists) only lives where `/doc-review` checks it.
- When a real incident occurs, PITFALLS gets the lesson via the Graduation Rule — that, not
  upfront design, is how this harness is meant to grow.
