# A3 Grounding Brief — PM Pre-Research (read before RESEARCH.md)

> **Status:** PM-verified facts + named design problems for the A3 executor. This is not
> the research — it's the map of where the research must dig. Produced from a full code
> trace 2026-06-11 after A1+A2 landed.
> **Reads with:** SEAM_CONTRACT.md (binding), [0610-program-roadmap.md](../0610-program-roadmap.md)
> (A3 row + Compatibility Guardrail), [0610-substrate.md](../0610-substrate.md) (C-5).

## 1. Verified good news (don't re-derive)

- **The read path is already nearly state-free.** `_get_client()` is NOT a global DB
  client — it's `_get_domain().get_db_adapter()` per operation (`tools/crud.py:30-32`).
  The only global is the domain singleton itself. `post_read`, formatting, semantic
  notes, grades: all parameter-driven.
- **`tools/crud.py` is import-clean** (ast/logging/operator/pydantic only — no
  alfred.graph/alfred.llm). A3 may import it without breaking isolation.
- **A2's `GradeRegistry.strip()` is ready** as the chain's strip link
  (`domain/grades.py:135`), built per-call via `from_context(ctx)`.
- **FK enrichment mechanics are separable from the session registry.** The S1
  implementation interweaves ref assignment (`id_registry.py:240-275`), but the
  *mechanics* are: `get_fk_enrich_map()` gives `field → (table, name_column)`; the
  enrich step batch-fetches names by UUID list (`tools/crud.py:758-814`). A state-free
  variant is a straightforward reimplementation: collect FK UUIDs per mapped field →
  one batch read per target table → replace values with display names. No counters,
  no session.

## 2. The five design problems (the actual work)

### P1 — `db_read` is global-domain-coupled; A3 must parameterize
`db_read` resolves the adapter via the module-global domain. A3's functions take
`ctx: DomainContext` as a parameter (seam §1) and must use `ctx.get_db_adapter()` —
**never the global** — because ledge's E3 model is a per-request ctx whose adapter
carries the request's JWT/tenant. Decide: add an optional `client=`/`ctx=` parameter to
`db_read` (additive, reuses filter machinery + user-scoping) vs a thin internal read in
the new module reusing `apply_filter`. Either is fine; silent fallback to the global
when ctx is provided is NOT.

### P2 — Contract tension: §1 names `format_record_for_context`, §2 says records are dicts
`format_record_for_context` returns a **prompt string** ("  - Chicken Thighs (2 lbs)
id:inv_5") — but `ShapedPayload.records` is `list[dict]` with display-ready **values**.
The §1 "internally these compose…" sentence is descriptive, §2 is binding. Resolution
to validate in research: the S2 chain's format step is **per-record dict value-shaping**
(a new substrate helper: NULL → "(not set)" signalling, date/number display rules), and
`format_record_for_context` (string) is NOT on the S2 path — it remains the S1/S3
string-context formatter, reachable as an alternative chain tail (the golden fixtures
need it). Flag the §1 wording to the ledge PM as a clarification, same convention as
the §3 transforms note. NULL signalling ("(not set)") exists NOWHERE in core today —
it's new, and it must live in the dict-shaping step so S1 output is untouched
(Guardrail #3).

### P3 — Identity policy (E9), including the record's own `id`
"No UUIDs in any value when grade is external" covers two distinct things:
- **FK values** → display names (the state-free fk_enrich above).
- **The record's own `id` column** → S1 replaces it with a session ref
  (`id_registry.py:196-238`); externally there is no registry. Proposed policy, to
  confirm with research: at external grade the `id` is **dropped** (the consuming AI
  re-finds entities by name/search — ledge's tool design assumes this); internally it
  may pass through. Implement identity handling as an explicit **policy parameter of
  the internal chain** (label-policy / passthrough-policy / caller-supplied callable),
  with the seam entrypoints selecting by grade. The S1 golden fixture proves the
  registry's translation can BE the identity step — composability, not import.

### P4 — Semantic notes are per-SUBDOMAIN; the header contract is per-TABLE
`get_semantic_notes()` returns `dict[subdomain → notes]` (`domain/context.py:322`),
consumed today via schema.py's subdomain context. `ShapedPayload.header` is a
"per-table interpretation hint," and ledge Phase 1 produces per-table slivers. Options
for research: (a) v0 header = subdomain notes (ledge folds table slivers into them);
(b) additive `get_table_notes(table)` defaulting to the subdomain's notes. Lean (b) —
it matches what Phase 1 actually produces and is zero-migration. Whichever wins, it's
a freeze-test bump and an injection-map row, and ledge must know which to declare into
(carry to the seam doc).

### P5 — `truncated` needs a detection decision
`ShapedPayload.truncated` is "limit clipped the result." PostgREST doesn't return
total counts on a plain limited select. Cheapest honest implementation: fetch
`limit + 1`, set `truncated = len > limit`, return `records[:limit]`. Decide in
research; don't ship a `truncated` that's always False.

## 3. Fixture guidance (the merge gate)

- **S1 ref-translated read:** chain with identity step = a wrapper over
  `SessionIdRegistry.translate_read_output` — proves the policy slot composes with
  session machinery WITHOUT the new module importing it (the fixture imports it, the
  module doesn't).
- **S3 recipe (memories-shaped):** multiple `assemble_*`/chain calls composed into one
  context block — proves per-set chain calls compose without re-reading config, and the
  string tail (`format_record_for_context`) works for LLM-bound output.
- **S5 preload (brainstorm-shaped):** profile + dashboard + multi-table reads → one
  frozen prompt context string — proves the chain serves preloads without grades
  interfering (passthrough identity, reply grade).

## 4. Carry-backs this feature will generate

- Seam §1 wording fix (P2) + per-table header sourcing (P4) → ledge PM ack, inline in
  SEAM_CONTRACT.md (Core PM handles).
- `schema_version` initial value: propose `"1"`; bump policy documented in the module.
- A4 doc queue additions: new entrypoints in core-public-api, injection-map rows for
  any new hooks (P4), member-count bump if (b) wins.
