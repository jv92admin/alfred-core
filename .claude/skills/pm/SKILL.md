---
name: pm
description: 'Project management for alfredagain. Research → Plan → Execute lifecycle for work items. Use for new features, bug fixes, status checks, releases, and backlog management.'
---

# /pm

Project management for `alfredagain` — a public PyPI package where traceability matters.

Trigger words: "roadmap", "plan", "what's next", "new feature", "backlog", "archive", "release", "ship"

---

## Context

This is a published PyPI package (`alfredagain`). Every change ships to real users. Every feature goes through a 3-stage lifecycle: **Research → Plan → Execute + Summarize**.

```
roadmap/
├── active/
│   └── MMDD-feature-slug/       ← One folder per work item
│       ├── RESEARCH.md           ← Stage 1: Investigate before committing to an approach
│       ├── PLAN.md               ← Stage 2: Proposed approach, presented to user
│       └── SUMMARY.md            ← Stage 3: What shipped, decisions, files changed
├── archive/                      ← Shipped work, grouped by PyPI version
│   └── v2.4.3/
│       └── 0308-subdomain-norm/
├── BACKLOG.md                    ← Ideas not yet scheduled
└── README.md                     ← Conventions + templates
```

---

## Workflows

Determine which workflow the user needs based on their request:

### 1. Start New Work Item (Research Stage)

When the user wants to explore or start a feature/fix/refactor:

1. Check `roadmap/BACKLOG.md` — is this idea already logged? If so, note it.
2. Check `roadmap/active/` — is there already a folder for this?
3. Create `roadmap/active/MMDD-slug/` folder
4. Create `RESEARCH.md` using the template from `roadmap/README.md`

**Research protocol — this is the critical stage:**

For every feature, trace the **complete function chain** through the pipeline:
- Which nodes are involved? (Understand → Think → Act → Reply → Summarize)
- What functions are called at each stage?
- What state flows between them?

Audit **defaults vs customizable** at every touchpoint:
- What does core provide by default?
- What DomainConfig hooks exist for override?
- Are there gaps where a domain SHOULD be able to customize but can't?
- **Default to errors when no domain input is provided.** We don't want silent failures in a public package — if a domain hook is required, fail loudly.

Use **sub-agents** for broad searches. Trace chains thoroughly.

Document all findings in RESEARCH.md before moving to planning.

### 2. Plan (Plan Stage)

When research is complete, or user says "plan this", "what's the approach":

1. Read the RESEARCH.md findings
2. Create `PLAN.md` in the same folder using the template
3. Present the plan to the user for review — do NOT start executing
4. Wait for user approval or adjustments

**IMPORTANT:** Plans live in the repo, not in Claude's plan mode (which saves to local PC and gets lost). The PLAN.md IS the plan of record.

### 3. Execute + Summarize

When the user approves the plan and says "go", "execute", "do it":

1. Read `.claude/PITFALLS.md` — note any patterns relevant to the files this plan touches
2. Work through the PLAN.md tasks
3. **Plan-adherence check:** re-read PLAN.md against the actual diff. Every Reuse Map row honored? Every deviation gets a row in SUMMARY.md "Deviations from Plan" — no silent drift
4. If a bug or near-miss during execution passes the PITFALLS Graduation Rule, add it to `.claude/PITFALLS.md` BEFORE writing SUMMARY.md
5. Create `SUMMARY.md` in the same folder
6. SUMMARY.md captures: what was actually done, decisions made during execution, files changed, any deviations from the plan

### 4. Ship / Release

When the user says "ship", "release", "publish", "push to PyPI":

1. Read `pyproject.toml` for current version
2. Determine new version (patch/minor/major based on changes)
3. Bump version in `pyproject.toml`
4. Update `CHANGELOG.md` with new entry
5. Run tests: `python -m pytest tests/ -v`
6. Commit, push, build, publish to PyPI
7. Archive: move shipped `roadmap/active/MMDD-slug/` folders to `roadmap/archive/v{version}/`
8. Fill in each SUMMARY.md's "Shipped" section (version, commits, date)
9. Run `/doc-review` (or remind user to run it)

