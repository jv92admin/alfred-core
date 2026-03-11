# Plan: Split analytical queries out of db_read into db_analyze

**Date:** 2026-03-10
**Based on:** RESEARCH.md

## Approach

Create `db_analyze` as a core built-in tool for analytical queries (count, sum, avg, min, max + GROUP BY + ORDER BY + LIMIT). Walk back aggregate params from `db_read` completely — clean break, no deprecation. Update Think to plan `analyze` steps for analytical questions and update the analyze prompt template with schema-aware query guidance. Gate via `get_tool_enabled_step_types()` which defaults to `{"read", "write", "analyze"}`.

## Tasks

### Phase 1: Walk back aggregates from db_read
- [ ] Remove `aggregate` and `aggregate_field` fields from `DbReadParams` (crud.py:67-69)
- [ ] Remove `_validate_aggregate` validator (crud.py:71-78)
- [ ] Remove `is_aggregate` branch from `db_read()` query building (crud.py:187-201)
- [ ] Remove `if not is_aggregate:` guard on order_by/limit (crud.py:262-267) — always apply
- [ ] Remove Aggregates section from read.md (lines 162-223)
- [ ] Remove aggregate params from db_read entry in crud.md (line 7)
- [ ] Remove `TestDbReadAggregates` class from test_crud.py (lines 293-422, 12 tests)

### Phase 2: Create db_analyze tool
- [ ] Create `DbAnalyzeParams` model in crud.py:
  - `table: str`
  - `aggregate: Literal["count", "sum", "avg", "min", "max"]`
  - `aggregate_field: str | None` (required for sum/avg/min/max, optional for count)
  - `filters: list[FilterClause]`
  - `or_filters: list[FilterClause]`
  - `group_by: str | None` (PostgREST auto-generates GROUP BY from mixed select)
  - `order_by: str | None`
  - `order_dir: Literal["asc", "desc"] = "desc"`
  - `limit: int | None`
- [ ] Create `db_analyze()` async function in crud.py:
  - Build SELECT: `"field.sum(),group_col"` or `"count"` etc.
  - Apply filters (reuse `apply_filter`)
  - Apply user_id filter for user-owned tables
  - Apply ORDER BY + LIMIT (always, unlike old aggregate code)
  - Return raw `list[dict]` — no entity tracking, no middleware
- [ ] Write `TestDbAnalyze` test class:
  - count (no field, with field)
  - sum, avg, min, max
  - group_by (mixed select → PostgREST GROUP BY)
  - filters + aggregate
  - order_by + limit (for "top N")
  - validation (sum without field → error)
  - user_id auto-filter
  - no entity tracking (registry stays empty)

### Phase 3: Wire into Act node
- [ ] In act.py, create `BUILTIN_ANALYZE = {"db_analyze"}` alongside `BUILTIN_CRUD` (line 1351)
- [ ] Update tool dispatch: `if decision.tool in BUILTIN_CRUD: ...` add `elif decision.tool in BUILTIN_ANALYZE:` path
  - Call `db_analyze()` with params + user_id
  - Store result in `current_step_tool_results` (no entity tracking)
- [ ] Update result formatting in `_format_step_results()` (line 515-521):
  - Keep aggregate detection heuristic (no `id` field) but label as `db_analyze` result
  - Handle multi-row grouped results (not just single-row scalars)
- [ ] Update result formatting in `_format_current_step_results()` (line 718-724):
  - Same: handle multi-row grouped results, format as table

### Phase 4: Update tool gating & prompt injection
- [ ] In base.py, change `get_tool_enabled_step_types()` default: `{"read", "write"}` → `{"read", "write", "analyze"}` (line 507)
- [ ] Update docstring to reflect new default and that analyze gets `db_analyze` (not CRUD)
- [ ] In injection.py, update tool injection (lines 429-439):
  - Keep `if step_type in ("read", "write"):` → CRUD tools
  - Add `if step_type == "analyze":` → `db_analyze` tool line
  - Custom tools still available for any tool-enabled step

### Phase 5: Update prompt templates

#### Prompt architecture recap

**Think:** `think.md` is core-owned with two domain placeholders (`{domain_context}`, `{domain_planning_guide}`). Think does NOT see schema. Domain can also fully replace via `get_think_prompt_content()`.

**Act/Analyze system prompt:** `base.md` (core, always) + `analyze.md` (core default, domain can replace via `get_act_step_template("analyze")`) + optional domain injection (`get_act_prompt_injection("analyze")`).

**Act/Analyze user prompt (15 sections):** Schema auto-injects when `tools_enabled=True` (Section 2). Once `"analyze"` is in default `get_tool_enabled_step_types()`, schema flows in automatically — no new plumbing.

#### What core owns vs domain configures

