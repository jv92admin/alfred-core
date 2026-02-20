# Domain Implementation Guide

Step-by-step guide to creating a new domain for Alfred's orchestration engine. Uses the FPL (Fantasy Premier League) domain as a worked example — FPL is a real, implemented domain that validated this guide.

---

## 1. Prerequisites

Before implementing a domain, you need:

| Prerequisite | Example (FPL) |
|-------------|---------------|
| **Entity list** | Players, teams, transfers, squads, gameweeks |
| **Database** | Supabase project with tables for each entity |
| **Subdomain grouping** | squad management, transfers, analysis, gameweeks |
| **At least one persona** | "You are an FPL advisor..." per subdomain/step_type |
| **Basic examples** | Example CRUD interactions per subdomain |

You do NOT need: custom CRUD middleware, bypass modes, payload compilers, or full prompt replacement content. These are optional and can be added later.

---

## 2. Scaffold the Package

Create the package structure:

```
src/alfred_fpl/
├── __init__.py          # Registration hook
├── config.py            # FPLSettings (extends CoreSettings)
├── domain/
│   ├── __init__.py      # FPLConfig + FPL_DOMAIN singleton
│   ├── schema.py        # Field enums, fallback schemas
│   ├── formatters.py    # Record formatting
│   └── prompts/
│       └── system.md    # "You are Alfred, an FPL advisor..."
├── db/
│   └── client.py        # Supabase client wrapper
└── main.py              # CLI entry point (optional)
```

### Registration Hook

`src/alfred_fpl/__init__.py`:

```python
from alfred.domain import register_domain

def _register():
    from alfred_fpl.domain import FPL_DOMAIN
    register_domain(FPL_DOMAIN)

_register()
```

This mirrors the kitchen pattern. Importing `alfred_fpl` anywhere in your app registers the domain.

---

## 3. Entity Definitions

Define your entities using `EntityDefinition` (see `alfred.domain.base.EntityDefinition`):

```python
from alfred.domain.base import EntityDefinition

FPL_ENTITIES = {
    "players": EntityDefinition(
        type_name="player",          # Refs: player_1, player_2, ...
        table="players",
        primary_field="web_name",    # Display name
        complexity="high",           # Think node prioritizes
        label_fields=["web_name"],
        detail_tracking=True,        # Track summary vs full reads
    ),
    "teams": EntityDefinition(
        type_name="team",
        table="teams",
        primary_field="name",
    ),
    "transfers": EntityDefinition(
        type_name="transfer",
        table="transfers",
        primary_field="player_id",
        fk_fields=["player_id", "team_id"],
        complexity="medium",
        label_fields=["player_id"],   # FK-based — enriched by registry
    ),
    "squads": EntityDefinition(
        type_name="squad",
        table="squad_selections",
        primary_field="gameweek",
        fk_fields=["player_id"],
        label_fields=["gameweek"],
    ),
    "gameweeks": EntityDefinition(
        type_name="gw",
        table="gameweeks",
        primary_field="number",
        label_fields=["number"],
    ),
}
```

### Key Fields

| Field | What It Controls |
|-------|-----------------|
| `type_name` | Ref prefix — `"player"` produces `player_1`, `player_2` |
| `table` | Database table name — used by CRUD executor |
| `primary_field` | Default display field for labels |
| `fk_fields` | Foreign keys — used for ref↔UUID translation and FK enrichment |
| `complexity` | Think node hint: `"high"` = stronger model, `"medium"` = standard, `None` = basic |
| `nested_relations` | Auto-include in reads (e.g., `["squad_players"]`) |
| `detail_tracking` | Track whether entity was read as summary or full detail |
| `label_fields` | Fields used to compute human-readable labels |

### Which Tables Need EntityDefs?

**All tables with FK columns need EntityDefinitions.** There is no lightweight alternative. Core's `_get_fk_fields()` in `id_registry.py` requires an EntityDef to know which fields are FKs. If a table has FK columns and you want ref translation, it needs an EntityDef.

Tables with only integer FKs (no UUIDs) and no current need for entity tracking can be excluded — but if you later need to track those records or translate their refs, you'll need to add the EntityDef.

### Reference vs Data Entities

Not all entities are equal in the pipeline. Recognize the distinction:

- **Reference entities** (players, teams, managers, leagues) — cross-turn stable, low volume, worth keeping in context. These are the entities users say "that player" or "the Arsenal one" about.
- **Data entities** (squad rows, gameweek stats, fixture rows) — ephemeral, high volume, should evict aggressively. A squad read can register 15+ entities in one call; these should not persist across many turns.

