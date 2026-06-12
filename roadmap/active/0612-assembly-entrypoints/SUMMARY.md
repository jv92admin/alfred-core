# Summary: State-Free Assembly Entrypoints (A3 / E2 / C-5)

**Date:** 2026-06-12

## What Was Done

- **`src/alfred/context/assembly.py`** (NEW): `ShapedPayload` (frozen, seam §2
  field-for-field, `SCHEMA_VERSION = "1"` with bump policy in the module docstring);
  `AssemblyError` family (`FilterValidationError`, `UnknownEntityTypeError`,
  `UnknownSubdomainError`, `TableNotInSubdomainError`, `RecordNotFoundError`);
  `parse_filters` (scalar = eq shorthand, `{op: value}` form, PostgREST op names,
  `similar` rejected loudly with the E10 pointer); the chain links — `read_table`
  (limit+1 truncation, adapter errors wrapped `from e`), `apply_post_read`
  (`user_id: str = ""` chain parameter — approval condition 1), `enrich_fk_values`
  (state-free, unresolved FK → `None` with the deliberate redaction-positive comment),
  `IdentityPolicy` + `identity_passthrough`/`identity_drop_ids`, `shape_record_values`
  (`"(not set)"` NULL signalling) — and the two **`async def`** seam entrypoints (F6
  as approved) as thin compositions, both docstrings carrying the tenant-scoping
  warning (approval condition 2). Grade validated pre-I/O (fail-fast before the read).
- **`DomainContext.get_table_notes(table)`** (P4 option b): defaulted member —
  owning subdomain's semantic notes (primary-table match preferred), `""` if unowned;
  `ABSTRACT_MEMBERS` unchanged → zero migration.
