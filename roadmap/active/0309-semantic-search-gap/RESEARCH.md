# Research: Semantic Search — Documentation Gap & Crash Path

**Goal:** Make `similar`/`_semantic` a properly documented first-class operator so domain owners are forced to handle it (build it or degrade it), instead of the current state where it's half-advertised and crashes silently.
**Type:** fix
**Date:** 2026-03-09

## Context

The `similar` operator and `_semantic` filter field enable semantic/vector search in the CRUD read path. This is a domain-provided capability — core provides the middleware hook, domains provide embeddings + vector infrastructure.

The problem: the operator is **inconsistently documented** across prompt templates, creating a gap where the LLM may or may not emit `_semantic` filters, and domains without middleware crash at runtime with an unhelpful `ValueError`.

## Function Chain

Full lifecycle of a `_semantic` filter, from prompt to crash-or-success:

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| **Prompt injection** | `get_subdomain_context()` in `tools/schema.py:366` | Assembles filter docs for Act prompt. Calls `_get_filter_schema()` which returns `FILTER_SCHEMA` (includes `similar`) unless domain overrides `get_filter_schema()` | `get_filter_schema()` — can replace entire filter docs |
| **Prompt injection** | `FILTER_SCHEMA` constant in `tools/schema.py:287-314` | Hardcoded markdown table listing all 14 operators including `similar`. Always shown unless domain overrides | None — hardcoded constant |
| **Prompt injection** | `crud.md` template in `prompts/templates/act/crud.md` | Documents 8 operators. **Does NOT include `similar`.** Contradicts `FILTER_SCHEMA` | `get_crud_reference()` — can replace |
| **Prompt injection** | `read.md` template in `prompts/templates/act/read.md` | Read step guide. No mention of semantic search | `get_act_step_template("read")` — can replace |
| **Prompt injection** | `get_semantic_notes()` in `tools/schema.py:384-387` | Appends domain-specific notes (e.g., "pantry = all inventory"). Only appears if domain returns non-empty dict | `get_semantic_notes()` — domain provides |
| **LLM decision** | Act node LLM | Reads filter docs + step description. Chooses `similar` if it seems appropriate. Pure judgment call — no routing logic | None — LLM inference |
| **Param validation** | `_fix_and_validate_tool_params()` in `act.py:1353` | Validates structure. `similar` passes because `FilterClause.op` Literal includes it at `crud.py:46` | None |
| **Input translation** | `_translate_input_params()` in `crud.py:491-493` | Translates refs → UUIDs in filter values. `_semantic` value is natural language, passes through unchanged | None |
| **Middleware pre_read** | `middleware.pre_read()` in `crud.py:164-171` | **Only place `_semantic` can be consumed.** Middleware must: detect `_semantic` filter, run vector search, return `pre_filter_ids`, strip filter from params | `CRUDMiddleware.pre_read()` — domain implements |
| **Filter application** | `apply_filter()` in `crud.py:100-132` | Iterates remaining filters. `similar` has no case match → **`case _:` raises `ValueError`** | None — crashes |
| **Error handling** | Act node `try/except` in `act.py:1363` | Catches `ValueError`. LLM sees error, can retry with `ilike` | None — recovery via LLM retry |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Filter operator docs (FILTER_SCHEMA) | Includes `similar` always | `get_filter_schema()` | **YES** — advertises capability that may not exist |
| Filter operator docs (crud.md) | Does NOT include `similar` | `get_crud_reference()` | **YES** — contradicts FILTER_SCHEMA |
| Read step template (read.md) | No mention of semantic search | `get_act_step_template("read")` | **YES** — should document `similar` as an advanced pattern |
| Semantic notes | Empty dict (no notes shown) | `get_semantic_notes()` | No — correctly empty by default |
| CRUDMiddleware.pre_read() | Pass-through (no-op) | Domain subclass | No — but means `_semantic` isn't consumed |
| apply_filter() crash | `ValueError` on unknown op | None | No — crash is correct behavior (forces domain owner to act) |
| FilterClause.op Literal | Includes `"similar"` | None | No — needs to stay so validation passes before middleware |

## Two Competing Filter Docs

The Act prompt sees **both** of these injected:

1. **`crud.md`** (via step template) — lists 8 operators, stops at `contains`, no `similar`
2. **`FILTER_SCHEMA`** (via `get_subdomain_context()`) — lists 14 operators, includes `similar` with examples

The LLM receives conflicting information about what operators are available.

## Findings

### The design gap is documentation, not code

The code path is actually correct:
- `FilterClause` accepts `similar` (so validation doesn't reject it prematurely)
- `apply_filter()` crashes on unknown ops (so domains without middleware fail loudly)
- `pre_read()` is the correct consumption point (domain-owned)
- The crash forces domain owners to decide: build semantic search or handle the filter

The problem is that `crud.md` and `FILTER_SCHEMA` disagree, and neither `crud.md` nor `read.md` document `similar` — so domain owners building from the templates don't know it exists, and the LLM gets inconsistent guidance.

### Semantic search is inherently domain-owned

Core cannot provide a default implementation because it requires:
- An embedding model (OpenAI, sentence-transformers, etc.)
- Vector storage (pgvector columns, indexes)
- A domain-specific RPC function (e.g., `match_recipes_semantic`)
- Knowledge of which columns to embed

This is infrastructure the domain owner must set up. Core's role is to provide the hook (`pre_read()`) and document the operator.

### The LLM chooses operators by judgment

There is no routing logic that says "use semantic for X, ilike for Y." The LLM reads:
- Think's step description (e.g., "find recipes similar to..." vs "find recipes named...")
- The filter docs (whatever is in the prompt)
- Semantic notes (domain-specific term clarifications)

The operator choice is pure LLM inference at the Act node.

### The crash is the right forcing function

When a domain owner doesn't implement `pre_read()` handling for `_semantic`:
1. LLM emits `_semantic` filter (because `FILTER_SCHEMA` told it about `similar`)
2. `apply_filter()` crashes with `ValueError`
3. Domain owner sees the crash and must decide:
   - **Build it** — implement `pre_read()` with embeddings/vector search
   - **Degrade it** — their `pre_read()` rewrites `_semantic` to `ilike` on a name/title column
   - **Remove it from prompts** — override `get_filter_schema()` to exclude `similar`

Silent stripping in core would hide this decision point. The crash is preferable.

## Open Questions

1. **Should `crud.md` be the single source of truth for operators?** Currently `FILTER_SCHEMA` and `crud.md` both exist and disagree. Should we consolidate?
2. **Should `read.md` have a "Semantic Search" section under Advanced Patterns?** This would make `similar` visible to domain owners reading the templates.
3. **Should we add a `supports_semantic_search` flag to DomainConfig?** This could conditionally include/exclude `similar` from the filter docs — but adds complexity. The override via `get_filter_schema()` already exists.
4. **Is the `FILTER_SCHEMA` constant still needed?** It's only used as the fallback when `get_filter_schema()` returns empty. Could be merged into `crud.md` or made the default return of `get_filter_schema()`.
