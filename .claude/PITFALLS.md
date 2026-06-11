# PITFALLS.md — Living Lessons

How to read: each **pattern** is the durable unit — a failure mode that has bitten (or will silently bite) this package. Each carries a `Check` that is grep- or pytest-runnable, a `Fix`, and an `Incidents` trail. The `silent-failure` tag marks patterns whose Check is load-bearing: when they fire, nothing crashes — the damage just ships.

**Consumed by:** `/pm` execute stage reads this before touching code (note patterns relevant to the files in PLAN.md). **Fed by:** `/pm` execute stage adds new entries before writing SUMMARY.md. **Pruned by:** `/doc-review` Tier 4 verifies each Check still resolves against current code; entries no longer true get archived in place (strike + date), not silently deleted.

## Graduation Rule

A lesson enters this file only if ALL five hold:

1. **Generalizable** — a pattern, not a one-off typo.
2. **Still true** — holds in the current architecture.
3. **Checkable** — the Check is runnable (grep or test), not prose.
4. **Silent or non-obvious** — loud crashes don't need a lessons file.
5. **Sourced** — dated incident (`YYYY-MM-DD · file:symbol → what happened`), or marked `source: founding` (seeded from System Boundaries before any incident).

If a lesson fails (1), it belongs in a code comment or test, not here. If it fails (4), the test suite is the right home.

---

## 1. Prompt / LLM boundary

### uuid-never-in-prompts
- **Severity:** P0 · silent-failure · source: founding
- **Pattern:** A raw UUID reaches prompt text instead of a SessionIdRegistry ref. The LLM echoes or mangles it; downstream ref resolution breaks or leaks internal IDs to users.
- **Check:** Any code path that formats entity data into a prompt goes through `SessionIdRegistry` (`src/alfred/core/id_registry.py`) first. Grep new prompt-assembly code for direct `.id` / `uuid` interpolation.
- **Fix:** Translate UUID → ref at the assembly boundary; never pass entities with live UUIDs into template context.
- **Incidents:** — (founding invariant)

### template-code-drift
- **Severity:** P1 · silent-failure · source: founding
- **Pattern:** A prompt template in `src/alfred/prompts/templates/` changes shape (section added/removed) but the code that fills it — or the docs describing it — still assumes the old shape. No error; the LLM just gets a degraded prompt.
- **Check:** `/doc-review` Tier 1 template review + line-count cross-reference against `prompt-assembly.md`.
- **Fix:** Template edits and their assembly-code/doc counterparts land in the same change.
- **Incidents:** — (founding invariant)

## 2. Failure-mode discipline

### loud-errors-over-silent-fallbacks
- **Severity:** P0 · silent-failure · source: founding
- **Pattern:** A required domain hook is missing and core silently falls back to a default instead of raising. The domain author ships believing their override is active.
- **Check:** Every new DomainConfig touchpoint that is *required* raises with a message naming the missing hook. Grep new code for `getattr(domain, ..., default)` and bare `except` around domain calls.
- **Fix:** Raise `ValueError`/dedicated error naming the hook and the domain. Defaults are only for touchpoints documented as optional in `injection-map.md`.
- **Incidents:** — (founding invariant)

## 3. State & CRUD discipline

### crud-owns-state
- **Severity:** P0 · source: founding
- **Pattern:** Entity lifecycle state is mutated outside the CRUD execution engine — a node or tool writes directly, duplicating mutation logic.
- **Check:** All lifecycle writes route through `src/alfred/tools/crud.py`. Grep new code for direct adapter write calls outside the CRUD layer.
- **Fix:** Add the operation to the CRUD engine; never inline a second write path.
- **Incidents:** — (founding invariant)

### gen-ref-approval-gate
- **Severity:** P0 · silent-failure · source: founding
- **Pattern:** Generated content (`gen_*` ref) gets persisted without explicit user approval — usually a new code path that shortcuts the approval flow "just for this case."
- **Check:** Every persistence path for `gen_*` refs is gated on user confirmation. Grep new persistence code for `gen_` handling.
- **Fix:** Route through the existing approval flow; no exceptions for "obviously wanted" content.
- **Incidents:** — (founding invariant)

### unimported-module-rot
- **Severity:** P1 · silent-failure · source: incident
- **Pattern:** A module in `src/alfred/` that no test imports can be syntactically invalid (or otherwise unimportable) while the whole suite stays green. ruff/mypy would catch it, but those gates aren't enforced repo-wide, so the rot ships.
- **Check:** `python -m compileall src/alfred -q` exits 0 (catches syntax errors in unimported modules). Stronger: a smoke test importing every `alfred.*` submodule.
- **Fix:** Fix the module, then re-run the compileall check. Don't rely on the test suite alone to prove importability.
- **Incidents:** 2026-06-11 · `agents/base.py:MultiAgentOrchestrator.__init__` → non-default arg after default (a `SyntaxError` on import) — invisible because zero call sites and zero test imports; surfaced when A1's mypy gate refused to check anything; fixed by reordering params (keyword-compatible, no silent default added).

## 4. Release / packaging

### doc-count-drift
- **Severity:** P2 · silent-failure · source: founding
- **Pattern:** Numeric facts repeated across docs (DomainConfig method count, test count, template line counts) drift from code. Each is correct the day it's written and wrong a release later.
- **Check:** `/doc-review` cross-reference step: count `def` in `base.py` DomainConfig, `pytest --co -q`, `wc -l` on templates — verify against CLAUDE.md, README.md, `core-domain-architecture.md`, `testing.md`, `prompt-assembly.md`.
- **Fix:** Update all copies in the release's doc-review pass, or remove the count from docs that don't need it.
- **Incidents:** — (founding invariant)

### version-triple-sync
- **Severity:** P1 · source: founding
- **Pattern:** `pyproject.toml`, the latest CHANGELOG entry, and the git tag disagree after a rushed ship.
- **Check:** `/pm` ship step verifies all three match before publishing; `/doc-review` Tier 3 re-verifies.
- **Fix:** Bump version + CHANGELOG in the same commit; tag from that commit only.
- **Incidents:** — (founding invariant)

---

## Adding an entry

During `/pm` execute, when a bug or near-miss passes the Graduation Rule:

```markdown
### short-kebab-slug
- **Severity:** P0|P1|P2 · [silent-failure] · source: incident
- **Pattern:** What goes wrong and why it's easy to miss.
- **Check:** Runnable verification (grep target or test).
- **Fix:** The correct pattern.
- **Incidents:** YYYY-MM-DD · file:symbol → what happened → how fixed
```

A repeat of an existing pattern gets a new dated line under that pattern's Incidents — not a new entry.
