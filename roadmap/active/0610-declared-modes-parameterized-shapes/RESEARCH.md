# Research: Declared Modes + Parameterized Shapes

**Goal:** Replace LLM-detected quick mode with caller-declared modes, redefine a mode as `(shape, dials)` data, and harvest the prompt gains that deterministic mode resolution unlocks.
**Type:** refactor
**Date:** 2026-06-10

## Context

Today there are two overlapping fast-path mechanisms: the caller passes `mode_context` (QUICK carries `skip_think: True`), *and* Understand independently LLM-classifies `quick_mode` per message. Two mechanisms, one job, and they can disagree. Understand is doing double duty — memory work (reference resolution, context curation) and control-flow work (routing classification) in one LLM call.

The compromise we've settled on: **the consumer declares the orchestration demand per request.** Full thinking = full loop, read mode = quick path, etc. Mode is resolved *before* the graph runs. This deletes the duplicate classification layer, demotes Understand to its coherent job, and — the real prize — makes prompt assembly a pure function of `(shape, dials, domain injections)`, fully determined before any LLM call.

## The Framing

### Shapes stay code, modes become data

The node chain cannot be fully configurable because system prompts depend materially on the mode (an Act prompt after Understand differs per mode). But there are really only ~3 **graph shapes**:

| Shape | Path | Owns |
|-------|------|------|
| **full** | Understand → Think → Act⟲ → Reply → Summarize | Routing + superset prompt skeleton |
| **single-shot** | Understand → Act-Quick → Reply → Summarize | Slim prompt, reduced action union |
| **bypass** | Domain handler, skips graph | Domain-owned flow + handoff |

Everything else about a mode is **dials**: `max_steps`, `proposal_required`, verbosity, model tier, `examples_in_prompt`, `profile_detail`, tool availability per step type.

- **Shape**: small hardcoded enum. Owns routing and prompt skeleton. Stays rigid, as it must.
- **Mode**: a named `(shape, dials)` bundle, declared by the caller per request. QUICK = (single-shot, terse, low tier). PLAN = (full, 8 steps, proposal). A domain can define "audit" = (full, 12 steps, proposal always, terse) without touching core routing.

This converts the frozen `MODE_CONFIG` constant (`src/alfred/core/modes.py:31-56`) into domain-overridable data and gets "custom modes" nearly free, without giving up "prompts depend on mode."

### Prompt gains (the main payoff)

Removing mode ambiguity means the model is *told* what mode it's in — and better, the prompt is *compiled for* that mode. Instructions that aren't present can't be misfollowed. Gains are not evenly distributed:

1. **Understand — biggest single win.** Delete the quick-mode detection table, classification instructions, and the `quick_mode`/`quick_intent`/`quick_subdomain` fields from `UnderstandOutput`. Single-objective call: resolve refs, curate context, flag ambiguity. In read shape it can also skip curating write-relevant context.
2. **Act — schema gains, not just prompt gains.** The 15-section builder (`src/alfred/prompts/injection.py`) becomes shape-gated. Read-shape Act drops write/generate step templates, create/update/delete CRUD reference, batch manifest instructions, and the multi-step loop contract. The **action union shrinks per shape** (generalizing the existing `ActQuickDecision` vs `ActDecision` split) → smaller action space → fewer malformed outputs → fewer retries on the cheap model.
3. **Think — exists only in full shape.** No more "if simple, plan fewer steps" hedging. Dials become stated facts in the prompt ("budget: 8 steps, proposal required") instead of behavior to infer. The deepest loop keeps the superset prompt — that's fine; gains come from the other shapes shedding the superset.
4. **Reply — cascade becomes static.** The priority cascade (clarification → quick_result → proposal → error → full LLM) is statically known per shape; quick shape can default to the deterministic formatter with LLM as fallback.

### Sleeper wins

- **Prefix caching.** Per `(domain, shape)` the prompt skeleton is byte-stable across requests. Structure assembly so the static skeleton is a stable prefix and only entity context + user message vary at the tail → provider-side prompt caching on every call. Direct latency/cost cut, zero model risk.
- **Golden-snapshot tests.** Deterministic assembly makes prompt regression testing per-shape file diffs in CI, instead of combinatorial conditional assembly.
- **Deterministic model tiering.** Read shape = mini tier everywhere; cost becomes predictable per mode — a PyPI consumer can price their product.
- **Per-shape evals** become possible (e.g., read-shape filter-construction accuracy) instead of whole-pipeline evals only.

### Implementation caution

Do **not** fork into N standalone per-shape templates — they will drift, and prompt drift is invisible until behavior degrades. Keep the section-based builder and make sections **shape-gated**: composition with flags, single source of truth per section. Full shape is the superset; other shapes are subtractions expressed in code, not copies.

## Function Chain

