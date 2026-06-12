# Core-Domain Architecture

How Alfred's core orchestration engine and domain-specific implementations relate.

---

## 1. Package Structure

Alfred core is a standalone package (`alfredagain` on PyPI). This repo's `src/` holds **only** core; domains (Kitchen — reference implementation, FPL — validates the abstraction) are separate packages in their own repos that depend on `alfredagain`.

```
src/
├── alfred/                          ← core orchestration (domain-agnostic)
│   ├── agents/                      AgentProtocol, AgentRouter (2 files)
│   ├── context/                     Context builders, entity tracking, reasoning + state-free assembly seam (6 files)
│   ├── core/                        SessionIdRegistry, modes, payload_compiler (4 files)
│   ├── db/                          DatabaseAdapter protocol (2 files)
│   ├── domain/                      DomainContext + AgentConfig + DomainConfig composition, grades, registration (5 files)
│   ├── graph/
│   │   ├── nodes/                   act, reply, router, summarize, think, understand (7 files)
│   │   ├── state.py                 AlfredState TypedDict + all data models
│   │   └── workflow.py              LangGraph construction + streaming
│   ├── llm/                         LLM client, model router, prompt logger (4 files)
│   ├── memory/                      Conversation history management (2 files)
│   ├── modes/                       Handoff protocol (2 files)
│   ├── observability/               LangSmith integration, session logging (3 files)
│   ├── prompts/
│   │   ├── injection.py             Act prompt assembly
│   │   └── templates/               11 core .md templates (1,635 lines)
│   ├── tools/                       CRUD executor, schema builder, normalization (5 files)
│   └── config.py                    CoreSettings (OpenAI, LangSmith, env)
```

A domain package supplies what core deliberately leaves out: entity definitions, subdomain registry, personas/examples/prompt content, formatters, a DB adapter, CRUD middleware, and (optionally) bypass-mode handlers — all behind the `DomainConfig` protocol. See [domain-implementation-guide.md](domain-implementation-guide.md) for the full shape of a domain package.

---

## 2. The DomainConfig Protocol

`DomainConfig` ([domain/base.py](src/alfred/domain/base.py)) is an ABC that every domain must implement. Since 2.8.0 it is **composed from two protocols** and has **80 members**:

```python
class DomainConfig(DomainContext, AgentConfig): ...   # defines nothing directly
```

### Member Census

| Protocol | File | Members | Abstract | Default | Concern |
|----------|------|---------|----------|---------|---------|
| `DomainContext` | [domain/context.py](src/alfred/domain/context.py) | 36 | 15 | 21 | Knowledge & data shaping: entities, subdomains, schema/FK config, CRUD middleware (`pre_write` lives here), formatting, strip fields, audience grades, table notes |
| `AgentConfig` | [domain/agent.py](src/alfred/domain/agent.py) | 44 | 8 | 36 | Pipeline & LLM: prompt content/injection, personas, modes, agents, tools, LLM config, handoff |
| **`DomainConfig` (composed)** | [domain/base.py](src/alfred/domain/base.py) | **80** | **23** | **57** | |

**23 abstract members** must be implemented. **57 default members** provide sensible fallbacks — a new domain can start with just the abstract members and progressively override defaults. Substrate-only consumers (shaped reads, no LLM pipeline) implement `DomainContext` alone.

> **Authoritative count:** the sort-freeze test in [tests/core/test_protocol_split.py](tests/core/test_protocol_split.py) pins every member to its bucket — when the census moves, that test fails and this table gets updated. Per-hook documentation by effect lives in [injection-map.md](injection-map.md).

### Supporting Dataclasses

Five dataclasses underpin the protocol:

**`EntityDefinition`** in [domain/context.py](src/alfred/domain/context.py) — describes one entity type:

