# The Substrate — Concept + Capability Catalog

> **Status:** Concept of record + tight capability spec (framing — no implementation committed)
> **Date:** 2026-06-10
> **Reads with:** [0610-mode-language.md](0610-mode-language.md) (shapes/modes consume this),
> [0610-shapes-substrate-program.md](0610-shapes-substrate-program.md) (roadmap), landscaping
> STRATEGY.md (the worldview: "own the context layer, rent the reasoning").

---

## 1. What the Substrate Is

**The substrate is the stateless service layer between domain data and any LLM touchpoint.**
Every shape consumes it; no shape owns it. It is the moat — encoded business judgment
(enrichment, redaction, labels, semantic hints, governance) that compounds as it's tuned and
is model-agnostic. When models commoditize, the substrate is the layer that makes any model
useful on the domain's data.

Four properties define it:

1. **Per-call and stateless.** No session, no `AlfredState`, no `ContextVar` plumbing. This is
   what makes it servable to MCP clients, TS consumers over the network, and background jobs.
   (Session state — the registry's *contents*, conversation memory — is S1's private service
   built *on* the substrate, not part of it.)
2. **Internally C0.** The substrate never makes a generative call. (Non-generative metered
   hops — an embeddings call behind candidate matching — are permitted.)
3. **Declare/enforce symmetry.** `DomainContext` declares (grades, governed fields, enrich
   maps, labels); core enforces (firing, stripping, refusing). Anything left to convention
   becomes courtesy — the E1 failure mode.
4. **Universal shaping.** "LLMs never see UUIDs" is the S1-flavored special case of the general
   rule: **every LLM touchpoint sees substrate-shaped data** — same enrichment, same redaction,
   same hints — whether the LLM is ours (S1/S3/S5) or the customer's (S2).

```
[A] domain knowledge ──→ [B] substrate services ──→ shaped, governed, attributable data
    (DomainContext           (core-owned                ──→ consumed by any shape's
     declarations)            execution)                    LLM operation + sink
```

## 2. The Capability Catalog

Ten capabilities. For each: the contract, who declares / who enforces, what exists today
(with file:line), and the gap.

### C-1 Scoped data access
- **Contract:** every read/write is tenant- + user-scoped before it touches the adapter;
  RLS backs it at the DB.
- **Declares:** `get_db_adapter()`, `get_user_owned_tables()`. **Enforces:** core auto-injects
  and auto-filters `user_id` (`tools/crud.py:485-486, 517-519, 554-556`); empty-filter delete
  guard (`crud.py:543-549`).
- **Exists today:** yes (`db/adapter.py` protocol + crud.py scoping).
- **Gap:** **E3** — auth context assumes one FastAPI entry; each mode entry (chat session,
  OAuth JWT, system actor) must establish tenant + actor explicitly.

### C-2 CRUD execution + guaranteed middleware firing
- **Contract:** `db_read/create/update/delete` + 14 filter ops; domain middleware
  (`pre_read`/`post_read`/`pre_write`/`deduplicate_batch`, `domain/base.py:141-215`) fires on
  **every** path that touches the adapter. Firing is core's guarantee; middleware *content*
  is the domain's.
- **Exists today:** read + create paths fire (`crud.py:359, 482, 490`).
- **Gap:** **E1 — confirmed defect**: `db_update`/`db_delete` take no middleware parameter
  (`crud.py:501, 529`). → WI-1.

### C-3 ID transcription (ref policy)
- **Contract:** no UUID ever reaches an LLM prompt; generated content (`gen_*`) never
  persists without explicit approval; every ref carries label, type, action, recency.
- **Exists today:** `SessionIdRegistry` (`core/id_registry.py`, ~51KB): `translate_read_output`,
  `register_generated/created/from_ui`, gen_* lifecycle + promotion, detail tracking,
  turn-recency windows.
- **Gap:** **E9** — the mechanism is session-welded. Target: **ref policy per shape** —
  session registry (S1), strip-graded UUID/no-ref policy (S2 external payloads), durable
  labels frozen at generation + provenance (S3 stored artifacts).

