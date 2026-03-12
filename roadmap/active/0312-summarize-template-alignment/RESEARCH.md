# Research: Summarize Node Prompt Template Alignment

**Goal:** Align `summarize.md` with how other node templates work, or move it to avoid confusion.
**Type:** refactor
**Date:** 2026-03-12

## Context

Every node in `src/alfred/prompts/templates/` has a `.md` file that gets loaded as an LLM prompt template — except `summarize.md`, which is a documentation/contracts file never loaded by code. This is confusing for domain authors who expect consistent patterns.

## Function Chain

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| Response summary | `summarize.py:493-529` | Inline `_DEFAULT_RESPONSE_SUMMARY_PROMPT` string | `get_summarize_system_prompts()["response_summary"]` |
| Turn compression | `summarize.py:532-570` | Inline `_DEFAULT_TURN_COMPRESSION_PROMPT` string | `get_summarize_system_prompts()["turn_compression"]` |
| Conversation compression | `summarize.py:637-642` | Inline `_DEFAULT_CONVERSATION_COMPRESSION_PROMPT` string | `get_summarize_system_prompts()["conversation_compression"]` |
| Engagement summary | `summarize.py:676-681` | Inline `_DEFAULT_ENGAGEMENT_SUMMARY_PROMPT` string | `get_summarize_system_prompts()["engagement_summary"]` |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Response summary prompt | Inline string in function | `get_summarize_system_prompts()` | Override exists, but defaults are inline not in template |
| Turn compression prompt | Inline string in function | `get_summarize_system_prompts()` | Same |
| Conversation compression prompt | Inline string in function | `get_summarize_system_prompts()` | Same |
| Engagement summary prompt | Inline string in function | `get_summarize_system_prompts()` | Same |
| `summarize.md` | Docs/contracts file | N/A | **Misleading location** |

## Findings

1. **Summarize already has domain overrides** via `get_summarize_system_prompts()` — the hook exists
2. The issue is purely structural: `summarize.md` sits alongside actual prompt templates but isn't one
3. Summarize has **4 separate inline prompt strings** (response summary, turn compression, conversation compression, engagement summary) — unlike other nodes which load a single template file
4. The 4 prompts are short system-level instructions, not big structured templates like `reply.md` or `think.md`

## Options

**Option A: Move `summarize.md` out of templates/**
- Move to `docs/architecture/` or `docs/contracts/` — it's documentation, not a prompt
- Simplest change, no code changes needed
- Pro: Honest about what the file is
- Con: Doesn't address the inline-vs-template inconsistency

**Option B: Extract inline prompts into `summarize.md` template**
- Replace the 4 inline strings with sections loaded from `summarize.md`
- Rewrite `summarize.md` as an actual prompt template with sections
- Pro: Fully consistent with other nodes
- Con: Over-engineering — the inline prompts are short and already overridable via `get_summarize_system_prompts()`

**Option C: Move `summarize.md` + add a note**
- Move to `docs/contracts/summarize-contracts.md`
- Add a comment in `summarize.py` explaining why there's no template file (4 short prompts, already overridable)
- Pro: Clear, honest, minimal
- Con: Slight documentation churn

## Open Questions

- Is Option A (just move the file) sufficient, or does the team want full template extraction (Option B)?
- Should the move target be `docs/architecture/` or `docs/contracts/`?