This distinction doesn't exist in the `EntityDefinition` fields — it lives in `get_entity_recency_window()` and in your prompt content (teach the LLM that data entity refs are ephemeral).

### Label Fields and Label Regression

`label_fields` controls what `compute_entity_label()` uses to build the human-readable label that Think and Act see (e.g., `player_1: Salah`). Be aware of **label regression**: if a read returns a column subset (e.g., middleware headline columns) that doesn't include the label fields, the label can regress to the bare ref (`player_1` instead of `Salah`). The LLM loses the human-readable name, and conversation quality degrades silently.

**Rule:** Any column subsetting by middleware must preserve the fields used in `compute_entity_label()`.

### `detail_tracking`

Use `detail_tracking=True` only on entities where summary vs full is a real distinction. For example, a player search returns headline columns (name, position, price), while a detail view adds form, fixture history, and ICT index. Think sees `[read:summary]` vs `[read:full]` and plans accordingly — it won't suggest a redundant full read if the entity was already read in full.

### Entities Without a Natural Primary Field

Some entities represent relationships, not things. A `manager_links` row (mapping a user UUID to an FPL integer ID) has no natural name — its identity is the relationship itself. Override `compute_entity_label_from_fks()` to build composite labels from FK targets:

```python
def compute_entity_label_from_fks(self, record, entity_type, ref, registry_data):
    if entity_type == "fixture":
        home = registry_data.get(record.get("team_h_id"), {}).get("label", "")
        away = registry_data.get(record.get("team_a_id"), {}).get("label", "")
        if home and away:
            return f"{home} vs {away}"
    return None  # Fall through to standard label logic
```

Default is no-op (returns `None`). Kitchen doesn't need it because all Kitchen entities have natural names.

---

## 4. Subdomain Definitions

Group tables into logical subdomains using `SubdomainDefinition` (see `alfred.domain.base.SubdomainDefinition`):

```python
from alfred.domain.base import SubdomainDefinition

FPL_SUBDOMAINS = {
    "squad": SubdomainDefinition(
        name="squad",
        primary_table="squad_selections",
        related_tables=["players", "teams"],
        description="Squad management. Select 15 players within budget.",
    ),
    "transfers": SubdomainDefinition(
        name="transfers",
        primary_table="transfers",
        related_tables=["players", "teams"],
        description="Transfer operations. Buy/sell players, manage free transfers.",
    ),
    "analysis": SubdomainDefinition(
        name="analysis",
        primary_table="players",
        related_tables=["teams", "gameweeks"],
        description="Player and team analysis. Stats, fixtures, form.",
    ),
    "gameweeks": SubdomainDefinition(
        name="gameweeks",
        primary_table="gameweeks",
        related_tables=["squad_selections"],
        description="Gameweek planning. Captaincy, bench, chip usage.",
    ),
}
```

The `description` field is injected into Think prompts — it helps the LLM understand what each subdomain handles.

---

## 5. Implement DomainConfig

Create `FPLConfig` implementing all 23 abstract methods. Start with the required ones and use defaults for everything else.

