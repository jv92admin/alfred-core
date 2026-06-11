# Serving Modes — What Consumers Actually Demand From Alfred Core

> **Status:** Demand framing / requirements (no implementation committed)
> **Date:** 2026-06-10
> **Origin:** Ledge "Alfred as Substrate" workstream — this doc names the Core-side expectations.
> **Reads with (the worldview — not repeated here):**
> - [STRATEGY.md](../../../landscaping/docs/sidequests/alfred-as-substrate/STRATEGY.md) — one substrate, many heads; own the context layer, rent the reasoning
> - [SCOPE.md](../../../landscaping/docs/sidequests/alfred-as-substrate/SCOPE.md) — the four consuming surfaces, the C0/C1/C2 tiering, the cascade boundary
> - [BRIEF.md](../../../landscaping/docs/sidequests/alfred-as-substrate/BRIEF.md) — the external MCP connector surface in detail
> - [CORE_RESTRUCTURE.md](../../../landscaping/docs/sidequests/alfred-as-substrate/CORE_RESTRUCTURE.md) — the `DomainContext` / `AgentConfig` protocol split
> - Local: [core-domain-architecture.md](../../docs/architecture/core-domain-architecture.md), [pipeline-stages.md](../../docs/architecture/pipeline-stages.md), [crud-and-database.md](../../docs/architecture/crud-and-database.md)

---

## 1. The Lead: the chat abstraction is optional — today it's mandatory

Every entry point into Alfred today assumes a **chat CX**: a session, an SSE stream,
`AlfredState`, and the Understand → Think → Act → Reply graph. Even the existing mode
system is conversation-shaped — the core `Mode` enum (`src/alfred/core/modes.py`:
QUICK / PLAN / CREATE) only adapts complexity *within* the graph, and domain
`bypass_modes` are explicitly "lightweight **conversation** modes that bypass the
LangGraph graph" (`src/alfred/modes/__init__.py`). There is no mode that isn't a
conversation.

But the consumers that actually exist want Alfred's **middleware + intelligence
helpers** — ID/ref translation (`SessionIdRegistry`), FK→name enrichment, `post_read`
beautification (cents→dollars), strip/redaction, `format_record_for_context` shaping,
semantic-notes hints — and several of them have **no user present at all**: they run
async, in the background, or machine-to-machine. The chat UX is valuable, but it is
*one head*. Core's job is to serve all the heads.

### The demand is observed, not hypothesized

Two production domains have independently built mode-dispatch scaffolding *around*
the graph because Core only offers the chat pipeline as an entry point:

1. **`alfred_memories`** (`c:\Projects\memories\alfred-memories`) — registers a
   `DomainConfig`, then routes around the graph entirely: its own `modes/` package
   (`go_generate.py`, `go_suggest.py`, `chat.py`) dispatched from `server.py`,
   importing only `alfred.llm.client` and the domain base classes. `go_generate` /
   `go_suggest` are one-shot C1 operations that never needed the graph.
2. **`ledge_alfred`** (`c:\Projects\landscaping\Alfred`) — the landscaping strategy
   docs found the same read-shaping substrate duplicated 2–3 times (Alfred's pipeline
   read path, `aiSummary.ts`, `get_domain_snapshot()`) because the canonical copy is
   welded to the Act step. See [STRATEGY.md](../../../landscaping/docs/sidequests/alfred-as-substrate/STRATEGY.md)
   "How We Got Here."

When two domains converge on the same workaround without coordinating, that is the
real grain of the system. This doc names what they were reaching for.

---

## 2. The Serving Modes (named demand constructs)

**Mode selection is explicit — user-selected or caller-declared, for now.** This
matches Core's existing doctrine ("Primary: User selects mode in UI — explicit,
reliable", `core/modes.py`). Auto-routing — the model's tool-choice on turn one, per
[SCOPE.md](../../../landscaping/docs/sidequests/alfred-as-substrate/SCOPE.md) "The
Router" — is a *later layer on top of* this catalog, not a prerequisite. Pinning the
mode contracts first de-risks the router: each mode is a typed, deterministic handler;
the router only ever picks among them.

