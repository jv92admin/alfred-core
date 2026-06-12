# CLAUDE.md

## What This Is

Alfred core — a domain-agnostic LLM orchestration engine built on LangGraph. Published as `alfredagain` on PyPI, imported as `import alfred`.

This package provides the pipeline, entity tracking, CRUD execution, prompt assembly, and conversation memory. Domains implement `DomainConfig` and call `register_domain()`.

**Core never imports any domain package.** New domains are separate packages that depend on `alfredagain`.

## System Boundaries

- All entity lifecycle changes are deterministic (CRUD layer owns state)
- LLMs never see UUIDs (SessionIdRegistry translates to simple refs)
- Generated content (`gen_*` refs) requires explicit user approval before persistence
- Never expose UUIDs to LLM prompts
- Never auto-save generated content without user confirmation
- Never duplicate state mutation logic

## Development Commands

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -e ".[dev]"

# Quality
pytest tests/ -v
ruff check src/
ruff format src/
mypy src/
```

## Key Files

| File | Role |
|------|------|
| `src/alfred/domain/base.py` | DomainConfig (80 members) — composition shim over `domain/context.py` (DomainContext) + `domain/agent.py` (AgentConfig) |
| `src/alfred/context/assembly.py` | State-free assembly entrypoints + ShapedPayload (external seam) |
| `src/alfred/domain/__init__.py` | `register_domain()`, `get_current_domain()` |
| `src/alfred/graph/workflow.py` | Entry points: `run_alfred()`, `run_alfred_streaming()` |
| `src/alfred/core/id_registry.py` | SessionIdRegistry — UUID ↔ ref translation |
| `src/alfred/db/adapter.py` | DatabaseAdapter protocol |
| `src/alfred/tools/crud.py` | CRUD execution engine |

## Project Management

This is a public PyPI package — traceability matters. Use `/pm` to manage work.

```
roadmap/
├── active/
│   └── MMDD-slug/        ← Research → Plan → Execute + Summarize
│       ├── RESEARCH.md   ← Trace function chains, audit defaults vs customizable
│       ├── PLAN.md       ← Proposed approach, approved before execution
│       └── SUMMARY.md    ← What shipped, decisions, files changed
├── archive/v{version}/   ← Shipped work grouped by PyPI version
└── BACKLOG.md
```

**Workflow:** `/pm` to start work, track status, or ship. `/doc-review` after every release.

**Lessons loop:** `.claude/PITFALLS.md` holds graduated lessons (grep-checkable, sourced). Read it before any code-touching work; add to it when a bug passes its Graduation Rule; `/doc-review` prunes stale entries.

## Canonical Sources

One source of truth per topic — other docs may carry brief copies, never the authoritative version.

| Topic | Canonical Source |
|-------|-----------------|
| PM workflow + templates | `.claude/skills/pm/SKILL.md` |
| Doc propagation protocol | `.claude/skills/doc-review/SKILL.md` |
| Lessons / pitfalls | `.claude/PITFALLS.md` |
| DomainConfig hooks (every knob) | `docs/architecture/injection-map.md` |
| Architecture index | `docs/architecture/overview.md` |
| Public API surface | `docs/architecture/core-public-api.md` |
| What shipped (user-facing) | `CHANGELOG.md` |
| Version | `pyproject.toml` |
| Work-item traceability | `roadmap/archive/v{version}/` |

## Documentation

| Path | Purpose |
|------|---------|
| `docs/architecture/overview.md` | Architecture index + pipeline diagram |
| `docs/architecture/core-domain-architecture.md` | Two-package split, DomainConfig protocol |
| `docs/architecture/core-public-api.md` | Entry points, extension protocols |
| `docs/architecture/injection-map.md` | Every domain knob/dial — organized by effect (reasoning, UI, capabilities) |
| `docs/architecture/domain-implementation-guide.md` | How to build a new domain |
| `docs/bridge/alfred-domain-design-guide.md` | Design-level guide for speccing new domains |
