# Roadmap

Project management for `alfredagain` (PyPI). Use `/pm` to manage work.

## Structure

```
roadmap/
├── active/
│   └── MMDD-feature-slug/       ← One folder per work item
│       ├── RESEARCH.md           ← Investigate: function chains, defaults, gaps
│       ├── PLAN.md               ← Proposed approach, approved by user
│       └── SUMMARY.md            ← What shipped, decisions, files changed
├── archive/
│   └── v2.4.3/                   ← Shipped work, grouped by PyPI version
│       └── 0308-subdomain-norm/
├── BACKLOG.md                    ← Ideas not yet scheduled
└── README.md                     ← This file
```

## Lifecycle

Every work item goes through 3 stages:

1. **Research** — Trace the complete function chain. Audit defaults vs customizable. Identify gaps. Document in RESEARCH.md.
2. **Plan** — Propose approach based on research. Present to user. Document in PLAN.md. Wait for approval.
3. **Execute + Summarize** — Do the work. Document what happened in SUMMARY.md.

On release, move the folder from `active/` to `archive/v{version}/`.

## Conventions

### Naming

- **Folder:** `MMDD-slug/` (e.g., `0309-batch-write-validation/`)
- `MMDD` = date created (sorts chronologically)
- `slug` = short kebab-case description

### Archiving

When a version is published to PyPI:

1. Create `archive/v{version}/` folder
2. Move shipped `active/` item folders into it
3. Fill in the "Shipped" section of each SUMMARY.md
4. The archive folder name **is** the PyPI version — direct traceability

### Scaling

- **Hotfix:** RESEARCH can be minimal (a few lines). PLAN can be brief. Still document.
- **Major feature:** RESEARCH should be thorough — sub-agents, chain tracing, gap analysis.
- **The stages are checkpoints, not bureaucracy.**

## Templates

See `/pm` skill for full RESEARCH.md, PLAN.md, and SUMMARY.md templates.

## Backlog

`BACKLOG.md` holds ideas not yet scheduled. When promoted to active, create an `active/MMDD-slug/` folder and note it in the backlog's "Promoted" section.
