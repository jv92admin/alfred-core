# Plan: Summarize Template Alignment (Option C)

**Date:** 2026-03-12
**Based on:** RESEARCH.md

## Approach

Move `summarize.md` from `prompts/templates/` to `docs/contracts/` since it's documentation, not a prompt template. Add a brief comment in `summarize.py` explaining why this node doesn't have a template file (4 short prompts, each individually overridable via `get_summarize_system_prompts()`).

## Tasks

- [ ] Move `src/alfred/prompts/templates/summarize.md` → `docs/contracts/summarize-node.md`
- [ ] Add comment block in `summarize.py` near the first `_DEFAULT_*_PROMPT` explaining the no-template-file design
- [ ] Grep for any imports/references to the old path and update them

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Target location | `docs/contracts/summarize-node.md` | It's a contracts doc, not architecture — keeps docs organized by purpose |
| Rename | `summarize.md` → `summarize-node.md` | Clearer standalone name outside the templates context |
| Code comment | Yes, brief | Prevents future confusion about "why is there no summarize template?" |

## Error Handling

N/A — no code behavior changes.

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/prompts/templates/summarize.md` | Delete (move) |
| `docs/contracts/summarize-node.md` | Create (moved file) |
| `src/alfred/graph/nodes/summarize.py` | Add explanatory comment |
