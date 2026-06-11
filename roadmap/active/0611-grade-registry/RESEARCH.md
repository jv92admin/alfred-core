# Research: Grade Registry (A2 / C-6 minimal)

**Goal:** Domains declare named redaction grades as strip sets; core validates `external ⊇ reply` at registration and ships a strip-application primitive for A3's assembly chain.
**Type:** feat
**Date:** 2026-06-11

## Context

Track A feature A2, bound by SEAM_CONTRACT.md §3 (agreed 2026-06-10). Grades are open
strings validated against a domain-declared registry; core ships `"reply"` and
`"external"` as well-known constants. Ledge Phase 1's column audit will pour its
`external` set into whatever declaration shape this feature defines — the shape is the
expensive-to-change part. A1 (protocol split) is done: `DomainContext` lives in
`src/alfred/domain/context.py`, exported via `alfred.context`, with sort-freeze and
import-isolation tests.

## Function Chain

Two chains: registration time (this feature's validation) and call time (A3's future
assembly chain — A2 delivers only the strip link).

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| Registration | `register_domain()` — `src/alfred/domain/__init__.py:31` | Sets `_current_domain` global. **Today: no validation of any kind.** A2 adds grade validation here (signature unchanged) | NEW: grade declaration method |
| Registration | `tests/core/conftest.py:243` | `register_domain(_STUB_DOMAIN)` runs at conftest import — every test run will exercise the new validation path for free | — |
| Call time (A3, future) | seam §1: `post_read → fk_enrich → strip(grade) → format_record_for_context → header` | A2 delivers the `strip(grade)` link as a standalone primitive; A3 composes the chain | strip sets per grade |
| Call time (today, S1) | `graph/nodes/reply.py:1075-1191` | `_get_strip_fields()` → `get_current_domain().get_strip_fields("reply")` — strips fields from **user-facing reply rendering** | `get_strip_fields(context)` (existing) |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Strip on LLM-bound assembly/injection | **Nothing is stripped — no mechanism exists** | none | A2 closes this: grade registry + primitive |
| Strip on user-bound reply rendering | `get_strip_fields("reply")` → `set()` (strip nothing) | `get_strip_fields` — `domain/context.py:547`, flat `set[str]`, contexts `"injection"`/`"reply"` | Different path; untouched by A2 (see Finding 2) |
| Grade validation at registration | No validation anywhere in `register_domain` | none | A2 adds: well-known grades present + `external ⊇ reply`, loud `GradeRegistryError` |
| Unknown grade at call time | n/a (no grades exist) | none | A2 adds: loud typed error, never silent passthrough |

## Findings

### 1. Ledge's real declaration shape is flat-with-a-base, not per-table

`ledge_alfred/domain.py:961-983` (`c:\Projects\landscaping\Alfred`):

```python
def get_strip_fields(self, context: str = "injection") -> set[str]:
    base = {"company_id", "qbo", "signwell", "call_data", "attribution"}  # ALWAYS strip
    if context == "reply":
        base |= {"modified_by", "source_system", "source_id", "group_id"}
    return base
```

Two structural facts the declaration shape must accommodate:
- **A cross-table "always strip" set is the dominant real-world case** (`company_id`,
  sync blobs — these column names recur across every table). A pure
  `dict[grade, dict[table, fields]]` would force ledge to repeat the base set per table
  or use a magic `"*"` key.
- **Ledge Phase 1's column audit is per-table by nature** (it walks columns
  table-by-table), so per-table sets must also be first-class.

→ Shape: a `StripSet` with both a global `fields` set and a `table_fields` per-table
map; effective strip for a table = union. Covers both declaration styles without magic
keys. Superset validation is well-defined (see Finding 3).

### 2. "Core has no strip concept" — refined: no strip on the LLM-bound path

The brief's claim needed sharpening. Core **does** have `get_strip_fields(context)` on
`DomainContext` (`domain/context.py:547`, default `set()`), consumed in exactly one
place: `graph/nodes/reply.py:1075-1191`, the **user-bound reply renderer**. Nothing on
the LLM-bound assembly/injection path calls it (`"injection"` context is declared but
has zero core consumers — grep-verified across `src/`).