- **Seam exports** — entrypoints, payload, `SCHEMA_VERSION`, errors, identity
  policies re-exported from `alfred.context`; chain links importable from
  `alfred.context.assembly` (Guardrail #1: entrypoints are consumers of the chain).
- **Import landmine fixed (discovered during gating, see Deviations):**
  `tools/schema.py.__getattr__` now name-checks before resolving the domain;
  `tools/__init__.py` exposes `SUBDOMAIN_REGISTRY` lazily. Before this, importing
  `alfred.tools` (hence `alfred.context`) **required a registered domain** —
  graduated to PITFALLS as `import-time-domain-coupling`.
- **THE THREE GOLDEN FIXTURES** (`tests/core/test_assembly_fixtures.py`): S1
  ref-translated read (real `SessionIdRegistry.translate_read_output` slotted into
  the identity seat from outside; refs not UUIDs; reply strips nothing), S3
  memories-shaped multi-fetch recipe (one context block, grade registry built once,
  exactly 3 adapter reads — no N+1), S5 brainstorm preload (frozen golden string;
  service-role adapter with **explicit scoping**: real `user_id` through
  `apply_post_read` + explicit filter clause — approval conditions 1+2 demonstrated;
  passthrough identity, grades don't interfere).
- **Unit suite** (`tests/core/test_assembly_entrypoints.py`, 27 items): payload
  frozen/versioned, seam canonicality, filter parsing + all loud-error paths,
  truncation both ways (adapter asked for limit+1, verified), strip-before-shape
  (stripped NULL doesn't resurrect), middleware transform visible + `user_id=""` at
  seam, unresolved FK never leaks a UUID, **no user filter ever applied** (recorded
  adapter calls), unknown grade fails before any read.
- **E5 enforcement** (`test_import_isolation.py`): subprocess test — assembly module
  forbids LLM stack **+ `alfred.core.id_registry`**; AST-based source test — no
  `get_current_domain`/`ContextVar`/`AlfredState` identifiers in the module.
- **Freeze test**: `CONTEXT_MEMBERS` 35→36 (80 total), documented in place (A2 style).
- **Test infra** (`conftest.py`): `FakeTableAdapter` (honest per-table fake — filters
  filter, limit limits, errors defer to `execute()` like PostgREST) +
  `AssemblyTestContext` (DomainContext-ONLY implementer) + `assembly_ctx_factory`.

**Gates at completion (same bar as A1/A2):** 266 tests pass (234 baseline + 32 new;
pre-existing tests edited: freeze counts + isolation additions only, per plan) ·
ruff check + format clean on all 10 touched files · mypy exact parity (368 → 368,
clean `--no-incremental`; `assembly.py` contributes 0) · `compileall` OK ·
**Guardrail #3 by construction**: `git diff` shows zero edits under `tools/crud.py`,
`graph/`, `core/id_registry.py`, `context/builders.py`.

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| (Approval condition 1) `user_id` placement | Chain parameter (`apply_post_read(..., user_id="")`); seam entrypoints pass the default; S5 fixture passes a real one | The chain is the durable surface; S5-style consumers on service-role adapters scope explicitly |
| (Approval condition 2) Tenant-scoping loudness | Both entrypoint docstrings + module docstring state "row scoping is the adapter's job — no user filter added"; S5 fixture is the copyable explicit-scoping pattern | Core can't mechanically detect a non-RLS adapter; the guard is documentary + fixture |
| schema.py `__getattr__` ordering | Name-check before `_get_domain()` | The import system probes `__path__`; resolving the domain first turned a benign AttributeError into "No domain registered" at import time |
| `SUBDOMAIN_REGISTRY` in `tools/__init__` | Lazy via module `__getattr__` (public surface unchanged) | Eager import required a registered domain at package-import time AND froze a stale snapshot; no in-repo consumer uses `from alfred.tools import SUBDOMAIN_REGISTRY` (grep-verified) |
| Grade validation timing | Membership check before the adapter read (message mirrors `GradeRegistry.strip`) | Loud error pre-I/O instead of after a wasted query |
| Entity read row mechanics | `id eq` with limit 1 (fetch 2), `truncated=False` always, first row returned | A >1 result on a PK read is a data-integrity surprise, not truncation |

## Deviations from Plan

1. **`src/alfred/tools/__init__.py` + `src/alfred/tools/schema.py` edited** (not in
   the plan's file list): the import landmine above made `import alfred.context`
   impossible without a registered domain — a direct blocker for the seam guarantee
   the plan's own isolation tests enforce. Both fixes are import-time-only and
   behavior-preserving (the schema.py diff beyond `__getattr__` is `ruff format`
   whitespace). GROUNDING had verified `tools/crud.py` import-clean; the parent
   package `__init__` was the bite. PITFALLS entry added (`import-time-domain-coupling`).
2. **`FakeTableAdapter` lives in `conftest.py`, not `test_assembly_fixtures.py`**:
   it's shared by the unit suite and the fixtures file, and cross-test-module imports
   are fragile in this layout (`tests/core` is a package without a `tests/__init__`);
   conftest is the established shared-infra home (`make_mock_db` precedent).
3. **Source-level E5 test is AST-based** rather than substring grep: the module's own
   docstring legitimately *mentions* the forbidden names while documenting its
   guarantees; only code identifiers fail the test.
4. Mechanical: mypy `+1` from the new untyped `__getattr__` → annotated (`368` exact
   restored); ruff `--fix`/`format` reflow on touched files (A2 precedent), including
   removal of a pre-existing unused `CRUDMiddleware` import in conftest.

Every Reuse Map row honored: `apply_filter`/`FilterClause` imported (one filter
dialect), `GradeRegistry.from_context(ctx).strip` is the strip link, adapter only via
`ctx.get_db_adapter()`, `post_read` fired per §3, `type_to_table`/`subdomains` for
target resolution, `format_record(s)_for_context` as the fixtures' string tail,
`translate_read_output` imported by the S1 fixture only (subprocess test proves the
module doesn't).

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/context/assembly.py` | NEW — payload, errors, filter layer, chain links, identity policies, 2 async entrypoints |
| `src/alfred/domain/context.py` | + `get_table_notes(table)` (defaulted, Data Shaping section) |
| `src/alfred/context/__init__.py` | Re-exports the 13 seam names |
| `src/alfred/tools/__init__.py` | Lazy `SUBDOMAIN_REGISTRY` (deviation 1 — import landmine) |
| `src/alfred/tools/schema.py` | `__getattr__` name-check before domain resolution (deviation 1) |
| `tests/core/test_protocol_split.py` | Freeze: +`get_table_notes`, 35→36 / 80 total |
| `tests/core/test_import_isolation.py` | + assembly subprocess test (forbids `id_registry`) + AST source test |
| `tests/core/test_assembly_entrypoints.py` | NEW — 27-item unit suite |
| `tests/core/test_assembly_fixtures.py` | NEW — the 3 golden fixtures |
| `tests/core/conftest.py` | + `FakeTableAdapter`, `AssemblyTestContext`, `assembly_ctx_factory` (deviation 2) |
| `.claude/PITFALLS.md` | + `import-time-domain-coupling` (graduated incident) |

## Handoffs

- **Carry-backs for the ledge PM** (Core PM relays; amendment block per approval):
  1. Seam §1 signatures are **`async def`** (F6 — approved with rationale of record:
     sync was never implementable once §3 routed transforms through async `post_read`).
  2. §1 wording fix: the S2 chain tail is dict value-shaping (`"(not set)"`
     signalling); `format_record_for_context` is the S1/S3 *string* tail, off the
     ShapedPayload path.
  3. P4: ledge Phase 1 declares per-table slivers into **`get_table_notes(table)`**
     (defaults to subdomain notes), not into `get_semantic_notes()`.
  4. `schema_version` initial value `"1"`; bump policy documented in
     `assembly.py`'s module docstring.
  5. Filter mapping shape for the MCP tool layer: scalar = eq shorthand,
     `{op: value}` for explicit ops; `similar` rejected (E10 is the semantic path).
- **A4 `/doc-review` queue (adds to A1/A2's):** core-public-api.md — 2 entrypoints +
  `ShapedPayload` + errors + identity policies + chain links; injection-map.md —
  `get_table_notes` row; member count 79→80 (CLAUDE.md, core-domain-architecture.md §2).
- **D7 (S1 convergence):** the S1 golden fixture is the convergence blueprint —
  registry-as-identity-policy over the same chain.
- **Program roadmap A3 status row** — left untouched for PM verification (A1/A2
  precedent: PM marks verified).

## Shipped

- **Version:** (filled on archive — ships in A4's additive minor release)
- **Commits:** (filled on archive)
- **Date:** (filled on archive)
