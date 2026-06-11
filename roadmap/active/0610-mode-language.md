# Mode Language — Shapes, Modes, and What's Customizable

> **Status:** Vocabulary / contract sketch (no implementation committed)
> **Date:** 2026-06-10
> **Reads with:** [0610-serving-modes.md](0610-serving-modes.md) (the demand catalog M1–M5),
> [0610-declared-modes-parameterized-shapes/RESEARCH.md](0610-declared-modes-parameterized-shapes/RESEARCH.md) (M1 internals)
> **References:** landscaping `alfred-as-substrate` docs (SCOPE/BRIEF/CORE_RESTRUCTURE), `alfred_memories` modes package

---

## 1. The Vocabulary

| Term | Definition | Owned by |
|------|-----------|----------|
| **Shape** | An execution topology with a contract: which steps run, the LLM **tier ceiling** (C0/C1/C2), the output sink type, and the safety guarantees that hold inside it. Small fixed vocabulary. | **Core** |
| **Mode** | A named registration: `(shape, dials, prompt content, context recipe, output schema, sink)`. The unit consumers actually call. | **Consumer** |
| **Dials** | The parameters a shape exposes per mode: max_steps, verbosity, tool availability, strip grade, model tier *within* the shape's ceiling, proposal gating, etc. | Core defines the dial set per shape; consumer sets values per mode |
| **Tier** | C0 = no **generative** call on our side · C1 = exactly one generative call · C2 = the agentic loop. A property of the **shape**, enforceable in code (expectation E5) — never of the prompt. Metered non-generative hops (e.g., an embeddings call behind semantic candidate matching) do not break C0 — the guarantee is "no generative inference," kept precise so it stays honest as fuzzy matching gets smarter. | **Core** |
| **Consumer** | A deployment that registers modes. Core has no consumer concept beyond auth context + the mode registry. | — |
| **Sink** | Where output lands: SSE stream, typed payload over protocol, stored record, staging card, DB write + event. | Declared per mode, from the shape's allowed set |

**The governing principle (decided 2026-06-10):** a consumer calling the same shape
many ways with different prompts/contexts is **just parallel mode registrations** —
Core is headless/async, so multiplicity is managed consumer-side. Core never needs
"variants" or "sub-shapes" to support this. Many modes per shape is the *normal*
condition, not an edge case.

**Shapes grow by observed convergence only.** A shape is promoted into core when a
second consumer independently hand-builds the same topology (the `alfred_memories`
signal) — never speculatively.

---

## 2. The Shape Vocabulary (v1 — four shapes + one escape hatch)

