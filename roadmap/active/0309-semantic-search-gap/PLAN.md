# Plan: Semantic Search — Documentation Gap & Crash Path

**Date:** 2026-03-09
**Based on:** RESEARCH.md

## Approach

Add `similar`/`_semantic` to `crud.md` and `read.md` so the operator is consistently documented across all prompt templates. No code changes — the crash path in `apply_filter()` is correct and intentional. Domain owners who see the crash must build semantic search, degrade it in their middleware, or override `get_filter_schema()` to remove it.

## Tasks

- [ ] Add `similar` row to `crud.md` operator table (align with `FILTER_SCHEMA`)
- [ ] Add "Semantic Search" section to `read.md` under Advanced Patterns
- [ ] Verify `FILTER_SCHEMA` and `crud.md` now agree on all operators (resolve the contradiction)
- [ ] Update `docs/architecture/crud-and-database.md` if it references filter operators (keep consistent)

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Crash vs silent strip | Keep the crash | Forces domain owners to make an explicit choice — build it, degrade it, or remove it from prompts. Silent stripping hides a missing capability. |
| Add flag to DomainConfig? | No | `get_filter_schema()` override already exists. A flag adds complexity for the same outcome. |
| Consolidate FILTER_SCHEMA into crud.md? | No (not in this PR) | They serve different injection points. Consolidation is a separate concern. Just make them agree. |
| Where to document | `crud.md` + `read.md` | `crud.md` is the operator reference (all step types see it). `read.md` is where domain owners look for read patterns. Both need it. |

## Error Handling

No new error handling. The existing `ValueError` in `apply_filter()` is the designed crash path. Act node's `try/except` already catches it and shows the error to the LLM for retry.

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/prompts/templates/act/crud.md` | Add `similar` row to operator table with note about domain middleware requirement |
| `src/alfred/prompts/templates/act/read.md` | Add "Semantic Search" section under Advanced Patterns |
| `docs/architecture/crud-and-database.md` | Verify operator list matches; update if needed |