| What | Where | Owner | Notes |
|------|-------|-------|-------|
| Step type definitions (read vs analyze) | `think.md` step types table | **Core** | Universal, not domain-specific |
| "Analytical question → analyze step" guidance | `think.md` | **Core** | Universal planning rule |
| `db_analyze` tool mechanics + examples | `analyze.md` | **Core default** | Domain can replace via `get_act_step_template("analyze")` |
| `db_analyze` param reference | `crud.md` | **Core** | Tool reference doc |
| "You can do arithmetic directly" | `analyze.md` | **Core default** | Percentage/comparison math needs no tool |
| Schema injection into analyze | `injection.py` | **Core** | Automatic when `tools_enabled=True` |
| Domain-specific analytical patterns | `get_examples(subdomain, "analyze")` | **Domain** | e.g. "for CRM, common analyses: pipeline value, win rate" |
| Domain-specific analyze rules | `get_act_prompt_injection("analyze")` | **Domain** | Appended after template |
| Full analyze template replacement | `get_act_step_template("analyze")` | **Domain** | Nuclear option — replaces analyze.md entirely |

#### Think template changes (core-owned)
- [ ] Update think.md step types table (line 71-78):
  - `read`: "Fetch records by ID or filter. Returns tracked entities with refs. Use when user wants to SEE records."
  - `analyze`: "Analytical queries (counts, totals, averages, comparisons) OR reasoning over data from prior steps. Use when user asks a QUESTION about data (how many, total, average, largest, compare). Each db_analyze call returns one aggregate — use multiple steps for comparisons (e.g. Q1 vs Q2)."
- [ ] Add guidance near read vs analyze decision section (lines 164-188):
  - "Want to SEE records → read. Want a NUMBER about records → analyze."
  - "Comparisons (YoY, QoQ, before/after) need multiple analyze steps — one query per period, then a reasoning step to compute the difference."

#### Analyze template changes (core default, domain-replaceable)
- [ ] Update analyze.md:
  - Add `db_analyze` tool usage section with examples (count, sum, avg, min, max, group_by)
  - Keep "reason over prior step data" capability (dual purpose: query OR reason)
  - Add: "You can compute percentages, differences, and comparisons directly — no tool needed. If you have results from prior steps, do the math."
  - Add: "One aggregate per call. For comparisons, prior steps should have fetched the other value."
  - Schema will auto-appear in user prompt (Section 2) — no template change needed for that

#### CRUD reference changes (core-owned)
- [ ] Update crud.md:
  - Remove aggregate params from db_read tool table entry
  - Add db_analyze section with params, examples: count, sum with group_by, top N, filtered aggregate
  - Note: "db_analyze is available in analyze steps only. db_read is for entity fetch in read/write steps."

### Phase 6: Ship
- [ ] Bump version to 2.6.0 in pyproject.toml
- [ ] Add CHANGELOG entry (breaking change: aggregate params removed from db_read)
- [ ] Run tests
- [ ] Commit, push, publish

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Tool availability | `db_analyze` only in analyze steps, CRUD only in read/write | Clean separation: entity fetch vs analytical query |
| Default step types | `{"read", "write", "analyze"}` | Analytical queries are common for any DB-backed domain |
| GROUP BY | Via PostgREST native (mixed select columns) | No RPC needed, works through existing `.table().select()` |
| Aggregate functions | count, sum, avg, min, max | All PostgREST-native. No median (needs window function) |
| count_distinct | Drop it | PostgREST count() on a specific field already counts non-null values; true DISTINCT COUNT isn't reliably supported via PostgREST aggregate syntax |
| Middleware | No middleware for db_analyze | Middleware adds nested relations/transforms for entity reads — irrelevant for aggregates |
| Result formatting | Detect via tool name, not heuristic | Current "single row + no id" heuristic breaks with GROUP BY multi-row results. Tag results by source tool instead. |

## Error Handling

- `db_analyze` with `aggregate` in `("sum", "avg", "min", "max")` and no `aggregate_field` → `ValueError`
- `db_analyze` with `group_by` but no `aggregate` → `ValueError`
- `db_analyze` on a table not in schema → PostgREST error (pass through)
- PostgREST `db-aggregates-enabled = false` → PostgREST error (document as prerequisite)

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/tools/crud.py` | Remove aggregate from DbReadParams, add DbAnalyzeParams + db_analyze() |
| `src/alfred/graph/nodes/act.py` | Add BUILTIN_ANALYZE set, dispatch db_analyze, update result formatting |
| `src/alfred/domain/base.py` | Default `get_tool_enabled_step_types()` → `{"read", "write", "analyze"}` |
| `src/alfred/prompts/injection.py` | Add db_analyze tool line for analyze steps |
| `src/alfred/prompts/templates/act/analyze.md` | Add db_analyze usage + examples |
| `src/alfred/prompts/templates/act/read.md` | Remove Aggregates section |
| `src/alfred/prompts/templates/act/crud.md` | Remove aggregate from db_read, add db_analyze section |
| `src/alfred/prompts/templates/think/think.md` | Add analyze vs read guidance for analytical queries |
| `tests/core/test_crud.py` | Remove TestDbReadAggregates, add TestDbAnalyze |
| `pyproject.toml` | Bump to 2.6.0 |
| `CHANGELOG.md` | Breaking change entry |