| Shape | Tier | Topology | Sinks | Safety contract |
|-------|------|----------|-------|-----------------|
| **S1 — agentic-loop** | C2 | Understand → [Think] → Act⟲ → Reply → Summarize. Sub-paths (skip_think single-shot, proposal gate) selected by dials. | Stream (optional) · stored artifact/draft · writes — **sink is a per-mode declaration; S1 does not imply chat** (see §8.3) | Only shape permitted cascade-triggering writes; `gen_*` approval gate; session ref registry; in-loop gates render per surface (in-stream propose, or pending-action artifact + resume token when headless) |
| **S2 — shaped-read** | C0 | auth → adapter read → `post_read` → fk_enrich → strip(grade) → `format_record_for_context` → semantic-notes header → typed payload | ShapedPayload over protocol (MCP etc.) | Never fires an LLM; RLS + named strip grade; read-only by construction |
| **S3 — one-shot** | C1 | context recipe assembly → exactly one LLM call (structured or streaming) → typed output → sink | Stored record, cache row, staging card, API response | Exactly one LLM call; no graph, no session; idempotent re-run (E8); provenance on any write (E4) |
| **S4 — bounded-write** | C0–C1 | validate (`pre_write` **must** fire — E1) → single-entity write (not a registered transition, never a transition-governed field) → event emit | DB write + event | Cascade boundary is read, not defined; provenance required; **gated on closing E1** ([0610-prewrite-update-delete](0610-prewrite-update-delete/RESEARCH.md)) |
| **S5 — preloaded-session** | C1 × N turns | deterministic context preload (reads + cached profile) → frozen context in system prompt → pure chat loop, one low-tier streaming call/turn, **no tools** → exit sentinel → one handoff call → typed `HandoffResult` into conversation | SSE stream + handoff record | Context frozen at init; no tools mid-session; the handoff is the only path back into substrate/conversation state |
| **(H) — handler** | any | Consumer-owned topology registered as a mode handler | consumer-defined | Core guarantees void inside; the supported escape hatch (today's `bypass_modes`, generalized) |

**Mapping to the demand catalog:** M1 = S1 · M2 = S2 · **M3 + M4 = S3** · M5 = S4 · kitchen cook/brainstorm = S5.

M3 (one-shot generate) and M4 (extraction/classify) are **the same shape**. The
evidence: `alfred_memories.go_generate` and `go_suggest` are structurally identical —
assemble context from substrate, one instructor call, typed output, yield done —
differing only in context recipe, prompt, and output schema. Those differences are
exactly what a *mode* carries. Fewer shapes, more modes.

**S5 promoted 2026-06-10 on kitchen evidence** (the "fixed passthrough" lane). Kitchen's
`cook` and `brainstorm` are the same topology twice with the scaffold duplicated
domain-side: deterministic preload (`db_read` recipe / inventory + 7-day meal-plan
reads + cached profile) → context injected into a frozen system-prompt template →
pure chat, one `complexity="low"` streaming call per turn, no tools → `__*_exit__`
sentinel → `generate_session_handoff()` → `HandoffResult` (summary, action:
save/update/close, verbatim recipe_content) injected into `conversation.recent_turns`
(`alfred_kitchen/domain/modes/cook.py:87-188`, `brainstorm.py:93-215`). Core already
owns half this shape — bypass dispatch and the handoff contract
(`src/alfred/modes/handoff.py`, `get_handoff_result_model()`); only the scaffold
(preload recipe, template injection, history cap, exit sentinel) is copy-pasted per
mode. Promotion means core owns the scaffold; a mode supplies context recipe +
prompt template + handoff prompts. This satisfies the convergence rule: two
independently maintained modes duplicating identical wiring is the same signal as two
consumers.

---

## 3. What's Customizable vs What's Not

### Consumer-customizable (per mode, no core changes)

| Knob | Notes |
|------|-------|
| Mode name + how many modes | Unlimited modes per shape; parallel registrations are the norm |
| Prompt content | Sections/templates per mode — compiled deterministically, snapshot-audited (see parameterized-shapes item) |
| Context recipe | Which entities/subdomains/depth get assembled (S2/S3), entity curation hints (S1) |
| Output schema | S3 structured-output model is per-mode (creative brief vs intake card vs summary) |
| Dials | max_steps, verbosity, proposal gating, profile detail, model within tier ceiling |
| Tool availability | Which tools per step type (S1); custom tools via `get_custom_tools()` |
| Strip grade | Named redaction profile per mode (S2 external vs internal) |
| Sink | Within the shape's allowed sink set |
| Middleware behavior | `post_read`/`pre_write` content is domain logic |

### Core-owned (not customizable)

| Invariant | Why |
|-----------|-----|
| Shape topologies + routing within S1 | Safety/streaming/state contracts are welded to the wiring |
| Tier ceiling per shape | E5: C0 never fires an LLM, C1 never loops — enforceable, not discipline |
| Middleware **firing** on every adapter path | E1: firing is a core guarantee; only the *content* is domain's |
| Cascade boundary enforcement | S4 reads the boundary (registered transitions); it cannot redefine it |
| Ref/UUID policy per shape | E9: session registry (S1), strip-graded payload policy (S2), durable labels (S3 sinks) |
| `gen_*` approval gate | Generated content never auto-persists (system boundary) |
| Provenance on writes | E4: no anonymous machine writes |
| Output contract types per shape | E6: SSE is S1-only; typed payloads are versioned external contracts |

---

## 4. Real Use-Case Catalog (the two reference consumers)

| Use case (source) | Shape | Mode sketch | Tier | Status today |
|---|---|---|---|---|
| Ledge chat — advanced (UC1b) | S1 | `ledge-chat-full`: full loop, cascade-aware writes | C2 | = today's pipeline |
| Ledge chat — basic reads (UC1a) | S1 single-shot sub-path | `ledge-chat-quick`: declared read mode, terse | C2 shape, ~1 call | = declared-modes work |
| Ledge chat — basic adds (UC1a) | S4 | `add_contact`, `log_note`, `add_task` | C0–C1 | Blocked on E1 |
| Project summaries (UC2) | S3 | `project-summary`: timeline-event context → 1 call → stored on record | C1 | Not yet built |
| MCP external read (UC3a) | S2 | One mode per subdomain registry entry (crm/estimating/design/…), external strip grade | C0 | The BRIEF connector |
| `ask_ledge` escalation (UC3a) | S1 | Escalation *into* `ledge-chat-full`; an inter-mode edge the consumer/router manages, not a shape | C2 | Concept |
| MCP internal adds (UC3b) | S4 | Same S4 modes exposed over MCP | C0–C1 | Blocked on E1 |
| Email/text intake (UC4) | S3 → (confirm) → S4 | `intake-extract`: classify + pre-fill staging card; the post-confirm persist is a separate S4 mode | C1 | Not yet built |
| memories `go_generate` | S3 | Family context recipe → creative-brief schema → directive sink | C1 | **Built domain-side** (no core construct) |
| memories `go_suggest` | S3 | Roster+edges+temporal recipe → ThemeSuggestion schema | C1 | **Built domain-side** |
| memories `chat` | (H) handler | Classify-intent → intent-specific context → streamed reply (2 calls) | ~C1×2 | Built domain-side; **watch item** below |
| kitchen `cook` | S5 | Recipe + profile preload → guided cooking session → handoff (save/update/close + verbatim variant) | C1/turn | Built domain-side (scaffold duplicated) |
| kitchen `brainstorm` | S5 | Profile + dashboard + inventory + meal-plan preload → ideation session → handoff with recipe content | C1/turn | Built domain-side (scaffold duplicated) |
| kitchen onboarding `synthesize_guidance` | S3 | Interview answers → 5 subdomain_guidance strings → preferences table (injected into every future prompt) | C1 | Built (separate flow, own LLM calls) |
| kitchen onboarding `generate_catchall` | S3 | Prior answers → 0–3 follow-up interview questions | C1 | Built (separate flow) |
| memories generation chain | S3 → consumer pipeline | `go_generate` emits `AlfredGenerationDirective` (WHAT/WHY); consumer's B11 + Generator Compiler render (HOW) | C1 ours; rendering theirs | Built; **the seam exemplar** (§6) |

**Counting:** ≥7 observed S3 modes across three consumers, 2 S5 modes, ≥4 S4 modes,
≥6 S2 modes — against exactly **one** unpromoted novel topology (memories chat). The
distribution confirms the posture: invest in making modes cheap to register, not in
making shapes customizable.

**Watch item — "classify-dispatch":** memories' `chat.py` (intent classification →
per-intent context → respond) is a candidate fifth shape, and it rhymes with the
landscaping Router ("tool-choice on turn one" short-circuiting the loop). One
observation is not convergence — do not promote yet. If the ledge router lands and
looks structurally like memories' chat, that's the second observation and it gets
promoted; until then it stays a handler mode.

