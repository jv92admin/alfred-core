# Research: Reply Continuity Guidance Override

**Goal:** Allow domains to customize or suppress the hardcoded reply continuity guidance.
**Type:** feat
**Date:** 2026-03-12

## Context

When `current_turn > 1`, `reply.py` injects hardcoded continuity guidance ("no Hello!", "don't introduce yourself"). There's no DomainConfig hook to override this, unlike nearly every other prompt injection point. Different domains may want different conversational tones.

## Function Chain

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| Reply prompt load | `reply.py:36-57` `_get_prompts()` | Loads reply template, checks `domain.get_reply_prompt_content()` | `get_reply_prompt_content()` |
| Reply subdomain | `reply.py:52-55` | Injects subdomain guide into template | `get_reply_subdomain_guide()` |
| Conversation flow | `reply.py:102-137` `_build_conversation_flow_section()` | Builds turn/phase info + **hardcoded continuity guidance** | **None — this is the gap** |
| Reply assembly | `reply.py` `reply_node()` | Combines template + flow section + context into final prompt | N/A |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Reply template | Core `reply.md` | `get_reply_prompt_content()` | No |
| Subdomain guide | None | `get_reply_subdomain_guide()` | No |
| System prompt | Core default | `get_system_prompt()` | No |
| Continuity guidance | Hardcoded lines 132-135 | **None** | **Yes** |

## Findings

1. The hardcoded guidance is in `_build_conversation_flow_section()` at lines 131-135
2. It's 3 bullet points injected when `current_turn > 1`
3. The function also includes turn number and phase info (from reasoning trace) — those are factual and shouldn't need override
4. Only the **guidance bullets** (lines 132-135) need a domain hook
5. This is a clean addition: add an optional `get_reply_continuity_guidance(turn: int) -> list[str] | None` to DomainConfig with the current text as default

## Open Questions

- Should the method return raw lines or a formatted block? Lines are more composable.
- Should `None` return mean "use default" and empty list mean "suppress entirely"? That's the standard pattern elsewhere.
