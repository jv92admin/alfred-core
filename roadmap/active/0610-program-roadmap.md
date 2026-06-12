# Core Program Roadmap — Substrate & Shapes (Sequential Feature List)

**Status:** In Progress — Track A: A0 ✅ A1 ✅ A2 ✅ A3 ✅ (verified 2026-06-12) · next: **A4 (release)** · B1, C1 startable
**Tracks:** 4 parallel + 1 cross-cutting · 19 features
**Supersedes:** the WI-table in [0610-shapes-substrate-program.md](0610-shapes-substrate-program.md) §7 (narrative docs remain the rationale; THIS doc is the build order)

---

## Overview

Four tracks run **in parallel** — no single narrative in series. Track A is the only
externally-committed track (ledge v41 Phase 2 depends on it; seam contract agreed, see
[SEAM_CONTRACT.md](../../../landscaping/docs/roadmaps/launch/v41-ledge-mcp/specs/SEAM_CONTRACT.md) §6).
Tracks B/C start immediately and independently. Track D starts after its first feature
(the mode declaration schema) is pinned, full speed after Track A ships.

Rationale docs (cite, don't duplicate): [0610-substrate.md](0610-substrate.md) (capabilities
C-1…C-10) · [0610-mode-language.md](0610-mode-language.md) (shapes S1–S5, E-series) ·
[0610-serving-modes.md](0610-serving-modes.md) (demand) ·
[0610-declared-modes-parameterized-shapes/RESEARCH.md](0610-declared-modes-parameterized-shapes/RESEARCH.md) (S1 internals).

---

## Track A — Substrate for External Serving 🔴 (committed: ledge v41)

*Goal: ledge Phase 2 swaps its shim for `import alfred.context` and the v41 demo passes.*