### 5. Check Status

When the user asks "what's active", "what are we working on", "status":

1. List all folders in `roadmap/active/`
2. For each, show: folder name, Goal line, which stage it's at (has RESEARCH? PLAN? SUMMARY?)
3. Check `roadmap/BACKLOG.md` for pending ideas
4. Report concisely

### 6. Manage Backlog

When the user has an idea but isn't starting it now:

1. Add to `roadmap/BACKLOG.md` Ideas table
2. If promoting an idea to active, move it to the Promoted table with a link

### 7. Review Roadmap

When the user asks "what's the plan", "roadmap", "priorities":

1. Show active items from `roadmap/active/` with their stages
2. Show backlog from `roadmap/BACKLOG.md`
3. Show broader priorities from `docs/ROADMAP.md` (P1-P5 backlog)
4. Suggest what to work on next based on priority and dependencies

---

## Templates

### RESEARCH.md

```markdown
# Research: {Title}

**Goal:** One sentence.
**Type:** fix | feat | refactor | docs | chore
**Date:** YYYY-MM-DD

## Context

Why this matters. 1-3 sentences.

## Function Chain

Trace through the pipeline — which nodes, functions, and state are involved.

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| ... | ... | ... | ... |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| ... | ... | ... | ... |

## Findings

Key observations, edge cases, risks.

## Open Questions

Questions to resolve before planning.
```

### PLAN.md

```markdown
# Plan: {Title}

**Date:** YYYY-MM-DD
**Based on:** RESEARCH.md

## Approach

1-3 sentences describing the chosen approach.

## Reuse Map

Existing code this work builds on. Cite **live symbols + paths you have grep-verified** — not docs. A "New" row must say what was searched and why nothing existing fits.

| Capability | Reuse / New | Symbol + Path | Why |
|------------|-------------|---------------|-----|
| ... | ... | ... | ... |

## Tasks

- [ ] Task 1
- [ ] Task 2

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| ... | ... | ... |

## Error Handling

How should failures behave? Default to loud errors over silent fallbacks.

## Files to Change

| File | Planned Change |
|------|---------------|
| ... | ... |

## Definition of Done

Tailor to the work type — these are the defaults:

- [ ] `pytest tests/ -v` passes
- [ ] New required domain touchpoints fail loudly when input is missing
- [ ] Relevant `.claude/PITFALLS.md` Checks pass for touched files
- [ ] Docs impact noted (which Tier 1/2 docs `/doc-review` will need to touch)
```

### SUMMARY.md

```markdown
# Summary: {Title}

**Date:** YYYY-MM-DD

## What Was Done

Bullet list of actual changes (with commit hashes if available).

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| ... | ... | ... |

## Deviations from Plan

Any changes from the original PLAN.md and why.

## Files Changed

| File | Change |
|------|--------|
| ... | ... |

## Shipped

- **Version:** (filled on archive)
- **Commits:** (filled on archive)
- **Date:** (filled on archive)
```

---

## Principles

- **Research first.** Trace the full chain before proposing changes. Use sub-agents.
- **Reuse claims cite live code.** A PLAN's Reuse Map points at grep-verified symbols + paths, never at docs. Docs are discovery aids, not the contract.
- **Pitfalls are part of the loop.** Read `.claude/PITFALLS.md` before executing; feed it (Graduation Rule) before summarizing.
- **Plans live in the repo.** Not in plan mode, not in your head — in `roadmap/active/`.
- **Present plans, don't just execute.** The user approves the plan before work begins.
- **Loud failures over silent defaults.** For core features, error when domain input is missing.
- **Archive by version.** The `archive/v{version}/` folder IS the PyPI traceability.
- **CHANGELOG is the public face.** Work items are internal; CHANGELOG is what users see.
- **Stages are checkpoints, not bureaucracy.** A hotfix can have a minimal RESEARCH + PLAN. A major feature needs thorough ones.
