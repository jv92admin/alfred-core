# Summary: Semantic Search — Documentation Gap & Crash Path

**Date:** 2026-03-09

## What Was Done

- Added `similar` operator row to `crud.md` operator table with "(domain middleware required)" note and explanation paragraph
- Added "Semantic Search" section to `read.md` under Advanced Patterns with single-filter and combined-filter examples
- Both templates now explicitly state: "If the domain has not implemented semantic search, this operator will error"
- Fixed operator count in `core-public-api.md` (12 → 14)
- Added `similar` row to `crud-and-database.md` filter table with explanation of the crash-by-design behavior
- Added `similar` to operator list in `alfred-domain-design-guide.md` (customer-facing)

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| FILTER_SCHEMA vs crud.md alignment | Keep both; crud.md is superset | They no longer contradict (both include `similar`). FILTER_SCHEMA is a summary; crud.md is the detailed reference. Consolidation is a separate concern. |
| Error warning in prompts | Added "will error" language | Matches project principle: loud failures over silent defaults. Domain owners reading templates see the requirement immediately. |
| crud-and-database.md | No changes | Already had complete operator docs including `similar` and the full middleware chain |

## Deviations from Plan

None.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/prompts/templates/act/crud.md` | Added `similar` row to operator table + semantic search explanation paragraph |
| `src/alfred/prompts/templates/act/read.md` | Added "Semantic Search" section under Advanced Patterns with two examples |
| `docs/architecture/core-public-api.md` | Fixed operator count: 12 → 14 |
| `docs/architecture/crud-and-database.md` | Added `similar` row to filter table + crash-by-design explanation |
| `docs/bridge/alfred-domain-design-guide.md` | Added `similar` to operator list |

## Shipped

- **Version:** (filled on archive)
- **Commits:** (filled on archive)
- **Date:** (filled on archive)
