# Plan: Protocol Split — DomainContext / AgentConfig (A1)

**Date:** 2026-06-11
**Based on:** RESEARCH.md (full 78-method sort, flagged ambiguities, import-chain audit)

## Approach

Split `DomainConfig` into two sibling ABCs by **verbatim relocation** of method bodies — `DomainContext` (34 members, 15 abstract) in a new `alfred/domain/context.py`, `AgentConfig` (44 members, 8 abstract) in a new `alfred/domain/agent.py` — and rewrite `base.py` as `class DomainConfig(DomainContext, AgentConfig)` plus a re-export shim covering every symbol any consumer imports today. Lock the seam contract's import-isolation guarantee with a subprocess-based pytest, and freeze the bucket sort itself with a conformance test so it can't drift silently.

## Reuse Map

| Capability | Reuse / New | Symbol + Path | Why |
|------------|-------------|---------------|-----|
| The two protocol bodies | **Reuse (move verbatim)** | All 78 members of `DomainConfig`, `src/alfred/domain/base.py:217-1419`; `CRUDMiddleware` at `base.py:141`; 5 dataclasses at `base.py:26-138` | A1 is a boundary, not a rewrite — bodies, signatures, docstrings unchanged |
| Back-compat import surface | **Reuse** | `from alfred.domain.base import DomainConfig, EntityDefinition, SubdomainDefinition, ReadPreprocessResult, ToolContext, CRUDMiddleware` — grep-verified consumers: `tests/core/conftest.py:17`, `tests/core/test_crud.py:263`, `src/alfred/graph/nodes/act.py:1549`, `src/alfred/core/id_registry.py:24`, `docs/bridge/domain-scaffold` | `base.py` re-exports make every existing import line keep working — zero migration |
| Registration | **Reuse (untouched)** | `register_domain()` / `get_current_domain()`, `src/alfred/domain/__init__.py:29,43` | Still typed `DomainConfig`; per-call `ctx: DomainContext` is A3's job |
| Isolation target module | **Reuse** | `alfred/context/__init__.py` (verified langgraph/instructor-free chain) | Seam §6 item 4 names `alfred.context` the home; it only needs a `DomainContext` re-export + a test lock |
| Zero-migration proof fixture | **Reuse** | `StubDomainConfig`, `tests/core/conftest.py:35` | The composed protocol unchanged ⇒ this class compiles and registers untouched |
| Import-linter mechanism | **New (searched)** | New `tests/core/test_import_isolation.py` | No `.github/workflows`, no `import-linter` in dev deps (`pyproject.toml`). A stdlib `subprocess` + `sys.modules` assertion needs zero new dependencies and runs in the existing `pytest tests/ -v` gate — adding the `import-linter` package would be a new dep for strictly less precision |
| Sort-drift guard | **New (searched)** | New `tests/core/test_protocol_split.py` | Nothing existing asserts protocol membership; `tests/core/test_domain_config.py` checks behavior, not topology |

## File Layout (decided from RESEARCH open question 1)

```
src/alfred/domain/
├── context.py    NEW — DomainContext ABC + EntityDefinition, SubdomainDefinition,
│                       ReadPreprocessResult, CRUDMiddleware (pre_write lives here — amendment of record)
├── agent.py      NEW — AgentConfig ABC + ToolDefinition, ToolContext
├── base.py       REWRITTEN — imports both halves; DomainConfig(DomainContext, AgentConfig);
│                       __all__ re-exports every public symbol that lives here today
└── __init__.py   EDITED — additionally export DomainContext, AgentConfig

src/alfred/context/__init__.py   EDITED — re-export DomainContext (the seam import path:
                                 `from alfred.context import DomainContext`)
```

`alfred.domain.context` (module) vs `alfred.context` (package) coexist without conflict; the canonical definition sits with the rest of the domain protocol, the seam-facing re-export sits where the contract says consumers import from.