### C-4 Entity intelligence
- **Contract:** raw rows become *legible* records: FK UUIDs → display names, computed labels,
  aliases resolve, per-table "how to read this" hints attach, meaningful NULLs signalled.
- **Declares:** `get_fk_enrich_map()` (`base.py:407`), `compute_entity_label[_from_fks]()`
  (`base.py:674, 690`), `get_subdomain_aliases()`, `get_semantic_notes()` (`base.py:432`).
- **Exists today:** yes, exercised via the read path + `context/entity.py:64`
  (`get_entity_context`, already registry-based rather than state-based).
- **Gap:** none structural — needs lifting into the callable layer (C-5) unchanged.

### C-5 Context assembly (the callable shaping chain)
- **Contract:** `assemble_entity_context(ctx, ref)` / `assemble_subdomain_read(ctx, subdomain,
  filters)` → typed **ShapedPayload**: adapter read → `post_read` → fk_enrich → strip at the
  mode's audience grade → `format_record_for_context` (`base.py:992`) → semantic-notes header.
  No `AlfredState` parameter, no session.
- **Exists today:** the chain exists but **welded** — `context/builders.py:472, 507, 542` are
  all parameterized on `AlfredState`; the shaping transforms live scattered across the Act
  read path and reply formatting.
- **Gap:** **E2** — the extraction. Plus **E6**: once S2 serves external AIs, ShapedPayload is
  a *versioned external contract*. → WI-2's core deliverable.

