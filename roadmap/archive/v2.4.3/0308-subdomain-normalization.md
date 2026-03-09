# Subdomain Normalization on Full Act Path

**Goal:** Fix alias subdomains (e.g. "deals" -> "crm") failing schema lookup on the full Act path.
**Type:** fix

## Context

Act Quick (line 1852) called `_normalize_subdomain()` before `get_schema_with_fallback()`, so aliases worked. Full Act (line 1225) skipped normalization — alias subdomains passed through raw and caused "Unknown subdomain" errors.

## Tasks

- [x] Add `_normalize_subdomain()` call before schema lookup in full Act path

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Normalize location | After `step_type` extraction, before any subdomain usage | Covers schema lookup and all downstream uses |

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/graph/nodes/act.py` | Added line 1107: `current_step.subdomain = _normalize_subdomain(current_step.subdomain)` |

## Shipped

- **Version:** 2.4.3
- **Commits:** 1c0ca69
- **Date:** 2026-03-08
