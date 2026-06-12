# Research: State-Free Assembly Entrypoints (A3 / E2 / C-5)

**Goal:** `assemble_entity_context` / `assemble_subdomain_read` → `ShapedPayload` in `alfred.context`, as thin compositions over an internal state-free assembly chain, per SEAM_CONTRACT §1–§2.
**Type:** feat
**Date:** 2026-06-12

## Context

This is Track A's keystone: the seam contract's deliverable (ledge v41 Phase 2 swaps its
shim for this import) AND the Compatibility Guardrail's proving ground (three golden
consumer fixtures — S1/S3/S5 — gate the merge). The GROUNDING brief
([0612-a3-grounding/GROUNDING.md](../0612-a3-grounding/GROUNDING.md)) verified the read
path is nearly state-free already; this research resolves its five design problems P1–P5
with code evidence, plus one problem the brief didn't name (F6: async).

## Function Chain

The chain the seam contract specifies, mapped to what exists today:

| Chain link (seam §1 + GROUNDING) | Exists today | File:line | State-free? |
|---|---|---|---|
| adapter read | `db_read()` — resolves adapter via module-global domain | `tools/crud.py:255-361`, global at `:270-271` (`_get_client` → `_get_domain().get_db_adapter()`, `:24-32`) | ❌ global domain (P1) |
| filter application | `apply_filter(query, FilterClause)` — pure function, loud `ValueError` on unknown op | `tools/crud.py:215-247`; `FilterClause` op `Literal` at `:40-49` | ✅ reusable as-is |
| `post_read` middleware | `CRUDMiddleware.post_read(records, table, user_id)` — **`async def`** | `domain/context.py:161-176`; fired at `crud.py:357-359` | ✅ parameter-driven (but async — F6) |
| fk_enrich | `_enrich_lazy_registrations` — mechanics are batch `in_` fetch of names by UUID, but welded to `SessionIdRegistry` queue | `tools/crud.py:758-814`; map from `get_fk_enrich_map()` (`domain/context.py:297-307`) | ❌ reimplement state-free (per GROUNDING §1, straightforward) |
| identity (id ↔ ref/label) | `SessionIdRegistry.translate_read_output(records, table)` — session-welded (counters, turn tracking) | `core/id_registry.py:173-238` | ❌ becomes a policy parameter (P3) |
| strip(grade) | `GradeRegistry.from_context(ctx).strip(records, table, grade)` — pure, loud on unknown grade | `domain/grades.py:84-156` | ✅ A2 shipped it for exactly this slot |
| value shaping / format | `format_record_for_context` returns a **prompt string**; no dict-shaping step exists; `"(not set)"` appears nowhere in `src/` (grep-verified 2026-06-12) | `domain/context.py:637-657` | new code (P2) |
| header | `get_semantic_notes()` → `dict[subdomain → notes]` — per-subdomain, not per-table | `domain/context.py:322-329` | gap (P4) |

Supporting surface:

| Need | Symbol | File:line |
|---|---|---|
| entity_type → table | `DomainContext.type_to_table` property | `domain/context.py:251-259` |
| subdomain → tables | `DomainContext.subdomains` → `SubdomainDefinition(primary_table, related_tables)` | `domain/context.py:69-87, 226-235` |
| adapter protocol | `DatabaseAdapter.table()/.rpc()` (PostgREST fluent) | `db/adapter.py:23-52` |
| middleware handle | `ctx.get_crud_middleware()` (defaulted, may be None) | `domain/context.py:363-380` |
| import isolation gate | forbidden prefixes `langgraph, instructor, alfred.graph, alfred.llm`; fresh-subprocess import of `alfred.context` | `tests/core/test_import_isolation.py:17-22, 45-51` |
| test stubs | `StubDomainConfig` (2 entities, 2 subdomains) + `make_mock_db` (full PostgREST chaining) | `tests/core/conftest.py:35-173, 181-233` |

