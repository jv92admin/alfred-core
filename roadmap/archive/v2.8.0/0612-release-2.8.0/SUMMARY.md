# Summary: Release 2.8.0 — A4 additive minor + X2

**Date:** 2026-06-12

## What Was Done

- **A3 committed separately** as `6b85a63` (feat: state-free assembly entrypoints) per A1/A2 precedent — owner-approved reading of "one commit" as scoping A4+X2, not folding A3 in.
- **Bucket 1 — legacy alias layer deleted:** `schema.py` module `__getattr__` + `_ATTR_MAP` (the 6 constant names FIELD_ENUMS / SEMANTIC_NOTES / FALLBACK_SCHEMAS / SUBDOMAIN_SCOPE / SUBDOMAIN_REGISTRY / SUBDOMAIN_EXAMPLES); `tools/__init__.py` lazy `__getattr__` hook, `__all__` entry, docstring line, now-unused `typing.Any` import. Verified by the existing A3 apparatus per PITFALLS `import-time-domain-coupling` Check — domain-free `import alfred.context` / `import alfred.tools` in fresh interpreters, full suite, compileall. No new gate invented. Deleted names now raise Python's own `AttributeError`.
- **Bucket 2 Tier 1 (docstrings/comments only, zero functional lines):** crud.py "ingredient enrichment" + DbCreateParams milk/eggs examples; alfred/`__init__.py` Pantry/Coach/Cellar docstring; schema.py kitchen-constants pointer, "Phase 3a" comment, kitchen banner, FALLBACK_SCHEMAS docstring mention.
- **Bucket 2 Tier 2 (deliberate prompt-byte changes, own CHANGELOG "Changed" entry):** `FILTER_SCHEMA` `["milk","eggs"]` → `["active","pending"]`, `"%chicken%"` → `"%draft%"`; `act/read.md` `"quick weeknight meals"` → `"quick low-effort options"`, `"light summer dinner"` → `"budget-friendly options"`. All three owner-approved adjacent finds included, explicitly tiered.
- **Version:** pyproject.toml 2.7.0 → 2.8.0; `alfred.__version__` "2.4.0" → "2.8.0" (was three minors stale); **new `tests/core/test_version_sync.py`** pins `__version__` to `importlib.metadata.version("alfredagain")` (owner addition — the mechanical fix, not just the correction).
- **CHANGELOG 2.8.0:** Added (protocol split / grade registry / assembly entrypoints / get_table_notes) · Removed (aliases, semver rationale inside the entry) · Changed (Tier 2) · Fixed (import-time coupling, `__version__`). Approved verbatim.
- **Doc-review queue cleared (final numbers, 80 members):** CLAUDE.md key-files (80 + assembly.py row); core-domain-architecture.md (two-protocol census 36/44 → 80 = 23 abstract + 57 default, authoritative-count pointer to the sort-freeze test, in-repo kitchen tree removed, registration snippet shows grade validation, all stale base.py anchors re-pointed, key-files line counts); overview.md (80); injection-map.md (+`get_audience_grades`, +`get_table_notes`, `get_table_format` stale consumer claim marked); core-public-api.md (new `alfred.context` seam section, "4 wheel targets" → `packages = ["src/alfred"]`, §5 rewritten as Packaging — extraction already happened, 80 members, key-files line counts incl. agents/base.py 319→250).
- **PITFALLS:** new entry `recorded-number-drift` (P2, silent-failure, incident-sourced: `__version__` stale through three minors; in-code sibling of `doc-count-drift`).
- **Archived:** 0611-protocol-split, 0611-grade-registry, 0612-assembly-entrypoints, 0612-a3-grounding → `roadmap/archive/v2.8.0/`; Shipped sections filled (fdc5840, 1b5b512, 6b85a63). Left active: 0610 program/design docs, 0610-prewrite-update-delete (B1), 0610-declared-modes-parameterized-shapes (C), 0309-semantic-search-gap (predates the program). This folder archives after publish confirmation.

## Gates