| Field | Type | Purpose |
|-------|------|---------|
| `type_name` | `str` | Short ref prefix (e.g., `"recipe"` → `recipe_1`) |
| `table` | `str` | Database table name |
| `primary_field` | `str` | Display label field (default: `"name"`) |
| `fk_fields` | `list[str]` | Foreign key columns |
| `complexity` | `str \| None` | Think node hint: `"high"`, `"medium"`, or `None` |
| `label_fields` | `list[str]` | Fields used to compute labels |
| `nested_relations` | `list[str] \| None` | Related tables to auto-include in reads |
| `detail_tracking` | `bool` | Whether to track summary vs full reads |

**`SubdomainDefinition`** in [domain/context.py](src/alfred/domain/context.py) — logical table grouping:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Subdomain identifier (e.g., `"recipes"`) |
| `primary_table` | `str` | Main table |
| `related_tables` | `list[str]` | Other tables in this subdomain |
| `description` | `str` | Human-readable description for Think prompt |

**`ReadPreprocessResult`** in [domain/context.py](src/alfred/domain/context.py) — returned by `CRUDMiddleware.pre_read()`:

| Field | Type | Purpose |
|-------|------|---------|
| `params` | `Any` | Modified read parameters |
| `select_additions` | `list[str]` | Extra SELECT clauses (e.g., nested relations) |
| `pre_filter_ids` | `list[str] \| None` | IDs from semantic search to filter by |
| `or_conditions` | `list[str] \| None` | Additional OR conditions |
| `short_circuit_empty` | `bool` | Return `[]` without querying |

**`ToolDefinition`** in [domain/agent.py](src/alfred/domain/agent.py) — a domain-provided tool:

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `str` | Tool name the LLM emits (e.g., `"run_python"`) |
| `description` | `str` | One-line description for Act prompt |
| `params_schema` | `str` | Human-readable param docs for Act prompt |
| `handler` | `Callable` | Async handler: `(params, user_id, ToolContext) -> Any` |

**`ToolContext`** in [domain/agent.py](src/alfred/domain/agent.py) — context passed to custom tool handlers:

| Field | Type | Purpose |
|-------|------|---------|
| `registry` | `Any` | SessionIdRegistry (ref ↔ UUID translation) |
| `step_results` | `list` | Results from prior steps in this turn |
| `current_step_results` | `list` | Tool results from current step so far |
| `state` | `dict` | Full AlfredState (read-only by convention) |

### Computed Properties

Two properties are auto-derived from `entities` — domains get these for free:

- `table_to_type` ([domain/context.py](src/alfred/domain/context.py)) — maps `"recipes"` → `"recipe"`
- `type_to_table` ([domain/context.py](src/alfred/domain/context.py)) — maps `"recipe"` → `"recipes"`

---

## 3. Registration

Domain registration uses a simple global pattern in [domain/__init__.py](src/alfred/domain/__init__.py):

```python
_current_domain: DomainConfig | None = None

def register_domain(domain: DomainConfig) -> None:
    GradeRegistry.from_context(domain)  # validates audience grades; raises GradeRegistryError
    global _current_domain
    _current_domain = domain

def get_current_domain() -> DomainConfig:
    if _current_domain is None:
        raise RuntimeError("No domain registered. Call register_domain() at app startup.")
    return _current_domain
```

No fallback, no auto-import. If no domain is registered, core raises `RuntimeError`. This enforces explicit registration at startup. Since 2.8.0, registration also validates the domain's audience-grade declarations (`external ⊇ reply` per table) and refuses to register on failure.

### How Domains Register

Each domain's `__init__.py` registers at import time:

```python
# alfred_kitchen/__init__.py (or alfred_fpl/__init__.py)
from alfred.domain import register_domain

def _register():
    from alfred_kitchen.domain import KITCHEN_DOMAIN
    register_domain(KITCHEN_DOMAIN)

_register()
```

### Startup Wiring

Every entry point must import its domain package before calling any core function:

| Entry Point | How It Registers |
|-------------|-----------------|
| `alfred_kitchen/main.py` | Top-level `import alfred_kitchen` |
| `alfred_kitchen/server.py` | Top-level `import alfred_kitchen` |
| `alfred_fpl/main.py` | Top-level `import alfred_fpl` |
| `tests/conftest.py` | `import alfred_kitchen` (or `alfred_fpl`) in fixture |

---

## 4. Core Guarantees

What `alfred` provides without any domain implementation:

| Capability | Module | What You Get |
|-----------|--------|-------------|
| LLM pipeline | `graph/workflow.py` | Understand → Think → Act → Reply → Summarize with conditional routing |
| Entity tracking | `core/id_registry.py` | UUID → human refs (`recipe_1`), detail levels, FK enrichment, cross-turn persistence |
| CRUD execution | `tools/crud.py` | Filter building, ref↔UUID translation, user_id scoping, batch manifests |
| Conversation memory | `memory/conversation.py` | Turn history, compression, engagement summaries, context windowing |
| Prompt assembly | `prompts/injection.py` | 15-section Act prompt builder, subdomain guidance, quick mode prompts |
| Mode system | `core/modes.py` | QUICK/PLAN/CREATE modes with per-mode LLM config |
| Context building | `context/builders.py` | Think/Act/Understand context assembly from state |
| LLM client | `llm/client.py` | `call_llm()` with structured output, model routing by complexity |
| Prompt templates | `prompts/templates/` | 11 structural .md templates as fallback prompts |
| Observability | `observability/` | LangSmith tracing, session logging |
| Agent protocol | `agents/base.py` | `AgentProtocol`, `AgentRouter`, `MultiAgentOrchestrator` |
| State model | `graph/state.py` | `AlfredState` TypedDict with all pipeline data models |

Core is functional with just the default `DomainConfig` methods — it will run a pipeline, track entities, execute CRUD, and produce responses. The results won't be useful without domain-specific entities, prompts, and formatting, but the machinery works.

---

## 5. Domain Responsibilities

### Must Implement (23 abstract methods)

A domain **must** provide:

**Identity:**
- `name` — domain identifier (`"kitchen"`, `"fpl"`)
- `entities` — entity definitions (what types of things exist)
- `subdomains` — how tables are grouped for Think planning

**Prompt content:**
- `get_persona(subdomain, step_type)` — LLM persona per subdomain
- `get_examples(subdomain, step_type, ...)` — contextual examples

**Schema:**
- `get_table_format(table)` — formatting rules per table
- `get_empty_response(subdomain)` — "no results" message
- `get_fk_enrich_map()` — FK→table→name_column mapping
- `get_field_enums()` — valid values for categorical fields
- `get_semantic_notes()` — subdomain clarifications
- `get_fallback_schemas()` — hardcoded schema fallbacks
- `get_scope_config()` — cross-subdomain relationships
- `get_user_owned_tables()` — tables needing user_id scoping
- `get_uuid_fields()` — FK field names containing UUIDs
- `get_subdomain_registry()` — subdomain→tables mapping
- `get_subdomain_examples()` — example queries per subdomain

**Entity processing:**
- `infer_entity_type_from_artifact(artifact)` — type from generated content structure
- `compute_entity_label(record, entity_type, ref)` — human-readable label
- `get_subdomain_aliases()` — informal name → canonical name mapping
- `get_subdomain_formatters()` — reply formatters per subdomain

**Mode/agent:**
- `bypass_modes` — graph-bypass mode handlers (e.g., cook, brainstorm)
- `default_agent` — agent name for single-agent mode

**Infrastructure:**
- `get_handoff_result_model()` — Pydantic model for bypass mode handoff
- `get_db_adapter()` — database access implementation

### Should Override (Key Defaults)

These defaults work but produce generic results:

| Method | Default | Why Override |
|--------|---------|-------------|
| `get_system_prompt()` | `"You are a helpful {name} assistant."` | Domain identity and personality |
| `format_entity_for_context()` | Simple key-value dump | Rich entity display (e.g., recipes with ingredients) |
| `format_record_for_context()` | `"  - {name} id:{ref}"` | Domain-specific fields (quantity, location, cuisine) |
| `get_crud_middleware()` | `None` (no middleware) | Semantic search, auto-includes, enrichment |
| `get_strip_fields()` | Empty set | Hide internal fields from LLM/user |
| Prompt content methods | `""` (fall back to core templates) | Domain-specific examples and guidance |

### Optional (Truly Optional Defaults)

These have sensible defaults that many domains won't need to change:

- `get_tracked_entity_types()` — auto-derived from entities with `complexity` set
- `get_relevant_entity_types()` — auto-derived same way
- `table_to_type`, `type_to_table` — auto-computed from `entities`
- `compute_artifact_label()` — uses `name`/`title` fields
- `get_priority_fields()` — default list: name, title, date, description, notes, category

---

## 6. Import Boundary

**Core never imports domain. Domain imports core freely.**

This is the foundational architectural rule. It means:

- `src/alfred/` has zero imports from any domain package (`alfred_kitchen`, `alfred_fpl`, …)
- Domain packages import freely from `alfred`
- Core accesses domain behavior exclusively through `get_current_domain()` → `DomainConfig` methods

### Enforcement

```bash
# These must return zero hits:
grep -rn "from alfred_kitchen" src/alfred/ --include="*.py"
grep -rn "from alfred_fpl" src/alfred/ --include="*.py"
```

Additionally, `alfred.context` (the substrate seam) must import cleanly with **no registered domain** and pull in no langgraph/instructor — enforced by subprocess tests in [tests/core/test_import_isolation.py](tests/core/test_import_isolation.py).

There are no exceptions — core has zero imports from any domain package. All backwards-compat shims were removed during the FPL domain build.

### Why This Matters

The import boundary ensures core can be extracted into a standalone package (`pip install alfred`) that has no knowledge of any specific domain. A new domain (FPL, fitness, etc.) implements `DomainConfig`, calls `register_domain()`, and the entire pipeline works without core changes.

---

## 7. Key Protocols

Four protocols define the extension surface:

### DomainConfig

**Files:** [domain/base.py](src/alfred/domain/base.py) (75-line composition shim) over [domain/context.py](src/alfred/domain/context.py) (603 lines) and [domain/agent.py](src/alfred/domain/agent.py) (598 lines)

The central protocol. 80 members across the two-protocol split (see section 2). A domain implements this to plug into Alfred's pipeline; substrate-only consumers implement `DomainContext` alone.

### DatabaseAdapter

