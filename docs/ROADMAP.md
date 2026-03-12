# Alfred Core Roadmap

**Last Updated:** 2026-03-11

---

## Completed

### Phase X — Repo Split (2.0.0)
Extracted core orchestration from kitchen monorepo into `alfredagain` PyPI package.

- DomainConfig protocol (23 abstract methods)
- 5-stage pipeline: Understand → Think → Act → Reply → Summarize
- Entity lifecycle, SessionIdRegistry, ref↔UUID translation
- CRUD executor with Supabase adapter
- Mode system, conversation memory, prompt assembly
- Domain scaffold + questionnaire
- 76 core tests → 182 (2.6.1)

### Test Coverage + LLM Resilience (2.4.1)
CRUD, pipeline, and act node tests. LLM client retry/timeout configuration.

- 88 new tests (76 → 164): CRUD engine (51), act node (16), pipeline (13), LLM resilience (8)
- `openai_timeout` + `openai_max_retries` settings, propagated to OpenAI/AsyncOpenAI constructors
- Enhanced mock DB adapter with full PostgREST fluent chaining
- Test architecture doc (`docs/architecture/testing.md`)

### Domain Extensibility (2.1.0 – 2.3.2)
Driven by FPL domain integration — the second domain to use core, surfacing gaps kitchen couldn't find.

- **Tool registry** (2.1.0) — `get_tool_enabled_step_types()` + `get_custom_tools()` + `ToolDefinition` / `ToolContext` dataclasses. Domains register custom tools.
- **Developer docs** (2.2.0) — "Running Your Domain" guide, `run_alfred()` docs, env var reference, quickstart runner script, `NEW-DOMAIN-START-HERE.md`.
- **Prompt hooks** (2.3.0) — `get_filter_schema()`, `get_understand_system_prompt()`, `get_summarize_system_prompts()`. Eliminates kitchen content leaking into non-kitchen domains.
- **Bug fixes** (2.3.1–2.3.2) — `not_in` multi-value filter fix, `order_dir` default `"desc"`, sorting params in crud.md.
- **Act prompt architecture** (2.4.0) — CRUD scoped to read/write only, custom tools independent for any tool-enabled step. `get_crud_reference()` + `get_act_step_template()` hooks. Generate steps now respect `tools_enabled`.

DomainConfig now: 23 abstract, 52 defaults, 75 total methods.

### Aggregates + db_analyze (2.5.0 – 2.6.1)

- **Aggregate queries** (2.5.0) — `aggregate`/`aggregate_field` params on `db_read` for count/sum/avg/count_distinct.
- **Auto-prepend `id`** (2.5.1) — `db_read` auto-prepends `id` to column selection to prevent entity tracking breakage.
- **`db_analyze` tool** (2.6.0) — New dedicated tool for analytical queries. Replaces aggregates on `db_read`. Supports count/sum/avg/min/max with GROUP BY, order_by + limit for "top N" queries. Analyze steps tool-enabled by default.
- **count() parens fix** (2.6.1) — `count` → `count()` in PostgREST select clause. Fixes GROUP BY compatibility on PostgREST v12+.

DomainConfig: 23 abstract, 52 defaults, 75 total methods (unchanged since 2.4.0 era).

---

## Backlog

### P1 — BlockedAction → Replan Path
Act's `should_continue_act()` routes all `BlockedAction` to `"reply"`. The `suggested_next: "replan"` field exists but has no graph edge back to Think. FPL needs this for assessment-driven re-planning ("got 0 results → replan with broader criteria").

**Scope:** New conditional edge from Act → Think in workflow.py. Think needs to handle mid-execution replanning (partial step_results, modified plan).

### P2 — FILTER_SCHEMA Domain-Configurable Constants
`get_filter_schema()` hook now exists (2.3.0), but other module-level constants in `tools/schema.py` still have kitchen traces. Full audit of remaining hardcoded content that should be domain-configurable.

### P3 — Auto-Generate Tool Param Schema
Domain Act prompts reverse-engineer param names from Pydantic models. Could auto-generate a param reference from `DbReadParams.model_json_schema()` and inject it alongside `crud.md`. Would make it impossible for domain prompts to teach wrong param names.

### P4 — Summarize Template Domain Hook ✅
Resolved: `summarize.md` was moved to `docs/contracts/summarize-node.md` (it was a contracts doc, not a prompt template). Summarize uses 4 inline prompts, each individually overridable via `get_summarize_system_prompts()`.

### P5 — Kitchen Content Audit
Systematic sweep of all prompt templates and constants for kitchen-specific language. Known items:
- `summarize.md` moved to `docs/contracts/summarize-node.md` (contracts doc, no kitchen-specific examples)
- `FILTER_SCHEMA` default still has kitchen examples (overridable via hook)
- `tools/schema.py` `__getattr__` lazy constants

---

## Version History

See [CHANGELOG.md](../CHANGELOG.md) for detailed per-version changes.
