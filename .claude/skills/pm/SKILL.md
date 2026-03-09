# /pm

Project management for `alfredagain` — a public PyPI package where traceability matters.

Trigger words: "roadmap", "plan", "what's next", "new feature", "backlog", "archive", "release", "ship"

---

## Context

This is a published PyPI package (`alfredagain`). Every change ships to real users. We track work in `roadmap/` with a simple active/archive system — no sprints, milestones, or phases.

```
roadmap/
├── active/          ← Work items in progress (MMDD-slug.md)
├── archive/         ← Shipped work, grouped by PyPI version
│   └── v2.4.3/     ← Version folder = traceability
├── BACKLOG.md       ← Ideas not yet scheduled
└── README.md        ← Conventions + template
```

---

## Workflows

Determine which workflow the user needs based on their request:

### 1. Start New Work Item

When the user wants to plan or start a feature/fix/refactor:

1. Check `roadmap/BACKLOG.md` — is this idea already logged? If so, note it.
2. Check `roadmap/active/` — is there already an item for this?
3. Create `roadmap/active/MMDD-slug.md` using the template from `roadmap/README.md`
4. Fill in: Goal, Type, Context, Tasks (as checklist)
5. If research is needed before implementation, add a `## Research` section — investigate first, then fill in Tasks and Decisions

**Research phase guidance:**
- Read relevant source files to understand current behavior
- Use sub-agents for broad codebase searches
- Document findings in the Research section
- Only move to Tasks once the approach is clear

### 2. Check Status

When the user asks "what's active", "what are we working on", "status":

1. List all files in `roadmap/active/`
2. For each, show: filename, Goal line, incomplete task count
3. Check `roadmap/BACKLOG.md` for pending ideas
4. Report concisely

### 3. Ship / Release

When the user says "ship", "release", "publish", "push to PyPI":

1. Read `pyproject.toml` for current version
2. Determine new version (patch/minor/major based on changes)
3. Bump version in `pyproject.toml`
4. Update `CHANGELOG.md` with new entry
5. Run tests: `python -m pytest tests/ -v`
6. Commit, push, build, publish to PyPI
7. Run `/doc-review` (or remind user to run it)
8. Archive: move shipped `roadmap/active/*.md` items to `roadmap/archive/v{version}/`
9. Fill in each archived item's "Shipped" section (version, commits, date)

### 4. Manage Backlog

When the user has an idea but isn't starting it now:

1. Add to `roadmap/BACKLOG.md` Ideas table
2. If promoting an idea to active, move it to the Promoted table with a link to the new active item

### 5. Review Roadmap

When the user asks "what's the plan", "roadmap", "priorities":

1. Show active items from `roadmap/active/`
2. Show backlog from `roadmap/BACKLOG.md`
3. Show broader priorities from `docs/ROADMAP.md` (P1-P5 backlog)
4. Suggest what to work on next based on priority and dependencies

---

## Work Item Template

Use this when creating new items in `roadmap/active/`:

```markdown
# {Title}

**Goal:** One sentence.
**Type:** fix | feat | refactor | docs | chore

## Context

Why this matters. 1-3 sentences.

## Research

(If needed — findings from investigating the codebase before planning tasks.)

## Tasks

- [ ] Task 1
- [ ] Task 2

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| ... | ... | ... |

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

- **One file per work item.** No PLAN/RESEARCH/SUMMARY split — keep it simple.
- **Research before tasks.** If unsure about approach, investigate first and document in the Research section.
- **Archive by version.** The `archive/v{version}/` folder name IS the PyPI traceability.
- **CHANGELOG is the public face.** Work items are internal; CHANGELOG is what users see.
- **Don't over-plan.** A work item can start as just a Goal + Context and grow Tasks as you go.
