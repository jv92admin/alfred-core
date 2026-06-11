# Shapes & Substrate — Program Recap + Roadmap Proposal

> **Status:** Program consolidation — the learnings of the 2026-06-10 design sessions in one
> place, plus the proposed work-item breakdown. Supersedes nothing; synthesizes everything.
> **Date:** 2026-06-10
> **Reads with:** [0610-serving-modes.md](0610-serving-modes.md) (demand),
> [0610-mode-language.md](0610-mode-language.md) (vocabulary of record, incl. §8 stress-test
> resolutions), [0610-declared-modes-parameterized-shapes/RESEARCH.md](0610-declared-modes-parameterized-shapes/RESEARCH.md)
> (S1 internals), [0610-prewrite-update-delete/RESEARCH.md](0610-prewrite-update-delete/RESEARCH.md) (E1 defect),
> landscaping `alfred-as-substrate` sidequest (worldview).

---

## 1. The Learnings (every aha, bulleted)

### What a shape is
- A **shape = execution topology + LLM tier**, owned by core, with a contract: which steps
  run, the tier ceiling (C0/C1/C2), the allowed sink set, and the safety guarantees that hold
  inside it.
- **Sink/surface is NOT part of shape identity** — it's a per-mode declaration. "Headless C2"
  (the full loop landing in a wizard as a draft estimate, no chat anywhere) is the cell that
  proves it. Only S1 has the graph; **S1 ≠ chat**.
- Tier means **no generative call** (C0) / exactly one (C1) / the loop (C2) — enforceable in
  code, never left to prompt discipline. Embeddings hops for matching don't break C0.
- Shapes are a **small fixed vocabulary that grows only by observed convergence** — promoted
  when a second consumer (or two independently maintained modes) hand-builds the same topology.
  Never speculatively.

### What a mode is
- A **mode = a named consumer registration**: `(shape, dials, prompt content, context recipe,
  output schema, audience grade, sink)`. The unit consumers actually call.
- **Many modes per shape is the normal condition.** A consumer calling the same shape ten ways
  with ten prompts is ten parallel registrations — core is headless/async; multiplicity is
  managed consumer-side. Core never needs "variants."
- Modes are **declared, not inferred**: caller-declared (or user-selected) for now; the router
  is a later layer that only ever *picks among* registered modes — pinning typed mode contracts
  first is what de-risks it.
- **Modes compose.** NL simple-add = S3(extract) → confirm → S4(write). Headless S1 cascade
  confirm = the same persist-after-confirm pattern at C2 (typed pending-action artifact +
  resume token). One gate mechanism, surface chooses the rendering.
- C1 **prompts and output schemas live in the mode registration** — the "third bucket" the
  DomainContext/AgentConfig split was missing.

### What the prompt gains are (S1 internals)
- Removing mode ambiguity makes prompt assembly a **pure function** `(shape, dials, domain) →
  prompt`: per-shape action unions (fewer malformed outputs), Understand demoted to pure
  entity resolution (its LLM quick-mode classifier deleted), Think dials stated as facts,
  Reply cascade statically known.
- Sleeper wins: **byte-stable prompt prefixes → provider prefix caching**; golden-snapshot
  prompt tests per (mode, node); deterministic model tiering → predictable cost per mode.
- Maintainability machinery is part of the work, not a follow-up: compiled-prompt fixtures in
  CI, build manifests on traces, section IDs as a versioned API (overriding a dead section =
  loud error), per-shape behavioral evals as the acceptance gate.

### The seams (what every consumer must decide)
- **Easy seam: do you need writes?** Refined by the cascade boundary: bounded S4 writes
  (not a registered transition, never a governed field) vs cascade-capable S1 writes.
