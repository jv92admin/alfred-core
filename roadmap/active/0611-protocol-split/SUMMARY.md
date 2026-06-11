# Summary: Protocol Split — DomainContext / AgentConfig (A1)

**Date:** 2026-06-11

## What Was Done

- Split the 78-member `DomainConfig` ABC into two composable ABCs by verbatim relocation:
  - **`src/alfred/domain/context.py`** — `DomainContext` (34 members, 15 abstract) + `EntityDefinition`, `SubdomainDefinition`, `ReadPreprocessResult`, and **`CRUDMiddleware` including `pre_write`** (the amendment of record, 0610-mode-language §5.1 — pinned by a test).
  - **`src/alfred/domain/agent.py`** — `AgentConfig` (44 members, 8 abstract) + `ToolDefinition`, `ToolContext`; re-declares `name`/`entities` abstract because three of its defaults derive from them (MRO merges the declarations in the composed class).
  - **`src/alfred/domain/base.py`** — now `class DomainConfig(DomainContext, AgentConfig)` plus an `__all__` shim re-exporting every symbol that historically lived there. All existing import paths work unchanged.
- `alfred.context` now exports `DomainContext` — the seam contract's import path (`from alfred.context import DomainContext`) exists from this release.
- **`tests/core/test_import_isolation.py`** — subprocess-based import-linter: `import alfred.context` (and `import alfred.domain`) pulls in no `langgraph`/`instructor`/`alfred.graph`/`alfred.llm`; names offenders on failure (seam contract §6 item 4).
- **`tests/core/test_protocol_split.py`** — sort-freeze (all 78 members pinned to their bucket; stray/missing names listed), composed abstract set frozen at 23, `DomainConfig` defines nothing directly, `pre_write` module pinned, `StubDomainConfig` satisfies all three protocols untouched, and a `DomainContext`-only implementer instantiates (the ledge shape).
- Added PITFALLS entry `unimported-module-rot` (incident below).

**Gates at completion:** 221 tests pass (208 pre-existing, zero edits to any + 13 new) · ruff check + format clean on every touched file · mypy at exact baseline parity (368 errors before = 368 after; the pre-existing annotation gaps relocated with the code) · `StubDomainConfig` and all consumer import paths byte-identical.

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| Pre-existing invalid Python in `agents/base.py:231` | Fixed (one-line param reorder) | `MultiAgentOrchestrator.__init__` had a non-default arg after a default — a `SyntaxError` that made the module unimportable and blocked mypy from checking *anything* in `src/`. Zero call sites exist; reorder keeps `default_agent` required (no invented silent default) and keyword callers unaffected |
| "ruff + mypy clean" gate scope | Touched files clean + repo baseline parity | The repo is not clean today (368 mypy errors in 27 files; widespread ruff violations in untouched modules). Repo-wide cleanup is not A1; gate = zero new violations, A1's new test files fully clean, relocated code carries its pre-existing errors at identical count |
| "Byte-for-byte" vs lint | Bodies/signatures verbatim; two provably no-op normalizations allowed | `from typing import Callable` → `collections.abc` (UP035, type-identical) and removal of redundant annotation quotes under `from __future__ import annotations` (UP037, runtime no-op). The mypy `type-arg` gaps (`dict` vs `dict[str, Any]`) were **not** fixed — tightening a public protocol's declared types is a compatibility decision, not lint |
| `ruff format` on touched files | Applied | Whitespace-only normalization by the project's own formatter (a CLAUDE.md quality command); no semantic change |
| `alfred/context/__init__.py` import sort | Fixed while editing | Pre-existing I001 in a file the plan already touches; mechanical |

## Deviations from Plan

1. **`src/alfred/agents/base.py` changed (1 line)** — not in the planned file list; required to make the mypy gate reachable at all (see decision table). Logged in PITFALLS as `unimported-module-rot`.
2. **Gate interpretation** — PLAN said "ruff check src/ + mypy src/ clean"; executed as touched-files-clean + baseline parity because the repo-wide state was already non-clean before A1 (discovered at baseline capture). Repo-wide lint/type cleanup is a separate work item; suggest adding to BACKLOG.
3. Everything else executed exactly as planned: every Reuse Map row honored, file list otherwise exact, no existing test modified.

## Watch Items (for later features — not blockers)

1. **`ToolDefinition`/`ToolContext` live in `agent.py` — honest today, revisit at D1.** `ToolContext` carries `step_results` and `AlfredState` (pipeline-coupled), so Agent-side is the correct bucket now. But D1's mode registry will need a tool story for non-S1 modes; when it does, look here — the likely shape is a narrower substrate-side tool context, not a re-home of these types.
2. **Two members have no core consumer** (`get_tracked_entity_types`, `get_entity_key_fields`) and `get_table_format`'s "used by the injection system" docstring is stale (no consumer found). Bucketed by semantics; candidates for deprecation review rather than silent carriage.

## Doc-Drift Queue for A4's `/doc-review` (so A4 doesn't rediscover)

| Doc | Drift |
|-----|-------|
| `CLAUDE.md` key-files table | "DomainConfig protocol (75 methods)" → 78, and base.py is now the composition shim (protocol bodies in `domain/context.py` / `domain/agent.py`) |
| `docs/architecture/core-domain-architecture.md` | §2 method census (75 → 78; 52 → 55 defaults), §7 "base.py (1,135 lines)" (now ~95 + two new modules), needs the split described; §1 still shows `src/alfred_kitchen/` in-repo (stale — `src/` holds only `alfred`) |
| `docs/architecture/injection-map.md` | Appendix should gain a Context/Agent column; `get_table_format` consumer claim stale |
| `docs/architecture/core-public-api.md` | New public surface: `DomainContext`, `AgentConfig` (+ `alfred.context` export); stale "4 wheel targets" claim (already on X2) |
| `0610-mode-language.md` §5.1 / §8.2 | "Carry back to the protocol-split plan" — satisfied; can be marked done |
| `roadmap/active/0610-substrate.md` | Owner refined §3 during execution (LLM-bound vs user-bound line) — consistent with the shipped sort, no further action |

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/domain/context.py` | NEW — `DomainContext` + 4 supporting types (incl. `CRUDMiddleware`/`pre_write`) |
| `src/alfred/domain/agent.py` | NEW — `AgentConfig` + `ToolDefinition`/`ToolContext` |
| `src/alfred/domain/base.py` | Rewritten: composition + `__all__` re-export shim (1,420 → ~95 lines) |
| `src/alfred/domain/__init__.py` | Exports `DomainContext`, `AgentConfig` |
| `src/alfred/context/__init__.py` | Re-exports `DomainContext` (seam path); import sort fixed |
| `src/alfred/agents/base.py` | 1-line fix: invalid param order (pre-existing `SyntaxError`) |
| `tests/core/test_import_isolation.py` | NEW — seam import-isolation lock (2 tests) |
| `tests/core/test_protocol_split.py` | NEW — sort-freeze + composition + narrow-half conformance (11 tests) |
| `.claude/PITFALLS.md` | Added `unimported-module-rot` |

## Shipped

- **Version:** (filled on archive — ships in A4's additive minor release)
- **Commits:** (filled on archive)
- **Date:** (filled on archive)
