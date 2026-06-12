# Plan: State-Free Assembly Entrypoints (A3 / E2 / C-5)

**Date:** 2026-06-12
**Based on:** RESEARCH.md (P1–P5 resolved + F6 async finding)

## Approach

One new module `src/alfred/context/assembly.py` holds `ShapedPayload`, the typed error
family, the filter parse/validate layer, the state-free per-record/per-set chain links
(read → post_read → fk_enrich → identity → strip → shape → header), and the two seam
entrypoints as thin compositions over those links. The chain links are the public
substrate surface (Guardrail #1); the entrypoints are two S2-flavored consumers of it.
`DomainContext` gains one defaulted member, `get_table_notes(table)` (P4). Nothing on
the pipeline path is touched — `db_read`, `crud.py`, builders, id_registry all unchanged.

## ⚠️ Approval gate — one contract deviation needs sign-off (F6)

The entrypoints will be **`async def`**, not `def` as seam §1 writes them. Reason:
`CRUDMiddleware.post_read` is `async def` ([context.py:161](../../../src/alfred/domain/context.py#L161))
and is load-bearing for the chain (§3: transforms like cents→dollars live there); a sync
wrapper needs `asyncio.run()`, which raises inside a running event loop — and ledge's
MCP server is the canonical async caller. No ledge shim exists yet, so nothing breaks.
This is a §1 amendment carry-back the Core PM relays to ledge. **Approving this plan
approves recommending async; ledge PM ack happens via the carry-back.**

## Public API (alfred.context)

```python
# seam entrypoints (§1 + F6 async)
async def assemble_entity_context(
    ctx: DomainContext, entity_type: str, entity_id: str, *, grade: str
) -> ShapedPayload: ...

async def assemble_subdomain_read(
    ctx: DomainContext, subdomain: str, table: str, filters: Mapping[str, Any],
    *, grade: str, limit: int = 25,
) -> ShapedPayload: ...

SCHEMA_VERSION: Final[str] = "1"   # bump policy documented in module docstring

@dataclass(frozen=True)
class ShapedPayload:               # exactly seam §2, field-for-field
    header: str; records: list[dict]; table: str; count: int
    truncated: bool; grade: str; schema_version: str

# identity (E9 / Guardrail #2)
IdentityPolicy = Callable[[list[dict], str], list[dict]]   # (records, table) -> records
def identity_passthrough(records, table) -> list[dict]: ...
def identity_drop_ids(records, table) -> list[dict]: ...

# errors — AssemblyError(ValueError) base
FilterValidationError, UnknownEntityTypeError, UnknownSubdomainError,
TableNotInSubdomainError, RecordNotFoundError
```

Chain links public in `alfred.context.assembly` (composable substrate surface; fixtures
and future S3/S5/D7 callers import them; not re-exported from the package `__init__`):

```python
def parse_filters(filters: Mapping[str, Any]) -> list[FilterClause]
async def read_table(ctx, table, clauses, *, limit=None) -> tuple[list[dict], bool]  # limit+1 → truncated
async def apply_post_read(ctx, records, table, user_id="") -> list[dict]
async def enrich_fk_values(ctx, records) -> list[dict]   # state-free fk_enrich; unresolved → None
def shape_record_values(record: dict) -> dict             # None → "(not set)"
# strip link = GradeRegistry.from_context(ctx).strip(records, table, grade)  (A2)
# header link = ctx.get_table_notes(table)                                   (P4)
```

Entrypoint internals (both): resolve/validate target → `parse_filters` (subdomain read)
or `id eq` clause (entity read, limit 2, 0 rows → `RecordNotFoundError`) → `read_table`
→ `apply_post_read` → `enrich_fk_values` → identity (grade `external` → drop_ids, else
passthrough) → `strip(grade)` (loud `UnknownGradeError` from A2) → `shape_record_values`
→ `ShapedPayload(header=ctx.get_table_notes(table), ..., schema_version=SCHEMA_VERSION)`.

Filter mapping (RESEARCH "Filter contract"): scalar value = `eq` shorthand; dict value =
`{op: value, ...}` with PostgREST op names (`eq/neq/gt/lt/gte/lte/in/not_in/ilike/
is_null/is_not_null/contains`) mapped to `FilterClause` symbols; `similar` rejected
loudly (needs `pre_read`, not on the S2 chain); adapter column errors re-raised as
`FilterValidationError ... from e`.

## Reuse Map

| Capability | Reuse / New | Symbol + Path | Why |
|------------|-------------|---------------|-----|
| Filter machinery | **Reuse** | `apply_filter`, `FilterClause` — `src/alfred/tools/crud.py:215-247, 40-49` | Pure (query, clause) function + validated op model; import-clean path (verified: `tools/__init__.py` + `schema.py:13-14` stdlib-only top-level) |
| Strip link | **Reuse** | `GradeRegistry.from_context(ctx).strip()` — `src/alfred/domain/grades.py:84-156` | A2 built it for exactly this slot; per-call, pure, loud |
| Adapter access | **Reuse** | `ctx.get_db_adapter()` — `src/alfred/domain/context.py:735-747`; protocol `src/alfred/db/adapter.py:23-52` | E3: per-request adapter, never the module global |
| post_read firing | **Reuse** | `CRUDMiddleware.post_read` — `src/alfred/domain/context.py:161-176` | §3-acked home of transform dispositions |
| entity_type→table | **Reuse** | `DomainContext.type_to_table` — `src/alfred/domain/context.py:251-259` | existing computed lookup |
| subdomain→tables | **Reuse** | `DomainContext.subdomains` → `SubdomainDefinition` — `src/alfred/domain/context.py:69-87` | typed structural declaration (vs prompt-oriented `get_subdomain_registry`) |
| String tail (S3/S5/S1 fixtures) | **Reuse** | `format_record(s)_for_context` — `src/alfred/domain/context.py:637-677` | stays the LLM-string formatter; NOT on the S2 dict path (P2) |
| S1 identity fixture | **Reuse (test-side only)** | `SessionIdRegistry.translate_read_output` — `src/alfred/core/id_registry.py:173-238` | fixture imports it; assembly module must not (subprocess test enforces) |
| Adapter read for the chain | **New** (`read_table`) | searched `db_read` (`crud.py:255-361`) — global-coupled at `:270-272`, fires `pre_read`, injects `user_id`, mutates `params.columns`, no truncation detection | P1: a thin read keeps the pipeline path byte-for-byte untouched; the reusable part (filters) IS imported |
| State-free fk_enrich | **New** (`enrich_fk_values`) | searched `_enrich_lazy_registrations` (`crud.py:758-814`) — welded to registry queue/labels | GROUNDING §1: mechanics reimplemented without counters/session |
| Dict value-shaping | **New** (`shape_record_values`) | grep `"(not set)"` in src/ → zero hits (2026-06-12) | P2: exists nowhere; must be new so S1 output is untouched |
| Per-table header | **New** (`get_table_notes`, defaulted) | `get_semantic_notes` (`context.py:322-329`) is per-subdomain | P4(b): zero-migration additive member |

## Tasks

- [ ] 1. `DomainContext.get_table_notes(table)` — defaulted: owning subdomain's
  semantic notes (primary-table match preferred over related), `""` if unowned;
  docstring names the S2 header role + ledge declaration target.
- [ ] 2. `src/alfred/context/assembly.py` — module docstring (state-free guarantees,
  schema_version bump policy, user_id="" convention for post_read); `ShapedPayload`;
  errors; `parse_filters`; chain links; identity policies; two entrypoints.
- [ ] 3. `alfred/context/__init__.py` — re-export entrypoints, `ShapedPayload`,
  `SCHEMA_VERSION`, errors, `IdentityPolicy` + both policies.
- [ ] 4. Freeze test: `CONTEXT_MEMBERS` 35→36 (80 total), documented in place (A2 style).
- [ ] 5. Import isolation: new subprocess test — `alfred.context.assembly` forbids
  existing prefixes **+ `alfred.core.id_registry`**; source-level test: no
  `get_current_domain`, no `ContextVar` in assembly.py.
- [ ] 6. `tests/core/test_assembly_entrypoints.py` — unit suite (see Test Plan).
- [ ] 7. `tests/core/test_assembly_fixtures.py` — `FakeTableAdapter` (per-table rows,
  honest `eq`/`in_`/`limit` behavior) + the three golden fixtures.
- [ ] 8. Gates: full pytest, ruff check+format on touched files, `mypy src/
  --no-incremental` total == 368, `python -m compileall src/alfred -q`.
- [ ] 9. Plan-adherence check → SUMMARY.md (+ PITFALLS graduation check).

## Test Plan (fixtures are first-class DoD)

**Golden fixtures (the merge gate, GROUNDING §3):**

| Fixture | Composition proven | Key asserts |
|---|---|---|
| **S1 ref-translated read** (fast-mode shaped) | `read_table` → `apply_post_read` → identity = `lambda r, t: registry.translate_read_output(r, t)` (real `SessionIdRegistry`, **imported by the test, not the module**) → `strip("reply")` → `format_records_for_context` | ids are `item_N` refs; zero raw UUIDs in output; reply grade strips nothing (Guardrail #3 heritage from A2's equality test) |
| **S3 recipe** (memories-shaped) | multiple chain calls (items + notes) composed into ONE context block, string tail via `format_record_for_context` | both tables' content in one block; config built once (registry/adapter constructed once, passed per call); adapter read count == expected |
| **S5 preload** (brainstorm-shaped) | stub-subclass `get_user_profile`/`get_domain_snapshot` + multi-table reads → one frozen prompt string; **passthrough identity, grade `reply`** | golden-string equality; ids present (passthrough — grades don't interfere); no UUID-stripping at reply |

**Unit suite:** payload frozen + `schema_version == "1"` + count/table self-description ·
filter parsing (scalar shorthand, op-form, multi-op per field, unknown op loud naming
valid set, `similar` rejected, non-mapping loud) · `UnknownEntityTypeError` /
`UnknownSubdomainError` / `TableNotInSubdomainError` name valid values ·
`RecordNotFoundError` on 0-row entity read · `UnknownGradeError` propagates ·
truncated: limit+1 fetch, exactly-limit rows returned, True/False both ways ·
`"(not set)"` for NULLs; stripped fields do NOT resurrect as `"(not set)"` (strip
before shape) · external drops `id` + FK values are display names; reply passes `id`
through · unresolved FK → `"(not set)"`, never a UUID (E9) · post_read transform
visible in payload (middleware fires) · adapter receives NO `user_id` eq filter
(recorded by fake adapter — E3 model) · E5: subprocess isolation + source-level checks.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| P1 read | Thin internal `read_table`; `db_read` untouched | Guardrail #3 by construction; seam read legitimately differs (no pre_read, no user_id injection, limit+1); filter machinery reused at the right grain |
| P2 tail | New `shape_record_values` dict shaper; `format_record_for_context` stays string tail off the S2 path | §2 binding over §1 wording; S1 byte-identical; carry-back the §1 wording fix |
| P3 identity | `IdentityPolicy` callable param; shipped `drop_ids`/`passthrough`; entrypoints map `external`→drop, else passthrough | E9 policy-not-property (Guardrail #2); S1 fixture proves registry slots in without import |
| P4 header | Additive defaulted `get_table_notes(table)` → owning subdomain's notes | Matches ledge Phase 1 per-table slivers; zero migration; freeze 35→36 |
| P5 truncated | limit+1 fetch, slice, `len > limit` | Only honest signal without count queries |
| **F6 async** | **`async def` entrypoints — needs approval** | post_read is async + load-bearing; MCP caller is async; `asyncio.run` wrapper breaks in running loops |
| post_read user_id | Chain takes `user_id: str = ""`; entrypoints pass `""` (documented) | Seam §1 has no user_id (E3: adapter carries tenant); middleware needing it gets it adapter-side |
| Filter format | Scalar = eq shorthand; dict = {op: value}; PostgREST op names; `similar` rejected | Matches §1 comment ("eq/ilike/in/gte"); `similar` without pre_read = silent-empty generator |
| Column validation | Pre-flight op/shape validation core-side; adapter 400s wrapped `from e` as `FilterValidationError` | No silent empty possible; avoids coupling to global-domain schema.py + an RPC per call |
| Entity not found | `RecordNotFoundError` (loud), not empty payload | Empty payload for a specifically-requested entity is the silent-failure shape |
| Unresolved FK value | → `None` → `"(not set)"` | Raw UUID must never survive at external (E9); RLS-hidden FKs degrade gracefully |
| Non-FK UUID columns (e.g. `user_id`) | Domain's `external` strip-set responsibility (ledge audit); documented boundary | Declare/enforce symmetry — core enforces what's declared (enrich map, id); it can't guess undeclared UUID columns |
| Exports | Seam names from `alfred.context`; chain links from `alfred.context.assembly` | Entrypoints are consumers of the chain (Guardrail #1); links stay importable for S3/S5/D7 without polluting the seam namespace |

## Error Handling

All failures loud and typed (PITFALLS `loud-errors-over-silent-fallbacks`):
`AssemblyError(ValueError)` family per RESEARCH taxonomy; `UnknownGradeError` from A2
unchanged; adapter exceptions never swallowed (wrapped with cause). No fallback to the
module-global domain anywhere — enforced by source-level test, not convention.

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/context/assembly.py` | NEW — payload, errors, filter layer, chain links, identity policies, 2 entrypoints |
| `src/alfred/domain/context.py` | + `get_table_notes(table)` (defaulted, Data Shaping section) |
| `src/alfred/context/__init__.py` | Re-export seam names |
| `tests/core/test_protocol_split.py` | Freeze: +`get_table_notes`, 35→36 / 80 total |
| `tests/core/test_import_isolation.py` | + assembly-specific subprocess test (forbid `alfred.core.id_registry`) + source-level E5 checks |
| `tests/core/test_assembly_entrypoints.py` | NEW — unit suite |
| `tests/core/test_assembly_fixtures.py` | NEW — FakeTableAdapter + 3 golden fixtures |

## Carry-backs (Core PM relays to ledge; record in SUMMARY too)

1. **§1 signatures gain `async`** (F6) — needs ledge PM ack.
2. **§1 wording fix** (P2): chain's S2 tail is dict value-shaping; `format_record_for_context` is the S1/S3 string tail — inline clarification, §3-note convention.
3. **P4**: per-table headers come from new `get_table_notes(table)` (defaults to subdomain notes) — ledge declares per-table slivers into it.
4. `schema_version` initial value `"1"`; bump policy = any §2 shape-breaking change, documented in module.

**A4 doc queue (adds to A1/A2's):** core-public-api.md — 2 entrypoints + ShapedPayload +
errors + identity policies; injection-map.md — `get_table_notes` row; member count
79→80 (CLAUDE.md, core-domain-architecture.md §2).

## Definition of Done

- [ ] Two entrypoints per seam §1 (+F6 amendment) in `alfred.context`, thin over the chain
- [ ] `ShapedPayload` frozen, `schema_version="1"` (seam §2 field-for-field)
- [ ] Core-side filter validation — loud typed errors, no silent empty read possible
- [ ] E5: no AlfredState/session/ContextVar/LLM on any path — subprocess + source tests green
- [ ] **Three golden fixtures green (S1 / S3 / S5)** — the merge gate
- [ ] Pipeline path untouched (`git diff` shows no edits under `tools/crud.py`, `graph/`, `core/id_registry.py`)
- [ ] Full pytest green (234 baseline + new); ruff check+format clean on touched files
- [ ] mypy exact parity: 368 total on clean `--no-incremental` run (error TOTAL is the metric)
- [ ] `python -m compileall src/alfred -q` exits 0 (PITFALLS `unimported-module-rot`)
- [ ] PITFALLS graduation check + SUMMARY.md with plan-adherence diff review
