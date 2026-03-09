# Genericize Default Prompts

**Goal:** Remove kitchen-domain contamination from core defaults so non-kitchen domains get neutral examples.
**Type:** fix

## Context

Audit of all default prompt injections revealed 3 locations with kitchen-specific examples ("recipes", "Mediterranean Chickpea & Herb Rice Bowl", "meal planning") baked into core. Also found 1 non-overridable prompt (engagement_summary).

## Tasks

- [x] Replace kitchen examples in all 3 Summarize default prompts with generic entities
- [x] Replace kitchen examples in FILTER_SCHEMA `similar` operator docs
- [x] Replace kitchen examples in reply.md editorial principles
- [x] Add `engagement_summary` key to `get_summarize_system_prompts()` override path
- [x] Update DomainConfig docstring for new 4th key
- [x] Add injection-map.md documenting every DomainConfig prompt hook

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Generic example entities | "items", "Weekly Budget Report", "pending tasks" | Neutral across all possible domains |
| Engagement summary override | Reuse existing `get_summarize_system_prompts()` dict | Consistent with the other 3 summarize overrides |

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/graph/nodes/summarize.py` | 3 default prompts genericized + engagement_summary override |
| `src/alfred/tools/schema.py` | FILTER_SCHEMA `similar` operator neutralized |
| `src/alfred/prompts/templates/reply.md` | Editorial examples neutralized |
| `src/alfred/domain/base.py` | Docstring updated for 4th key |
| `docs/architecture/injection-map.md` | New — 831-line comprehensive hook reference |

## Shipped

- **Version:** 2.4.2
- **Commits:** c834808
- **Date:** 2026-03-03