```python
# src/alfred_fpl/domain/__init__.py

from typing import Any, Callable
from alfred.domain.base import DomainConfig, EntityDefinition, SubdomainDefinition


class FPLConfig(DomainConfig):

    # === Core Properties (3 abstract) ===

    @property
    def name(self) -> str:
        return "fpl"

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        return FPL_ENTITIES  # defined above

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        return FPL_SUBDOMAINS  # defined above

    # === Prompt/Persona (2 abstract) ===

    def get_persona(self, subdomain: str, step_type: str) -> str:
        personas = {
            "squad": "You are an FPL squad advisor. Focus on value picks and team balance.",
            "transfers": "You are an FPL transfer expert. Consider price changes and fixtures.",
            "analysis": "You are an FPL data analyst. Use stats, form, and fixtures.",
            "gameweeks": "You are an FPL gameweek planner. Optimize captaincy and bench.",
        }
        return personas.get(subdomain, "You are an FPL advisor.")

    def get_examples(self, subdomain: str, step_type: str,
                     step_description: str = "", prev_subdomain: str | None = None) -> str:
        # Start with minimal examples, expand as needed
        if step_type == "read" and subdomain == "squad":
            return '''## Examples
- Read current squad: `{"tool": "db_read", "params": {"table": "squad_selections", "filters": [{"field": "gameweek", "op": "eq", "value": 25}]}}`'''
        return ""

    # === Schema/FK (11 abstract) ===

    def get_table_format(self, table: str) -> dict[str, Any]:
        return {}  # Start with no custom formatting

    def get_empty_response(self, subdomain: str) -> str:
        return {
            "squad": "No squad selection found for this gameweek.",
            "transfers": "No transfers recorded.",
            "analysis": "No player data found.",
            "gameweeks": "No gameweek data available.",
        }.get(subdomain, "No data found.")

    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        # UUID FKs ONLY. Integer FKs cause silent failure —
        # core does WHERE id IN (values) on a UUID column.
        # For integer FKs, use post_read middleware instead.
        return {
            "player_id": ("players", "web_name"),
            "team_id": ("teams", "name"),
        }

    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        # Values MUST be strings. Core does ', '.join(values) —
        # integer or boolean values cause TypeError.
        # Use "0", "1", "true", "false" for non-string types.
        return {
            "squad": {"position": ["GKP", "DEF", "MID", "FWD"]},
            "analysis": {"position": ["GKP", "DEF", "MID", "FWD"]},
        }

    def get_semantic_notes(self) -> dict[str, str]:
        # Keyed by SUBDOMAIN name, not topic. Core does
        # get_semantic_notes().get(subdomain, "") — direct lookup.
        return {
            "squad": "Squad has exactly 15 players: 2 GKP, 5 DEF, 5 MID, 3 FWD",
            "transfers": "Free transfers reset each gameweek. Hits cost 4 points.",
        }

    def get_fallback_schemas(self) -> dict[str, str]:
        # NOT a dead stub. This is LOAD-BEARING if your Supabase instance
        # doesn't have the get_table_columns RPC function.
        # Without it, Act prompts show "Schema unavailable" for every table
        # and the LLM guesses column names — causing most queries to fail.
        # See Section 6 for the RPC setup choice.
        return {}  # Start with {}; add real schemas if DB introspection fails

    def get_scope_config(self) -> dict[str, dict]:
        return {
            "squad": {"can_access": ["analysis"]},
            "transfers": {"can_access": ["squad", "analysis"]},
        }

    def get_user_owned_tables(self) -> set[str]:
        return {"squad_selections", "transfers"}

    def get_uuid_fields(self) -> set[str]:
        return {"player_id", "team_id", "gameweek_id"}

    def get_subdomain_registry(self) -> dict[str, dict]:
        return {
            name: {"tables": [sd.primary_table] + sd.related_tables}
            for name, sd in FPL_SUBDOMAINS.items()
        }

    def get_subdomain_examples(self) -> dict[str, str]:
        # Must return dict[str, str], not dict[str, list[str]].
        # Core does parts.append(examples) where examples is a string.
        return {
            "squad": '## Example\nUser: "show my squad"\nAction: db_read on squad_selections\nFilters: gameweek eq <current>',
            "transfers": '## Example\nUser: "buy Salah"\nAction: db_read on players, then db_create on transfers',
            "analysis": '## Example\nUser: "compare strikers"\nAction: db_read on players with position filter',
        }

    # === Entity Processing (4 abstract) ===

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        if "web_name" in artifact or "position" in artifact:
            return "player"
        if "gameweek" in artifact and "player_id" in artifact:
            return "squad"
        return "transfer"

    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        if entity_type == "player":
            return record.get("web_name") or ref
        if entity_type == "team":
            return record.get("name") or ref
        if entity_type == "transfer":
            return f"Transfer {ref}"
        return record.get("name") or record.get("title") or ref

    def get_subdomain_aliases(self) -> dict[str, str]:
        return {
            "team": "squad",
            "my team": "squad",
            "buy": "transfers",
            "sell": "transfers",
            "stats": "analysis",
            "fixtures": "analysis",
            "captain": "gameweeks",
            "bench": "gameweeks",
        }

    def get_subdomain_formatters(self) -> dict[str, Callable]:
        return {}  # Start with no custom formatters — use generic

    # === Mode/Agent (2 abstract) ===

    @property
    def bypass_modes(self) -> dict[str, type]:
        return {}  # No bypass modes initially

    @property
    def default_agent(self) -> str:
        return "main"

    # === Handoff (1 abstract) ===

    def get_handoff_result_model(self) -> type:
        from alfred.modes.handoff import HandoffResult
        return HandoffResult  # Use base model — no domain-specific fields

    # === Database (1 abstract) ===

    def get_db_adapter(self):
        from alfred_fpl.db.client import get_client
        return get_client()


# Singleton
FPL_DOMAIN = FPLConfig()
```

### What You Get for Free

By implementing just these 23 methods, core provides:

- Full Understand → Think → Act → Reply → Summarize pipeline
- Entity refs: `player_1`, `team_3`, `transfer_2` (auto-generated from `type_name`)
- FK enrichment: `player_id: "abc-123"` → `player_id: "abc-123" (Salah)` in prompts
- CRUD execution with ref↔UUID translation
- Mode system (QUICK/PLAN/CREATE)
- Conversation memory with compression
- Prompt assembly with core templates as fallback

