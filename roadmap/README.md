# Roadmap

Project management for `alfredagain` (PyPI).

## Structure

```
roadmap/
├── active/          ← Work items in progress or planned
├── archive/         ← Shipped work, grouped by version
│   └── v2.4.3/     ← All items that shipped in this release
└── BACKLOG.md       ← Parked ideas, not yet scheduled
```

## Conventions

### Active Items

**Filename:** `MMDD-slug.md` (e.g., `0309-batch-write-validation.md`)

- `MMDD` = date the item was created (sorts chronologically)
- `slug` = short kebab-case description
- One file per work item (no separate PLAN/SUMMARY split)

### Archiving on Release

When a version is published to PyPI:

1. Create `archive/v{version}/` folder
2. Move all active items that shipped in this release into it
3. The archive folder name **is** the PyPI version — direct traceability

### Work Item Template

```markdown
# {Title}

**Goal:** One sentence.
**Type:** fix | feat | refactor | docs | chore

## Context

Why this matters. 1-3 sentences.

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

### Backlog

`BACKLOG.md` holds ideas not yet scheduled. When promoted to active, create an `active/MMDD-slug.md` and note it in the backlog's "Promoted" section.
