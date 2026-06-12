# Research: Protocol Split — DomainContext / AgentConfig (A1, C-1)

**Goal:** Split the `DomainConfig` ABC into two composable protocols — `DomainContext` (domain knowledge + shaping, no LLM/pipeline) and `AgentConfig` (pipeline-only) — with `DomainConfig` composed of both, zero migration for existing implementers.
**Type:** refactor (additive release posture)
**Date:** 2026-06-11
**Program:** Track A feature A1 ([0610-program-roadmap.md](../0610-program-roadmap.md)) · implements substrate C-1 boundary ([0610-substrate.md](../0610-substrate.md)) · seam contract §1/§6 ([SEAM_CONTRACT.md](../../../../landscaping/docs/roadmaps/launch/v41-ledge-mcp/specs/SEAM_CONTRACT.md))

## Context

Ledge v41 Phase 2 swaps its MCP shim for `import alfred.context`; the seam contract types its entrypoints on `ctx: DomainContext` with an import-isolation guarantee (importing only `alfred.context` never imports langgraph/instructor). A1 draws the protocol boundary; A2 (grades) and A3 (state-free entrypoints) build on it. The split must be audited against all five shapes (S1–S5), not just the MCP read path.

## Verified Current State

| Fact | Evidence |
|------|----------|
| `DomainConfig` has **78** methods/properties (docs say 75 — doc-count-drift, note for `/doc-review`) | `def` count inside class, `src/alfred/domain/base.py:217-1419` |
| 23 abstract, 55 default | matches docs' abstract count; totals drifted |
| `base.py` imports only `abc`, `dataclasses`, `typing` (+ TYPE_CHECKING `DatabaseAdapter`) — already LLM-free | `base.py:15-22` |
| `langgraph` is imported in exactly one module: `graph/workflow.py:28`; `instructor` only in `llm/client.py:18` | grep `langgraph\|instructor` over `src/alfred` |
| `alfred/context/` package (entity, conversation, builders, reasoning) has **no module-level imports** outside `dataclasses`/`typing`/intra-package — all `alfred.domain` access is function-level | grep `^(import\|from)` over `src/alfred/context` |
| `alfred/__init__.py` is trivial (docstring + `__version__`) | read |
| ⇒ `import alfred.context` is **already** langgraph/instructor-free today. A1 locks the guarantee with a test rather than refactoring imports | — |
| `CRUDMiddleware` (with `pre_read`/`pre_write`/`post_read`/`deduplicate_batch`) is a class in `base.py:141`, reached via `DomainConfig.get_crud_middleware()` — so "`pre_write` lands in DomainContext" concretely means: **the whole CRUDMiddleware class + `get_crud_middleware()` live on the Context side** | `base.py:141-214, 576` |
| All external import paths flow through `alfred.domain.base` / `alfred.domain` (conftest, kitchen-style scaffold, core nodes) — re-exports from `base.py` preserve every consumer | grep `from alfred.domain` |
| No `.github/workflows` — "CI" = the pytest suite; the import-linter lands as a test | `Test-Path` |
| Tests use `StubDomainConfig` in `tests/core/conftest.py:35` — implements the 23 abstracts, subclasses `DomainConfig`. Zero-migration proof target | read |
| mypy strict, ruff `E,F,I,UP,B`, hatchling builds `src/alfred` only | `pyproject.toml` |

## The Bucket Test (operationalized)

