# Summary: Grade Registry (A2 / C-6 minimal)

**Date:** 2026-06-11

## What Was Done

- **`src/alfred/domain/grades.py`** (NEW, stdlib-only): `GRADE_REPLY` / `GRADE_EXTERNAL` /
  `WELL_KNOWN_GRADES` constants; `GradeError` → `GradeRegistryError` (registration) +
  `UnknownGradeError` (call time) taxonomy; `StripSet` (global `fields` +
  per-table `table_fields`, effective set = union); `GradeRegistry` with
  `from_context()` (validation) and `strip()` (the A3 chain link — pure, list-in/list-out,
  loud on unregistered grade).
- **`DomainContext.get_audience_grades()`** — defaulted declaration method (well-known
  grades, empty strip sets = exactly today's behavior; `ABSTRACT_MEMBERS` unchanged →
  zero migration for Kitchen/FPL/Stub).
- **`register_domain()` validates** — `GradeRegistry.from_context(domain)` in the body
  before assignment (signature unchanged): well-known grades present + `external ⊇ reply`
  per-table; failure = `GradeRegistryError` naming domain, grade, table, exact fields;
  domain is NOT registered on failure. Exercised by every suite run via
  `conftest.py:243`'s module-level registration.
- **Seam exports** — the 7 public grade names re-exported from both `alfred.domain` and
  `alfred.context` (seam path), pinned canonical by test.
- **Cross-referencing docstrings (approval addition 2)** — `get_audience_grades` names
  the LLM-bound/external-bound assembly path; `get_strip_fields` names the user-bound
  reply-rendering path; each points at the other and warns against bridging
  (RESEARCH Finding 2 / Guardrail #3).
- **Freeze test updated as the deliberate compat decision** — `CONTEXT_MEMBERS` 34→35
  (78→79 total), new member documented in-place, `ABSTRACT_MEMBERS` untouched.
- **`tests/core/test_grade_registry.py`** (NEW, 13 tests): defaults, Guardrail #3
  no-op-by-equality (+ purity), global∪per-table strip, open-world tables, input
  immutability, loud unknown grade, missing well-known grade, global superset violation,
  per-table-covered-by-global validity, per-table uncovered violation, custom grade,
  zero-migration registration, seam-import canonicality.

**Gates at completion (same bar as A1):** 234 tests pass (221 baseline + 13 new; only
pre-existing test edited is the freeze, per plan) · ruff check + format clean on all 6
touched files · mypy exact parity (368 before → 368 after, clean `--no-incremental` run;
`grades.py` contributes 0) · import-isolation tests green unchanged ·
`compileall src/alfred` OK (PITFALLS `unimported-module-rot` check).

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| (Approval addition 1) Decision 10 recorded in PLAN | Grades are pure field removal; transforms (cents→dollars) stay `post_read` middleware, grade-independent | Core-side half of the seam clarification now in SEAM_CONTRACT.md §3; also stated in `grades.py` module docstring |
| (Approval addition 2) Cross-ref docstrings | Both `get_audience_grades` and `get_strip_fields` name their path + no-bridge warning | RESEARCH Finding 2 made durable at the API surface, not just in roadmap docs |
| `WELL_KNOWN_GRADES` export scope | Public in `grades.py`, not re-exported via `alfred.domain`/`alfred.context` | Plan specified 7 seam names; the frozenset is an implementation convenience |
| mypy file-count discrepancy | Accepted total-parity (368=368) as the gate | A1 recorded "368 in 27 files"; clean runs today report "368 in 28 files" — and a cache-warm pre-change run reported "9 files". The files-with-errors figure is cache-sensitive reporting; the error **total** is the stable, contracted metric and is exact. Zero errors attributable to any A2 file (grep-verified per touched file) |

## Deviations from Plan

1. **None of substance.** Every Reuse Map row honored; file list exact; the 12 planned
   test rows shipped as 13 test functions (the strip-union row split from the open-world
   table row for sharper failure messages).
2. Two mechanical lint fixes during gating: ruff B905 (`zip(..., strict=True)` in a new
   test) and `ruff format` reflow of `grades.py` — the project's own quality commands,
   no semantic change.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/domain/grades.py` | NEW — constants, errors, `StripSet`, `GradeRegistry` (validate + strip primitive) |
| `src/alfred/domain/context.py` | +`get_audience_grades()` (Data Shaping section); `get_strip_fields` docstring cross-ref; imports from `grades` |
| `src/alfred/domain/__init__.py` | `register_domain` validates (body-only); `__all__` + grade names |
| `src/alfred/context/__init__.py` | Re-exports the 7 grade names (seam path) |
| `tests/core/test_protocol_split.py` | Freeze update: +`get_audience_grades`, counts 34→35 / 79 total, A2 comment |
| `tests/core/test_grade_registry.py` | NEW — 13 tests |

## Handoffs

- **A3 (state-free entrypoints):** the chain's strip link is
  `GradeRegistry.from_context(ctx).strip(records, table, grade)` — build per call
  (state-free, E2/E5), slot between fk_enrich and `format_record_for_context` per seam §1.
  Guardrail #3's grade-`reply` conformance fixture can build directly on
  `test_default_reply_grade_strips_nothing`.
- **Ledge Phase 1 auditors:** declare into
  `StripSet(fields=<cross-table base>, table_fields=<per-table audit output>)`; field
  names are raw column names (fk_enrich never renames keys). Transform dispositions go
  to middleware, not grades (SEAM_CONTRACT §3 clarification).
- **A4 `/doc-review` queue (adds to A1's):** member count 78→79 (CLAUDE.md,
  core-domain-architecture.md §2); injection-map.md gains `get_audience_grades`;
  core-public-api.md gains the 7 grade exports; substrate.md C-6 row already corrected
  by owner (2026-06-11).
- **Program roadmap A2 status row** — left untouched for PM verification (A1 precedent:
  PM marks verified).

## Shipped

- **Version:** 2.8.0
- **Commits:** 1b5b512 (feature)
- **Date:** 2026-06-12
