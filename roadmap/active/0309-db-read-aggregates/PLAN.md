# Plan: db_read Aggregate Functions

**Date:** 2026-03-09
**Based on:** RESEARCH.md

## Approach

Add an optional `aggregate` + `aggregate_field` pair to `DbReadParams`. When set, `db_read()` swaps the SELECT clause from column projection to a Supabase aggregate expression (e.g., `.select("count")`). Aggregate results skip SessionIdRegistry translation (no entity IDs) and get dedicated formatting in the Act node. Single aggregate per call for v1; GROUP BY explicitly out of scope.

## Tasks

### 1. Data model (`src/alfred/tools/crud.py`)
- [ ] Add `aggregate` and `aggregate_field` to `DbReadParams`
- [ ] Add Pydantic validator: `aggregate_field` required for `sum`, `avg`, `count_distinct`; optional for `count`
- [ ] `columns` must be `None` when `aggregate` is set (mutual exclusion validator)

```python
# New fields on DbReadParams (after existing fields)
aggregate: Literal["count", "sum", "avg", "count_distinct"] | None = None
aggregate_field: str | None = None  # Required for sum/avg/count_distinct
```

### 2. Query execution (`src/alfred/tools/crud.py` — `db_read()`, ~line 140)
- [ ] After line 172 (middleware pre-processing), branch on `params.aggregate`
- [ ] Build aggregate SELECT clause instead of column SELECT
- [ ] Silently skip `order_by` and `limit` for aggregates (they're meaningless)
- [ ] Filters, user_id scoping, middleware `pre_read` all apply normally (WHERE before aggregate)
- [ ] Middleware `post_read` still runs (domains may want to transform the scalar result)

```python
# Aggregate SELECT mapping
if params.aggregate:
    match params.aggregate:
        case "count":
            select_clause = "count"
        case "sum":
            select_clause = f"{params.aggregate_field}.sum()"
        case "avg":
            select_clause = f"{params.aggregate_field}.avg()"
        case "count_distinct":
            # PostgREST: count with distinct
            select_clause = f"{params.aggregate_field}.count()"
            # Need to verify exact Supabase syntax for DISTINCT
```

**NOTE:** Exact Supabase aggregate syntax needs verification during execution. PostgREST may use `.select("count")` or column-level `.select("field.count()")` depending on version. Spike this first.

### 3. Output translation (`src/alfred/tools/crud.py` — `execute_crud()`, ~line 516)
- [ ] No changes expected — `_translate_output()` already guards on `if "id" in record`
- [ ] Aggregate results like `[{"count": 42}]` naturally skip ref assignment
- [ ] `_enrich_lazy_registrations` and `_add_enriched_labels` are no-ops (no FK refs)
- [ ] Verify this with a test — don't just assume

### 4. Act node result formatting (`src/alfred/graph/nodes/act.py`)
- [ ] `_format_current_step_results()` (~line 708): add aggregate branch inside the `db_read` block

```python
# Inside the db_read block, before the existing isinstance(result, list) check:
if tool_name == "db_read":
    # Check if this is an aggregate result
    if (isinstance(result, list) and len(result) == 1
            and isinstance(result[0], dict)
            and not result[0].get("id")):
        # Aggregate result — format as scalar
        agg = result[0]
        parts = [f"{k}: {v}" for k, v in agg.items()]
        lines.append(f"**Result:** {', '.join(parts)}")
    elif isinstance(result, list):
        # ... existing record formatting
```

- [ ] `_format_step_results()` (~line 514): same detection for step summary formatting

### 5. Prompt templates
- [ ] Update `src/alfred/prompts/templates/act/crud.md` — add `aggregate`, `aggregate_field` to the db_read row in the Tools table
- [ ] Update `src/alfred/prompts/templates/act/read.md` — add "Aggregates" section with examples and "when to use" guidance

**crud.md** — add to Tools table:
```
| `db_read` | Fetch rows or aggregate | `table`, `filters`, `or_filters`, `columns`, `limit`, `order_by`, `order_dir`, `aggregate`, `aggregate_field` |
```

**read.md** — new section after "Advanced Patterns":
```markdown
## Aggregates

Count, sum, or average instead of fetching rows. Use when the user asks
"how many", "total", "average" — not when they want to see the actual records.

**`aggregate`** — the function: `count`, `sum`, `avg`, `count_distinct`
**`aggregate_field`** — the column (required for sum/avg/count_distinct, optional for count)

### Count all rows
{"table": "items", "aggregate": "count"}
→ [{"count": 42}]

### Count with filter
{"table": "items", "filters": [{"field": "status", "op": "=", "value": "active"}], "aggregate": "count"}
→ [{"count": 15}]

### Sum a numeric column
{"table": "items", "aggregate": "sum", "aggregate_field": "quantity"}
→ [{"sum": 150}]

### Average
{"table": "items", "aggregate": "avg", "aggregate_field": "price"}
→ [{"avg": 12.5}]

### Count distinct values
{"table": "items", "aggregate": "count_distinct", "aggregate_field": "category"}
→ [{"count": 3}]

**Rules:**
- Aggregate results are scalars, not entity records — no IDs, no refs
- `columns`, `limit`, `order_by` are ignored when `aggregate` is set
- Filters work normally (they become the WHERE before aggregation)
- If the user wants to SEE the items, use a normal read. If they want a NUMBER about the items, use aggregate.
```

### 6. Tests (`tests/core/test_crud.py`)
- [ ] Spike: verify exact Supabase aggregate SELECT syntax against a real or mock client
- [ ] `test_db_read_count` — count all rows, assert `[{"count": N}]`
- [ ] `test_db_read_count_with_filters` — count with WHERE, assert filtered count
- [ ] `test_db_read_sum` — sum a numeric column
- [ ] `test_db_read_avg` — average a numeric column
- [ ] `test_db_read_count_distinct` — count distinct values
- [ ] `test_db_read_aggregate_skips_registry` — verify no ref assignment on aggregate result
- [ ] `test_db_read_aggregate_ignores_limit_orderby` — verify no error when LLM sends these
- [ ] `test_db_read_aggregate_rejects_columns` — validation error when both set

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Single vs multi-aggregate | Single per call | Simpler for LLM, multi can be two calls |
| `limit`/`order_by` with aggregate | Silently ignore | Less LLM friction, fewer retries |
| `columns` with aggregate | Validation error | Mutually exclusive, fail loud |
| GROUP BY | Out of scope | Different result shape, future work |
| Analyze step access | No | Analyze doesn't do DB calls |
| Param naming | `aggregate` + `aggregate_field` | Close to SQL, self-explanatory |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `aggregate="sum"` without `aggregate_field` | Pydantic validation error (loud) |
| `aggregate` + `columns` both set | Pydantic validation error (loud) |
| `aggregate` + `limit`/`order_by` | Silently ignored |
| `aggregate_field` references non-existent column | Supabase error propagates (existing behavior) |
| Aggregate on empty table | Returns `[{"count": 0}]` or `[{"sum": null}]` (Supabase default) |

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/tools/crud.py` | `DbReadParams` new fields + validator; `db_read()` aggregate branch |
| `src/alfred/graph/nodes/act.py` | `_format_current_step_results()` and `_format_step_results()` aggregate formatting |
| `src/alfred/prompts/templates/act/crud.md` | Add aggregate params to db_read row |
| `src/alfred/prompts/templates/act/read.md` | New "Aggregates" section with examples |
| `tests/core/test_crud.py` | New `TestDbReadAggregates` test class |

## Open Risk

**Supabase aggregate syntax** — the exact `.select()` syntax for SUM/AVG/COUNT DISTINCT needs a spike. PostgREST has evolved this syntax across versions. Task 6 includes a spike step to verify before writing the production code. If the syntax differs from expected, only `db_read()` line ~174 changes — the rest of the plan holds.