Consequences:
- **Grade `"reply"`'s core default is the empty strip set** — today's LLM-bound
  assembly strips nothing, and Guardrail #3 (byte-for-byte reply reproduction) binds the
  registry to that. Confirmed, stated explicitly.
- **Do NOT bridge the default grade declaration to `get_strip_fields()`.** Tempting
  ("ledge's declaration flows in automatically") and wrong: `get_strip_fields("reply")`
  feeds the *user-bound* renderer. Bridging it into the *LLM-bound* reply grade would
  strip 9 fields from ledge's S1 context that the LLM sees today — exactly the silent
  Guardrail #3 break the roadmap warns about. The two paths stay separate; convergence
  is D7's question, not A2's.
- `get_strip_fields` and `reply.py` are **untouched** by A2.

### 3. Superset validation is per-table, with global-covers-global asymmetry

`external ⊇ reply` with the two-part shape means: for **every** table (including tables
not yet known), external's effective set contains reply's. Mechanically:

1. `reply.fields ⊆ external.fields` — a global reply field must be globally stripped by
   external (a per-table external entry can't cover unknown future tables).
2. For each table `t` in `reply.table_fields`:
   `reply.table_fields[t] ⊆ external.fields ∪ external.table_fields.get(t, ∅)` — a
   per-table reply field may be covered by external's global set.

Both checks are exact and cheap; failure messages can name the grade, table, and
offending fields.

### 4. Where validation hooks in — `register_domain` body, signature unchanged

`register_domain(domain)` (`domain/__init__.py:31-42`) is a 2-line global setter.
Validation = build the registry from the domain's declaration before assigning the
global; raise typed error on failure. No signature change, no new parameter. The
registry is **not** stored globally — A3's chain is state-free and builds it from the
`ctx` parameter per call (cheap dict construction); registration-time validation is the
gate, not a cache.

### 5. Strip sets use raw column names (fk_enrich enriches values, not keys)

Per seam §1 the chain order is `fk_enrich → strip(grade)`. FK enrichment
(`get_fk_enrich_map`, `core/id_registry.py:688,878`) replaces FK *values* with display
names — record **keys stay raw column names** (`client_id` stays `client_id`). Ledge's
existing strip fields are raw column names. So strip sets are declared in raw column
names and the primitive matches keys exactly. No rename mapping needed.

### 6. Freeze-test impact (the expected compat decision)

Adding one method to `DomainContext` trips `tests/core/test_protocol_split.py`:
`CONTEXT_MEMBERS` (34 → 35), `test_member_count_matches_research` (34/44 → 35/44),
total 78 → 79. `ABSTRACT_MEMBERS` is **unchanged** (the method has a default
implementation — that's the zero-migration requirement). Updating the freeze in the
same commit, with the new member documented, IS the deliberate compatibility decision
the test was built to force.

### 7. Import isolation constraints

`tests/core/test_import_isolation.py` pins `import alfred.context` and
`import alfred.domain` to zero langgraph/instructor/alfred.graph/alfred.llm. The new
module must be stdlib-only. Placement: `alfred/domain/grades.py` (sibling of
`context.py`) so `register_domain` imports it without pulling `alfred.context`'s
package init (builders/conversation/reasoning); `alfred.context` re-exports the public
names as the seam path. One import-direction caution: `context.py` imports `StripSet`
at runtime (method signature + default body); `grades.py` needs `DomainContext` only
for typing → `TYPE_CHECKING` import, no runtime cycle.

### 8. No ledge shim code exists yet

Grep across `c:\Projects\landscaping` for grade code: nothing built. SEAM_CONTRACT.md §3
is the only binding artifact — A2's declaration shape is what ledge will code against.

### 9. Baselines to capture at execution

A1 closed at: 221 tests passing, mypy 368 errors (exact parity required — re-measure
before touching anything), ruff clean on touched files only (repo-wide is not clean).

## Open Questions

All resolved into PLAN.md decisions:

1. ~~Strip-set shape~~ → `StripSet(fields, table_fields)`, Finding 1.
2. ~~What "reply" means~~ → empty strip set, no bridge to `get_strip_fields`, Finding 2.
3. ~~Validation hook~~ → `register_domain` body, Finding 4.
4. Declaration method name → `get_audience_grades()` (mode-language §8.6 terminology) — PLAN decision.
5. Override omits a well-known grade → loud error vs silent merge — PLAN decision (loud).