## Tasks

- [ ] 1. Create `src/alfred/domain/context.py`: module docstring stating the bucket test + the two amendments of record (`pre_write` per 0610-mode-language §5.1; C-10 compilers per 0610-substrate); move `EntityDefinition`, `SubdomainDefinition`, `ReadPreprocessResult`, `CRUDMiddleware` and the 34 CTX members verbatim into `class DomainContext(ABC)`. Only imports: `abc`, `dataclasses`, `typing` (+ TYPE_CHECKING `DatabaseAdapter`).
- [ ] 2. Create `src/alfred/domain/agent.py`: move `ToolDefinition`, `ToolContext` and the 44 AGT members verbatim into `class AgentConfig(ABC)`; re-declare `name` and `entities` as abstract members with identical signatures (AGT defaults reference them — RESEARCH flag 11). Same import discipline.
- [ ] 3. Rewrite `src/alfred/domain/base.py`: keep module + class docstrings; `class DomainConfig(DomainContext, AgentConfig)` with body = docstring only; explicit `__all__` re-exporting `DomainConfig`, `DomainContext`, `AgentConfig`, `EntityDefinition`, `SubdomainDefinition`, `ReadPreprocessResult`, `ToolDefinition`, `ToolContext`, `CRUDMiddleware`.
- [ ] 4. Edit `src/alfred/domain/__init__.py`: add `DomainContext`, `AgentConfig` to imports + `__all__`.
- [ ] 5. Edit `src/alfred/context/__init__.py`: add `from alfred.domain.context import DomainContext` + `__all__` entry (keeps the package import-clean: `alfred.domain.context` imports nothing heavy).
- [ ] 6. Add `tests/core/test_import_isolation.py`: in a fresh subprocess, `import alfred.context` then assert no `sys.modules` entry starts with `langgraph`, `instructor`, `alfred.graph`, or `alfred.llm`; on failure print the offending modules (loud, named). Second case: same guarantee for `import alfred.domain`.
- [ ] 7. Add `tests/core/test_protocol_split.py`:
  - `DomainConfig` is a subclass of both halves; `StubDomainConfig()` is an instance of all three (zero-migration proof).
  - Frozen `CONTEXT_MEMBERS` / `AGENT_MEMBERS` name-sets (from RESEARCH tables) match exactly what each ABC defines — a method added to the wrong half or to `DomainConfig` directly fails the test with the stray names listed.
  - `pre_write` is defined on the `CRUDMiddleware` exported by `alfred.domain.context` (amendment pinned in code).
  - The composed abstract set == the frozen 23-name set (release-compat guard).
  - A minimal `DomainContext`-only subclass implementing its 15 abstracts instantiates — proving the narrow half is independently implementable (what ledge does).
