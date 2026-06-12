# Plan: Release 2.8.0 — A4 additive minor + X2

**Date:** 2026-06-12
**Based on:** RESEARCH.md

## Approach

One release, three buckets: (1) delete the legacy domain-backed alias layer, verified by the existing A3 isolation apparatus; (2) kitchen-residue sweep under the two-tier diff standard; (3) pm Ship mechanics — version 2.8.0, CHANGELOG, consolidated `/doc-review`, gates, archive. All commits land directly on **main** (owner constraint: no branching). **Hard stop before PyPI publish.**

## Commit sequence (all on main)

1. `feat: state-free assembly entrypoints (A3, substrate C-5/E2)` — the currently-uncommitted A3 working tree, committed as its own feature per A1/A2 precedent.
2. `release: 2.8.0 — Track A substrate seam + X2 legacy alias deletion` — buckets 1–3, one commit per owner decision.
3. Tag `v2.8.0` created locally with the release commit; **pushed only at publish-confirm** (PITFALLS `version-triple-sync`).

## CHANGELOG draft (verbatim — this is the approval artifact)

```markdown
## [2.8.0] — 2026-06-12

### Added
- **Protocol split: `DomainContext` / `AgentConfig`** — the 80-member `DomainConfig` ABC
  is now composed from two protocols: `DomainContext` (knowledge & data shaping, incl.
  `CRUDMiddleware.pre_write`) and `AgentConfig` (pipeline & LLM concerns).
  `class DomainConfig(DomainContext, AgentConfig)` — existing domains work unchanged,
  zero migration. New seam import: `from alfred.context import DomainContext` is
  guaranteed free of langgraph/instructor imports (enforced by isolation tests).
- **Audience-grade registry** — domains declare named grades as field strip-sets via the
  new defaulted `DomainContext.get_audience_grades()` hook. Core ships well-known grades
  `"reply"` and `"external"`; `register_domain()` validates `external ⊇ reply` per table
  and fails loudly (`GradeRegistryError`). `StripSet`, `GradeRegistry`, and the 7 public
  grade names are exported from `alfred.domain` and `alfred.context`.
- **State-free assembly entrypoints** — `async assemble_entity_context()` and
  `async assemble_subdomain_read()` in `alfred.context`: no `AlfredState`, no session, no
  LLM call on any path. Return a frozen `ShapedPayload` (`schema_version="1"` — versioned
  external contract). Core validates filters (loud typed errors, never a silent empty
  read); identity handling is a policy parameter; the underlying chain links are
  importable from `alfred.context.assembly` for richer consumers.
- **`get_table_notes(table)` hook** — defaulted `DomainContext` member supplying
  per-table semantic notes for assembly headers (defaults to the owning subdomain's
  notes; zero migration).

### Removed
- **Legacy domain-backed module aliases** — `FIELD_ENUMS`, `SEMANTIC_NOTES`,
  `FALLBACK_SCHEMAS`, `SUBDOMAIN_SCOPE`, `SUBDOMAIN_REGISTRY`, `SUBDOMAIN_EXAMPLES` are
  no longer importable from `alfred.tools.schema` or `alfred.tools` (the module
  `__getattr__` alias layers are deleted). Removed in a minor release because the names
  were undocumented, had zero grep-verified consumers, their documented consumer
  (`web/schema_routes.py`) was already deleted, and they were broken-by-design without a
  registered domain. Use the `DomainConfig` accessor methods instead
  (`get_field_enums()`, `get_subdomain_registry()`, …).

### Changed
- **Built-in prompt defaults de-domained** — the built-in `FILTER_SCHEMA` example values
  (`["milk", "eggs"]` → generic) and the `act/read.md` semantic-search examples
  (`"quick weeknight meals"` → generic) no longer assume a kitchen domain. This changes
  default prompt bytes only for domains that don't override `get_filter_schema()` or the
  Act templates; overriding domains are unaffected.

### Fixed
- **Import-time domain coupling** — importing `alfred.tools` (and therefore
  `alfred.context`) no longer requires a registered domain. Domain-free import of the
  seam module is enforced by subprocess isolation tests.
- **`alfred.__version__`** — was stale at `"2.4.0"`; now matches the package version.
```

*(Pending approval decisions below may add `"light summer dinner"` / `"%chicken%"` to the Changed entry — drafted as included.)*

## Decisions (proposals needing approval)

| # | Decision | Proposal | Why |
|---|----------|----------|-----|
| 1 | Adjacent Tier 2 residue (`read.md:132` "light summer dinner", `schema.py:296` "%chicken%") | **Include** in Tier 2 | Same class, same files, same CHANGELOG entry; leaving them makes the sweep incomplete |
| 2 | Adjacent Tier 1 residue (`crud.py:184-188` DbCreateParams milk/eggs docstring) | **Include** in Tier 1 | Docstring-only; grep-verified no prompt path (RESEARCH) |
| 3 | `alfred.__version__` stale at 2.4.0 | Sync to `"2.8.0"` + CHANGELOG Fixed line | Public attribute, three minors wrong |
| 4 | A3 commit separation | Own `feat:` commit before the release commit | A1/A2 precedent; "one commit" decision scopes A4+X2, not A3's feature |
| 5 | Tag timing | Tag at release commit, push tag only at publish-confirm | `version-triple-sync` without publishing pressure |

## Reuse Map

