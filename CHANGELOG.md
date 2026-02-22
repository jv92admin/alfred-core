# Changelog

All notable changes to `alfredagain` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/). Versioning: [SemVer](https://semver.org/).

---

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