| # | Feature | Definition of done | Status |
|---|---------|--------------------|--------|
| A0 | **Seam contract sign-off** | SEAM_CONTRACT.md agreed (signatures, ShapedPayload + `schema_version`, grade registry, Core re-validates filters) | ✅ 2026-06-10 |
| A1 | **Protocol split (C-1)** | `DomainContext` + `AgentConfig` protocols; `DomainConfig` = composed (Kitchen/FPL untouched, zero migration); **`pre_write` lands in `DomainContext`** (amendment of record); CI import-linter: `alfred.context` imports no langgraph/instructor | ✅ 2026-06-11 — PM-verified ([0611-protocol-split](0611-protocol-split/SUMMARY.md): 78 members 34/44, 23 abstract frozen, 221 tests, mypy 368→368, seam import live) |
| A2 | **Grade registry (C-6 minimal)** | Domain declares named grades as strip sets; core validates `external ⊇ reply` at registration (loud failure); grades applied at assembly time | ✅ 2026-06-11 — PM-verified ([0611-grade-registry](0611-grade-registry/SUMMARY.md): `grades.py` stdlib-only, `get_audience_grades` defaulted (35/44, abstract unchanged), 234 tests, mypy 368→368, seam exports canonical, Guardrail #3 pinned by equality test) |
| A3 | **State-free entrypoints (E2/C-5)** | `assemble_entity_context` / `assemble_subdomain_read` per seam contract, built as thin compositions over the internal assembly chain (identity policy + grade as parameters); core-side filter validation; no AlfredState/session/LLM on any path (E5 test); **3 golden consumer fixtures green (S1-ref read, S3 recipe, S5 preload — see Compatibility Guardrail)** | ✅ 2026-06-12 — PM-verified ([0612-assembly-entrypoints](0612-assembly-entrypoints/SUMMARY.md): `context/assembly.py` async per amended §1, all 3 fixtures green, 266 tests, mypy 368→368, S1 path untouched by construction; deviation accepted: import-time-domain-coupling fix in schema.py/tools — behavior-identical for registered domains, graduated to PITFALLS) |
| A4 | **Release: additive minor** | Tests green incl. new conformance tests (E2, E5-C0, import isolation, grade ordering); CHANGELOG; ledge pins min version; `/doc-review` run | Not Started |

## Track B — Write-Path Correctness 🟠 (starts now, small)

*Goal: every adapter write path is validated, attributed, and governed.*

| # | Feature | Definition of done | Status |
|---|---------|--------------------|--------|
| B1 | **E1 fix: middleware on update/delete** | Hook-shape decision (reuse `pre_write` vs `pre_update`/`pre_delete`); middleware threaded through `db_update`/`db_delete` (crud.py:501,529); loud error if domain middleware exists on a path that can't honor it; back-compat defaults for existing implementers | Not Started (stub: [0610-prewrite-update-delete](0610-prewrite-update-delete/RESEARCH.md)) |
| B2 | **E4 provenance: actor on writes** | `Actor` (user/system/integration) parameter on the write path; recorded; no anonymous machine writes | Not Started |
| B3 | **E11 write governance** | `get_transition_governed_fields()` + `is_registered_transition()` on `DomainContext`; executor refuses governed writes loudly | Not Started |

## Track C — S1 Declared Modes & Prompt Parameterization 🟡 (starts now, independent)

*Goal: chat CX improves (faster reads, predictable cost); prompts become deterministic, audited artifacts.*

| # | Feature | Definition of done | Status |
|---|---------|--------------------|--------|
| C1 | **Mode declaration schema** (one-pager, shared with Track D) | `{name, shape \| handler, dials, prompt content, context recipe, output schema, audience grade, sink}` pinned; unknown mode name = loud error (kills `from_dict` silent PLAN fallback) | Not Started |
| C2 | **Declared modes in S1** | Understand's LLM quick-mode classifier deleted (fields off `UnderstandOutput`); `MODE_CONFIG` → domain-overridable data; routing reads declared flags | Not Started |
| C3 | **Shape-gated prompt assembly** | injection.py sections shape-gated (composition, no template forks); per-shape action unions (generalize `ActQuickDecision`); compiled-prompt fixtures committed + diffed in CI; build manifest attached to traces | Not Started |
| C4 | **Per-shape evals + cache-stable prefixes** | Read-shape eval set (filter construction) + full-shape eval set (plan quality) green vs baseline; static skeleton = stable prefix (provider prefix caching verified) | Not Started |

## Track D — Mode Registry & New Shapes 🟢 (starts after C1; full speed after A4)

*Goal: registering a mode is cheap; S3 ships a real consumer; kitchen's duplication debt paid.*

| # | Feature | Definition of done | Status |
|---|---------|--------------------|--------|
| D1 | **Mode registry + dispatch** | Registry implementing C1 schema; `bypass_modes` deprecation path (existing handlers auto-register as handler-modes); E3 per-entry auth context | Not Started |
| D2 | **S3 one-shot executor** | Context recipe (over A3 entrypoints) → one LLM call (mode-owned prompt + output schema) → sink writer; idempotency key (upsert on entity+mode, run provenance — E8); audience grade applied (A2); C1-tier enforced in code (E5); headless traces (E7) | Not Started |
| D3 | **First S3 consumer shipped** | Ledge project summaries **or** memories `go_generate` migrated — one real consumer in production through the registry | Not Started |
| D4 | **S5 scaffold promotion** | Core owns preload/template-inject/history-cap/exit-sentinel/handoff scaffold; kitchen `cook` + `brainstorm` re-register as S5 modes (scaffold duplication deleted) | Not Started |
| D5 | **S4 bounded-write executor** | Needs B1+B3; refuses governed writes; declared-caller surfaces only (MCP internal adds, intake confirm); composition contract with S3 (persist-after-confirm) | Not Started |
| D6 | **E10 candidate retrieval + intake pattern** | `resolve_candidates(ctx, hints)` (C0; embeddings OK); selection inside the consuming mode's one call; S3→confirm→S4 intake flow proven with ledge UC4 | Not Started |
| D7 | **S1 read-path convergence** | S1 consumes the same assembly chain (grade `reply`, ref identity policy); the pipeline's bespoke read-shaping deleted; one substrate codepath | Not Started |

## Cross-Cutting

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| X1 | **Conformance checklist E1–E11** | One numbered doc in core; every other doc references by number; each E gains a test as its feature lands (E1→B1, E2/E5→A3/A4, E4→B2, E8→D2, E9→A3+D2, E10→D6, E11→B3) | Not Started |
| X2 | **Doc debt + legacy alias deletion** | core-public-api.md stale "4 wheel targets" fixed; P5 kitchen-residue sweep (`"quick weeknight meals"`, `["milk","eggs"]`, `__init__.py` Pantry docstring, crud.py "ingredient enrichment"); **delete the legacy domain-backed alias layer** (schema.py `__getattr__` + the 6 constant names, tools/`__init__` lazy hook + `__all__` entries — zero consumers grep-verified, `web/` is gone; one CHANGELOG "Removed" line, no deprecation cycle) | Not Started |

---

## Compatibility Guardrail — design for five shapes, build for one consumer

**The risk (named 2026-06-10):** the first consumer only cares about the first consumer.
Ledge MCP needs exactly two single-table, label-only, external-grade reads — if the
assembly layer gets shaped like that caller, the other shapes can't use it and will
bypass it, recreating the duplicated-substrate problem *inside* core. Four specific
exposure points and their guards:

1. **The seam functions are consumers of the assembly core, not the core itself.**
   `assemble_entity_context` / `assemble_subdomain_read` are thin S2-flavored
   compositions over an internal per-record/per-set chain (post_read → enrich →
   identity-translate → strip → format → header). Richer callers compose the chain
   directly: S3 recipes (memories `go_generate` pulls children + roster + facts +
   familypedia in one recipe), S5 preloads (brainstorm: profile + dashboard + inventory
   + 7-day meal plan), S1's read path. The chain is the substrate surface; the seam
   functions are two modes of using it.
2. **Identity is a policy parameter, not a payload property (E9).** ShapedPayload's
   "labels only" is the *external-grade* policy. The chain takes an identity strategy:
   session refs (S1, via registry translation), label-only (S2 external), UUID + label
   (internal tooling), durable labels + provenance (S3 sinks). Hard-coding label-only
   into the chain would lock S1 out — fast mode ("read mode") consumes the same chain
   with ref policy.
3. **Grade `"reply"` must reproduce today's S1 output byte-for-byte.** The grade
   registry's first conformance test is that S1's existing reply formatting maps to
   grade `reply` unchanged — proving grades wrap existing behavior rather than forking it.
4. **A1's bucket test is "knowledge/shaping, no LLM" — never "does ledge need it."**
   Already bitten once (`pre_write` mis-bucketed by CORE_RESTRUCTURE); the split is
   audited against all five shapes' needs, not the MCP read path.

**The mechanism — golden consumer fixtures (added to A3's DoD):** three non-ledge
fixture recipes live as tests against the assembly core from day one —
(a) an S1 ref-translated read (fast-mode shaped), (b) a memories-shaped multi-fetch S3
recipe, (c) a kitchen-brainstorm S5 preload. None ships a consumer; each proves the
layer can express that shape **without bypass**. A Track-A feature that breaks a fixture
doesn't merge. Cheap to write, permanent compatibility pressure.

**The convergence feature (new, D-track):** D7 — S1's read path consumes the same
assembly chain (grade `reply`, ref identity policy). Not urgent, but planned now so the
two shaping codepaths are a temporary state with an owner, not permanent drift.

## Dependency Graph

```
A0 ✅ → A1 → A2 → A3 → A4 ──────────→ (ledge v41 Phase 2 swap)
                          └→ D2 (uses A3 entrypoints + A2 grades)
B1 ──────────→ B2 → B3 ──→ D5
C1 ──→ C2 → C3 → C4
  └──→ D1 → D2 → D3 → D4
              └────────→ D5 (also needs B1+B3) → D6
```

**Start now, in parallel:** A1 · B1 · C1. Nothing else blocks on a conversation.

## Key Decisions (locked 2026-06-10)

| # | Decision | Reference |
|---|----------|-----------|
| K1 | Seam contract agreed with amendments: grade = registry string (not enum), Core re-validates filters, `schema_version` on ShapedPayload, header inside entrypoints, `alfred.context` home | SEAM_CONTRACT.md §6 |
| K2 | S-framing supersedes M-catalog; sink is per-mode declaration; S1 ≠ chat | 0610-mode-language.md §8.3 |
| K3 | Shapes fixed (5 + handler), grown by convergence only; modes unlimited per consumer | 0610-mode-language.md §1 |
| K4 | C1 prompts/schemas live in mode registrations (third bucket); `pre_write` in `DomainContext` | 0610-mode-language.md §5.1, §8.2 |
| K5 | S4 last — gated on E1+E11; first consumers are declared-caller surfaces, not chat | 0610-mode-language.md §8.7 |
| K6 | Auto-escalation / replan edge / dynamic mode switching deferred (single Act→Think edge buys all later) | 0610-declared-modes RESEARCH |
| K7 | No patch-release rush on E1; lands as B1 inside the program | Owner, 2026-06-10 |
| K8 | Declare/enforce symmetry is doctrine: DomainContext declares, core enforces, convention = failure | 0610-substrate.md §1 |
| K9 | First-consumer pressure is guarded mechanically: golden consumer fixtures (S1/S3/S5) gate every Track-A merge; seam functions are consumers of the assembly chain, never the chain itself; identity is an E9 policy parameter | Compatibility Guardrail section |

## Non-Goals (this program)

- No router/auto-routing (later layer; only ever picks among registered modes)
- No new shapes beyond S1–S5 + handler (classify-dispatch stays a watch item)
- No OAuth / external auth work (ledge-side, v1)
- No TS substrate port (service exposure is consumer-side until demand says otherwise)
- No package/extras split (import-level isolation suffices; defer)
