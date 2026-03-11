# Research: Split analytical queries out of db_read into db_analyze

**Goal:** Remove aggregate params from `db_read` (entity-focused), create a new `db_analyze` built-in tool for analytical queries.
**Type:** feat (breaking — removes v2.5.0 aggregate params from db_read)
**Date:** 2026-03-10

## Context

`db_read` was designed as an entity-based system: fetch records by ID/filter, track with refs via SessionIdRegistry. In v2.5.0 we bolted aggregate params onto it (`aggregate`, `aggregate_field`) but they're second-class citizens — skip entity tracking, get special-case formatting in Act, silently ignore `limit`/`order_by`, are mutually exclusive with `columns`. CRM use cases reveal the gap further: analytical queries like "total deal value by sales rep" or "largest deal" need GROUP BY, NULL-aware sorting, and no entity tracking. These don't belong in `db_read`.

## Function Chain: Current Aggregate Flow

| Stage | File:Lines | What Happens | Domain Hook |
|-------|-----------|--------------|-------------|
| **Params** | crud.py:50-78 | `DbReadParams` has `aggregate` + `aggregate_field` fields, Pydantic validation, mutually exclusive with `columns` | None |
| **Query Build** | crud.py:187-212 | `is_aggregate` branch builds PostgREST syntax (`"count"`, `"qty.sum()"`) instead of column SELECT | None |
| **Skip Rules** | crud.py:263-267 | `if not is_aggregate:` — order_by and limit silently skipped | None |
| **Entity Tracking** | crud.py + act.py | Naturally skipped — aggregate results have no `id` field, so registry guards pass through | None |
| **Result Format (history)** | act.py:514-522 | `_format_step_results()`: detects single row + no id → `"Step N (aggregate: count=42)"` | None |
| **Result Format (current)** | act.py:718-724 | `_format_current_step_results()`: same detection → `"Aggregate result: count: 42"` | None |
| **Prompt Teaching** | read.md:162-223 | Full "Aggregates" section with 5 examples + rules | None |
| **CRUD Reference** | crud.md:7,49-54 | Tool table lists aggregate params; Column Selection section | None |
| **Think** | think.py | Zero awareness of aggregates — plans `read` steps generically | None |
| **Tests** | test_crud.py:293-422 | 12 tests in `TestDbReadAggregates` | None |

## Function Chain: Analyze Step Infrastructure

| Stage | File:Lines | What Happens | Domain Hook |
|-------|-----------|--------------|-------------|
| **Tool Gating** | base.py:491-507 | `get_tool_enabled_step_types()` → default `{"read", "write"}` | Override to include `"analyze"` |
| **Tool Registration** | base.py:509-524 | `get_custom_tools()` → dict of `ToolDefinition` | Domain registers tools |
| **Prompt Injection** | injection.py:427-433 | CRUD tools only for read/write; custom tools for any tool-enabled step | None |
| **Schema Injection** | injection.py:379-380, act.py:1238-1241 | Schema injected when `tools_enabled=True` or `step_type=="generate"` | None |
| **Tool Dispatch** | act.py:1350-1532 | Generic: BUILTIN_CRUD path or custom_tools path | Domain handler |
| **Analyze Template** | analyze.md | "Make tool calls unless tools are explicitly available" — already tool-aware | `get_act_step_template()` |

## Key Finding: PostgREST Supports GROUP BY (v12+)

**Corrected:** PostgREST v12.0.0+ supports automatic GROUP BY. When you mix aggregate and non-aggregate columns in `select`, PostgREST auto-generates the GROUP BY clause:

```
select=value.sum(),sales_rep
→ SELECT SUM(value), sales_rep ... GROUP BY sales_rep
```

This works through the existing `.table().select()` interface — no RPC needed. The `db-aggregates-enabled` PostgREST config is already a prerequisite for our v2.5.0 aggregates.

**Supported natively:** count(), sum(), avg(), min(), max()
**Not supported:** median (needs `percentile_cont` — window function, not standard aggregate)
**Limitations:** No HAVING clause, no ordering by aggregated columns

## Decisions Made

| Decision | Choice | Why |
|----------|--------|-----|
| Core built-in vs domain tool | **Core built-in** | `db_analyze` is a core data capability like `db_read`. Gate via `get_tool_enabled_step_types()` |
| Default tool-enabled types | **Add `"analyze"` to default** | Any domain on a DB needs analytical queries. `{"read", "write", "analyze"}` |
| GROUP BY | **Yes — PostgREST native** | v12+ supports it via select clause. No RPC needed |
| Aggregate functions | **count, sum, avg, min, max** | All PostgREST-native. Median excluded (needs window function) |
| Walk back strategy | **Clean break in 2.6.0** | Remove aggregate params from db_read, no deprecation period |
| Think awareness | **Yes — teach analyze vs read** | Think needs guidance: analytical question → analyze step, entity fetch → read step |
| Prompt updates | **Think + analyze templates** | Both need schema awareness and db_analyze guidance |

## What db_analyze Supports

| Capability | Support | Notes |
|------------|---------|-------|
| COUNT | Yes | `select("count")` or `select("field.count()")` |
| SUM | Yes | `select("field.sum()")` — PostgREST 12+ |
| AVG | Yes | `select("field.avg()")` — PostgREST 12+ |
| MIN | Yes | `select("field.min()")` — PostgREST 12+ |
| MAX | Yes | `select("field.max()")` — PostgREST 12+ |
| GROUP BY | Yes | PostgREST auto-generates from mixed select columns |
| ORDER BY | Yes | For "top N" / "largest" queries |
| LIMIT | Yes | Combined with ORDER BY for ranked queries |
| Filters | Yes | WHERE before aggregation |
| Entity tracking | No | Returns raw results, no refs |
| HAVING | No | PostgREST limitation |
| Median | No | Needs window function — out of scope |

## Files Impacted

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py` | Remove aggregate params from `DbReadParams`, add `DbAnalyzeParams` + `db_analyze()` |
| `src/alfred/graph/nodes/act.py` | Add `db_analyze` to `BUILTIN_CRUD` set, update result formatting |
| `src/alfred/domain/base.py` | Change default `get_tool_enabled_step_types()` → `{"read", "write", "analyze"}` |
| `src/alfred/prompts/injection.py` | Add `db_analyze` tool line for analyze steps |
| `src/alfred/prompts/templates/act/analyze.md` | Add schema-aware analytical query guidance |
| `src/alfred/prompts/templates/act/read.md` | Remove Aggregates section |
| `src/alfred/prompts/templates/act/crud.md` | Remove aggregate params from db_read, add db_analyze section |
| `src/alfred/prompts/templates/think/think.md` | Add guidance: analytical question → analyze step |
| `tests/core/test_crud.py` | Remove `TestDbReadAggregates`, add `TestDbAnalyze` |
| `CHANGELOG.md` | Breaking change entry |
| `pyproject.toml` | Bump to 2.6.0 |