**Import-cleanliness of the reuse path:** `from alfred.tools.crud import apply_filter,
FilterClause` executes `alfred/tools/__init__.py` first, which also imports
`tools/schema.py` — both are clean (schema.py's only top-level imports are
`time`/`typing`, `schema.py:13-14`; domain access is lazy via `_get_domain`,
`schema.py:25-28`). `AlfredState` lives at `graph/state.py:624` — already a forbidden
prefix, so the existing isolation test mechanically covers E5's "no AlfredState" the
moment the new module is imported from `alfred/context/__init__.py`.

## P1 — db_read parameterization: **thin internal read in the new module** (option 2)

Evidence against the additive-param option: `db_read` is global-coupled at *two* points,
not one — the client (`crud.py:270`) and `get_user_owned_tables()` (`crud.py:272`), so
"add `client=`" actually means "add `ctx=` and fork both resolutions". It also carries
S1-specific behavior the seam chain must NOT have:

- `pre_read` middleware firing (`crud.py:279-286`) — seam §1's chain starts at
  `post_read`; `pre_read` is S1 query intelligence (semantic search, auto-includes).
- `user_id` eq-injection (`crud.py:301-303`) — the seam signatures have **no `user_id`
  parameter**; E3's model is that tenant/user scoping arrives via the ctx's adapter
  configuration (JWT → RLS), per seam §1 constraints. Core must not invent a user_id.
- in-place mutation of `params.columns` (`crud.py:289-290`) and no truncation detection
  (`limit` applied blind, `crud.py:351-352`).

A thin internal `_read_table(adapter, table, clauses, limit_plus_one)` (~25 lines)
reusing `apply_filter` + `FilterClause` verbatim keeps the pipeline path **byte-for-byte
untouched** (Guardrail #3 satisfied by construction, not by care) and gives the seam
read its own legitimate semantics (limit+1, no pre_read, no user_id injection). The
filter machinery — the part worth reusing — IS `apply_filter`/`FilterClause`, and those
are imported, not duplicated. No silent global anywhere: the adapter comes only from
`ctx.get_db_adapter()`, and a source-level conformance test asserts
`get_current_domain` never appears in the new module.

## P2 — Dict value-shaping is a new step; `format_record_for_context` stays off the S2 path

Confirmed exactly as GROUNDING proposed:

- `format_record_for_context` returns a one-line **string** with `id:` interpolation
  (`domain/context.py:649-657`) — structurally wrong for `ShapedPayload.records:
  list[dict]` and would re-leak ids the identity policy dropped. §2 is binding.
- The S2 chain tail is a new pure helper `shape_record_values(record) -> dict`:
  `None → "(not set)"` (new — grep-verified absent from src/), everything else passes
  through. Value *transforms* (cents→dollars, derived display values) are `post_read`
  middleware by the §3 clarification (ledge PM acked 2026-06-11), already applied
  earlier in the chain — so the shaper stays minimal and grade-independent.
- Shaping runs **after** strip, so stripped fields never resurrect as `"(not set)"`.
- `format_record_for_context` remains reachable as an alternative chain tail for
  string-context consumers — the S3 and S5 golden fixtures use it
  (`format_records_for_context`, `domain/context.py:659-677`).
- S1 output untouched: nothing on the pipeline path calls the new shaper.

**Carry-back:** seam §1's "internally these compose … `format_record_for_context`"
needs a wording fix (the dict-shaping step is the S2 tail; the string formatter is the
S1/S3 tail). Inline edit in SEAM_CONTRACT.md + ledge PM ack, same convention as §3.

## P3 — Identity policy: callable parameter; external drops the record's own `id`

Two distinct identity concerns, two distinct chain links (confirming GROUNDING):

1. **FK values** → display names: the state-free fk_enrich step. Mechanics lifted from
   `_enrich_lazy_registrations` (`crud.py:758-814`) minus the registry: collect UUIDs
   per field in `ctx.get_fk_enrich_map()`, one batch `in_` read per target table via
   `ctx.get_db_adapter()`, replace values with names. An FK value that doesn't resolve
   (RLS-hidden, dangling) is replaced with `None` — never left as a raw UUID (E9);
   the shaper then renders it `"(not set)"`.
2. **The record's own `id`**: S1 replaces it with a session ref
   (`id_registry.py:196-238` — counters, turn tracking, label memory: inseparable from
   session state). Externally there is no registry → at grade `external` the `id` key is
   **dropped**; the consuming AI re-finds entities by name/search (ledge's tool design
   assumes this, per GROUNDING). Internally it passes through.

Design: `IdentityPolicy = Callable[[list[dict], str], list[dict]]` (records, table →
records), with two shipped policies — `identity_drop_ids` and `identity_passthrough` —
and any callable accepted (the S1 fixture's slot-in is
`lambda records, table: registry.translate_read_output(records, table)`, proving the
session registry composes into the slot **without** the module importing it). The seam
entrypoints select by grade: `external → drop`, anything else → passthrough; richer
callers pass their own. Scope boundary (documented, not enforced): non-FK UUID columns
like `user_id` are the domain's `external` strip-set responsibility (ledge Phase 1
audit), not the identity policy's — core's mechanical E9 guard covers `id` + enrich-map
FK fields.

