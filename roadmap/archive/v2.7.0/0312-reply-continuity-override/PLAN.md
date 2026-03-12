# Plan: Reply Continuity Guidance Override

**Date:** 2026-03-12
**Based on:** RESEARCH.md

## Approach

Add an optional `get_reply_continuity_guidance()` method to DomainConfig. The Reply node calls it when `current_turn > 1`. Returns `None` for default behavior, or a list of strings for custom guidance (empty list = suppress entirely). Non-breaking: existing domains don't need to change.

## Tasks

- [ ] Add `get_reply_continuity_guidance(self, current_turn: int) -> list[str] | None` to DomainConfig in `base.py`
- [ ] Update `_build_conversation_flow_section()` in `reply.py` to call the new hook
- [ ] Add test for default behavior (returns current hardcoded text)
- [ ] Add test for custom override
- [ ] Add test for empty list (suppression)
- [ ] Update DomainConfig method count in docs (74 → 75)

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Return type | `list[str] \| None` | `None` = use default, `[]` = suppress, `[...]` = custom. Consistent with other optional hooks |
| Turn number param | Pass `current_turn` | Domain may want turn-aware guidance (e.g., stricter on turn 2, relaxed by turn 5) |
| Placement in base.py | Near `get_reply_subdomain_guide()` (~line 1305) | Group reply-related hooks together |

## Error Handling

If the method raises, fall back to default guidance and log a warning.

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/domain/base.py` | Add `get_reply_continuity_guidance()` method |
| `src/alfred/graph/nodes/reply.py` | Call hook in `_build_conversation_flow_section()` |
| `tests/` | Tests for default, override, and suppression |
| `docs/` | Update method count (74 → 75) |
