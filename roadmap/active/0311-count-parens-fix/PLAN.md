# Plan: db_analyze count() parens fix

**Date:** 2026-03-11
**Based on:** RESEARCH.md

## Approach

One-line fix: change `"count"` to `"count()"` at crud.py:294. Update two test assertions that check the generated select string.

## Tasks

- [x] Fix crud.py:294 — `"count"` → `"count()"`
- [x] Update test_count_no_field assertion — `"count"` → `"count()"`
- [x] Update test_count_group_by assertion — `"count,status"` → `"count(),status"`
- [x] Run TestDbAnalyze suite — 17/17 pass

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/tools/crud.py` | Line 294: `"count"` → `"count()"` |
| `tests/core/test_crud.py` | Lines 311, 394: update select assertions |
