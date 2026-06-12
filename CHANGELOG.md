# Changelog

All notable changes to `alfredagain` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: [SemVer](https://semver.org/).

---

## [2.8.0] — 2026-06-12

### Added
- **Protocol split: `DomainContext` / `AgentConfig`** — the 80-member `DomainConfig` ABC
  is now composed from two protocols: `DomainContext` (knowledge & data shaping, incl.
  `CRUDMiddleware.pre_write`) and `AgentConfig` (pipeline & LLM concerns).
  `class DomainConfig(DomainContext, AgentConfig)` — existing domains work unchanged,
  zero migration. New seam import: `from alfred.context import DomainContext` is
  guaranteed free of langgraph/instructor imports (enforced by isolation tests).
- **Audience-grade registry** — domains declare named grades as field strip-sets via the
  new defaulted `DomainContext.get_audience_grades()` hook. Core ships well-known grades
  `"reply"` and `"external"`; `register_domain()` validates `external ⊇ reply` per table
  and fails loudly (`GradeRegistryError`). `StripSet`, `GradeRegistry`, and the 7 public
  grade names are exported from `alfred.domain` and `alfred.context`.
- **State-free assembly entrypoints** — `async assemble_entity_context()` and
  `async assemble_subdomain_read()` in `alfred.context`: no `AlfredState`, no session, no
  LLM call on any path. Return a frozen `ShapedPayload` (`schema_version="1"` — versioned
  external contract). Core validates filters (loud typed errors, never a silent empty
  read); identity handling is a policy parameter; the underlying chain links are
  importable from `alfred.context.assembly` for richer consumers.
- **`get_table_notes(table)` hook** — defaulted `DomainContext` member supplying
  per-table semantic notes for assembly headers (defaults to the owning subdomain's
  notes; zero migration).

### Removed
- **Legacy domain-backed module aliases** — `FIELD_ENUMS`, `SEMANTIC_NOTES`,
  `FALLBACK_SCHEMAS`, `SUBDOMAIN_SCOPE`, `SUBDOMAIN_REGISTRY`, `SUBDOMAIN_EXAMPLES` are
  no longer importable from `alfred.tools.schema` or `alfred.tools` (the module
  `__getattr__` alias layers are deleted). Removed in a minor release because the names
  were undocumented, had zero grep-verified consumers, their documented consumer
  (`web/schema_routes.py`) was already deleted, and they were broken-by-design without a
  registered domain. Use the `DomainConfig` accessor methods instead
  (`get_field_enums()`, `get_subdomain_registry()`, …).

### Changed
- **Built-in prompt defaults de-domained** — the built-in `FILTER_SCHEMA` example values
  (`["milk", "eggs"]` → generic, `"%chicken%"` → generic) and the `act/read.md`
  semantic-search examples (`"quick weeknight meals"`, `"light summer dinner"` → generic)
  no longer assume a kitchen domain. This changes default prompt bytes only for domains
  that don't override `get_filter_schema()` or the Act templates; overriding domains are
  unaffected.

### Fixed
- **Import-time domain coupling** — importing `alfred.tools` (and therefore
  `alfred.context`) no longer requires a registered domain. Domain-free import of the
  seam module is enforced by subprocess isolation tests.
- **`alfred.__version__`** — was stale at `"2.4.0"`; now matches the package version and
  is pinned to the installed metadata by a new version-sync test.

## [2.7.0] — 2026-03-12

### Added
- **`calculate` tool** — safe arithmetic evaluation for analyze steps. Accepts a dict of labeled formulas (`{"formulas": {"label": "expression"}}`), evaluates via AST whitelist (no `eval`/`exec`), returns `{"label": result}`. Supports `+`, `-`, `*`, `/`, `//`, `%`, `**` with per-formula error handling. Analyze steps now have three modes: query (`db_analyze`), arithmetic (`calculate`), and reasoning.
- **`get_reply_continuity_guidance()` domain hook** — domains can now override Reply node conversational continuity guidance on turn 2+. Return custom guidance lines, `None` for core defaults, or `[]` to suppress entirely. DomainConfig now has **75 methods** (was 74).
- **22 new calculate tests** — AST safety (rejects functions, variables, imports, strings, large exponents), params validation, batch evaluation with per-formula errors, `execute_crud` dispatch.
- **3 new reply continuity tests** — default guidance, custom override, suppression via empty list.

### Changed
- **Analyze prompt template expanded** — three-mode guidance (was dual-mode): query, arithmetic, reasoning. `calculate` tool documented with examples for single and batch calculations.
- **CRUD reference updated** — `calculate` tool added to tools table in `act/crud.md`.
- **Summarize node template alignment** — removed stale `summarize.md` template (summarize uses inline prompts, not templates). Moved contracts to `docs/contracts/summarize-node.md`.

## [2.6.1] — 2026-03-11

### Fixed
- **`db_analyze` count with GROUP BY** — `count` without parens caused PostgREST 400 errors when combined with `group_by`. Now generates `count()` which works in all contexts (solo and grouped). Fixes PostgREST v12+ auto-GROUP BY support.

## [2.6.0] — 2026-03-10

### Added
- **`db_analyze` tool** — new core built-in for analytical queries. Supports `count`, `sum`, `avg`, `min`, `max` aggregates with `group_by` for grouped results (PostgREST v12+ auto-generates GROUP BY). Includes `order_by` + `limit` for "top N" queries. Available in analyze steps only — returns raw results, no entity tracking.
- **Analyze steps now tool-enabled by default** — `get_tool_enabled_step_types()` returns `{"read", "write", "analyze"}`. Analyze steps get schema injection and `db_analyze` access automatically.
- **Think guidance for read vs analyze** — Think template updated with clear decision rules: "want to SEE records → read, want a NUMBER about records → analyze". Includes multi-step comparison patterns (YoY, QoQ).
- **Analyze prompt template rewritten** — dual-mode guidance: query mode (db_analyze) and reasoning mode (arithmetic over prior step data). Includes full parameter reference and examples.
- **18 new db_analyze tests** — count/sum/avg/min/max, group_by, filters, order_by + limit, validation, user_id auto-filter, no entity tracking, OR filters.

### Removed (Breaking)
- **`aggregate` and `aggregate_field` params removed from `db_read`** — aggregate queries now use `db_analyze` instead. `db_read` is purely entity-focused (fetch rows, track with refs). The `count_distinct` function is also removed.
- **Aggregate detection heuristic in Act result formatting** — replaced with tool-name-based detection. Multi-row grouped results now format correctly.

### Changed
- **CRUD reference loaded for analyze steps** — analyze steps now see filter syntax and tool reference docs.
- **Act node tool dispatch** — new `BUILTIN_ANALYZE` set alongside `BUILTIN_CRUD` for clean separation.

## [2.5.1] — 2026-03-09

### Fixed
- **Auto-prepend `id` to column selection** — if the LLM passes `columns` without `id`, `db_read` now prepends it automatically. Prevents silent entity tracking breakage. No-op when `id` is already present or `columns` is omitted.
- **Stronger column selection guidance in prompts** — `crud.md` and `read.md` now explicitly discourage passing `columns` unless needed, and warn that `id` is mandatory.

## [2.5.0] — 2026-03-09

### Added
- **Aggregate functions for `db_read`** — `count`, `sum`, `avg`, `count_distinct` via new `aggregate` and `aggregate_field` parameters. Enables scalar queries ("how many?", "total of?", "average?") without fetching all rows. Filters apply as WHERE before aggregation. Results are single-row scalars (`[{"count": 42}]`) with no entity ref tracking. Requires PostgREST 12+ for sum/avg/count_distinct; count works on all versions.
- **Aggregate prompt teaching** — `read.md` includes new Aggregates section with 5 examples and usage rules. `crud.md` updated with aggregate params.
- **Aggregate result formatting** — Act node detects aggregate results (single row, no `id` field) and formats as `"Aggregate result: count: 42"` instead of `"1 records found"`.
- **12 new aggregate tests** (`TestDbReadAggregates`) — count/sum/avg/count_distinct SELECT clauses, filter composition, validation, registry passthrough, silent limit/order_by ignore. Total: 176 tests.

## [2.4.3] — 2026-03-08

### Fixed
- **Subdomain normalization on full Act path** — alias subdomains (e.g. "deals" → "crm") were not normalized before schema lookup, causing "Unknown subdomain" errors. Act Quick already normalized; full Act now does too.

## [2.4.2] — 2026-03-03

### Fixed
- **Domain-neutral default prompts** — removed kitchen-domain examples ("recipes", "Mediterranean Chickpea & Herb Rice Bowl", "meal planning") from all 3 Summarize defaults, FILTER_SCHEMA semantic search docs, and Reply editorial examples. Core defaults now use generic entities ("items", "Weekly Budget Report", "pending tasks").
- **FILTER_SCHEMA `similar` operator** — label changed from "(recipes only)" to "(if supported by domain)" with neutral examples

### Added
- **`engagement_summary` override** — `get_summarize_system_prompts()["engagement_summary"]` now supported; previously the only Summarize prompt with no domain override path
- **Injection Map** (`docs/architecture/injection-map.md`) — comprehensive reference of every DomainConfig prompt hook organized by what it affects (reasoning, UI, capabilities)

### Changed
- `get_summarize_system_prompts()` docstring updated — documents all 4 keys, removed stale "kitchen-oriented examples" caveat

## [2.4.1] — 2026-02-22

### Added
- **CRUD test coverage** (`test_crud.py`, 51 tests) — all 14 filter operators, db_read/create/update/delete, middleware hooks, UUID/NULL sanitization, SessionIdRegistry translation, `gen_*` ref rerouting
- **Act node test coverage** (`test_act_node.py`, 16 tests) — `should_continue_act` routing for all action types, circuit breaker limits, duplicate empty read detection, tool dispatch with mocked LLM
- **Pipeline test coverage** (`test_pipeline.py`, 13 tests) — `route_after_understand`/`route_after_think` routing functions, graph topology (6 nodes, entry point), default router output
- **LLM call resilience** — OpenAI client now configured with explicit `timeout` (60s, configurable via `OPENAI_TIMEOUT`) and `max_retries` (3, configurable via `OPENAI_MAX_RETRIES`). Uses SDK built-in exponential backoff on 429, 5xx, and connection errors. No new dependencies.
- **LLM resilience tests** (`test_llm_resilience.py`, 8 tests) — settings defaults, env var overrides, constructor arg propagation, singleton lifecycle
- **Test documentation** (`docs/architecture/testing.md`) — full coverage map, mock strategies, shared infrastructure reference
- **Enhanced mock DB adapter** (`conftest.py`) — `make_mock_db()` with full PostgREST fluent chaining (14+ filter methods, `not_` proxy)

### Changed
- `CoreSettings` — added `openai_timeout: int = 60` and `openai_max_retries: int = 3`
- `get_client()` — passes `timeout` and `max_retries` to `OpenAI()` constructor
- `get_raw_async_client()` — passes `timeout` and `max_retries` to `AsyncOpenAI()` constructor
- Test count: 76 → 164

## [2.4.0] — 2026-02-21

### Changed
- **Act prompt architecture overhaul** — CRUD docs (`crud.md`) now only injected for read/write steps (not analyze/generate). Custom tool docs injected independently for any tool-enabled step type.
- `_build_decision_section()` — generate steps now respect `tools_enabled` (was hardcoded to step_complete-only regardless of tools)
- `get_custom_tools()` docstring updated — custom tools are independent of CRUD, not "alongside"
- `get_tool_enabled_step_types()` docstring updated — clarifies read/write get CRUD+custom, analyze/generate get custom only

### Added
- `get_crud_reference()` — domain hook to override or replace `crud.md` content for read/write steps
- `get_act_step_template(step_type)` — domain hook to override individual step templates (read.md, write.md, analyze.md, generate.md) without losing base.md, entity tagging, or the decision builder
- DomainConfig: 23 abstract, 50 defaults, 73 total methods

## [2.3.2] — 2026-02-20

### Fixed
- `DbReadParams.order_dir` default changed from `"asc"` to `"desc"` — safer failure mode for "top N" queries when LLM omits or misspells the param
- `crud.md` tool reference now includes `order_by` and `order_dir` params — LLM can now see sorting params exist

## [2.3.1] — 2026-02-20

### Fixed
- `not_in` filter with multiple values no longer silently dropped — uses `query.not_.in_()` instead of logging a warning and returning unfiltered results

## [2.3.0] — 2026-02-20

### Added
- `get_filter_schema()` — domain hook to replace kitchen-specific filter examples (`["milk", "eggs"]`, semantic search) with domain-specific ones
- `get_understand_system_prompt()` — domain hook to override Understand node system prompt (e.g., disable quick mode detection)
- `get_summarize_system_prompts()` — domain hook to override Summarize node system prompts per LLM call (`response_summary`, `turn_compression`, `conversation_compression`)

### Changed
- DomainConfig: 23 abstract, 48 defaults, 71 total methods

## [2.2.0] — 2026-02-20

### Added
- "Running Your Domain" section in `domain-implementation-guide.md` — `run_alfred()` signature, `initialize_conversation()` return shape, multi-turn pattern, streaming events, config wiring explanation
- `scripts/runner.py` in domain scaffold — copy-paste multi-turn conversation loop
- Environment variables reference — all `ALFRED_*` env vars with defaults and purposes
- `.env.example` expanded with all env vars and descriptions
- `NEW-DOMAIN-START-HERE.md` — phased reading order for new domain developers

## [2.1.0] — 2026-02-19

### Added
- `get_tool_enabled_step_types()` — domain hook controlling which step types get tool access (default: `{"read", "write"}`)
- `get_custom_tools()` — domain hook to register custom tools alongside built-in CRUD
- `ToolDefinition` dataclass — `name`, `description`, `params_schema`, `handler`
- `ToolContext` dataclass — `registry`, `step_results`, `current_step_results`, `state`
- Three-branch tool dispatch in Act: CRUD → custom → unknown (BlockedAction)
- Custom tool docs auto-injected into Act prompts as "Domain Tools Reference" table
- Dynamic tool examples in decision prompt (`injection.py`)

### Changed
- `ActDecision.tool` widened from `Literal["db_read", ...]` to `str | None`
- `ToolCallAction.tool` widened from `Literal[...]` to `str`
- `execute_crud()` signature relaxed from `Literal` to `str`
- `analyze.md` / `generate.md` templates: softened tool-restrictive language
- DomainConfig: 23 abstract, 45 defaults, 68 total methods

## [2.0.1] — 2026-02-18

### Fixed
- Excluded `.venv-test` from sdist (22MB → 242KB package size)
- README clone URL corrected
- `.env.example` added to domain scaffold

## [2.0.0] — 2026-02-18

### Added
- Initial release: domain-agnostic LLM orchestration engine
- 5-stage pipeline: Understand → Think → Act → Reply → Summarize
- `DomainConfig` protocol with 23 abstract methods
- Entity lifecycle: `SessionIdRegistry`, ref↔UUID translation, FK enrichment
- CRUD executor with Supabase adapter
- Mode system (QUICK/PLAN/CREATE)
- Conversation memory with compression
- Prompt assembly with core templates as fallback
- Domain scaffold template with questionnaire
- 76 core tests