- **Hard seam: who generates / who interprets?** Empirically answered by the references:
  - Artifact lands **in the substrate** (recipe, meal plan, stored summary) → Alfred generates
    in full; **payload compilers** bridge rich artifact → schema (kitchen's 5 compilers).
  - Artifact is an **experience** (storybook, script, media) → Alfred stops at the **directive**
    (WHAT + WHY: entity selection, beats, creative brief); the consumer renders (HOW).
    Memories validated this empirically — quality degraded when Alfred made HOW decisions.
  - Interpretation mirror: who reads Alfred's output is a declared part of each mode's output
    contract (S1: our Reply/formatters · S2: the consuming AI · S3: the sink's consumer).
- **Declare/enforce symmetry everywhere:** DomainContext declares (governed fields, audience
  floors, strip grades), core enforces. Anything left to convention becomes courtesy — the E1
  failure mode.

### Conformance expectations (E1–E11, the testable spine)
- E1 middleware fires on every adapter path (**confirmed defect today**: `db_update`/`db_delete`
  take no middleware — crud.py:501,529). E2 state-free context assembly. E3 per-entry auth
  context. E4 write provenance (no anonymous machine writes). E5 tier guarantees in code.
  E6 output contracts per mode (SSE is S1-only; payloads versioned). E7 observability parity
  for headless modes. E8 idempotency for background modes (S3 sink = upsert on (entity, mode)
  + run provenance). E9 ref policy per shape (session refs never enter stored artifacts;
  durable labels + provenance at generation). E10 candidate retrieval primitive (identity-free
  intake). E11 write governance read by core via protocol.

---

## 2. The Substrate, Outlined (the piece we hadn't named)

> **Now has its own doc of record:** [0610-substrate.md](0610-substrate.md) — the tight
> capability catalog (C-1…C-10) with per-capability contracts, declare/enforce split,
> exists-today file:line evidence, and gap → work-item mapping. The summary below stands;
> the substrate doc governs on detail.

**The substrate is the stateless service layer between domain data and any LLM touchpoint.**
It is the moat ("own the context layer, rent the reasoning") — encoded business judgment that
compounds and is model-agnostic. Every shape consumes it; no shape owns it. Two halves:

### Declarations (`DomainContext` — the domain's knowledge, no LLM imports)
- Entities + subdomains (`EntityDefinition`, `SubdomainDefinition`), table↔type maps
- Schema knowledge: field enums, fallback schemas, semantic notes ("how to read this table"),
  meaningful-NULL signalling
- FK→name enrichment map; labels (`compute_entity_label`) + aliases
- Strip/**audience grades** (named redaction profiles, read-time AND assembly-time)
- **Write governance** (E11): transition-governed fields, registered-transition check
- The `DatabaseAdapter`

### Services (core-owned execution every shape calls)
1. **Scoped data access** — adapter reads/writes, RLS, automatic user_id scoping
2. **CRUD engine + middleware firing** — `pre_read`/`post_read`/`pre_write` (+ update/delete
   after E1), batch dedup; firing is core's guarantee, content is the domain's
3. **ID transcription** — the generalized `SessionIdRegistry` concern (E9): UUID↔ref
   translation so LLMs never see UUIDs; `gen_*` lifecycle (generated → approved → promoted);
   ref labels/actions/recency/detail tracking; **policy per shape** — session registry (S1),
   strip-graded payload policy (S2), durable labels frozen at generation (S3 sinks)
4. **Entity intelligence** — FK enrichment, label computation, active-context curation inputs
5. **Context assembly (the callable layer, E2)** — `assemble_entity_context(ctx, ref)` /
   `assemble_subdomain_read(ctx, subdomain, filters)`: shape → enrich → strip at the mode's
   audience grade → format → semantic-notes header → typed ShapedPayload. No `AlfredState`.
6. **Candidate retrieval (E10)** — identity-free matching: hints → ranked shaped candidates
7. **Write governance + provenance (E11, E4)** — refuse governed writes loudly; actor on every
   write (user / system / integration)
8. **Schema introspection** — live schema RPC + fallback chain + cache

### Explicitly NOT substrate
- Conversation memory, the session registry's *state*, prompts, the graph — those are
  shape/mode-level. Session state is S1's private service. The substrate is per-call and
  stateless; that's what makes it servable to TS consumers over the network and to MCP.

**The generalizing aha:** "LLMs never see UUIDs" was always a substrate rule wearing S1
clothing. The general form: **every LLM touchpoint sees substrate-shaped data** — same
enrichment, same redaction, same hints — whether the LLM is ours (S1/S3/S5) or the
customer's (S2).

---

## 3. Proven Shapes (evidence-backed)

| Shape | Tier | One-liner | Evidence |
|-------|------|-----------|----------|
| **S1 agentic-loop** | C2 | The graph; sub-paths by dials; sink per mode (chat stream OR stored draft) | Kitchen + FPL production; ledge UC1b; deep-estimating headless cell |
| **S2 shaped-read** | C0 | Substrate middleware chain → typed ShapedPayload; no LLM ours | Ledge MCP (BRIEF.md); ≥6 modes implied by subdomain registry |
| **S3 one-shot** | C1 | Context recipe → exactly one call → typed output → sink | **The workhorse: ≥7 observed modes, 3 consumers** — memories go_generate/go_suggest, ledge summaries + intake + dashboard insights, kitchen onboarding ×2 |
| **S4 bounded-write** | C0–C1 | Validated non-cascading single-entity write + event | Ledge UC1a adds, MCP internal adds, intake confirm. **Gated on E1 + E11** |
| **S5 preloaded-session** | C1×N | Deterministic preload → frozen prompt → pure chat → typed handoff | Kitchen cook + brainstorm (identical scaffold duplicated; core already owns the handoff contract) |
| (H) handler | any | Consumer topology, guarantees void | memories chat (watch item: "classify-dispatch" promotes if the ledge router converges on it) |

---

## 4. How Shapes Get Consumed — Worked Examples

### Landscaping (Ledge)
- **MCP serving** → S2 modes, one per subdomain (crm/estimating/design/construction/billing/
  plants), external audience grade; `ask_ledge` = registered escalation edge into S1
- **Project AI summaries** → S3 mode: load-bearing event fires → timeline context recipe →
  one call at the page's **floor audience grade** → upsert on (project, mode) with provenance
- **Email intake** → S3 mode with E10 candidate retrieval + in-call selection → staging card →
  (human confirm) → S4 write. C1 preserved; confidence never gates an unconfirmed write
- **Chat basic adds** → S3→confirm→S4 composition (chat-originated), bare S4 from typed
  surfaces (UI quick-add, MCP tools). Chat lane-2 waits for the router by design
- **Deep estimating (later)** → **headless S1**: full loop, `sink: draft estimate in wizard`,
  streaming optional, mid-loop cascade confirm = pending-action artifact + resume

### Memories
- **go_generate / go_suggest** → re-register as S3 modes: prompt builders become mode prompt
  content; hand-rolled `db.py` fetches become context recipes over the callable layer; output
  = `AlfredGenerationDirective` — Alfred owns WHAT/WHY, the consumer's B11 + Generator
  Compiler render HOW (the seam exemplar)
- **chat** → stays a handler mode, unchanged; nothing is forced through a graph

### Kitchen
- **Main pipeline** → S1; gains declared modes (read mode = the old LLM-guessed quick mode,
  now caller-declared) + prompt slimming for free
- **cook / brainstorm** → S5 modes once core owns the scaffold (preload recipe + template +
  history cap + exit sentinel); kitchen keeps context recipes + handoff prompts
- **Onboarding synthesize/catchall** → S3 modes (today: separate hand-rolled flow)

### Hypotheticals that fall out for free
- **Daily digest email** (any domain): S3 mode, cron-triggered, audience grade = recipient,
  sink = email render payload
- **FPL gameweek report**: S3 mode — squad context recipe → one call → stored report
- **Webhook enrichment** ("new lead from web form"): E10 candidates → S3 classify → S4 write
  after confirm — the intake pattern, different transport
- **Voice surface**: S1 modes with a different sink/renderer — no core change, which is the
  point of sink-as-declaration

---

## 5. First Shapes to Run (proposal: 4, in this order)

1. **S3 one-shot** — highest observed demand (7+ modes), cheapest construct, first consumer
   ready (memories go_generate migration or ledge summaries), and it forces the substrate
   callable layer + mode registry to exist. **Build the registry around S3.**
2. **S2 shaped-read** — pure substrate proof (no LLM risk at all), strategically loudest
   (MCP = "Ledge in your AI of record"), and it hardens audience grades + E9 payload policy.
3. **S1 declared modes** — improves the *existing* product CX (see §6); independent work
   stream (modes.py + injection.py + understand), can run in parallel with 1–2.
4. **S5 preloaded-session** — cheap once the registry exists; pays kitchen's duplication debt
   and validates registry ergonomics on a session-ful shape.

**S4 is deliberately last** — gated on E1 (confirmed defect) + E11 (protocol addition), and
its first consumers are declared-caller surfaces that don't exist until S2/intake land.

## 6. First Improved Product CX

- **First *new* CX shipped on the substrate:** **Ledge project AI summaries (S3)** — visible,
  low-risk, async, and exercises audience grades + idempotency + provenance end-to-end.
  Runner-up same construct: memories Go modes migrate with zero CX change but faster iteration.
- **First *improved existing* CX:** **declared modes in S1 chat** — the read path gets
  snappier (no Think, slim prompts, prefix caching), cost gets predictable per mode, and
  misrouted "quick" turns disappear because routing is declared, not guessed. Kitchen and FPL
  inherit it without domain code changes.
- **The flagship CX (after S2):** Ledge data legible inside the customer's AI of record —
  the strategy's reason to exist.

---

## 7. Roadmap Proposal (work items + sequencing)

> **Superseded 2026-06-10** by [0610-program-roadmap.md](0610-program-roadmap.md) — the
> sequential feature list (4 parallel tracks, 19 features, v41 interlock). The table below
> remains as the original derivation.

| # | Work item | Folder | Scope | Depends on |
|---|-----------|--------|-------|------------|
| WI-1 | **E1 fix: middleware on update/delete** | `0610-prewrite-update-delete/` (exists, stub) | Thread middleware through `db_update`/`db_delete`; decide hook shapes (pre_update/pre_delete vs reuse); loud-failure stance | — |
| WI-2 | **Substrate: protocol split + callable layer** | new: `0611-substrate-callable-layer/` | `DomainContext`/`AgentConfig` split (with `pre_write` in Context, per amendment); E2 entrypoints; E9 ref policy; audience grades at assembly; E4 provenance; E10 candidate retrieval (phase 2); import-level isolation (`alfred.context`) | WI-1 (shares crud.py surface) |
| WI-3 | **Mode registry + S3 construct** | new: `0611-mode-registry-s3/` | Mode declaration schema (the shared contract both programs consume); registry + dispatch; S3 executor (one call, idempotency key, sink writers); first consumer migration (memories go_generate OR ledge summary); bypass_modes deprecation path | WI-2 |
| WI-4 | **S1 declared modes + parameterized prompts** | `0610-declared-modes-parameterized-shapes/` (exists) | Delete Understand classifier; MODE_CONFIG → data; shape-gated sections; snapshots/manifests/evals | mode schema from WI-3 (contract only — can start on research/plan now) |
| WI-5 | **S2 shaped-read / MCP serving** | new | ShapedPayload as versioned contract (E6); external audience grade; with ledge as consumer | WI-2 |
| WI-6 | **S5 scaffold promotion** | new | Core owns preload/template/history/exit/handoff scaffold; kitchen cook+brainstorm migrate | WI-3 |
| WI-7 | **S4 bounded write** | new | E11 protocol additions; S4 executor with loud refusal; declared-caller surfaces first | WI-1 + WI-2 (E11 lives in the split) |
| X-1 | **Conformance checklist E1–E11** | doc, inside WI-2 | One numbered list all docs reference; each E becomes a test as its WI lands | — |

```
WI-1 ──→ WI-2 ──→ WI-3 ──→ WI-6
              ├──→ WI-5         WI-4 (parallel from now; consumes WI-3's mode schema)
              └──→ WI-7 (also needs WI-1)
```

**Recommended start:** WI-1 research→plan (small, already stubbed, unblocks two others) +
WI-2 research in parallel. WI-4 research is already done; its PLAN.md can be drafted once
WI-3's mode declaration schema is pinned (a one-pager, first task inside WI-3).
