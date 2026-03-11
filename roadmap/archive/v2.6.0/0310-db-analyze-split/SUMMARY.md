# Summary: Split analytical queries out of db_read into db_analyze

**Date:** 2026-03-10

## What Was Done

- Removed `aggregate` and `aggregate_field` params from `DbReadParams` — `db_read` is now purely entity-focused (fetch rows, track with refs)
- Created `DbAnalyzeParams` model + `db_analyze()` function in crud.py — supports count, sum, avg, min, max with GROUP BY, ORDER BY, LIMIT, filters
- Added `BUILTIN_ANALYZE` dispatch path in Act node — separate from CRUD, no registry translation, no middleware
- Changed default `get_tool_enabled_step_types()` from `{"read", "write"}` to `{"read", "write", "analyze"}` — schema auto-injects for analyze steps
- Added `db_analyze` tool line in injection.py decision section for analyze steps
- CRUD reference (crud.md) now loaded for analyze steps too (filter syntax reference)
- Updated Act result formatting — `db_analyze` results detected by tool name, handles multi-row GROUP BY results
- Rewrote analyze.md — dual-mode template: query mode (db_analyze) + reasoning mode (arithmetic over prior data)
- Updated think.md — read vs analyze decision guidance, multi-step comparison patterns
- Updated crud.md — added `db_analyze` to tool table with "Available In" column, added sorting note for both tools
- Removed Aggregates section from read.md
- 18 new `TestDbAnalyze` tests, 12 old `TestDbReadAggregates` tests removed (net +6, total 182)

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| `db_analyze` dispatch via `execute_crud` | Early return before registry/middleware | Simplest path — no entity tracking needed |
| Result formatting by tool name | `if tool_name == "db_analyze"` branch | Old heuristic (single row + no id) breaks with GROUP BY multi-row |
| CRUD ref loaded for analyze | Extended condition to include "analyze" | LLM needs filter syntax reference for db_analyze |
| Dropped `count_distinct` | Not carried to db_analyze | PostgREST count() on specific field already counts non-null; true DISTINCT not reliable |

## Deviations from Plan

- Plan said "detect via tool name, not heuristic" for step results formatting — kept the heuristic (no-id detection) for `_format_step_results()` since step results don't carry tool names, but improved it to handle multi-row grouped results. Tool-name detection used in `_format_current_step_results()` where tool name is available.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py` | Removed aggregate from DbReadParams, added DbAnalyzeParams + db_analyze(), early return in execute_crud |
| `src/alfred/graph/nodes/act.py` | Added BUILTIN_ANALYZE set + dispatch, updated result formatting (both locations), CRUD ref loaded for analyze |
| `src/alfred/domain/base.py` | Default get_tool_enabled_step_types() → {"read", "write", "analyze"}, updated docstring |
| `src/alfred/prompts/injection.py` | Added db_analyze tool line for analyze steps |
| `src/alfred/prompts/templates/act/analyze.md` | Full rewrite — dual-mode with db_analyze examples |
| `src/alfred/prompts/templates/act/read.md` | Removed Aggregates section (62 lines) |
| `src/alfred/prompts/templates/act/crud.md` | Added db_analyze to tool table, "Available In" column, sorting note updated |
| `src/alfred/prompts/templates/think.md` | Updated step types table, read vs analyze decision guidance |
| `tests/core/test_crud.py` | Removed TestDbReadAggregates (12 tests), added TestDbAnalyze (18 tests) |
| `pyproject.toml` | Bumped to 2.6.0 |
| `CHANGELOG.md` | Breaking change entry |

## Shipped

- **Version:** 2.6.0
- **Commit:** c73c500
- **Date:** 2026-03-10