| Capability | Reuse / New | Symbol + Path | Why |
|------------|-------------|---------------|-----|
| Deletion verification | Reuse | `tests/core/test_import_isolation.py` (subprocess domain-free imports) | PITFALLS `import-time-domain-coupling` Check verbatim — no new gate invented |
| Rot check | Reuse | `python -m compileall src/alfred -q` | PITFALLS `unimported-module-rot` Check |
| Constant access post-deletion | Reuse | `DomainConfig.get_field_enums()` etc. + `_get_*` helpers in `tools/schema.py` (live consumers: `get_subdomain_context`, `validate_schema_drift`) | The aliases were redirects to these; the redirects go, the methods stay |
| New code | **None** | — | Pure deletion + text edits + docs + version mechanics |

## Files to Change

**Bucket 1 — deletions:**

| File | Change |
|------|--------|
| `src/alfred/tools/schema.py` | Delete `__getattr__` + `_ATTR_MAP` + legacy comment (≈lines 341–362) |
| `src/alfred/tools/__init__.py` | Delete `__getattr__` hook, `"SUBDOMAIN_REGISTRY"` from `__all__`, docstring line, now-unused `from typing import Any` |

**Bucket 2 — Tier 1 (comments/docstrings ONLY — review standard: zero functional lines in these hunks):**

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py` | `:458` "ingredient enrichment" → generic; `:184-188` milk/eggs docstring examples → generic (Decision 2) |
| `src/alfred/__init__.py` | Pantry/Coach/Cellar docstring → domain-agnostic |
| `src/alfred/tools/schema.py` | `:9-10` kitchen-constants pointer, `:19` "Phase 3a" comment, `:316-318` banner, `:439` FALLBACK_SCHEMAS docstring mention |

**Bucket 2 — Tier 2 (deliberate prompt-byte changes, own CHANGELOG entry):**

| File | Change |
|------|--------|
| `src/alfred/prompts/templates/act/read.md` | `:142` "quick weeknight meals" → generic; `:132` "light summer dinner" → generic (Decision 1) |
| `src/alfred/tools/schema.py` | `FILTER_SCHEMA` `:295` `["milk", "eggs"]` → generic; `:296` `"%chicken%"` → generic (Decision 1) |

**Bucket 3 — release mechanics + doc-review:**

| File | Change |
|------|--------|
| `pyproject.toml` | `2.7.0` → `2.8.0` |
| `src/alfred/__init__.py` | `__version__` → `"2.8.0"` (Decision 3) |
| `CHANGELOG.md` | The 2.8.0 entry above |
| `CLAUDE.md` | Key-files row: 80 members, base.py = composition shim |
| `docs/architecture/core-domain-architecture.md` | Census 75→80 (23 abstract / 57 defaulted); split described; stale line-counts, anchors, in-repo kitchen tree; `get_table_format` caveat |
| `docs/architecture/overview.md` | `:67` 75→80 |
| `docs/architecture/injection-map.md` | + `get_audience_grades`, + `get_table_notes` rows; fix `get_table_format` stale consumer claim |
| `docs/architecture/core-public-api.md` | + `alfred.context` surface (DomainContext, 7 grade names, entrypoints, ShapedPayload, errors, identity policies); fix "4 wheel targets" → `["src/alfred"]`; 75→80; verify agents/base.py line count |
| `roadmap/active/0610-program-roadmap.md` | A4 + X2 rows → ✅ shipped v2.8.0 |
| `roadmap/active/0612-release-2.8.0/SUMMARY.md` | New |

**Archive (after gates, in release commit):** `0611-protocol-split/`, `0611-grade-registry/`, `0612-assembly-entrypoints/`, `0612-a3-grounding/` → `roadmap/archive/v2.8.0/`; fill each SUMMARY's Shipped section. **Stays active:** `0610-*` program/design docs, `0610-prewrite-update-delete` (B1), `0610-declared-modes-parameterized-shapes` (C), `0309-semantic-search-gap` (untouched by this release).

## Tasks

- [ ] Commit A3 working tree as `feat:` commit (main)
- [ ] Bucket 1 deletions
- [ ] Bucket 2 Tier 1 edits (verify: zero functional lines in diff hunks)
- [ ] Bucket 2 Tier 2 edits
- [ ] Version bump (pyproject + `__version__`) + CHANGELOG entry
- [ ] Doc-review queue (table above)
- [ ] Gates: full suite · isolation tests · compileall · ruff (touched) · mypy clean run (zero new; record total)
- [ ] Archive folders + fill Shipped sections + roadmap rows
- [ ] SUMMARY.md (incl. new mypy baseline if reduced)
- [ ] Release commit on main + push + `python -m build`
- [ ] **HARD STOP** — present CHANGELOG, version, gate results, artifact list; owner publishes

## Error Handling

No new runtime paths. Deleted names now raise plain `AttributeError` from Python itself (loud, correct). If any gate fails: stop, diagnose, no force-push, no gate-skipping.

## Definition of Done

- [ ] `pytest tests/ -v` green (≥266 baseline; zero existing tests edited)
- [ ] Domain-free `import alfred.context` / `import alfred.tools` in fresh interpreters (PITFALLS `import-time-domain-coupling` Check — the X2 verification)
- [ ] `compileall` exit 0 (`unimported-module-rot` Check)
- [ ] mypy clean `--no-incremental`: zero NEW errors; total ≤ 368, new baseline documented
- [ ] ruff check + format clean on touched files
- [ ] `version-triple-sync`: pyproject = CHANGELOG = tag
- [ ] Tier 1 hunks contain zero functional lines (review standard)
- [ ] Built artifacts exist; publish NOT executed