## P4 — Per-table header: **additive `get_table_notes(table)` defaulting to subdomain notes** (option b)

`get_semantic_notes()` is per-subdomain (`domain/context.py:322-329`), consumed via
schema.py's subdomain context; `ShapedPayload.header` is per-**table**, and ledge
Phase 1 produces per-table slivers. Option (b) is confirmed lean:

- Default implementation on `DomainContext`: find the subdomain owning `table`
  (`primary_table` or in `related_tables`, `domain/context.py:84-87`) and return
  `get_semantic_notes().get(that_subdomain, "")`; `""` when the table is unowned.
  Zero migration (defaulted member, `ABSTRACT_MEMBERS` unchanged — A2's
  `get_audience_grades` precedent).
- Costs: freeze-test bump `CONTEXT_MEMBERS` 35→36 (80 total), injection-map row (A4
  doc queue), and the carry-back: ledge must know to declare per-table notes into
  `get_table_notes` rather than folding slivers into subdomain notes.

## P5 — `truncated` via limit+1

Confirmed: no count surface on a plain limited PostgREST select, and core's `db_read`
applies `limit` blind (`crud.py:351-352`). The internal read fetches `limit + 1`, sets
`truncated = len(rows) > limit`, returns `rows[:limit]`. `assemble_entity_context`
reads with limit 2 on `id eq` (a >1 result for a PK read is a data-integrity surprise —
but truncated is simply False and the first record returned; no fake count). `count =
len(records)` post-strip per §2.

## F6 — NEW (not in GROUNDING): the chain has an async link; seam §1 writes `def`

`CRUDMiddleware.post_read` is `async def` (`domain/context.py:161`) and the §3
clarification makes it load-bearing for the chain (transform dispositions — the
exit-criteria "cents as dollars" — live there). A sync entrypoint would need
`asyncio.run()`, which **raises `RuntimeError` inside a running event loop** — and
ledge's MCP server is the canonical async caller. No shim exists yet in landscaping
(grep 2026-06-12: only the contract docs mention the signatures), so nothing is built
against `def`.

