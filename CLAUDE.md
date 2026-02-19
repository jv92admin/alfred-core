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
| `src/alfred/domain/base.py` | DomainConfig protocol (66 methods) |
| `src/alfred/domain/__init__.py` | `register_domain()`, `get_current_domain()` |
| `src/alfred/graph/workflow.py` | Entry points: `run_alfred()`, `run_alfred_streaming()` |
| `src/alfred/core/id_registry.py` | SessionIdRegistry — UUID ↔ ref translation |
| `src/alfred/db/adapter.py` | DatabaseAdapter protocol |
| `src/alfred/tools/crud.py` | CRUD execution engine |

## Documentation

| Path | Purpose |
|------|---------|
| `docs/architecture/overview.md` | Architecture index + pipeline diagram |
| `docs/architecture/core-domain-architecture.md` | Two-package split, DomainConfig protocol |
| `docs/architecture/core-public-api.md` | Entry points, extension protocols |
| `docs/architecture/domain-implementation-guide.md` | How to build a new domain |
| `docs/bridge/alfred-domain-design-guide.md` | Design-level guide for speccing new domains |
