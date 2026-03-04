# Changelog

All notable changes to `alfredagain` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: [SemVer](https://semver.org/).

---

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
