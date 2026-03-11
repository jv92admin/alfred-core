# Research: db_analyze count() parens fix

**Goal:** Fix `db_analyze` generating `count` instead of `count()` in PostgREST select clause.
**Type:** fix
**Date:** 2026-03-11

## Context

A domain consumer reported that `db_analyze` with `aggregate="count"` and `group_by` returns a 400 from PostgREST. The root cause: PostgREST v12+ requires `count()` (with parens) in mixed select clauses for auto-GROUP BY to work. Without parens, PostgREST treats `count` as a column name, producing `42803: column must appear in GROUP BY clause`.

## Function Chain

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| CRUD dispatch | `execute_crud()` crud.py | Routes `db_analyze` to `db_analyze()` | — |
| Select build | `db_analyze()` crud.py:292-302 | Builds `agg_part` + optional `group_by` | — |
| **Bug** | crud.py:294 | `agg_part = "count"` — missing parens | — |
| PostgREST call | crud.py:304 | `client.table().select(select_clause)` | — |

## Findings

- `count` (no parens) works solo: `select=count` → PostgREST returns `[{"count": N}]`
- `count` (no parens) **fails** with group_by: `select=count,status` → 400 error (column not in GROUP BY)
- `count()` (with parens) works in both cases — strictly better
- The field-specific aggregates (line 297) already use parens: `field.sum()` etc.
- Live-tested against Supabase/PostgREST to confirm both behaviors

## Open Questions

None — fix is straightforward.
