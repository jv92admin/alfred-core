# Research: db_read Aggregate Functions (COUNT, SUM, AVG)

**Goal:** Add SQL aggregate support to `db_read` so LLMs can answer "how many?", "total of?", "average?" without fetching all rows.
**Type:** feat
**Date:** 2026-03-09

## Context

Today `db_read` always returns a list of entity records. When a user asks "how many recipes do I have?", the LLM must fetch all rows and count them in the reply — wasteful and breaks on large tables. Native aggregates are a key unlock for consumers building dashboards, summaries, and analytics-style interactions.

Supabase/PostgREST already supports aggregates natively:
```python
client.table("items").select("count").execute()                    # [{"count": 42}]
client.table("items").select("sum(quantity)").execute()             # [{"sum": 150}]
client.table("items").select("count(distinct category)").execute()  # [{"count": 3}]
```

No upstream blocker — this is purely an Alfred plumbing + prompt teaching task.

## Function Chain

Trace through the pipeline — which nodes, functions, and state are involved.

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| Think | `think_node()` in `graph/nodes/think.py` | Plans step with `step_type="read"` | `get_examples(sub, "read")` |
| Act — prompt assembly | `build_act_user_prompt()` in `prompts/injection.py` | Assembles 15-section prompt; includes schema, CRUD ref, read persona | `get_act_subdomain_header()`, `get_act_prompt_injection("read")`, `get_examples()` |
| Act — LLM decision | Act node in `graph/nodes/act.py` | LLM returns `{"tool": "db_read", "params": {...}}` | — |
| Act — dispatch | `execute_crud("db_read", ...)` in `tools/crud.py:457` | Translates refs→UUIDs, calls `db_read()` | `get_crud_middleware()` |
| Act — query | `db_read()` in `tools/crud.py:140` | Builds `.select(columns)`, applies filters, executes | Middleware `pre_read()` |
| Act — output | `_translate_output()` in `tools/crud.py:518` | Registry translates UUIDs→refs | Middleware `post_read()` |
| Act — format | Result formatting in `act.py` | Formats as "N records" for next step / reply | — |

### Aggregate-specific changes needed at each stage

| Stage | Change Required |
|-------|----------------|
| Think | None — step_type stays "read" |
| Act — prompt | Add aggregate examples to `crud.md` and `read.md` |
| Act — LLM decision | LLM must learn new params: `aggregate`, `aggregate_field` |
| Act — dispatch | Minor — pass new params through |
| Act — query (`db_read`) | Branch: if `aggregate`, use `.select("count")` instead of `.select("*")` |
| Act — output | **Skip registry translation** — aggregate results have no `id` field |
| Act — format | Branch: "count=42" instead of "42 records" |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Aggregate support | Not supported | N/A | **Yes — this feature** |
| User-owned table auto-filter | Auto-adds `user_id` filter | `get_user_owned_tables()` | No — works with aggregates (WHERE before GROUP) |
| Middleware pre_read | None | `get_crud_middleware()` | No — pre_read can enrich filters before aggregate |
| Middleware post_read | None | `get_crud_middleware()` | Minor — post_read receives `[{"count": 42}]` not records; domains must handle |
| Schema in prompts | From `get_fallback_schemas()` | Domain provides | No change needed |
| Read examples | From `get_examples(sub, "read")` | Domain provides | Domains may want aggregate-specific examples |

## Findings

### 1. SessionIdRegistry is safe
`translate_read_output()` guards on `if "id" in record and record["id"]`. Aggregate results like `[{"count": 42}]` naturally skip this — no `id` field, no ref assignment, no crash. The existing code **already handles this case gracefully**.

### 2. Supabase syntax is straightforward
- `COUNT(*)`: `.select("count")`
- `SUM(col)`: `.select("sum(col)")`
- `AVG(col)`: `.select("avg(col)")`
- `COUNT(DISTINCT col)`: `.select("count(distinct col)")`

All return single-row results: `[{"count": N}]` or `[{"sum": N}]`.

### 3. Filters compose cleanly
Existing `apply_filter()` works unchanged — filters become the WHERE clause before aggregation. `or_filters` also work. `limit` and `order_by` are meaningless for aggregates but harmless.

### 4. The prompt teaching is the hardest part
The LLM needs to learn:
- **When** to use aggregates (counting, totaling) vs row fetch (listing, reading details)
- **What** the result shape looks like (scalar, not entity list)
- **That** aggregate results can't be referenced later (no refs)

### 5. `columns` and `aggregate` are mutually exclusive
Can't SELECT columns AND aggregate in the same call. Validation needed.

### 6. GROUP BY is explicitly out of scope
GROUP BY returns multiple rows of aggregates (e.g., count per category) — different result shape, harder to teach, save for later.

## Open Questions

1. **Single vs multi-aggregate per call?** `aggregate: "count"` (simple) vs `aggregates: [{function, field}]` (flexible). Recommendation: start with single.
2. **Should `analyze` step type also get aggregate access?** Or keep it read-only? Likely yes — analyze steps often need counts.
3. **Naming: `aggregate` + `aggregate_field` vs `select_aggregate` vs something else?** Keep it simple, LLM-friendly.
4. **Should we add a validator that rejects `limit`/`order_by` when `aggregate` is set?** Or just ignore them silently? Recommendation: ignore silently (less LLM friction).