| Gate | Result |
|------|--------|
| Full suite | **267 passed** (266 baseline + 1 new version-sync test; zero existing tests edited) |
| Import isolation (X2 verification) | Domain-free `import alfred.context` + `import alfred.tools` in fresh interpreters ✅; subprocess tests in suite ✅ |
| compileall | Exit 0 |
| ruff (touched files) | check + format clean (crud.py: check clean; format not applied — see Decisions) |
| mypy clean `--no-incremental` | **366 errors** (was 368) — zero new; the −2 are the deleted `__getattr__` code's own errors. **New baseline: 366.** |
| version-triple-sync | pyproject = CHANGELOG = 2.8.0; tag `v2.8.0` at release commit, pushed at publish-confirm |

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| `ruff format` on crud.py | NOT applied (check passes; format violations pre-exist in untouched hunks) | Formatting would reflow ~8 hunks unrelated to the Tier 1 docstring edits, violating the crisp-diff standard ("zero functional lines" review hunks). A1 gate precedent: zero NEW violations, repo-wide cleanup is not this work item |
| Tier 2 replacement values | `["active","pending"]` / `"%draft%"` / `"budget-friendly options"` / `"quick low-effort options"` | Domain-neutral; reuses the generic register the file already established (`"high priority tasks"`, `"budget-friendly options"`) |
| core-public-api.md §5 | Rewritten "Multi-Repo Extraction" → "Packaging" | The section described extraction as future; it shipped (package = `alfredagain`, wheel = `src/alfred` only). Fixing only the toml block would leave contradicting prose |
| core-domain-architecture.md census | Replaced 8-concern-area table with the two-protocol census + pointer to the sort-freeze test | The old table's row-level counts were unverifiable without a recount (forbidden — final numbers given); the split census is exact (36+44=80, 15+8=23, 21+36=57) and the test is the durable authority (doc-count-drift fix: stop duplicating numbers docs don't need) |
| 0612-release-2.8.0 folder | Stays active until publish confirmed | Its own Shipped section can't be truthfully filled before the owner publishes |

## Deviations from Plan

1. **None of substance.** Every Reuse Map row honored (isolation tests, compileall, DomainConfig accessors); file list exact plus `docs/architecture/overview.md`'s "(75 methods)" (covered by "everywhere it appears").
2. Mechanical: ruff `--fix` import-sort in `tools/__init__.py` (I001 surfaced by the `Any` removal); `ruff format` trailing-newline fix in `alfred/__init__.py`.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/tools/schema.py` | Bucket 1 deletion + Tier 1 docstrings + Tier 2 FILTER_SCHEMA values |
| `src/alfred/tools/__init__.py` | Bucket 1 deletion (hook, `__all__`, docstring, unused import) |
| `src/alfred/tools/crud.py` | Tier 1 docstrings only |
| `src/alfred/__init__.py` | Docstring de-domained; `__version__` → 2.8.0 |
| `src/alfred/prompts/templates/act/read.md` | Tier 2: two semantic-search example values |
| `pyproject.toml` | 2.7.0 → 2.8.0 |
| `tests/core/test_version_sync.py` | NEW — version-sync pin (owner addition) |
| `CHANGELOG.md` | 2.8.0 entry (approved verbatim) |
| `CLAUDE.md`, `docs/architecture/{core-domain-architecture,core-public-api,injection-map,overview}.md` | Doc-review queue (details above) |
| `.claude/PITFALLS.md` | + `recorded-number-drift` |
| `roadmap/active/0610-program-roadmap.md` | A4 + X2 rows ✅; status line → Track A COMPLETE |
| `roadmap/archive/v2.8.0/*` | Four folders archived, Shipped sections filled |

## Shipped

- **Version:** 2.8.0 — published: https://pypi.org/project/alfredagain/2.8.0/
- **Commits:** fdc5840 (A1), 1b5b512 (A2), 6b85a63 (A3), 0db524e (release); tag `v2.8.0`
- **Date:** 2026-06-12 — owner-confirmed publish (upload first, tag push second)