LLM tiers (defined in SCOPE.md): **C0** = no LLM on our side · **C1** = one LLM call ·
**C2** = the full agentic loop.

| # | Serving mode | Tier | Sync? | Chat abstraction? | Output sink |
|---|--------------|------|-------|-------------------|-------------|
| M1 | **Agentic chat** | C2 | Sync, streaming | **Yes** — the one head that does | SSE stream + writes |
| M2 | **Context provision (MCP serving)** | C0 | Sync request/response | No | Shaped payload over protocol |
| M3 | **One-shot generate** (summaries; memories' `go_generate`) | C1 | Async-friendly | No | Stored record / cache |
| M4 | **Extraction / classify** (email-text intake) | C1 | Async | No | Typed staging card, persist-after-confirm |
| M5 | **Bounded write** (non-cascading single-entity write) | C0–C1 | Sync | No | DB write + event emit |

### M1 — Agentic chat

Today's pipeline, unchanged in role: multi-step, tool-chaining, cascade-aware writes,
stream output. The existing QUICK/PLAN/CREATE modes are *sub-modes of M1*, not
siblings of M2–M5. M1 is the only mode allowed to perform cascade-triggering writes
(the cascade boundary is defined mechanically in SCOPE.md — a registered transition
with `transition_actions`).

### M2 — Context provision (MCP serving)

**"Deliver an MCP" is a named thing Alfred can serve as a mode.** The middleware
stack, in order — this *is* the contract:

```
establish auth context (tenant + actor)
  → adapter read (RLS-scoped)
  → CRUDMiddleware.post_read          (beautification, e.g. cents→dollars)
  → fk_enrich                          (FK UUID → display name)
  → strip_fields (external grade)      (redaction beyond RLS — rows≠fields)
  → format_record_for_context          (compact shape + meaningful-NULL signalling)
  → semantic-notes header              (per-table "how to read this" hint)
  → typed ShapedPayload out
```

No LLM call on our side — the consuming AI reasons. No graph, no `AlfredState`, no
SSE, no `ContextVar` session plumbing. The one escape hatch (`ask_ledge`) is an
explicit escalation *into M1*, not part of M2. Connector shape, host/client/server
roles, Tools-vs-Resources: see [BRIEF.md](../../../landscaping/docs/sidequests/alfred-as-substrate/BRIEF.md).

### M3 — One-shot generate

State-free context assembly + exactly one LLM call + write to a sink (stored summary,
cache row). Async by default — no session, no stream. `alfred_memories.modes.go_generate`
is this mode, currently implemented domain-side because Core has no construct for it.

### M4 — Extraction / classify

Substrate read for context + one structured-output call. Classify-first,
persist-after-confirm: the call assigns a *type* and pre-fills a card; a human
confirms; the actual write happens after confirmation (and is then an M5 write). The
bar is "usably parsed and organized," not perfect — see SCOPE.md UC4.

### M5 — Bounded write

A write touching one entity with **no downstream cascade** (add contact, log note),
with no reasoning loop. Two hard requirements:

1. **The cascade boundary is read, not defined** — an M5 write must not be a
   registered transition and must never touch a transition-governed status/stage
   field (SCOPE.md "The Cascade Boundary").
2. **`pre_write` middleware MUST fire** — see Core expectation E1 below. This is the
   single gating risk: the Core executor skips `pre_write` for `db_update` /
   `db_delete` (ledge v28 Phase 3 finding — **confirmed in this repo 2026-06-10**:
   `db_create` accepts `middleware` and fires `pre_write`, `src/alfred/tools/crud.py:454,482`;
   `db_update` (`crud.py:501`) and `db_delete` (`crud.py:529`) take no middleware
   parameter at all, so no code path exists on which `pre_write` can fire). Until
   that is closed, "mechanical write" silently means "unvalidated write," and M5
   cannot ship. Note this also affects M1 today: the Act loop's updates/deletes are
   equally unvalidated.

---

## 3. What This Demands of Core (testable expectations)

Each of these is a conformance assertion Core should eventually be able to test, not
a design preference.

- **E1 — Entry-path-independent middleware.** `pre_write` and `post_read` fire on
  *every* path that touches the adapter — Act loop, M5 bounded write, M3 background
  job. Middleware firing is a Core guarantee, not domain courtesy. (Verified open 2026-06-10:
  `db_update`/`db_delete` have no middleware parameter — `src/alfred/tools/crud.py:501,529`.
  First action: close it.)
- **E2 — State-free context assembly.** `context/builders.py` machinery callable with
  `DomainContext` + an entity ref / subdomain filter — no `AlfredState` parameter.
  This is the extraction described in [CORE_RESTRUCTURE.md](../../../landscaping/docs/sidequests/alfred-as-substrate/CORE_RESTRUCTURE.md)
  ("The Callable Layer Already Half-Exists").
- **E3 — Auth context as a per-entry boundary.** Every mode establishes tenant +
  actor explicitly at its own entry: chat session (today), OAuth-minted JWT (M2
  external), system actor (M3/M4 background). Kill the assumption that one FastAPI
  entry's `ContextVar` plumbing covers all paths.
- **E4 — Provenance on every write.** M3/M5 writes record *who* (user / system /
  integration actor) — no anonymous machine writes. Ledge already has the `Actor`
  union slot in its transition context; Core's adapter path needs the equivalent.
- **E5 — Cost guarantee per tier.** C0 modes never fire an LLM; C1 modes never enter
  the graph. The tier is part of the mode's contract, enforceable in code — not an
  optimization left to discipline.
- **E6 — Output contract per mode.** SSE/streaming is optional and M1-only. Typed,
  structured payloads are first-class returns. Once M2 serves external AIs, the
  `ShapedPayload` becomes an **external contract** and needs versioning expectations.
- **E7 — Observability parity.** Headless modes get traces and evals too. The eval
  harness cannot remain chat-transcript-only; an M3 summary run or an M2 read needs
  its own trace/eval story (`src/alfred/observability/` is the seam).
- **E8 — Async semantics.** Background modes (M3, M4) need idempotency and retry
  rules that chat never had: re-running a summary generation must be safe;
  a retried intake extraction must not double-create staging cards.

---

## 4. Open Questions

1. **Mode registry shape.** Is `DomainConfig.bypass_modes` the mechanism, or does a
   real `alfred.modes` registry replace it? Evidence leans toward the latter:
   `bypass_modes` models *conversation* shortcuts, while `alfred_memories` built a
   domain-side `modes/` package for things that aren't conversations at all. M2–M5
   may deserve first-class Core dispatch rather than per-domain scaffolding.
2. **Assembler location.** Does the shaped-payload assembler live in Core
   (`alfred.context`, parameterized on `DomainContext`) or per-domain? Carried from
   CORE_RESTRUCTURE.md — leaning Core, so all domains benefit.
3. **"External grade" strip.** M2 redaction should strip *at least* as hard as
   `strip_fields(context="reply")` — what exactly is the external profile, and is it
   a Core concept (a named strip context) or per-domain config?
4. **Kitchen / FPL migration.** Per the founding posture (STRATEGY.md), the clean
   design leads and legacy domains migrate to it. What's the sequencing for Kitchen
   and FPL adopting the mode catalog — and does `alfred_memories`' `modes/` package
   fold back into it?
5. **Router layering.** When auto-routing arrives (tool-choice on turn one), does it
   live in M1's Understand step, or above the mode catalog entirely? Out of scope
   here; the catalog must simply not preclude it.