- [ ] 8. Run `pytest tests/ -v`, `ruff check src/`, `ruff format src/`, `mypy src/` — all green/clean, zero edits to `StubDomainConfig` or any test that exists today.
- [ ] 9. Plan-adherence check against the diff, then SUMMARY.md (incl. doc-drift notes for A4: method count 75→78, `get_table_format` stale claim, core-domain-architecture §2/§7).

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| ABC composition vs `typing.Protocol` | Two ABCs, `DomainConfig` inherits both | Preserves abstractmethod enforcement, 55 default bodies, isinstance semantics — byte-for-byte back-compat. Protocol buys structural typing nobody needs (all consumers import the class anyway) and complicates defaults under mypy strict |
| `pre_write` home | `DomainContext` (whole `CRUDMiddleware` class moves there) | Amendment of record — E1/S4: bounded writes have no pipeline, middleware must still fire (0610-mode-language §5.1; roadmap K4). Deliberately overrides CORE_RESTRUCTURE's bucket table |
| `infer_entity_type_from_artifact`, `compute_artifact_label`, `get_payload_compilers` | `DomainContext` | Bucket test passes (structural knowledge / C-10 shaping, no LLM); S3 substrate sinks need them with no pipeline. Two further deliberate departures from CORE_RESTRUCTURE, argued in RESEARCH flags 2–4 |
| Reply-rendering family (`get_subdomain_formatters` et al.) | `AgentConfig` | User-bound rendering ≠ LLM-bound shaping; substrate §3 excludes UI rendering. The LLM-bound shaping set (`get_strip_fields`, `format_*_for_context`) stays Context |
| `name` + `entities` re-declared abstract on `AgentConfig` | Yes | Three AGT defaults derive from them; identical signatures merge cleanly in the composed MRO; keeps each half self-contained for mypy strict without `type: ignore` |
| Import-linter form | Subprocess pytest, not the `import-linter` package | Zero new dependency; runs inside the existing test gate (repo has no workflow CI); asserts the *exact* seam guarantee incl. internal `alfred.graph`/`alfred.llm` |
| `alfred.context` exports `DomainContext` in A1 | Yes | Costless now; means the import path ledge will use exists from this release and the isolation test guards the true seam surface |
| `register_domain` signature | Unchanged (`DomainConfig`) | A1 splits the protocol only; per-call `ctx: DomainContext` arrives with A3's entrypoints |
| Module names | `domain/context.py` + `domain/agent.py` | Mirrors the protocol names; gives B3's future `get_transition_governed_fields()` an obvious home (context.py) |

## Error Handling

- No behavioral code paths change, so no new runtime failure modes are introduced; the loud-failure obligations here are **test-side**: the isolation test names the offending imported modules; the sort-conformance test names stray/missing methods; the abstract-set test names the changed abstracts.
- No `getattr(domain, ..., default)` and no `try/except` around domain calls anywhere in the new code (PITFALLS: loud-errors-over-silent-fallbacks).
- `AgentConfig`'s abstract `name`/`entities` mean a hypothetical AgentConfig-only implementer fails at instantiation (loud) rather than at first default-method call (silent attribute error).

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/domain/context.py` | NEW — DomainContext + 4 supporting types (moved verbatim) |
| `src/alfred/domain/agent.py` | NEW — AgentConfig + 2 supporting types (moved verbatim) |
| `src/alfred/domain/base.py` | Rewritten as composition + `__all__` re-export shim |
| `src/alfred/domain/__init__.py` | Export the two new protocols |
| `src/alfred/context/__init__.py` | Re-export `DomainContext` |
| `tests/core/test_import_isolation.py` | NEW — seam import-isolation lock |
| `tests/core/test_protocol_split.py` | NEW — composition, sort-freeze, abstract-set, narrow-half instantiability |

Nothing else in `src/` changes. No existing test file changes.

## Definition of Done (A1, from the program roadmap + pm defaults)

- [ ] `pytest tests/ -v` passes with zero edits to existing tests (`StubDomainConfig` untouched = Kitchen/FPL-style zero migration proven)
- [ ] `DomainConfig` composed abstract set unchanged (frozen-set test) — additive release posture
- [ ] `pre_write` (via `CRUDMiddleware`) lives in `alfred.domain.context` — amendment-of-record test
- [ ] Import-isolation test green: `import alfred.context` ⇒ no langgraph/instructor (nor `alfred.graph`/`alfred.llm`)
- [ ] Sort-conformance test pins all 78 members to their bucket (audited against all five shapes in RESEARCH, not the MCP read path)
- [ ] Seam §1 signatures remain implementable over `DomainContext` alone (RESEARCH five-shape audit; narrow-half instantiability test)
- [ ] `ruff check src/` + `ruff format src/` + `mypy src/` clean
- [ ] Docs impact noted for A4 `/doc-review`: method count 75→78 (CLAUDE.md, core-domain-architecture.md §2/§7), split description, injection-map `get_table_format` stale claim, mode-language §5.1 "carry back" satisfied