### Behavioral Contracts

Several DomainConfig methods have implicit contracts that aren't obvious from their signatures:

| Method | Contract |
|--------|----------|
| `get_fk_enrich_map()` | **UUID FKs only.** Including integer FKs causes core to attempt `WHERE id IN (integers)` on a UUID column — silent failure, no enrichment, no error. Use `post_read` middleware for integer FK enrichment instead. |
| `get_field_enums()` | **Values must be strings.** Core does `', '.join(values)`. Integer or boolean values cause `TypeError`. Use `"0"`, `"true"` etc. |
| `get_semantic_notes()` | **Keyed by subdomain name.** Core does `.get(subdomain, "")` — direct lookup. Don't key by topic. |
| `get_subdomain_examples()` | **Returns `dict[str, str]`**, not `dict[str, list[str]]`. Core does `parts.append(examples)` where `examples` is a single string. |
| `get_fallback_schemas()` | **Load-bearing if no RPC.** Core calls a `get_table_columns` RPC to discover schemas. If the RPC doesn't exist in your Supabase, every table shows "Schema unavailable" in Act prompts. Provide real fallback schemas with column names and types. |
| `compute_entity_label()` | **Never downgrade a real label to a bare ref.** Core calls this on re-reads with column subsets. If the label fields are missing from the result, return the existing label (or `ref`) — not an empty string. |
| `table_to_type` / `type_to_table` | **Computed properties**, rebuilt from `self.entities` on every access. Not cached. The fallback for `table_to_type` is `table.rstrip("s")` — works for regular plurals only. |

---

## 6. Database Adapter

Implement the `DatabaseAdapter` protocol (see `alfred.db.adapter.DatabaseAdapter`):

```python
# src/alfred_fpl/db/client.py

from supabase import create_client

_client = None

def get_client():
    """Return Supabase client (matches DatabaseAdapter protocol)."""
    global _client
    if _client is None:
        from alfred_fpl.config import settings
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client
```

The Supabase client already satisfies `DatabaseAdapter` — it has `.table()` and `.rpc()` methods. No wrapper needed.

### Supabase Expectations

Core's CRUD executor assumes your database follows these conventions:

| Requirement | Why |
|-------------|-----|
| UUID `id` primary key on every table | `translate_read_output` uses `id` for entity registration. Missing `id` causes `UnboundLocalError`. |
| `user_id` column on user-owned tables | CRUD auto-scopes queries by `user_id`. Tables listed in `get_user_owned_tables()` must have this column. |
| RLS policies enabled | All data access goes through the authenticated Supabase client. Never use raw DB access or service role keys in application code. |

### Schema Discovery: RPC vs Fallback Schemas

Core calls a Supabase RPC function `get_table_columns` to discover table schemas at runtime. This function only exists if you create it in your Supabase instance. You have two options:

**Option A: Create the RPC** (Kitchen's approach). Add a PostgreSQL function that returns column metadata. `get_fallback_schemas()` can return `{}`.

**Option B: Use fallback schemas** (FPL's approach). Skip the RPC and implement `get_fallback_schemas()` with real column definitions for every table in every subdomain. This is load-bearing — without either the RPC or fallback schemas, Act prompts show "Schema unavailable" and the LLM guesses column names.

FPL uses Option B because creating the RPC requires Supabase admin access and the fallback approach is simpler for read-heavy domains with stable schemas.

### Auth / Request Context

Copy `request_context.py` from kitchen or FPL into your domain package. This module manages context variables (`access_token`, `user_id`) that flow through the pipeline. Use unique context variable names to avoid collision if multiple domains are loaded:

```python
# Kitchen uses: "access_token", "user_id"
# FPL uses: "fpl_access_token", "fpl_user_id"
```

Do NOT import request context from another domain — that creates a cross-domain dependency. The file is pure context variable machinery (6 functions, no domain logic). Copy and rename.

### Environment Config

Use a dual `.env` pattern when your domain has its own Supabase instance but shares API keys (e.g., OpenAI) with other domains:

```python
class FPLSettings(CoreSettings):
    model_config = SettingsConfigDict(
        env_file=("fpl/.env", ".env"),  # FPL-specific vars first, shared vars as fallback
    )
```

FPL-specific variables (Supabase URL, Supabase key) come from `fpl/.env`. Shared variables (OpenAI key, LangSmith key) come from the root `.env`.

---

## 7. CRUD Middleware (Optional)

If your domain needs query intelligence beyond raw CRUD, implement `CRUDMiddleware` (see `alfred.domain.base.CRUDMiddleware`):

```python
from alfred.domain.base import CRUDMiddleware, ReadPreprocessResult

class FPLCRUDMiddleware(CRUDMiddleware):

    async def pre_read(self, params, user_id) -> ReadPreprocessResult:
        # Example: auto-include current gameweek for squad reads
        if params.table == "squad_selections" and not any(
            f.field == "gameweek" for f in (params.filters or [])
        ):
            # Add current gameweek filter
            from alfred_fpl.db.client import get_current_gameweek
            gw = await get_current_gameweek()
            params.filters = (params.filters or []) + [
                FilterClause(field="gameweek", op="eq", value=gw)
            ]
        return ReadPreprocessResult(params=params)
```

Then wire it in `FPLConfig`:

```python
def get_crud_middleware(self):
    return FPLCRUDMiddleware()
```

### `post_read` Hook

If your domain needs to transform results after a query (e.g., enrich integer FKs with names):

```python
class FPLCRUDMiddleware(CRUDMiddleware):

    async def post_read(self, records: list[dict], table: str, user_id: str) -> list[dict]:
        # Example: add manager name from integer FK
        if table == "squads" and records:
            for r in records:
                r["manager_name"] = self._lookup_manager_name(r.get("manager_id"))
        return records
```

The default `post_read` is a pass-through (returns records unchanged). Called in `crud.py` after query execution, before results are returned to the pipeline.

### Stateful Middleware (Singleton Pattern)

If your middleware holds state across CRUD calls (e.g., bridge dicts mapping UUIDs to integer IDs), cache the instance:

```python
class FPLConfig(DomainConfig):
    _middleware = None

    def get_crud_middleware(self):
        if self._middleware is None:
            self._middleware = FPLCRUDMiddleware()
        return self._middleware
```

Core calls `get_crud_middleware()` once per CRUD operation (not per session) — `crud.py:501` does `_get_domain().get_crud_middleware()` inside `execute_crud()`. Without caching, stateful middleware loses its state between calls. Kitchen's stateless middleware masks this entirely — the issue only surfaces with stateful middleware.

### Middleware Behavioral Contracts

These rules were discovered during the FPL build and apply to all domains:

**`pre_read` receives UUIDs, not refs.** Core's `_translate_input_params()` fires *before* `execute_crud()` passes params to middleware. By the time `pre_read` sees a filter, `mgr_3` has already been translated to a UUID. If your domain has integer FKs, the translation chain is: ref → UUID (registry) → integer (middleware). Two stages, two different systems.

**Default filter injection belongs in `pre_read`.** "If no `manager_id` filter on a manager-scoped table, auto-inject the primary manager" is middleware logic, not prompt engineering. The LLM shouldn't need to know about default scoping — middleware handles it transparently.

**Default limits belong in `pre_read` too.** Tables that can return hundreds of rows need a default `limit` injected unless the LLM explicitly requested more. This protects against context window blowout from large result sets.

**Null filter stripping.** The LLM sometimes passes `{"field": "manager_id", "op": "=", "value": null}` when it expects middleware to fill in the value. The null reaches the database as the string `"None"` and causes type errors. Strip filters where `value is None` before processing — this restores the "no filter present" state that triggers auto-injection.

**`post_read` is for output-side enrichment.** Use it when your domain has FK types that core's UUID-based enrichment can't handle. FPL uses it to inject `manager_name` from a bridge dict into results for tables with integer `manager_id` columns. Core's FK enrichment pipeline (`_enrich_lazy_registrations`) works exclusively with UUIDs — integer FKs need `post_read` or denormalized columns.

### FK Enrichment: Two Systems

Core has two completely different FK enrichment paths. Understanding the difference prevents silent bugs:

| System | Handles | How It Works | Path |
|--------|---------|-------------|------|
| **Registry enrichment** | UUID FKs | `get_fk_enrich_map()` → `WHERE id IN (uuids)` → fetch labels from target table | `_enrich_lazy_registrations()` → `apply_enrichment()` |
| **Middleware enrichment** | Integer FKs | `post_read()` → domain-specific lookup → inject names into records | `CRUDMiddleware.post_read()` |

**Enrichment is two-phase.** Phase 1: `translate_read_output()` assigns refs and queues FK UUIDs for enrichment. Phase 2: `apply_enrichment()` resolves the queue by fetching names from target tables. Testing only phase 1 gives you refs with no human-readable labels. Harness tests must simulate both phases.

**Enrichment is output-side, translation is input-side.** When a user says "show player_3's stats", the ref is *translated* to a UUID (input-side, `_translate_input_params()`). When results come back with a `team_id` UUID, that UUID is *enriched* with the team name (output-side, `_enrich_lazy_registrations()`). Different paths, different code.

---

## 7b. Optional Configuration Methods

These methods have sensible defaults. Override only when your domain needs different behavior.

### Entity Recency Window

Controls how many turns an entity stays "recent" (automatically included in Think/Act context):

```python
def get_entity_recency_window(self) -> int:
    return 1  # FPL: evict data refs faster (default: 2)
```

### FK Field Aliases

Maps non-standard FK field names to their standard equivalents for ref resolution:

```python
def get_fk_field_aliases(self) -> dict[str, str]:
    return {"parent_recipe_id": "recipe_id"}  # Kitchen example
```

### Tool-Enabled Step Types

Controls which step types get CRUD tool access (schema, db_read, db_create, etc.) in Act prompts:

```python
def get_tool_enabled_step_types(self) -> set[str]:
    return {"read", "write", "analyze"}  # Default: {"read", "write"}
```

Default: `{"read", "write"}` — only read/write steps can make database calls. Override to include `"analyze"` if your domain needs mid-analysis data fetching (e.g., pulling additional stats during a comparison), or `"generate"` if content generation needs live data.

When a step type is tool-enabled, its Act prompt includes `crud.md` (tool reference), database schema, current step tool results, and the full tool_call + step_complete decision template. The `step_complete` handler is unchanged — for analyze steps, `decision.data` (the LLM's analysis output) flows downstream regardless of whether tool calls happened during the step.

### Custom Tools

Register domain-specific tools alongside built-in CRUD via `get_custom_tools()`. Custom tools are dispatched by Act's tool_call handler — core routes by name, the domain owns the handler.

```python
from alfred.domain.base import ToolDefinition, ToolContext

def get_custom_tools(self) -> dict[str, ToolDefinition]:
    return {
        "run_python": ToolDefinition(
            name="run_python",
            description="Execute sandboxed Python on DataFrames from prior steps",
            params_schema="`code` (str): Python code to execute, `datasets` (list[str]): step refs to load",
            handler=self._run_python,
        ),
        "render_chart": ToolDefinition(
            name="render_chart",
            description="Render a matplotlib chart headlessly to PNG",
            params_schema="`code` (str): matplotlib code, `title` (str): chart title",
            handler=self._render_chart,
        ),
    }
```

The handler signature is `async (params: dict, user_id: str, context: ToolContext) -> Any`. `ToolContext` gives the handler access to the session registry (for ref↔UUID translation), prior step results (for DataFrame lookup), and the full pipeline state.

Custom tools skip CRUD-specific logic (param validation, delete cleanup, batch manifests). Error handling: return a dict for soft failure (LLM retries within `MAX_TOOL_CALLS_PER_STEP=3`), raise an exception for hard failure (→ `BlockedAction`, step terminates).

Custom tool definitions are injected into Act prompts as a "Domain Tools Reference" table when tools are enabled for the step type. `get_tool_enabled_step_types()` controls WHEN tools appear, `get_custom_tools()` controls WHICH additional tools appear — the two axes are orthogonal.

### Prompt Log Adapter

Returns a DB client for prompt logging, or `None` to disable DB logging:

```python
def get_prompt_log_adapter(self):
    from alfred_fpl.db.client import get_client
    return get_client()  # Only if your DB has a prompt_logs table
```

Default: `None` (DB logging disabled, file logging still works with `ALFRED_LOG_PROMPTS=1`). File-based logging is the recommended starting point — it requires no database setup and produces full prompt logs for debugging.

### Known Limitation: FILTER_SCHEMA Kitchen Content

Core's `FILTER_SCHEMA` constant (`tools/schema.py:288-314`) includes Kitchen-specific `similar` operator docs and `_semantic` filter examples about recipe queries. This content appears in every domain's Act prompts. Your users will see recipe-oriented semantic search docs in their prompts. Not a blocker — provide strong domain-specific examples in `get_examples()` to overpower the generic content. A future core change will make this domain-configurable.

---

## 8. Prompts

### Minimum: System Prompt

Create `src/alfred_fpl/domain/prompts/system.md`:

```markdown
You are Alfred, a Fantasy Premier League assistant.

You help managers make smart FPL decisions: squad selection, transfers,
captaincy, chip usage, and player analysis.

You have access to player stats, fixture data, and the manager's squad.
```

Wire it in `FPLConfig`:

```python
def get_system_prompt(self) -> str:
    path = Path(__file__).parent / "prompts" / "system.md"
    return path.read_text(encoding="utf-8")
```

### Progressive Enhancement

Start with core templates as fallback (they work generically). Override as you tune prompts:

| Priority | Method | What It Does |
|----------|--------|-------------|
| 1st | `get_system_prompt()` | Domain identity |
| 2nd | `get_persona()` + `get_examples()` | Per-subdomain guidance in Act prompts |
| 3rd | `get_think_prompt_content()` | Full Think prompt with FPL-specific planning examples |
| 4th | `get_act_prompt_content(step_type)` | Full Act prompt per step type with FPL examples |
| 5th | `get_reply_prompt_content()` | Reply formatting rules (stat tables, squad displays) |
| 6th | `get_understand_prompt_content()` | Reference resolution patterns for FPL entities |

Each override replaces the core template entirely for that node. See [prompt-assembly.md](prompt-assembly.md) for the full fallback chain.

### Prompt Design Lessons

These patterns were discovered across both Kitchen and FPL:

**Entity volume drives prompt design.** Kitchen has ~10-30 entities in context at any time. FPL can have 50+ — a single squad read registers 15 squad rows, each with player and team FKs (45 entities in one read). The active entities block that Think and Act see grows proportionally. Tune `get_entity_recency_window()` to control how fast data entities evict from context.

**Two entity tiers in prompts.** Your prompt content should teach the LLM that data table refs (`squad_1`, `pgw_1`, `fix_1`) are ephemeral — demote them if the user hasn't referenced a specific one. Reference entity refs (`player_1`, `team_1`, `mgr_1`) are cross-turn stable and worth keeping. This tiering isn't in the protocol — it's prompt engineering that accounts for the entity lifecycle.

**Personas shape step behavior, not just tone.** A persona for `act/read` should emphasize filter construction and table selection. A persona for `act/analyze` should emphasize data interpretation and domain rules. The persona isn't just "you are an FPL expert" — it's context-specific: "you are building a CRUD query" vs "you are interpreting statistical data."

**Examples must show the exact output format.** The LLM doesn't learn from description alone. Each execution pattern (read, analyze, generate, write) needs at least one worked example showing the exact JSON or markdown structure expected. A concrete example of a 3-step plan for "compare midfielders" teaches more than any generic instruction.

**Live chat runs are the last-mile eval.** Unit tests validate structure. Live runs validate prompt *behavior* — do personas sound right? Are examples guiding the LLM toward good plans? Does reply formatting feel natural? Use `ALFRED_LOG_PROMPTS=1` for file-based prompt logs that capture exactly what each node sees. This feedback loop (run → observe → tune prompt → run again) is where prompt quality actually improves.

---

## 9. Bypass Modes (Optional)

If your domain has interactive modes that skip the pipeline (like kitchen's cook mode):

```python
# src/alfred_fpl/domain/modes/draft.py

async def run_draft_session(user_message, conversation, user_id):
    """Interactive draft assistant — guides squad building."""
    yield {"type": "chunk", "content": "Let's build your squad..."}
    # ... interactive logic ...
    yield {"type": "done", "response": "Squad complete!", "conversation": conversation}
```

Wire it:

```python
@property
def bypass_modes(self) -> dict[str, type]:
    from alfred_fpl.domain.modes.draft import run_draft_session
    return {"draft": run_draft_session}
```

---

## 10. Testing

### With StubDomainConfig (Core Tests)

Test core behavior without your domain:

```python
from alfred.domain import register_domain
from alfred.domain.base import DomainConfig, EntityDefinition

class StubConfig(DomainConfig):
    # Minimal implementation — 2 entities, 1 subdomain
    ...

register_domain(StubConfig())
```

### With Your Domain (Integration Tests)

```python
import alfred_fpl  # triggers registration

async def test_squad_read():
    from alfred.graph.workflow import run_alfred
    response, conversation = await run_alfred(
        user_message="show my squad",
        user_id="test-user",
    )
    assert "squad" in response.lower() or "player" in response.lower()
```

### What to Test First

| Test | What It Validates |
|------|-------------------|
| Entity registration | `domain.entities` has expected keys, `table_to_type` maps correctly |
| FK enrichment | `get_fk_enrich_map()` returns valid table/column pairs |
| Persona loading | `get_persona("squad", "read")` returns non-empty string |
| CRUD round-trip | `db_read` on a known table returns data with refs |
| Quick mode | "show my squad" → QUICK mode → single CRUD call → formatted response |

---

## Checklist

Steps to go from zero to working domain:

- [ ] Create `src/alfred_{name}/` package
- [ ] Implement `__init__.py` with `_register()` hook
- [ ] Define `EntityDefinition` instances for each entity type
- [ ] Define `SubdomainDefinition` instances for each subdomain group
- [ ] Implement all 23 abstract methods in `DomainConfig`
- [ ] Create `db/client.py` returning a `DatabaseAdapter`-compatible client
- [ ] Create `prompts/system.md` with domain identity
- [ ] Write `get_persona()` for each subdomain
- [ ] Write basic `get_examples()` for common CRUD patterns
- [ ] Register in entry point (`main.py`, `server.py`, or test conftest)
- [ ] Test: entity refs appear correctly (`player_1`, `team_2`)
- [ ] Test: basic CRUD works (read, create)
- [ ] Test: quick mode produces formatted responses

### Optional Enhancements (Add Later)

- [ ] `CRUDMiddleware` with `pre_read`/`post_read` for query intelligence
- [ ] `get_entity_recency_window()` override (default: 2 turns)
- [ ] `get_fk_field_aliases()` for non-standard FK naming
- [ ] `get_prompt_log_adapter()` for DB-based prompt logging
- [ ] Full prompt replacement content (Think, Act, Reply, Understand)
- [ ] `SubdomainCompiler` for artifact→schema mapping
- [ ] Bypass modes for interactive features
- [ ] Custom `format_entity_for_context()` for rich entity display
- [ ] Custom `format_records_for_reply()` for user-facing formatting

---

## 11. Implicit Contracts

These are the hard-won rules that aren't in any method signature. They were discovered during the FPL build — the second domain to use Alfred's core. Kitchen couldn't surface them because it was built simultaneously with core. Every rule below is a pattern that any future domain builder will hit.

### Entity Contracts

| Rule | Why |
|------|-----|
| **Any column subsetting by middleware must preserve `id`.** | `translate_read_output` uses `record["id"]` for entity registration. Missing `id` causes `UnboundLocalError`. If your middleware selects headline columns, always include `id`. |
| **Any column subsetting must preserve label fields.** | If `label_fields=["web_name"]` and your middleware returns a column subset without `web_name`, the label regresses to the bare ref. The LLM loses the human-readable name. |
| **FK-dependent labels require ordering.** | If fixture labels are "Arsenal vs Chelsea" (from FK lookups on `team_h_id`/`team_a_id`), the team entities must be in the registry *before* fixture rows are processed. Usually naturally satisfied by query flow, but a cold-open query may have no teams registered yet. Labels upgrade on the next read that pulls in the FK targets. |
| **All FK-bearing tables need EntityDefs.** | There is no lightweight alternative. `_get_fk_fields()` requires an EntityDef. |

### Middleware Contracts

| Rule | Why |
|------|-----|
| **Middleware is instantiated per CRUD call.** | Core does `_get_domain().get_crud_middleware()` inside `execute_crud()`. Cache the instance if your middleware is stateful. |
| **`pre_read` receives UUIDs, not refs.** | `_translate_input_params()` fires before middleware. The filter value is already a UUID by the time `pre_read` sees it. |
| **FK enrichment is UUID-only.** | `get_fk_enrich_map()` feeds `WHERE id IN (values)` on a UUID column. Including integer FKs causes silent failure — no error, no enrichment. Use `post_read` for integer FK enrichment. |
| **Enrichment is two-phase.** | Phase 1: `translate_read_output()` queues FK UUIDs. Phase 2: `apply_enrichment()` resolves them. Testing only phase 1 gives refs with no labels. |

### Schema Contracts

| Rule | Why |
|------|-----|
| **`get_fallback_schemas()` is required unless the `get_table_columns` RPC exists.** | Without either, Act prompts show "Schema unavailable" for every table. The LLM guesses column names — most queries fail. |
| **Enum values must be strings.** | Core does `', '.join(values)`. Non-string types cause `TypeError`. |
| **Semantic notes are keyed by subdomain.** | Core does `.get(subdomain, "")`. Don't key by topic. |
| **Subdomain examples must be strings, not lists.** | Core does `parts.append(examples)`. |

### Pipeline Contracts

| Rule | Why |
|------|-----|
| **The 2-turn entity recency window is configurable.** | Override `get_entity_recency_window()` if your domain has high-volume reads. FPL uses `1` to evict data entity refs faster. Default: `2`. |
| **`FILTER_SCHEMA` contains Kitchen content.** | Core's filter schema docs include `similar` operator and recipe examples. Your domain's Act prompts inherit this. Provide strong domain-specific examples to overpower it. Open core finding — will be made domain-configurable. |
| **`table_to_type` strips trailing "s".** | The fallback pluralization is `table.rstrip("s")`. Works for "players"→"player" but not irregular plurals. If your tables have irregular plural names, verify the mapping. |

### The Meta-Rule

**If Kitchen doesn't exercise a code path, assume it's untested.** Kitchen was built alongside core. Every edge case Kitchen happens to avoid is an edge case your domain will find first. The rules above are the ones FPL found. Domain #3 will find more.