From the roadmap (Compatibility Guardrail #4): **"is it knowledge/shaping with no LLM?"** — never "does the MCP read path need it." Operationally:

- **DomainContext (CTX)** — declarative domain knowledge (A) or data-shaping transforms on LLM-bound/external-bound payloads (B). No concept of prompts, personas, nodes, steps, turns, modes, agents, or conversation. Implementable with zero LLM machinery.
- **AgentConfig (AGT)** — anything whose *semantics* require the pipeline (nodes/steps/turns/modes/agents/conversation memory), LLM behavior (prompt content, personas, LLM config, prompt logging), or user-facing conversational rendering (substrate boundary: "no UI rendering" — [0610-substrate.md](../0610-substrate.md) §3).
- **Neither** — single-call prompts + output schemas are mode-owned (third bucket, [0610-mode-language.md](../0610-mode-language.md) §8.2). Nothing in today's `DomainConfig` falls there; noted so the split doesn't accidentally claim future mode territory.

## Full Method Sort — all 78

### DomainContext — 34 members (15 abstract)

| # | Member | Abstract? | Core consumer (verified) | Rationale (one line) |
|---|--------|-----------|--------------------------|----------------------|
| 1 | `name` | ✦ | workflow, reply | Structural identity; every shape needs it |
| 2 | `entities` | ✦ | workflow, act, summarize | The data model — C-4 root |
| 3 | `subdomains` | ✦ | think, act | Table grouping — structural knowledge |
| 4 | `table_to_type` | — | (derived) | Computed from `entities` |
| 5 | `type_to_table` | — | (derived) | Computed from `entities` |
| 6 | `get_table_format` | ✦ | **none found in core** (flag: doc drift) | Per-table formatting rules = shaping knowledge |
| 7 | `get_fk_field_aliases` | — | id_registry:846 | FK normalization — C-3/C-4 knowledge |
| 8 | `get_fk_enrich_map` | ✦ | id_registry | C-4 entity intelligence (FK → display name) |
| 9 | `get_field_enums` | ✦ | schema.py | C-9 schema knowledge |
| 10 | `get_semantic_notes` | ✦ | schema.py, entity context | C-5 chain's header sliver (seam §1) |
| 11 | `get_fallback_schemas` | ✦ | schema.py | C-9 deterministic fallback chain |
| 12 | `get_scope_config` | — | schema.py:38 | Cross-subdomain relationships — declarative |
| 13 | `get_crud_middleware` | — | crud.py | **C-2: middleware fires on every adapter path — incl. S4 bounded writes (no pipeline). `pre_write` here is the amendment of record** ([0610-mode-language.md](../0610-mode-language.md) §5.1) |
| 14 | `get_user_owned_tables` | ✦ | crud.py | C-1 scoped access |
| 15 | `get_uuid_fields` | ✦ | crud.py `_sanitize_uuid_fields` | C-10 write-side sanitization |
| 16 | `get_subdomain_registry` | ✦ | schema.py | C-9 introspection map |
| 17 | `infer_entity_type_from_artifact` | ✦ | act.py:66, summarize.py:846 | ⚠ flagged below — structural artifact→type knowledge, no LLM |
| 18 | `compute_entity_label` | ✦ | id_registry | C-4 labeling |
| 19 | `compute_entity_label_from_fks` | — | id_registry | C-4 labeling fallback |
| 20 | `get_entity_data_legend` | — | context/builders:303 | C-4 "how to read this" hint |
| 21 | `detect_detail_level` | — | id_registry:219 | Structural (record fields → summary/full); registry mechanism is substrate (C-3) |
| 22 | `compute_artifact_label` | — | act.py:72 | ⚠ flagged — durable labels frozen at generation are an E9/§8.6 substrate concern |
| 23 | `get_subdomain_aliases` | ✦ | normalization | C-7 fragment (candidate matching) |
| 24 | `get_strip_fields` | — | act, reply | C-6 grade precursor — the method A2's registry generalizes |
| 25 | `format_entity_for_context` | — | act entity context | C-5 shaping (LLM-bound) |
| 26 | `infer_table_from_record` | — | act, reply, memory | Structural record→table knowledge |
| 27 | `format_record_for_context` | — | act | **Named step of the C-5 chain (seam §1)** |
| 28 | `format_records_for_context` | — | act | C-5 list shaping |
| 29 | `get_payload_compilers` | — | core/payload_compiler.py:117 | ⚠ flagged below — C-10 write-side shaping is substrate |
| 30 | `get_user_profile` | — | think, act | B-layer data assembly; S5 preloads + S3 recipes consume it |
| 31 | `get_domain_snapshot` | — | think | B-layer data assembly (S5 brainstorm preload uses dashboard) |
| 32 | `get_subdomain_guidance` | — | think, act | Per-user preference *data* (kitchen's is S3-written to a table); consumed by prompts but is data assembly |
| 33 | `get_db_adapter` | ✦ | crud.py | C-1; carries auth/tenant context per seam E3 |
| 34 | `get_entity_key_fields` | — | **none found in core** (flag) | Entity-card display-shaping knowledge |

Plus the **supporting types** that move with CTX: `EntityDefinition`, `SubdomainDefinition`, `ReadPreprocessResult`, `CRUDMiddleware` (all four hooks, incl. `pre_write`).

### AgentConfig — 44 members (8 abstract)

| # | Member | Abstract? | Core consumer | Rationale |
|---|--------|-----------|---------------|-----------|
| 35 | `get_persona` | ✦ | act quick | LLM persona — prompt content |
| 36 | `get_examples` | ✦ | act | Few-shot prompt content |
| 37 | `get_act_subdomain_header` | — | injection.py | Act prompt section |
| 38 | `get_empty_response` | ✦ | reply.py:343 | ⚠ flagged — user-facing copy (substrate: "no UI rendering") |
| 39 | `get_entity_recency_window` | — | id_registry:1035, builders:364 | ⚠ flagged — "turns" exist only in session shapes; session-scoped registry *contents* are S1 services (substrate §3) |
| 40 | `get_tool_enabled_step_types` | — | act | Steps are pipeline topology |
| 41 | `get_custom_tools` | — | act tool dispatch | `ToolContext` carries `AlfredState` — pipeline-welded |
| 42 | `get_crud_reference` | — | injection.py | Prompt documentation |
| 43 | `get_act_step_template` | — | injection.py | Prompt template layer |
| 44 | `get_prompt_log_adapter` | — | llm/prompt_logger:211 | ⚠ flagged — LLM observability; no C0 path touches it |
| 45 | `get_subdomain_examples` | ✦ | schema.py:339→prompt context | ⚠ flagged — example *queries* are prompt content even though a schema-module function consumes them |
| 46 | `get_archive_key_for_description` | — | act.py:1724 | Pipeline step-result archive |
| 47 | `get_archive_keys_for_subdomain` | — | act.py:1782 | Pipeline archive lifecycle |
| 48 | `get_bold_skip_words` | — | memory, summarize | Parses *assistant prose* — exists only where an LLM replied |
| 49 | `get_generated_content_markers` | — | memory/conversation:87 | Conversation-memory detection |
| 50 | `get_generated_content_label` | — | memory/conversation:99 | Conversation-summary copy |
| 51 | `get_relevant_entity_types` | — | memory/conversation:394 | ⚠ flagged — conversation-context salience (S1 service) |
| 52 | `get_tracked_entity_types` | — | **none found in core** (flag) | ⚠ flagged — "tracked across orchestration steps" = session salience |
| 53 | `get_subdomain_formatters` | ✦ | reply.py:350 | ⚠ flagged — deterministic *reply rendering* (user-bound, not LLM-bound) |
| 54 | `get_system_prompt` | — | reply | Assistant identity — prompt content |
| 55 | `get_quick_write_confirmation` | — | reply.py:355 | User-facing copy, quick-mode |
| 56 | `get_priority_fields` | — | reply.py:1226 | Reply display ordering |
| 57 | `format_records_for_reply` | — | reply.py:1119 | Reply rendering |
| 58 | `get_item_tracking_keys` | — | reply.py:993 | Conversation item-name tracking |
| 59 | `bypass_modes` | ✦ | workflow | Mode dispatch |
| 60 | `default_agent` | ✦ | workflow | Agent routing |
| 61 | `agents` | — | workflow | Multi-agent registration |
| 62 | `agent_router` | — | workflow | Routing |
| 63 | `get_mode_llm_config` | — | workflow/modes | LLM config |
| 64 | `get_reply_prompt_content` | — | reply | Prompt replacement |
| 65 | `get_act_prompt_content` | — | act | Prompt replacement |
| 66 | `get_act_prompt_injection` | — | act | Prompt injection |
| 67 | `get_think_prompt_content` | — | think | Prompt replacement |
| 68 | `get_understand_prompt_content` | — | understand | Prompt replacement |
| 69 | `get_understand_system_prompt` | — | understand | Prompt content |
| 70 | `get_filter_schema` | — | injection (Act prompts) | Filter *documentation for the LLM*. Note: seam A2's core-side filter **validation** is core code + C-9 schema — it does not depend on this method |
| 71 | `get_summarize_system_prompts` | — | summarize | Prompt content |
| 72 | `get_think_domain_context` | — | think | Prompt placeholder |
| 73 | `get_think_planning_guide` | — | think | Prompt placeholder |
| 74 | `get_reply_continuity_guidance` | — | reply | Turn-indexed prompt guidance |
| 75 | `get_reply_subdomain_guide` | — | reply | Prompt placeholder |
| 76 | `get_router_prompt_injection` | — | router | Prompt content |
| 77 | `get_handoff_system_prompts` | — | modes/handoff | Bypass-mode prompt content |
| 78 | `get_handoff_result_model` | ✦ | modes/handoff | Bypass/S5 pipeline contract (D4 re-homes the scaffold; mode-side today) |

Plus supporting types that move with AGT: `ToolDefinition`, `ToolContext` (carries `AlfredState`).

**Counts:** 34 + 44 = 78 ✓ · abstracts 15 + 8 = 23 ✓ (composed `DomainConfig` abstract set unchanged).

## Flagged / Ambiguous Calls (explicit, per DoD)

1. **`pre_write` → CTX (amendment of record).** CORE_RESTRUCTURE.md bucketed it Agent ("genuinely pipeline-side"). Overridden per [0610-mode-language.md](../0610-mode-language.md) §5.1: E1/S4 — bounded writes have **no pipeline** and `pre_write` MUST fire on them. Mechanically: `CRUDMiddleware` (the whole class) + `get_crud_middleware()` sit in the Context module, so B1's update/delete threading happens entirely substrate-side.
2. **`infer_entity_type_from_artifact` → CTX (second deliberate departure from CORE_RESTRUCTURE).** The bucket test passes: dict-structure → type name, no LLM, no session. Five-shape audit: S3 modes with substrate sinks (D2 sink writer, C-10 "callable from any shape that writes generated artifacts") need artifact→type without a pipeline. CORE_RESTRUCTURE's "only matters mid-pipeline" was the first-consumer fallacy in reverse.
3. **`compute_artifact_label` → CTX.** Same family; §8.6 requires stored artifacts to carry *durable labels frozen at generation* — the label source must be reachable from non-pipeline shapes.
4. **`get_payload_compilers` → CTX.** CORE_RESTRUCTURE grouped compilers under Mode/agent (C/D). The substrate doc (newer, 0610) names payload compilation **C-10, substrate**, gap = "callable from any writing shape." Compilers are data→schema shaping with no LLM. Departure #3, same rationale as #2.
5. **Reply-rendering family → AGT** (`get_subdomain_formatters`, `format_records_for_reply`, `get_priority_fields`, `get_empty_response`, `get_quick_write_confirmation`, `get_item_tracking_keys`). These are user-bound rendering/copy, not LLM-bound shaping — substrate §3 excludes UI rendering. Not a CORE_RESTRUCTURE conflict: its "Reply formatting → Context (B)" row names only `strip_fields` + `format_record/entity_for_context`, which all land CTX here. Watch item: if D7 (S1 read-path convergence) later wants deterministic formatters on the substrate chain, that's a mode-registration concern, not a protocol move.
6. **`get_entity_recency_window` → AGT.** Consumed by the registry (C-3 substrate *mechanism*), but it parameterizes turn-recency of session-scoped *contents*, which substrate §3 explicitly assigns to S1. No turn concept exists in S2/S3/S4; S5 freezes context.
7. **`get_tracked_entity_types` / `get_relevant_entity_types` → AGT.** Session/conversation salience filters. Defaults derive from `entities` (CTX), so AgentConfig declares `entities` abstract (see below). `get_tracked_entity_types` currently has **no core consumer** — bucketed by semantics.
8. **`get_prompt_log_adapter` → AGT.** It returns a DB adapter (no LLM import), but its sole purpose is LLM-call observability; no C0 path can reach it. Future S3 prompt logging is the mode registry's concern (C1 third bucket), not DomainContext's.
9. **`get_subdomain_examples` → AGT.** Consumed via `tools/schema.py`'s prompt-context builder, but the content is example *queries for the Think/Act LLM* — prompt content. A3's read path must not call the prompt-side schema function (A3 concern, noted for that feature).
10. **`get_table_format` + `get_entity_key_fields` → CTX, currently unconsumed in core.** Shaping-knowledge semantics; flag for `/doc-review` (injection-map claims `get_table_format` is used by injection — stale).
11. **Cross-half default-implementation references:** AGT defaults read `self.name` (`get_system_prompt`) and `self.entities` (`get_tracked_entity_types`, `get_relevant_entity_types`, `get_item_tracking_keys`). AgentConfig must re-declare `name` and `entities` as abstract members (identical signatures — MRO merges them in the composed class; mypy-strict clean; zero implementer impact).

## Five-Shape Audit (Guardrail #4)

| Shape | What it needs from the split | Satisfied? |
|-------|------------------------------|-----------|
| S1 agentic-loop | Everything | Composed `DomainConfig` unchanged ✓ |
| S2 shaped-read | adapter, scoping, `post_read`, fk_enrich, strip(grade), `format_record_for_context`, semantic notes, schema introspection, aliases | All CTX ✓ (seam §1 chain implementable over CTX alone) |
| S3 one-shot | Context recipes (profile/snapshot/guidance, entity intelligence, formatting); sinks (compilers, artifact type/label inference, uuid sanitization, `pre_write`, dedupe) | All CTX ✓; prompts/schemas deliberately in neither (mode-owned, §8.2) |
| S4 bounded-write | `pre_write` firing, scoping, sanitization; later `get_transition_governed_fields` (B3) | CTX ✓; B3's new declarations have a natural CTX home |
| S5 preloaded-session | Preload recipe = reads + profile/snapshot (CTX ✓); frozen template + handoff prompts/model (AGT/mode-owned — D4 re-registers via registry) | ✓ |

## Findings

1. **The import-isolation half of the DoD is a lock, not a refactor.** `alfred.context` is already clean (verified above); the deliverable is a subprocess-based pytest that fails loudly if anyone adds a module-level langgraph/instructor/`alfred.graph`/`alfred.llm` import to the chain.
2. **ABC composition, not `typing.Protocol`.** Today's `DomainConfig` is an ABC with 55 default bodies and abstractmethod enforcement. Two ABC halves + `class DomainConfig(DomainContext, AgentConfig)` preserves isinstance checks, default inheritance, and the abstract set byte-for-byte. CORE_RESTRUCTURE sketched `Protocol`, but Protocol-with-defaults changes runtime semantics and mypy behavior for zero benefit — every consumer imports `alfred.context` anyway (nominal subtyping is fine, and ledge subclasses `DomainContext` directly).
3. **Zero-migration surface is exactly the `base.py` re-export list:** `DomainConfig`, `EntityDefinition`, `SubdomainDefinition`, `ReadPreprocessResult`, `ToolDefinition`, `ToolContext`, `CRUDMiddleware` (grep-verified: conftest, scaffold, core internals all import via `alfred.domain.base` or `alfred.domain`).
4. **Method bodies don't move semantically** — verbatim relocation into two modules; `base.py` becomes composition + re-exports. No call-site in `src/alfred` changes (`get_current_domain()` still returns `DomainConfig`).
5. **Doc drift found:** method count 78 vs documented 75; `get_table_format` documented as injection-consumed but isn't. Both queue for A4's `/doc-review` (doc-count-drift pitfall).
6. **A3 remains implementable over the split** (seam §1): every function in the internal chain (post_read → fk_enrich → strip → format → header) plus filter validation inputs (FilterClause ops, C-9 schema methods) types against CTX members only.

## Open Questions (carried to PLAN)

1. File layout: `alfred/domain/context.py` + `alfred/domain/agent.py` (recommended) vs one `protocols.py`.
2. Should `alfred.context` re-export `DomainContext` now (A1) so ledge's eventual import path (`from alfred.context import DomainContext`) exists from day one? (Recommended: yes — costless, and the import-linter test then guards the real seam surface.)
3. Whether `register_domain()` should also accept/validate the halves — **no** for A1 (it stays `DomainConfig`; per-call `ctx: DomainContext` arrives with A3).
