# Core Public API

What `alfred` (core) provides — entry points, capabilities, extension points, and the path to standalone extraction.

---

## 1. Entry Points

### Primary: `run_alfred_streaming()`

[workflow.py:672](src/alfred/graph/workflow.py#L672) — the main entry point for processing user requests with real-time updates.

```python
async def run_alfred_streaming(
    user_message: str,
    user_id: str,
    conversation_id: str | None = None,
    conversation: dict | None = None,
    mode: str = "plan",
    ui_changes: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
```

Yields 11 typed events as the pipeline executes (thinking, step, step_complete, done, etc.). The `done` event contains the final response and updated conversation state.

### Batch: `run_alfred()`

[workflow.py:530](src/alfred/graph/workflow.py#L530) — returns `(response, conversation)` tuple without streaming. Used by CLI and tests.

### Simple: `run_alfred_simple()`

[workflow.py:657](src/alfred/graph/workflow.py#L657) — returns just the response string. For single-turn interactions.

### Registration: `register_domain()`

[domain/__init__.py:29](src/alfred/domain/__init__.py#L29) — registers a `DomainConfig` implementation. Must be called before any entry point.

```python
from alfred.domain import register_domain
register_domain(my_domain)
```

### Graph Construction: `create_alfred_graph()`

[workflow.py:427](src/alfred/graph/workflow.py#L427) — builds the LangGraph `StateGraph`. Called internally by the entry points above. Not typically called by domains directly.

### Substrate: `alfred.context` (state-free assembly seam)

Added in 2.8.0 for external consumers (e.g. MCP servers) that need shaped reads without the LLM pipeline. Importing `alfred.context` never pulls in langgraph/instructor and never requires a registered domain — enforced by subprocess isolation tests ([test_import_isolation.py](tests/core/test_import_isolation.py)).

```python
from alfred.context import (
    # the substrate protocol — the knowledge/shaping half of DomainConfig
    DomainContext,
    # async, state-free entrypoints (no AlfredState, no session, no LLM on any path)
    assemble_entity_context,      # one entity by id, shaped
    assemble_subdomain_read,      # filtered table read, shaped
    ShapedPayload,                # frozen result: header, records, table, count, truncated, grade, schema_version
    SCHEMA_VERSION,               # current payload schema version: "1"
    # identity policies (identity is a policy parameter, not a payload property)
    IdentityPolicy, identity_passthrough, identity_drop_ids,
    # loud typed errors — invalid input never produces a silent empty read
    AssemblyError, FilterValidationError, UnknownEntityTypeError,
    UnknownSubdomainError, TableNotInSubdomainError, RecordNotFoundError,
    # audience grades — domain-declared strip sets; core validates external ⊇ reply at registration
    GRADE_REPLY, GRADE_EXTERNAL, StripSet, GradeRegistry,
    GradeError, GradeRegistryError, UnknownGradeError,
)
```

Both entrypoints take an explicit `DomainContext` (no global state), validate filters and grade before any I/O, and return a `ShapedPayload` (`schema_version` bump policy documented in [context/assembly.py](src/alfred/context/assembly.py)'s module docstring). Richer consumers compose the underlying chain links directly from `alfred.context.assembly` — the entrypoints are thin compositions over that chain, not the chain itself.

---

## 2. Capabilities Table

What core gives a domain for free:

| Capability | Module | What You Get |
|-----------|--------|-------------|
| **LLM pipeline** | `graph/workflow.py` | Understand → Think → Act (loop) → Reply → Summarize with conditional routing, 3 entry paths. Act dispatches each step according to its execution pattern (Read, Analyze, Generate, Write), loading pattern-specific tools, prompts, and context |
| **Entity lifecycle** | `core/id_registry.py` | UUID→human refs (`recipe_1`), detail level tracking, FK enrichment, cross-turn persistence |
| **CRUD execution** | `tools/crud.py` | Filter building (14 operators), ref↔UUID translation, user_id scoping, batch manifests |
| **Conversation memory** | `memory/conversation.py` | Turn history with compression, engagement summaries, context windowing (full vs condensed) |
| **Prompt assembly** | `prompts/injection.py` | 15-section Act prompt builder, quick mode prompts, subdomain guidance injection |
| **Prompt templates** | `prompts/templates/` | 11 structural .md templates (1,635 lines) as fallback when domain doesn't provide full prompts |
| **Mode system** | `core/modes.py` | QUICK/PLAN/CREATE modes with per-mode config (max_steps, skip_think, proposal_required) |
| **Context building** | `context/builders.py` | Think/Act/Understand context assembly from state, entity context tiering |
| **LLM client** | `llm/client.py` | `call_llm()` with structured output via Instructor, model routing by complexity |
| **Model routing** | `llm/model_router.py` | Complexity→model mapping (low→mini, medium→standard, high→premium) |
| **Observability** | `observability/` | LangSmith tracing, session logging, prompt logging |
| **Agent protocol** | `agents/base.py` | `AgentProtocol`, `AgentRouter`, `MultiAgentOrchestrator` (Phase 2.5) |
| **Payload compilation** | `core/payload_compiler.py` | `SubdomainCompiler` protocol, `PayloadCompilerRegistry` for artifact→schema mapping |
| **State model** | `graph/state.py` | `AlfredState` TypedDict with all data models (ThinkStep, ActDecision, BatchManifest, etc.) |
| **Handoff protocol** | `modes/handoff.py` | Bypass mode → graph pipeline handoff with structured summaries |

---

## 3. Extension Points

These are the protocols and hooks a domain implements to customize core behavior:

### DomainConfig (80 members)

[domain/base.py](src/alfred/domain/base.py) — the central protocol, composed since 2.8.0 from two protocols: `DomainContext` ([domain/context.py](src/alfred/domain/context.py) — knowledge & data shaping) and `AgentConfig` ([domain/agent.py](src/alfred/domain/agent.py) — pipeline & LLM concerns). See [core-domain-architecture.md](core-domain-architecture.md) for the full method census.

23 abstract members define what a domain **is** (entities, subdomains, personas). 57 default members provide fallbacks that a domain can progressively override. Substrate-only consumers (shaped reads, no LLM pipeline) can implement `DomainContext` alone.

### DatabaseAdapter

[db/adapter.py:23](src/alfred/db/adapter.py#L23) — how core accesses the database.

```python
class DatabaseAdapter(Protocol):
    def table(self, name: str) -> Any      # query builder
    def rpc(self, function_name: str, params: dict) -> Any
```

Returned by `DomainConfig.get_db_adapter()`. Core's CRUD executor calls `adapter.table(name).select(...).eq(...).execute()` — the query builder must support PostgREST-style fluent methods.

### CRUDMiddleware

[domain/context.py](src/alfred/domain/context.py) — optional query intelligence layer (lives on the `DomainContext` side of the split).

```python
class CRUDMiddleware:
    async def pre_read(self, params, user_id) -> ReadPreprocessResult
    async def post_read(self, records, table, user_id) -> list[dict]
    async def pre_write(self, table, records) -> list[dict]
    def deduplicate_batch(self, table, records) -> list[dict]
```

Returned by `DomainConfig.get_crud_middleware()`. `pre_read` and `pre_write` fire before database operations; `post_read` fires after the query returns. Default: pass-through (no middleware).

### SubdomainCompiler

[core/payload_compiler.py:50](src/alfred/core/payload_compiler.py#L50) — maps generated artifacts to schema-ready payloads.

```python
class SubdomainCompiler(ABC):
    @property
    def subdomain(self) -> str: ...
    def compile(self, artifacts, context) -> CompilationResult: ...
```

Returned by `DomainConfig.get_payload_compilers()`. Runs between Generate and Write steps. Default: no compilers (artifacts pass through raw).

### AgentProtocol

[agents/base.py:50](src/alfred/agents/base.py#L50) — for multi-agent routing (Phase 2.5, not yet active).

```python
class AgentProtocol(ABC):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def capabilities(self) -> list[str]: ...
    async def process(self, state: AgentState) -> dict: ...
    async def process_streaming(self, state: AgentState) -> AsyncIterator[StreamEvent]: ...
```

Returned by `DomainConfig.agents`. Currently unused — kitchen runs in single-agent mode.

### Bypass Modes

`DomainConfig.bypass_modes` — dict mapping mode name to handler function. These skip the LangGraph pipeline entirely. Kitchen registers `cook` and `brainstorm` modes.

The handler function receives the user message and conversation state, yields streaming events directly, and produces a handoff summary for the pipeline to process when the mode completes.

---

## 4. What Domain Does NOT Touch

These are internal to core — domains never import or interact with them directly:

| Component | Why Hands-Off |
|-----------|--------------|
| Graph wiring (`workflow.py:427-512`) | Node connections, conditional edges, routing logic — all domain-agnostic |
| LLM client internals (`llm/client.py`) | `call_llm()` handles model selection, Instructor, retries — domains just call it |
| SessionIdRegistry internals (`core/id_registry.py`) | Ref allocation, detail tracking, FK enrichment — driven by `EntityDefinition` config |
| Conversation compression (`memory/conversation.py`) | Turn summarization, context windowing — generic text operations |
| Prompt template loading/caching | Module-level caches in each node — transparent to domains |
| Entity context tiering | Active/long-term/generated classification — driven by recency and `EntityDefinition` |
| Batch manifest tracking | Per-item status in Write steps — core handles the lifecycle |
| Step execution loop (`act_node()`) | Tool call → execute → cache → loop mechanics — domain provides the intelligence via prompts |
| Filter application (`apply_filter()`) | 12 PostgREST operators — domain provides filters via CRUD middleware |

---

## 5. Packaging

Core is a standalone PyPI package: `pip install alfredagain`, imported as `import alfred`. The wheel builds **only** `src/alfred` — domain packages (kitchen, FPL, …) live in their own repos and depend on `alfredagain`:

```toml
[project]
name = "alfredagain"

[tool.hatch.build.targets.wheel]
packages = ["src/alfred"]
```

**Dependencies** (core only — no Supabase, no FastAPI):

```toml
dependencies = [
    "langgraph>=0.2.0",
    "langchain-openai>=0.2.0",
    "langsmith>=0.1.0",
    "instructor>=1.4.0",
    "openai>=1.50.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]
```

**Not in core:** `supabase`, `fastapi`, `uvicorn`, `recipe-scrapers`, `httpx`, `bcrypt`, `typer`, `rich`

### Import Boundary

Core has zero imports from any domain package. All backwards-compat shims were removed during the FPL domain build.

```bash
# Returns zero hits — core is fully domain-agnostic:
grep -rn "from alfred_kitchen" src/alfred/ --include="*.py"
grep -rn "from alfred_fpl" src/alfred/ --include="*.py"
```

- `db/__init__.py` exports only `DatabaseAdapter` — no `get_client` shim
- `config.py` exports only `CoreSettings`, `get_core_settings()`, `core_settings` — no domain settings shim
- `tools/schema.py` routes through `get_current_domain()` — clean indirection via `DomainConfig` (the legacy module-level constant aliases were removed in 2.8.0)
- `alfred.context` imports no langgraph/instructor and needs no registered domain (subprocess-enforced)

---

## Key Files

| File | Lines | Role |
|------|-------|------|
| [src/alfred/graph/workflow.py](src/alfred/graph/workflow.py) | 875 | Entry points: `run_alfred_streaming()`, `run_alfred()`, `create_alfred_graph()` |
| [src/alfred/domain/base.py](src/alfred/domain/base.py) | 75 | DomainConfig composition shim (`DomainContext` + `AgentConfig`) + re-exports |
| [src/alfred/domain/context.py](src/alfred/domain/context.py) | 603 | DomainContext protocol (knowledge & shaping) + CRUDMiddleware |
| [src/alfred/domain/agent.py](src/alfred/domain/agent.py) | 598 | AgentConfig protocol (pipeline & LLM) + ToolDefinition/ToolContext |
| [src/alfred/domain/grades.py](src/alfred/domain/grades.py) | 122 | StripSet, GradeRegistry, grade errors |
| [src/alfred/context/assembly.py](src/alfred/context/assembly.py) | 420 | State-free entrypoints, ShapedPayload, chain links, identity policies |
| [src/alfred/domain/__init__.py](src/alfred/domain/__init__.py) | 75 | `register_domain()` (validates grades), `get_current_domain()` |
| [src/alfred/db/adapter.py](src/alfred/db/adapter.py) | 53 | DatabaseAdapter protocol |
| [src/alfred/core/payload_compiler.py](src/alfred/core/payload_compiler.py) | 174 | SubdomainCompiler, PayloadCompilerRegistry |
| [src/alfred/agents/base.py](src/alfred/agents/base.py) | 250 | AgentProtocol, AgentRouter, MultiAgentOrchestrator |
| [pyproject.toml](pyproject.toml) | — | Build config (wheel = `src/alfred` only) |
