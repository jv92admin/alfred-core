# Research: Release 2.8.0 — A4 additive minor + X2 dead-code deletion

**Goal:** Ship Track A (A1–A3) as the additive minor release 2.8.0 with X2 (legacy alias deletion + kitchen-residue sweep) riding in the same release.
**Type:** chore (release) + refactor (X2)
**Date:** 2026-06-12
**Depth:** light (hotfix-grade) — verification of given scope, not discovery. Owner decision of record (2026-06-12): one release, one CHANGELOG; no 2.8.1-that-only-deletes-dead-code.

## Context

A0–A3 are ✅ PM-verified (program roadmap). This fulfills SEAM_CONTRACT.md §4: "C-1 + C-2 ship as a normal additive `alfred` release; ledge pins the minimum version." Publish is owner-gated (hard stop before `twine upload`).

## Bucket 1 — Deletion inventory (verified against live code)

Grep across repo (excluding `roadmap/`) for the 6 constant names: **only** `schema.py`, `tools/__init__.py`, and the PITFALLS incident line match. No test, no src consumer, no doc claim. `web/` does not exist in the repo. Zero-consumer claim re-verified today.

| Site | Lines | What goes |
|------|-------|-----------|
| `src/alfred/tools/schema.py` | 341–362 | Module `__getattr__` + `_ATTR_MAP` (6 names) + "Legacy constant access" comment block |
| `src/alfred/tools/__init__.py` | 39–54 | Lazy `__getattr__` hook (A3's minimal bridge — deletion fodder by design) |
| `src/alfred/tools/__init__.py` | 71 | `"SUBDOMAIN_REGISTRY"` in `__all__` |
| `src/alfred/tools/__init__.py` | 13 | Docstring line "SUBDOMAIN_REGISTRY: Maps subdomains to tables" |
| `src/alfred/tools/__init__.py` | 17 | `from typing import Any` — becomes unused once `__getattr__` is gone |

**Stays:** the `_get_*` helper functions in schema.py (`_get_field_enums` etc.) — live consumers: `get_subdomain_context()`, `get_schema_with_fallback()`, `validate_schema_drift()`.

**Verification = the existing A3 apparatus, no new gate** — PITFALLS `import-time-domain-coupling` Check verbatim: *"`python -c "import alfred.context"` and `python -c "import alfred.tools"` succeed in a fresh interpreter with NO domain registered (`tests/core/test_import_isolation.py` covers the seam path in subprocesses)."* Plus full suite + `compileall` (PITFALLS `unimported-module-rot` Check).

## Bucket 2 — Residue classification (every edit, tiered)

**Tier 1 — comments/docstrings only, zero functional lines** (review standard for every pipeline-file edit):

| Site | Residue |
|------|---------|
| `src/alfred/tools/crud.py:458` | "ingredient enrichment, deduplication" in `db_create` docstring |
| `src/alfred/__init__.py:5-7` | "Pantry: Kitchen inventory, recipes, meal planning / Coach / Cellar" module docstring |
| `src/alfred/tools/schema.py:9-10` | "Kitchen-specific constants (FIELD_ENUMS, SEMANTIC_NOTES, etc.) live in alfred.domain.kitchen.schema" |
| `src/alfred/tools/schema.py:19` | "Constants moved to alfred.domain.kitchen.schema (Phase 3a)" comment |
| `src/alfred/tools/schema.py:316-318` | "Kitchen Constants — Moved to …" section banner |
| `src/alfred/tools/schema.py:439` | `validate_schema_drift` docstring says "Compare FALLBACK_SCHEMAS" (the deleted alias name) |

Tier 1 classification verified: greps for `__doc__`, `model_json_schema`, `.schema()` across `src/` → **no matches**; Pydantic model/function docstrings never reach prompt bytes in this codebase.

**Tier 2 — deliberate default-prompt-text changes** (alter prompt bytes for domains that don't override the hooks; own CHANGELOG "Changed" entry):

| Site | Residue |
|------|---------|
| `src/alfred/prompts/templates/act/read.md:142` | `"quick weeknight meals"` semantic-search example |
| `src/alfred/tools/schema.py:295` | `FILTER_SCHEMA` `in` example: `["milk", "eggs"]` |

**Adjacent residue found during research, NOT in the given scope** (flagged for explicit owner decision in PLAN, not silently folded):

| Site | Residue | Tier if included |
|------|---------|------------------|
| `src/alfred/prompts/templates/act/read.md:132` | `"light summer dinner"` semantic-search example | Tier 2 (same template, same class as :142) |
| `src/alfred/tools/schema.py:296` | `FILTER_SCHEMA` ilike example: `"%chicken%"` | Tier 2 (same constant as :295) |
| `src/alfred/tools/crud.py:184-188` | `DbCreateParams` docstring: `{"name": "milk"}` / `{"name": "eggs"}` examples | Tier 1 (docstring; grep-verified no prompt path) |

## Bucket 3 — Release mechanics findings

- `pyproject.toml:3` = `2.7.0`; wheel target (`pyproject.toml:33`) = `packages = ["src/alfred"]` — confirms the docs' "4 wheel targets" claim is stale.
- **Finding (not in scope): `src/alfred/__init__.py:10` has `__version__ = "2.4.0"`** — three minors stale vs pyproject. PITFALLS `version-triple-sync` covers pyproject/CHANGELOG/tag but not this attribute. Proposed: sync to `2.8.0` in this release + CHANGELOG "Fixed" line.
- **Finding: A3's work is uncommitted.** Working tree holds the entire A3 diff (assembly.py, tests, schema.py/tools fixes, roadmap/PITFALLS edits). A1/A2 each got their own `feat:` commit. Proposed: commit A3 as its own `feat:` commit first (traceability precedent), then the single A4+X2 release commit. The owner's "one commit" decision read as scoping A4+X2 together — not as squashing A3's feature into the release commit. Needs plan approval.
- **Constraint (owner, mid-research): stay on `main`, no branching.** All commits land directly on main.
- Archive targets exist: `0611-protocol-split/`, `0611-grade-registry/`, `0612-assembly-entrypoints/` (each PLAN/RESEARCH/SUMMARY), `0612-a3-grounding/` (GROUNDING.md only) → `roadmap/archive/v2.8.0/`. Stays active: `0610-*` program/design docs, `0610-prewrite-update-delete` (B1), `0610-declared-modes-parameterized-shapes` (C), and `0309-semantic-search-gap` (predates the program; untouched by this release).

## Doc-review queue (consolidated from the 3 SUMMARYs + scope; FINAL numbers — 80 members, not recounted)

| Doc | Fix |
|-----|-----|
| `CLAUDE.md:39` | "DomainConfig protocol (75 methods)" → 80 members; base.py is now the composition shim (bodies in `domain/context.py` / `domain/agent.py`) |
| `docs/architecture/core-domain-architecture.md` | §2 census 75 → 80 (23 abstract, 57 defaulted); §7/file-table "base.py (1,135 lines)" → composition shim + two protocol modules; `:67` stale `base.py:156` anchor; §1/§61 in-repo `src/alfred_kitchen/` tree (stale — `src/` holds only `alfred`); `:239` `get_table_format` listed without stale-consumer caveat |
| `docs/architecture/overview.md:67` | "(75 methods)" → 80 ("everywhere it appears") |
| `docs/architecture/injection-map.md` | + `get_audience_grades` row, + `get_table_notes` row; `get_table_format` "used by the injection system" consumer claim is stale (no consumer — A1 watch item) |
| `docs/architecture/core-public-api.md` | + `alfred.context` surface (DomainContext, 7 grade names, 2 async entrypoints, ShapedPayload + `SCHEMA_VERSION`, error family, identity policies, chain-link module); `:179` stale "4 wheel targets" `packages` list → `["src/alfred"]`; `:77`/`:227` 75 → 80; `:231` agents/base.py "319 lines" — verify against live file during execution |

X2's deletions do not move the member count — 80 stands (aliases were module attributes, not protocol members). A1's suggested injection-map "Context/Agent column" is NOT in the owner's final queue — deferred, noted here so it isn't rediscovered.

## Gates (same bar as A1–A3)

- Full suite green (266 at A3 baseline).
- Import-isolation tests green (the X2 verification apparatus — PITFALLS `import-time-domain-coupling` Check).
- `python -m compileall src/alfred -q` exit 0 (`unimported-module-rot` Check).
- ruff check + format on touched files.
- mypy clean `--no-incremental` run: zero NEW errors is the gate; error total is the metric (368 at A3). Deletions may reduce the total — document the new baseline in SUMMARY.
- `version-triple-sync` (PITFALLS): pyproject + CHANGELOG + tag agree; tag pushed only at publish-confirm.

## Open Questions (resolved in PLAN as proposals)

1. Include the 3 adjacent residue sites? (recommended: yes, with tier labels)
2. Sync `alfred.__version__` → 2.8.0? (recommended: yes, CHANGELOG Fixed)
3. Separate `feat:` commit for A3 before the release commit? (recommended: yes)