### C-6 Redaction / audience grades
- **Contract:** named redaction profiles (grades), declared per mode, applied by core at
  **read time** (S2) and at **assembly time** for any mode whose output outlives the request
  (S3 stored artifacts generate at the audience's floor visibility). Rows ≠ fields ≠ derived
  text: RLS protects rows; grades protect fields and everything generated from them.
- **Declares:** the grade definitions (a domain RBAC judgment). **Enforces:** core strips
  during C-5 assembly.
- **Exists today:** partial and wrong-shaped (corrected 2026-06-11 — A2 research caught an
  audit error here): core has `get_strip_fields(context)` on `DomainContext`
  (`domain/context.py:547`, flat set, contexts `injection`/`reply`), but it is consumed
  **only by the user-bound reply renderer** (`reply.py:1075`); the `injection` context has
  zero core consumers, and **no strip mechanism exists on the LLM-bound path**. Ledge
  declares into it domain-side.
- **Gap:** the grade registry (A2, in progress): named grades as `StripSet`s
  (global + per-table), validated `external ⊇ reply` at registration, applied on the
  LLM-bound assembly path. Deliberately NOT bridged to `get_strip_fields` — the user-bound
  and LLM-bound paths stay separate until D7. Grades are **pure field removal**; value
  transforms (cents→dollars) remain `post_read` middleware, grade-independent. The
  sharpest risk this closes: a system-actor S3 run baking financials into a summary a
  restricted viewer can open.

### C-7 Candidate retrieval (identity-free matching)
- **Contract:** `resolve_candidates(ctx, hints) → ranked, shaped candidate sets` — for inputs
  that arrive with **no entity identity attached** (email intake, webhooks). C0 by contract
  (embeddings permitted, nothing generative). Selection happens *inside the consuming mode's
  one LLM call*, never as a second call; self-reported confidence never gates an unconfirmed
  write.
- **Exists today:** fragments only — `similar` filter op delegating to domain `pre_read`
  semantic search, `ilike`, aliases, label computation. No named entrypoint.
- **Gap:** **E10** — the primitive itself. → WI-2 phase 2.

### C-8 Write governance + provenance
- **Contract:** core *refuses loudly* any non-S1 write that touches a transition-governed
  field (the cascade boundary is read by core, not trusted to callers); every write carries an
  actor (user / system / integration) — no anonymous machine writes.
- **Declares:** `get_transition_governed_fields()`, `is_registered_transition()` (new
  protocol methods — the write-side sibling of strip grades). **Enforces:** the S4 executor.
- **Exists today:** user-scoping + the empty-filter delete guard only. No transition
  awareness, no actor concept in core's write path.
- **Gap:** **E11** (governance) + **E4** (provenance). → WI-2 declarations, WI-7 enforcement.

### C-9 Schema introspection
- **Contract:** live schema (`get_table_columns` RPC) with deterministic fallback chain
  (domain `get_fallback_schemas()`) and field enums; cached (TTL 300s), invalidated on write.
- **Exists today:** yes (`tools/schema.py`, 509 lines).
- **Gap:** none structural; FILTER_SCHEMA default examples still carry kitchen residue
  (roadmap P2/P5 — cosmetic).

### C-10 Payload compilation (write-side shaping)
- **Contract:** the mirror of C-5 on the write path: rich generated artifacts → schema-ready
  payloads (field mapping, linked records, lossy-field warnings surfaced, UUID-field
  sanitization), so generation output can land in the substrate safely.
- **Declares:** domain compilers (`get_payload_compilers()` — kitchen ships 5,
  `alfred_kitchen/domain/compilers.py:19-117`). **Enforces:** core registry + invocation
  (`core/payload_compiler.py`, `graph/nodes/act.py:469`), `_sanitize_uuid_fields`
  (`crud.py:444`).
- **Exists today:** yes, but invoked only from the S1 Act loop.
- **Gap:** callable from any shape that writes generated artifacts (an S3 mode whose sink is
  a substrate record needs the same bridge).

## 3. What the Substrate Is NOT (the boundary)

- **No prompts, no personas** — those live in mode registrations (C1 shapes) or `AgentConfig`
  (the S1 pipeline).
- **No generative calls** — tier C is always the consuming shape's concern.
- **No routing or mode selection** — the registry dispatches; the substrate serves whoever
  arrives with an auth context.
- **No session or conversation state** — the registry *mechanism* is substrate (C-3); its
  session-scoped *contents* and conversation memory are S1 services.
- **No UI rendering** — confirmed in the strategy docs: no surface needs the substrate to
  render UI; it exists only on LLM-bound payload paths. Frontends keep their own helpers.
  Refined by the A1 sort (2026-06-10): the precise line is **LLM-bound vs user-bound** —
  shaping a record for an LLM (`format_record_for_context`) is substrate; rendering a
  reply for a human (`format_records_for_reply`, `get_subdomain_formatters`,
  `get_empty_response`) is Agent-side.

## 4. How Consumers Reach It

- **Python consumers** (S1 pipeline, S3/S5 modes, MCP server): `import alfred.context` —
  import-level dependency isolation; importing only the substrate never touches
  langgraph/instructor. No package split needed (defer extras).
- **Non-Python consumers** (TS summaries, intake workers): the substrate **exposed as a
  service** — both ends async, so the network hop is free (per the strategy's converged
  decision). The service wrapper is consumer-side until demand says otherwise.
- **Every entry establishes auth context explicitly** (E3): chat session / OAuth-minted JWT /
  system actor. No shared ContextVar assumption.

## 5. Current State → Target (one line per capability)

| Capability | Exists in core | Gap | Lands in |
|---|---|---|---|
| C-1 Scoped access | ✅ | E3 per-entry auth | WI-2 |
| C-2 CRUD + middleware firing | ⚠️ read/create only | **E1 defect** (update/delete) | **WI-1** |
| C-3 ID transcription | ✅ session-welded | E9 ref policy per shape | WI-2 |
| C-4 Entity intelligence | ✅ | lift into callable layer | WI-2 |
| C-5 Context assembly | ⚠️ welded to AlfredState | **E2 extraction**; E6 versioned payload | **WI-2 (core)** |
| C-6 Audience grades | ❌ (ledge domain-side only) | promote to core, assembly-time | WI-2 |
| C-7 Candidate retrieval | fragments | E10 primitive | WI-2 ph.2 |
| C-8 Governance + provenance | ❌ | E11 + E4 | WI-2 decl / WI-7 enf |
| C-9 Schema introspection | ✅ | cosmetic residue only | — |
| C-10 Payload compilation | ✅ S1-only invocation | callable from any writing shape | WI-3 |

**Tightness check for any future capability proposal:** if it (a) makes a generative call,
(b) needs session state, or (c) renders UI — it is not substrate. If two shapes would
otherwise duplicate it, it is.