| Stage | Function/File | What Happens Today | Change Under This Framing |
|-------|--------------|--------------------|---------------------------|
| Entry | `run_alfred_streaming()` / `run_alfred()` (`src/alfred/graph/workflow.py:530,672`) | `mode_context` passed in; UI selection already highest priority | Mode (= named shape+dials bundle) becomes the authoritative routing input, resolved before graph runs |
| Mode resolution | `ModeContext.from_dict()` (`src/alfred/core/modes.py:109-120`) | Falls back to PLAN; `MODE_CONFIG` frozen constant | `MODE_CONFIG` → data; domain can re-tune bundles / define named modes mapping onto shapes |
| Understand | `understand.py` (~:40-93) | Resolves entities AND LLM-detects `quick_mode`/`quick_intent`/`quick_subdomain` | Delete classification; pure entity resolution + clarification + curation; slimmer prompt + output schema |
| Routing | `route_after_understand()` (`workflow.py:374-397`) | Reads `understand_output.quick_mode` | Reads declared shape flags (`skip_think`) — deterministic |
| Act | `act_node` / `act_quick_node` (`act.py:1889-2048`), `injection.py` (15 sections) | One hedged template, mode-conditional sections | Shape-gated sections; per-shape action unions; stable-prefix assembly for caching |
| Think | `think.py` | Hedges across complexity | Full shape only; dials injected as stated facts |
| Reply | `reply.py` (cascade ~:549) | Runtime priority cascade | Cascade statically known per shape; quick → deterministic formatter default |
| Summarize | `summarize.py` | Unchanged | Unchanged |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap → Resolution |
|------------|----------------|-----------------|------------------|
| Mode set | Hardcoded enum QUICK/PLAN/CREATE (`modes.py:22-28`) | None | Modes become named `(shape, dials)` data; domains define bundles |
| Mode dials | Frozen `MODE_CONFIG` (`modes.py:31-56`) | None | Domain-overridable per mode |
| Quick-path detection | LLM in Understand + domain prompt table via `get_understand_prompt_content()` | Prompt-level only | Deleted from core; classification is the consumer's job (see Open Questions) |
| Graph shapes / routing | Hardcoded (`workflow.py:374-425, 427-545`) | None | Stays hardcoded — by design |
| Act prompt sections | Mode-conditional hedging | Per-section domain hooks | Shape-gated composition, single source per section |
| Tool availability | `get_tool_enabled_step_types()` (`base.py:491-510`) | Domain | Could become a per-mode dial |
| Model tier | Complexity guess (`model_router.py`) | `get_mode_llm_config()` | Declared per shape/dials |

Per the loud-failure principle: if a caller declares an unknown mode name, **error loudly** — do not silently fall back to PLAN as `from_dict()` does today (`modes.py:115`).

## Findings

- Half the machinery already exists: `mode_context` is already passed in and UI selection already wins. This is mostly a **deletion** (Understand's classifier) plus a data-model change (`MODE_CONFIG`), not a new build. Zero new graph topology, no new edges.
- `ActQuickDecision` vs `ActDecision` already proves the per-shape action-union pattern works; this generalizes it.
- Default hygiene audit (2026-06-10) found the quick-mode prompt table is one of the spots where core prompt text hedges across modes — it disappears entirely under this framing.

## Explicitly Deferred (follow-up work items, not this one)

| Deferred | Why | Note |
|----------|-----|------|
| Auto-escalation on misdeclared mode | Scoped out by decision 2026-06-10 | A declared "read mode" request that needs a write will surface as a blocked/failed step for now |
| BlockedAction → Replan edge (docs/ROADMAP.md P1) | Separate item | Key insight to preserve: quick-mode escalation and mid-plan replanning are **the same Act → Think edge**. `BlockedAction.suggested_next="replan"` exists (`state.py:446,456`; emitted at `act.py:1326,1401,1541,1581`) but `should_continue_act()` routes all BlockedAction to `"reply"`. Build the edge once, get both. |
| Dynamic mode switching mid-conversation | Follow-up | Parameterized deterministic shapes are exactly the substrate it would plug into |

## Open Questions

1. **Who classifies in a freeform chat box?** Classification moves to the consumer. For products with explicit surfaces (toggle, slash command, separate quick-ask bar) it's free and better. For a single chat box: ship a tiny optional pre-graph classifier as a convenience (one cheap LLM call, outside the graph, opt-in)? Core's contract either way: mode resolved before the graph runs.
2. **Mode vocabulary.** Do we rename QUICK/PLAN/CREATE to orchestration-demand names (read / full-thinking / create), keep both as aliases, or let domains name their own bundles with core shipping defaults?
3. **Which dials are per-mode vs per-domain?** e.g., should `get_tool_enabled_step_types()` become a per-mode dial (read mode = read tools only)?
4. **Backward compatibility.** `mode_context` dicts from existing consumers (Kitchen, FPL) — migration path for the `from_dict()` PLAN fallback becoming a loud error.
5. **CREATE shape.** Is CREATE truly a distinct shape, or full shape with different dials? (Current config suggests the latter: same path, `max_steps=4`, proposal optional.)
6. **Resolved 2026-06-10:** the outer iteration landed as [0610-serving-modes.md](../0610-serving-modes.md). This work item is now scoped as **M1 internals** — QUICK/PLAN/CREATE are sub-modes of M1 (agentic chat), and the shapes/dials framing here parameterizes M1 only. M2–M5 (MCP serving, one-shot generate, extraction, bounded write) are siblings of M1 at the serving-mode layer, not shapes within the graph. The two items compose and can proceed independently; mode *vocabulary* decisions (Q2 above) should defer to the serving-mode catalog's naming.
