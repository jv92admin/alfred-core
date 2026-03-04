# Alfred Architecture Overview

> Entry point for understanding Alfred's technical architecture.

---

## Two-Package Structure

Alfred is split into a core engine and domain packages:

- **`alfred`** (core) — Domain-agnostic orchestration engine: LangGraph pipeline, entity tracking, CRUD execution, prompt assembly, conversation memory
- **`alfred_kitchen`** (domain) — Kitchen-specific implementation: entities, subdomains, prompts, database adapter, CRUD middleware, bypass modes
- **`alfred_fpl`** (domain) — Fantasy Premier League data companion: 11 entities, 6 subdomains, separate Supabase instance

Core never imports any domain. Domains import core freely. See [core-domain-architecture.md](core-domain-architecture.md) for the full protocol.

---

## Pipeline

```
                              ┌─────────────┐
                              │  ACT QUICK  │ ← Single tool call
                              └──────┬──────┘
                                     │
┌────────────┐   quick_mode?   ┌─────▼─────┐   ┌───────────┐
│ UNDERSTAND │───────────────▶│   REPLY   │──▶│ SUMMARIZE │
└─────┬──────┘                 └───────────┘   └───────────┘
      │
      │ !quick_mode
      ▼
┌───────┐   ┌─────────────────┐   ┌───────┐   ┌───────────┐
│ THINK │──▶│    ACT LOOP     │──▶│ REPLY │──▶│ SUMMARIZE │
└───────┘   └─────────────────┘   └───────┘   └───────────┘
```

### Execution Patterns

Think decomposes any request into a chain of steps. Each step follows one of four execution patterns:

| Pattern | What it does | Tools | Side effects |
|---------|-------------|-------|-------------|
| **Read** | Pull data from external sources | `db_read` | None |
| **Analyze** | Reason over data already in context | Domain-configurable (default: none) | None |
| **Generate** | Produce structured artifacts | Domain-configurable (default: none) | None |
| **Write** | Push data to external destinations | `db_create`, `db_update`, `db_delete` | **Yes** |

Act dispatches each step according to its pattern — loading pattern-specific tools, prompts, and context. Reply then synthesizes the full reasoning chain into a user-facing response. The built-in tools are Supabase CRUD. Domains can register additional tools via `DomainConfig.get_custom_tools()` (e.g., sandboxed Python execution for analysis). The pattern abstraction means new data sources, destinations, and computation tools plug in without changing core.

---

## Documentation Index

### Internals (how it works)

| Doc | Covers |
|-----|--------|
| [crud-and-database.md](crud-and-database.md) | CRUD executor, DatabaseAdapter, middleware hooks, filter system, ref translation |
| [sessions-context-entities.md](sessions-context-entities.md) | SessionIdRegistry, entity lifecycle, context builders, conversation memory |
| [pipeline-stages.md](pipeline-stages.md) | Graph nodes, routing, state shape, input/output contracts per stage |
| [prompt-assembly.md](prompt-assembly.md) | Template loading, injection.py composition, domain prompt overrides |

### Architecture (how it's structured)

| Doc | Covers |
|-----|--------|
| [core-domain-architecture.md](core-domain-architecture.md) | Two-package split, DomainConfig protocol (66 methods), registration, import boundary |
| [core-public-api.md](core-public-api.md) | Entry points, capabilities table, extension points, multi-repo extraction path |
| [injection-map.md](injection-map.md) | Every domain knob, dial, and toggle — organized by what it affects (reasoning, UI, capabilities) |
| [domain-implementation-guide.md](domain-implementation-guide.md) | Step-by-step guide to building a new domain (FPL worked example) |

### Testing & Operations

| Doc | Covers |
|-----|--------|
| [testing.md](testing.md) | Test suite structure, coverage map (164 tests), mock strategies, shared infrastructure |
| [capabilities.md](capabilities.md) | User-facing capabilities and API surface |
| [../ROADMAP.md](../ROADMAP.md) | Active work, recently completed, backlog |