**File:** [db/adapter.py:23](src/alfred/db/adapter.py#L23) (52 lines)

```python
@runtime_checkable
class DatabaseAdapter(Protocol):
    def table(self, name: str) -> Any:     # Returns query builder
    def rpc(self, function_name: str, params: dict) -> Any:
```

Thin wrapper over the database client. Uses `@runtime_checkable` for duck typing. The `table()` method returns a query builder compatible with PostgREST's fluent API (`.select()`, `.eq()`, `.insert()`, `.execute()`, etc.). Core's `apply_filter()` in `tools/crud.py` calls 12 query builder methods directly.

**Conscious coupling:** The adapter is tied to the PostgREST query builder pattern. This is acceptable while all domains use Supabase. If a future domain uses a different DB, `apply_filter()` is the refactor point.

Kitchen implements this by returning the Supabase client from `get_client()`.

### CRUDMiddleware

**File:** [domain/context.py](src/alfred/domain/context.py)

```python
class CRUDMiddleware:
    async def pre_read(self, params, user_id) -> ReadPreprocessResult
    async def post_read(self, records, table, user_id) -> list[dict]
    async def pre_write(self, table, records) -> list[dict]
    def deduplicate_batch(self, table, records) -> list[dict]
```

Optional domain intelligence layer that fires inside `execute_crud()`. Default implementations are pass-throughs. `post_read()` fires after the database query, before results return to the pipeline — use it for record enrichment or computed fields. Kitchen's `KitchenCRUDMiddleware` adds semantic search (pgvector), auto-includes (recipe_ingredients), fuzzy name matching, and ingredient enrichment.

See [crud-and-database.md](crud-and-database.md) for the full middleware architecture.

### EntityDefinition

**File:** [domain/context.py](src/alfred/domain/context.py)

Configuration dataclass for entity types. Not a protocol — it's a value object that domains instantiate. 8 fields control how core handles each entity type (ref naming, FK tracking, nested relations, detail levels).

---

## Kitchen as Reference Implementation

Kitchen implements all 23 abstract methods and overrides ~20 defaults across 673 lines of `KitchenConfig` ([domain/__init__.py](src/alfred_kitchen/domain/__init__.py)), plus ~3,500 lines across 12 submodules (formatters, personas, examples, schema, compilers, middleware, prompts, etc.).

### Kitchen's Entities (10 types)

| Entity | `type_name` | Table | Complexity | Nested Relations |
|--------|------------|-------|-----------|-----------------|
| Recipes | `recipe` | `recipes` | high | `recipe_ingredients` |
| Recipe Ingredients | `ri` | `recipe_ingredients` | — | — |
| Inventory | `inv` | `inventory` | — | — |
| Shopping List | `shop` | `shopping_list` | — | — |
| Meal Plans | `meal` | `meal_plans` | medium | — |
| Tasks | `task` | `tasks` | — | — |
| Preferences | `pref` | `preferences` | — | — |
| Ingredients | `ing` | `ingredients` | — | — |
| Cooking Log | `log` | `cooking_log` | — | — |
| Flavor Preferences | `flavor` | `flavor_preferences` | — | — |

### Kitchen's Subdomains (7 groups)

| Subdomain | Primary Table | Related Tables |
|-----------|--------------|---------------|
| inventory | `inventory` | `ingredients` |
| recipes | `recipes` | `recipe_ingredients`, `ingredients` |
| shopping | `shopping_list` | `ingredients` |
| meal_plans | `meal_plans` | `recipes`, `tasks` |
| tasks | `tasks` | `recipes`, `meal_plans` |
| preferences | `preferences` | `flavor_preferences` |
| history | `cooking_log` | — |

### Kitchen's Bypass Modes

| Mode | Handler | Purpose |
|------|---------|---------|
| `cook` | `run_cook_session` | Interactive cooking guidance (skips graph pipeline) |
| `brainstorm` | `run_brainstorm` | Recipe brainstorming (skips graph pipeline) |

---

## Key Files

| File | Lines | Role |
|------|-------|------|
| [src/alfred/domain/base.py](src/alfred/domain/base.py) | 75 | `DomainConfig` composition shim + historical re-exports |
| [src/alfred/domain/context.py](src/alfred/domain/context.py) | 603 | `DomainContext`, EntityDefinition, SubdomainDefinition, CRUDMiddleware, ReadPreprocessResult |
| [src/alfred/domain/agent.py](src/alfred/domain/agent.py) | 598 | `AgentConfig`, ToolDefinition, ToolContext |
| [src/alfred/domain/grades.py](src/alfred/domain/grades.py) | 122 | StripSet, GradeRegistry, grade errors |
| [src/alfred/domain/__init__.py](src/alfred/domain/__init__.py) | 75 | `register_domain()` (validates grades), `get_current_domain()` |
| [src/alfred/db/adapter.py](src/alfred/db/adapter.py) | 53 | DatabaseAdapter protocol |
| [src/alfred/db/__init__.py](src/alfred/db/__init__.py) | 13 | Exports `DatabaseAdapter` protocol |