---

## 5. Alignment with the Substrate Worldview (direct read of the sidequest, 2026-06-10)

The landscaping `alfred-as-substrate` docs model every AI feature as
`[A] domain knowledge → [B] context assembly → [C] LLM operation → [D] output sink`,
with A+B the shared substrate and C+D diverging per surface. The vocabularies map 1:1:

| Substrate worldview | This doc |
|---|---|
| A+B (`DomainContext` after the protocol split) | What every shape consumes; the **context recipe** is a mode's parameterization of B |
| C (LLM operation: none / one call / loop) | The shape's **tier** (C0/C1/C2) |
| C+D contract (what thinking + where it goes) | The **shape** |
| A head ("thin head bolted onto the substrate") | A **mode** registration |

Three reconciliation notes from reading the sidequest in full:

1. **Conflict to resolve — `pre_write`'s bucket.** CORE_RESTRUCTURE.md sorts `pre_write`
   into `AgentConfig` ("genuinely pipeline-side"). That contradicts E1/S4: bounded
   writes have **no pipeline** and `pre_write` MUST fire on them. `pre_write` is
   B-layer write-shaping and belongs in `DomainContext`. The serving-modes E1
   expectation supersedes the bucket assignment; carry this back to the protocol-split
   plan.
2. **Stale packaging claim.** CORE_RESTRUCTURE's "mono-repo already builds 4 wheel
   targets" escape hatch cites `core-public-api.md:172-179`, which is stale — this
   repo's `pyproject.toml:33` builds only `src/alfred` post-split (doc fix needed,
   `/doc-review` item). The *stronger* argument stands unaided: import-level isolation
   (consumers importing only `alfred.context` never touch langgraph) needs no package
   split. Defer extras.
3. **Posture license.** STRATEGY.md's founding posture: extraction/zero-migration is
   the **floor, not the mandate** — the clean design leads and Kitchen/FPL migrate to
   it. Our planning is not constrained to additive-only changes; protocol
   re-architecture is a deliberate cost call, available when it serves the design.

