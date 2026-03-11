# Summary: db_analyze count() parens fix

**Date:** 2026-03-11

## What Was Done

- Fixed `db_analyze` to generate `count()` instead of `count` in PostgREST select clause
- Updated two test assertions to match the corrected syntax
- All 17 `TestDbAnalyze` tests pass

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| Use `count()` everywhere | Yes — even solo selects | `count()` works in all contexts; `count` only works solo. Strictly better. |

## Deviations from Plan

None.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py:294` | `"count"` → `"count()"` |
| `tests/core/test_crud.py:311` | Assert `"count()"` instead of `"count"` |
| `tests/core/test_crud.py:394` | Assert `"count(),status"` instead of `"count,status"` |

## Shipped

- **Version:** v2.6.1
- **Commits:** 9b3bc08
- **Date:** 2026-03-11
