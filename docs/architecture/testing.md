# Testing

> Test suite structure, coverage map, and how to run tests.

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Core tests only
pytest tests/core/ -v

# Single file
pytest tests/core/test_crud.py -v

# Quality checks
ruff check src/
ruff format src/
```

---

## Test Architecture

All core tests live in `tests/core/` and use a **StubDomainConfig** — a minimal 2-entity, 2-subdomain domain defined in `tests/core/conftest.py`. This proves that the entire orchestration engine works with _any_ domain, not just Kitchen.

No test requires a real database, real LLM calls, or any domain package installed.

### Shared Infrastructure (`conftest.py`)

| Fixture | Purpose |
|---------|---------|
| `StubDomainConfig` | Minimal `DomainConfig` with items + notes entities, registered via `register_domain()` |
| `make_mock_db()` | Full PostgREST-compatible mock with fluent chaining for all 14+ filter methods |
| `register_stub_domain` | Autouse fixture — registers StubDomainConfig before each test, resets after |
| `mock_openai` | Pre-configured `MagicMock` OpenAI client for unit tests |

The mock DB adapter supports the complete PostgREST query builder chain: `select`, `insert`, `update`, `delete`, `eq`, `neq`, `gt`, `lt`, `gte`, `lte`, `ilike`, `in_`, `is_`, `contains`, `or_`, `order`, `limit`, plus the `not_` proxy for `not_.in_()` and `not_.is_()`. Tests verify that the correct methods are called with correct arguments — actual filtering is Supabase's responsibility.

---

## Coverage Map

176 tests across 11 test files.

### CRUD Engine — `test_crud.py` (63 tests)

Tests `src/alfred/tools/crud.py` — the execution layer every domain hits on every turn.

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestApplyFilter` | 16 | All 14 filter operators map to correct PostgREST methods; unknown operator raises `ValueError` |
| `TestDbRead` | 11 | Column selection, ordering (asc/desc), limit, user-owned auto-filter, AND/OR filters, middleware hooks (`short_circuit_empty`, `pre_filter_ids`, `post_read`) |
| `TestDbReadAggregates` | 12 | count/sum/avg/count_distinct SELECT clause, filters with aggregates, validation (columns mutual exclusion, required aggregate_field), order/limit silently skipped, user_id auto-filter, registry passthrough (no ref assignment) |
| `TestDbCreate` | 9 | Single/batch insert, `user_id` injection, UUID sanitization (empty→None), NULL byte stripping, middleware (`pre_write`, `deduplicate_batch`) |
| `TestDbUpdate` | 3 | Filter application, user-owned auto-filter, multiple filters |
| `TestDbDelete` | 4 | Filter application, user-owned auto-filter, empty filter safety (ValueError for non-user tables, allowed for user-owned) |
| `TestExecuteCrud` | 8 | Dispatch to correct function, unknown tool ValueError, SessionIdRegistry input/output translation, `gen_*` ref rerouting |

### Act Node — `test_act_node.py` (16 tests)

Tests `src/alfred/graph/nodes/act.py` — the most complex node in the pipeline.

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestShouldContinueAct` | 9 | Routing function for all action types: None→reply, ToolCall→continue, StepComplete (more/done), RequestSchema→continue, RetrieveStep→continue, AskUser→ask_user, Blocked→reply, Fail→fail |
| `TestActNodeCircuitBreaker` | 4 | `MAX_TOOL_CALLS_PER_STEP` forces completion, duplicate empty reads force completion, missing think_output→FailAction, all steps done→None |
| `TestActNodeToolDispatch` | 3 | LLM tool_call dispatches CRUD correctly, step_complete advances index, schema request blocked after limit |

### Pipeline — `test_pipeline.py` (13 tests)

Tests `src/alfred/graph/workflow.py` — routing logic and graph topology.

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestRouteAfterUnderstand` | 4 | Clarification→reply, quick_mode→act_quick, normal→think, missing output→think |
| `TestRouteAfterThink` | 4 | plan_direct→act, propose→reply, clarify→reply, missing output→reply |
| `TestGraphStructure` | 3 | Graph compiles, has all 6 nodes, entry point is understand |
| `TestDefaultRouter` | 2 | Creates correct RouterOutput from StubDomainConfig defaults |

### LLM Resilience — `test_llm_resilience.py` (8 tests)

Tests `src/alfred/config.py` + `src/alfred/llm/client.py` — timeout and retry configuration.

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestCoreSettingsDefaults` | 4 | `openai_timeout=60`, `openai_max_retries=3`, env var overrides (`OPENAI_TIMEOUT`, `OPENAI_MAX_RETRIES`) |
| `TestClientConstruction` | 4 | Sync/async clients receive timeout+retries, singleton reuse, singleton reset rebuilds |

### Domain Config — `test_domain_config.py` (22 tests)

Tests `src/alfred/domain/base.py` — DomainConfig protocol and StubDomainConfig implementation.

| Class | Tests | What it covers |
|-------|-------|---------------|
| `TestStubDomainConfig` | 14 | All StubDomainConfig properties and methods: name, entities, subdomains, table↔type mapping, domain registration, bypass modes, default agent, aliases, user-owned tables, UUID fields, entity inference, label computation |
| `TestDomainConfigDefaults` | 8 | Default implementations of optional methods: CRUD middleware, data legends, detail level, archive keys, entity/record formatting, system prompts, LLM config, think context |

### Supporting Tests

| File | Tests | What it covers |
|------|-------|---------------|
| `test_id_registry.py` | 11 | SessionIdRegistry: ref creation, UUID↔ref lookup, generated entities, promote to real, filter/payload translation, serialization round-trip, prompt formatting |
| `test_state_models.py` | 8 | Pydantic state models: EntityRef, RouterOutput, ThinkStep, ThinkOutput, StepCompleteAction, AlfredState |
| `test_modes.py` | 11 | Mode enum, ModeConfig, ModeContext: default/round-trip/max_steps/verbosity |
| `test_model_router.py` | 7 | Model selection, node temperatures, cost estimation, cost tracker |
| `test_cost_tracker.py` | 6 | Cost estimation per model, CostTracker aggregation, summary structure |
| `test_health.py` | 5 | Import smoke tests for core modules |

---

## Mock Strategies

### CRUD Tests
Patch `get_current_domain()` to return StubDomainConfig with a `make_mock_db()` adapter. Tests verify that the correct PostgREST methods are called with correct arguments.

### Act Node Tests
- **Circuit breaker tests** need no mocks — they fire before any LLM call
- **Tool dispatch tests** patch `call_llm` (returns mock ActDecision), `execute_crud`, `get_schema_with_fallback`, `set_current_node`, `format_full_context`, and `build_act_user_prompt`

### Pipeline Tests
Test routing functions as pure functions (state dict in, string out). Graph structure tests use `create_alfred_graph()` directly and inspect nodes/edges.

### LLM Resilience Tests
Patch `OpenAI`/`AsyncOpenAI` constructors and `settings` object. Verify constructor args without making real HTTP calls.

---

## Adding Tests

1. Put new tests in `tests/core/`
2. Use `StubDomainConfig` from conftest — don't import any domain package
3. Use `make_mock_db()` for DB interactions
4. For async tests, pytest-asyncio is configured in auto mode
5. Run `pytest tests/core/ -v` to verify