One more observed data point: STRATEGY.md's convergence story counts **dashboard
insights** (`aiSummary.ts`: gather metrics → one call → cache) as a third
independently-built gather→shape→one-call→sink surface — a 5th observed S3 mode,
further confirming S3 as the workhorse shape.

## 6. Capability Lanes and the Seams

### Lanes — the consumer-facing axis

Consumers don't think in topologies; they think in capabilities. The lane taxonomy
(named 2026-06-10) maps onto shapes cleanly:

| Lane (what the consumer asks for) | Shape(s) | Examples |
|---|---|---|
| **Read only** | S2 | MCP serving; some memories context reads |
| **Fixed passthrough** — deterministic CRUD injected + system prompt | S3 (one-shot over fixed context) · S5 (session over fixed context) | Daily AI summaries (S3); kitchen cook/brainstorm (S5) |
| **Read + Analyze + Generate** (no writes) | S1 with write tools disabled via dials | Deeper analysis/metrics; richer MCP-triggered reports |
| **Full CRUD + Analyze/Generate** | S1 full | The full Alfred pipeline |

Lanes 3 and 4 differ only by a dial (tool availability per mode) — evidence that
write-capability is per-mode configuration, not a shape boundary. Lane 2 splits by
session-ness: one call (S3) vs a conversation over the same frozen context (S5).

A future **specialist** lane (deep single-domain expert modes) is parked — noted,
not designed.

### The seams — what every consumer must decide

**The easy seam: do you need writes?** Lane 1–2 vs 3–4, refined by the cascade
boundary (bounded S4 writes vs cascade-capable S1 writes).

**The hard seam: who generates, and who interprets Alfred's results?** The two
reference consumers answer it from opposite ends, and together they give the rule:

- **Kitchen (artifact = substrate record):** generation happens *inside* the graph
  (Act `generate` steps → `gen_*` artifacts), and **payload compilers** translate the
  rich artifact into schema-ready payloads for the write step
  (`alfred_kitchen/domain/compilers.py:19-117`, 5 compilers; core registry
  `src/alfred/core/payload_compiler.py`). Alfred generates fully because the output
  *is* a domain record.
- **Memories (artifact = experience):** Alfred's mode stops at the
  **directive** — `go_generate` emits `AlfredGenerationDirective` (entity selection,
  story beats, creative brief = WHAT + WHY); the consumer's B11 + Generator Compiler
  render story text, scenes, illustration prompts (HOW). Empirically validated: when
  Alfred was asked to make HOW decisions (scene treatment, camera direction), quality
  degraded (`memories/docs/architecture/generation-pipeline.md:31-35`). Intelligence
  flows downstream only; no component re-interprets upstream decisions; all modes
  converge on one directive type.

**The deciding question for any new use case:** *does the generated artifact land in
the substrate or in an experience pipeline?* Substrate record (recipe, meal plan,
summary-on-record) → Alfred generates in full and compilers bridge artifact → schema.
Experience artifact (storybook, script, media) → Alfred stops at the directive;
the consumer renders. Both sides of the seam are typed contracts — the compiler
input shape on one side, the directive model on the other.

**The interpretation seam is the mirror image:** who reads Alfred's output? S1 —
Reply/formatters (ours). S2 — the consuming AI (theirs). S3 — the sink's consumer
(theirs). It's part of each mode's output contract (E6), declared, not assumed.

## 7. Implications Worth Holding Onto

1. **Escalation is an inter-mode edge, not a shape feature.** `ask_ledge` → S1,
   intake-confirm → S4: consumers/routers wire modes together; core stays headless
   and per-call. Keeps core simple and matches "managed on the consumer end."
2. **The router (later) only ever picks among registered modes.** Pinning typed mode
   contracts first is what de-risks it — selection becomes the only non-determinism.
3. **Per-consumer prompt divergence is a registry fact, not folklore** — every mode's
   compiled prompt is snapshot-tested and manifest-traced (parameterized-shapes item).
4. **What `alfred_memories` migration looks like in this language:** `go_generate`
   and `go_suggest` re-register as S3 modes (their prompt builders become mode prompt
   content; their `db.py` fetches become context recipes over the callable layer);
   `chat` stays a handler mode unchanged. Nothing is forced through a graph.

## 8. Stress-Test Resolutions (2026-06-10)

A four-walkthrough stress test (email intake, stored summaries, headless deep
estimating, NL simple-adds) exposed cracks the catalog above had not surfaced.
Resolutions, now part of the language:

### 8.1 E10 — Candidate retrieval is a missing substrate primitive