**Recommendation: `async def` entrypoints**, matching core's read path (`db_read` is
async) and MCP servers' async-native tool handlers. This is a §1 signature deviation →
explicit carry-back needing ledge PM ack (alongside P2's wording fix and P4). Fallback
if ledge insists on sync: sync wrappers via `asyncio.run` that document the
no-running-loop constraint — not recommended.

## Filter contract: `Mapping[str, Any]` → validated `FilterClause` list

Seam §1 types `filters` as a **Mapping** with "adapter filter ops (eq/ilike/in/gte...)"
— PostgREST op *names*, while `FilterClause.op` uses symbols (`"="`, `">="`,
`crud.py:48`). So core needs a small parse+validate layer:

- Value forms: scalar → `eq` shorthand (`{"status": "active"}`); dict of op→value for
  explicit/multiple ops (`{"price": {"gte": 100, "lte": 500}}`).
- Op-name map: `eq/neq/gt/lt/gte/lte/in/not_in/ilike/is_null/is_not_null/contains` →
  the `FilterClause` symbols. **`similar` is rejected**: it's implemented by `pre_read`
  middleware (`crud.py:44-46` docstring), which is not on the S2 chain — silently
  accepting it would be a silent-empty-read generator.
- Loud typed errors: `FilterValidationError` naming the field, the bad op, and the
  valid op set. Non-mapping `filters`, non-dict op-form values, unknown ops — all
  pre-flight failures before any adapter call.
- Column existence: PostgREST rejects unknown columns with a 400 (loud, not silent) —
  the adapter exception propagates wrapped (`raise FilterValidationError(...) from e`)
  so the caller gets one typed error family. Pre-flight schema introspection
  (`tools/schema.py` RPC) is deliberately NOT pulled in: it's global-domain-coupled,
  cached statefully, and adds an RPC per call for an error the DB already raises loudly.

The "silent empty read" failure mode the contract bans cannot occur: every invalid
input path either raises pre-flight (shape/op) or surfaces the adapter's own error
(columns/values) as a typed error.

## Error taxonomy (loud, typed — PITFALLS `loud-errors-over-silent-fallbacks`)

`AssemblyError(ValueError)` base in the new module, with:
`FilterValidationError`, `UnknownEntityTypeError` (names valid types),
`UnknownSubdomainError` / `TableNotInSubdomainError` (names valid tables),
`RecordNotFoundError` (entity read found 0 rows — an empty payload for a
specifically-requested entity is the silent-failure shape).
`UnknownGradeError` comes from `domain/grades.py:45` unchanged.

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|---|---|---|---|
| adapter | — (abstract) | `ctx.get_db_adapter()` (`context.py:735-747`) | none — E3 by construction |
| post_read transforms | no-op passthrough | `ctx.get_crud_middleware()` (defaulted None, `context.py:363-380`) | none |
| FK enrichment | — (abstract map) | `ctx.get_fk_enrich_map()` (`context.py:297-307`) | none — empty map = no enrich |
| identity | by-grade selection in entrypoints | chain parameter (callable) | new — P3 design |
| grades | well-known, empty strip sets | `ctx.get_audience_grades()` (A2) | none — unknown grade is loud (`grades.py:150-153`) |
| value shaping | `None → "(not set)"`, pass-through otherwise | none in v0 (core-owned display rule) | acceptable — transforms belong to middleware (§3) |
| header | subdomain notes via table→subdomain lookup, `""` if unowned | NEW `ctx.get_table_notes(table)` (defaulted) | P4 — freeze bump 35→36 |
| filters | — | core-validated, typed errors | new — validation layer |

## Findings (summary)

1. **P1 → thin internal read** reusing `apply_filter`/`FilterClause`; `db_read`
   untouched; no `user_id` parameter anywhere on the seam path (E3: adapter carries it).
2. **P2 → new `shape_record_values` dict tail**; `format_record_for_context` stays the
   string tail for S1/S3/S5; seam §1 wording carry-back.
3. **P3 → `IdentityPolicy` callable** with `drop_ids`/`passthrough` shipped;
   entrypoints select by grade (external → drop); unresolved FK values → `None`, never
   raw UUIDs.
4. **P4 → `get_table_notes(table)`** defaulted to owning-subdomain notes; freeze 35→36;
   carry-back so ledge declares into it.
5. **P5 → limit+1**, slice, `truncated = len > limit`.
6. **F6 → `async def` entrypoints** (post_read is async; MCP caller is async); §1
   signature carry-back needing ledge ack — flagged for plan approval.
7. Golden fixtures are buildable test-side with a small in-memory fake adapter
   (per-table canned rows + real `eq`/`in_` filtering so fk_enrich batch reads behave
   honestly); `make_mock_db` (`conftest.py:181`) returns identical data for every table,
   which can't express multi-table recipes/preloads.

## Open Questions

1. **F6 sync vs async** — recommendation is `async def`; needs owner sign-off at plan
   approval because it amends seam §1 (carry-back to ledge PM either way).
2. None other — P1–P5 resolutions above are confident and evidence-backed.