M4-style intake is the only demand whose input arrives with **no entity identity
attached** — context assembly is candidate retrieval (sender → contact match, fuzzy
name → project candidates), not `assemble_entity_context(ref)`. The substrate has
fragments (`similar` op → domain `pre_read` semantic search, `get_subdomain_aliases`,
`compute_entity_label`) but no named entrypoint. **E10:**
`resolve_candidates(ctx, hints) → ranked shaped candidate sets`, C0 by contract.
Matching policy: deterministic candidate fetch + **selection inside the mode's one
LLM call** (output schema includes `matched: one-of(candidates) | none`) — never a
second call; no confident match → artifact ships unlinked with candidates for the
human confirm step. Two guard rails: (a) "C0 by contract" means no *generative*
call — an embeddings hop for similarity is permitted (see Tier definition, §1);
(b) the selection confidence is LLM-self-reported and known-unreliable — the human
confirm step absorbs it, and it must **never** gate an unconfirmed write path.

### 8.2 C1 prompts live in the mode registration (third bucket)

CORE_RESTRUCTURE's A+B/C+D split has no home for single-call prompts + structured
output schemas: not `DomainContext` (would drag LLM concerns into the no-LLM half),
not `AgentConfig` (defeats the split for non-pipeline consumers). They are
**mode-owned** — the registry is the C+D declaration layer for everything that isn't
the pipeline. Carry this amendment back to the protocol-split plan alongside the
`pre_write` bucket fix (§5.1).

### 8.3 Tier × sink are two axes — "headless C2" is a real cell

The M-catalog flattened a 2-axis matrix (LLM tier × output surface) into five cells,
hiding the **loop-without-chat** cell (e.g. deep estimating fired from a wizard,
landing as a draft estimate — C2 by every SCOPE.md test, no chat anywhere). In shape
language: **shape = topology + tier; sink is a per-mode declaration.** Deep
estimating = an S1 mode with `sink: stored draft`, streaming optional. Correct
sentence: *only S1 has the graph; S1 does not imply chat.*

### 8.4 Modes compose — persist-after-confirm is a cross-cutting contract

The catalog cells are composable units, not exclusive boxes:
- **NL simple-add is S3 → confirm → S4** (extract → staging card → write). Bare S4
  is for typed callers only (UI quick-adds, MCP tools, intake-confirm). Price
  chat-originated adds as one C1 call + a confirm, not zero.
- **Headless S1 cascade confirmation** is the same pattern at C2: the in-stream
  propose becomes a **typed pending-action artifact + resume token**. One gate
  mechanism; the surface (chat stream, wizard card, review UI) chooses the rendering.

### 8.5 E11 — Write governance is read by Core, via the protocol

"The cascade boundary is read, not defined" never named the reader. Core is
domain-agnostic and cannot see a consumer's transition registry, so `DomainContext`
grows the **write-side sibling of `strip_fields`**:
`get_transition_governed_fields() → dict[table, fields]` (+
`is_registered_transition(table, change)`). The S4 executor **refuses loudly** any
write touching a governed field. "The caller knows not to" is the E1 domain-courtesy
failure mode reproduced one layer up.

### 8.6 Audience grade generalizes strip grades to generation time

Stored C1 artifacts bake data in at generation time with elevated (system-actor)
visibility — read-side redaction cannot protect them (RLS protects rows, not prose
derived from them). Every mode whose output **outlives the request** declares an
**audience grade**; context assembly strips at that grade *before* the LLM sees
data. Default: generate at the **floor visibility** of the artifact's audience;
per-audience artifacts are the opt-in expensive variant. Same symmetry as E11:
**DomainContext declares, Core enforces** — the audience floor per mode is a domain
judgment (which roles can open which pages lives in the consumer's RBAC config),
surfaced through a protocol declaration; core applies the strip at assembly time.
Left to convention it becomes courtesy — the E1 failure mode again. Companion contracts: S3
takes an idempotency key (sink write = upsert on `(entity, mode)` with run
provenance — E8 concrete); stored text carries durable labels frozen at generation
+ provenance (`generated_at`, source UUIDs) — staleness is detectable, regeneration
picks up renames, session refs never enter a stored artifact (E9 concrete).

### 8.7 Sequencing consequence — S4's first consumers are not chat

"User-selected for now" assumes surfaces with mode affordances. Single-chat-box
surfaces (Ledge) cannot reach S4 until the router lands; S4 ships first on
**declared-caller surfaces** (MCP internal adds, intake confirm, UI quick-adds).
Chat-originated lane-2 is router-gated by design, not a launch blocker.
