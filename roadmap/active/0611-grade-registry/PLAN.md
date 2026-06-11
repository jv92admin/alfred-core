# Plan: Grade Registry (A2 / C-6 minimal)

**Date:** 2026-06-11
**Based on:** RESEARCH.md

## Approach

New stdlib-only module `alfred/domain/grades.py` holding the grade types
(`StripSet`, `GradeRegistry`), well-known constants, typed errors, and the strip
primitive. `DomainContext` gains one defaulted method (`get_audience_grades`);
`register_domain()` validates the declaration in its body (signature unchanged);
`alfred.context` re-exports the public names as the seam path. No existing behavior
changes — grade `"reply"` defaults to the empty strip set and nothing calls the
primitive until A3.

## Reuse Map

| Capability | Reuse / New | Symbol + Path | Why |
|------------|-------------|---------------|-----|
| Registration gate | Reuse | `register_domain` — `src/alfred/domain/__init__.py:31` | Seam §3: validate at domain registration; body-only change, signature intact |
| Protocol home | Reuse | `DomainContext` — `src/alfred/domain/context.py:190` | A1's substrate half; the declaration method joins its "Data Shaping" section (`context.py:543`) |
| Seam export path | Reuse | `alfred/context/__init__.py:42` re-export pattern | A1 established it for `DomainContext`; grades follow identically |
| Freeze test | Reuse (update) | `CONTEXT_MEMBERS` — `tests/core/test_protocol_split.py:26` | The deliberate compat decision — same commit, documented |
| Import isolation | Reuse (unchanged) | `tests/core/test_import_isolation.py` | Must stay green; new module is stdlib-only |
| Grade types + primitive | **New** | `src/alfred/domain/grades.py` | Searched `src/` for strip/grade machinery: only `get_strip_fields` (`context.py:547`) exists — flat `set[str]`, consumed solely by the user-bound reply renderer (`reply.py:1075`). Wrong shape (no per-table, no named grades) and wrong path (user-bound, not LLM-bound); bridging it would break Guardrail #3 (RESEARCH Finding 2). It stays untouched |

## API Shape

```python
# src/alfred/domain/grades.py  (stdlib-only; TYPE_CHECKING import of DomainContext)

GRADE_REPLY: Final[str] = "reply"
GRADE_EXTERNAL: Final[str] = "external"
WELL_KNOWN_GRADES: Final[frozenset[str]] = frozenset({GRADE_REPLY, GRADE_EXTERNAL})


class GradeError(ValueError):
    """Base for all grade-registry errors."""

class GradeRegistryError(GradeError):
    """Invalid grade declaration — raised at register_domain()."""

class UnknownGradeError(GradeError):
    """Unregistered grade string at call time — never a silent passthrough."""


@dataclass(frozen=True)
class StripSet:
    """Fields to remove from records at a given grade. Raw column names
    (fk_enrich replaces FK values, not keys — RESEARCH Finding 5)."""
    fields: frozenset[str] = frozenset()                 # stripped from EVERY table
    table_fields: Mapping[str, frozenset[str]] = ...     # per-table extras (default {})

    def fields_for(self, table: str) -> frozenset[str]:
        return self.fields | self.table_fields.get(table, frozenset())


@dataclass(frozen=True)
class GradeRegistry:
    grades: Mapping[str, StripSet]

    @classmethod
    def from_context(cls, ctx: DomainContext) -> GradeRegistry:
        """Build + validate from ctx.get_audience_grades(). Raises GradeRegistryError."""

    def strip(self, records: Sequence[Mapping[str, Any]], table: str, grade: str) -> list[dict[str, Any]]:
        """The A3 chain link (post_read → fk_enrich → THIS → format → header).
        Pure: returns new dicts, never mutates inputs.
        Raises UnknownGradeError for any grade not in the registry."""
```

```python
# src/alfred/domain/context.py — joins the "Data Shaping" section

def get_audience_grades(self) -> dict[str, StripSet]:
    """Named redaction grades (seam contract §3; mode-language §8.6).
    Default: well-known grades with empty strip sets — strips nothing,
    exactly today's behavior (Compatibility Guardrail #3)."""
    return {GRADE_REPLY: StripSet(), GRADE_EXTERNAL: StripSet()}
```

```python
# src/alfred/domain/__init__.py — body-only change

def register_domain(domain: DomainConfig) -> None:
    GradeRegistry.from_context(domain)   # raises GradeRegistryError — loud, at startup
    global _current_domain
    _current_domain = domain
```

## Validation Mechanics (`GradeRegistry.from_context`)

1. **Well-known grades present.** Both `"reply"` and `"external"` must be keys in the
   returned mapping. Missing → `GradeRegistryError` naming the domain, the missing
   grade, and `get_audience_grades` as the hook. No silent merge of defaults
   (Decision 3).
2. **`external ⊇ reply`, per-table exact** (RESEARCH Finding 3):
   - `reply.fields ⊆ external.fields` (a global reply field must be covered globally —
     per-table externals can't cover future tables);
   - for each `t` in `reply.table_fields`:
     `reply.table_fields[t] ⊆ external.fields | external.table_fields.get(t, ∅)`.
   Violation → `GradeRegistryError` naming grade, table (or "all tables"), and the
   exact uncovered fields.
3. **Custom grades**: any other key is accepted as-is — no ordering constraint exists
   for them in the contract (registry-over-enum rationale, seam §3).
4. Errors include `domain.name` so multi-domain test logs identify the offender.

## Call-Time Mechanics (`strip`)

- `grade not in self.grades` → `UnknownGradeError` listing the requested string and
  the registered grade names. Never returns unstripped data on a bad grade.
- Strip = `{k: v for k, v in record.items() if k not in strip_set.fields_for(table)}`
  per record; new dicts, inputs untouched.
- Empty strip set → key-identical copies (this IS grade `"reply"`'s default — the
  Guardrail #3 conformance test asserts equality).
- A table with no per-table entry gets the global set only — not an error (tables are
  open-world; grades are closed-world).

## Tasks

- [ ] Capture baselines: `pytest tests/ -q` count, `mypy src/` error count (expect 368)
- [ ] `src/alfred/domain/grades.py` — constants, errors, `StripSet`, `GradeRegistry` (validation + strip primitive)
- [ ] `src/alfred/domain/context.py` — `get_audience_grades()` default + runtime import of `StripSet`/constants
- [ ] Cross-referencing docstrings on BOTH `get_audience_grades` and `get_strip_fields` — each names its path (LLM-bound assembly vs user-bound reply rendering) and warns against bridging (approval addition; RESEARCH Finding 2)
- [ ] `src/alfred/domain/__init__.py` — validation call in `register_domain`; export grade names in `__all__`
- [ ] `src/alfred/context/__init__.py` — re-export `StripSet`, `GradeRegistry`, `GRADE_REPLY`, `GRADE_EXTERNAL`, `GradeError`, `GradeRegistryError`, `UnknownGradeError`
- [ ] `tests/core/test_protocol_split.py` — freeze update: `get_audience_grades` into `CONTEXT_MEMBERS`, counts 34→35 (78→79 total), comment citing A2 (the compat decision)
- [ ] `tests/core/test_grade_registry.py` — NEW (test plan below)
- [ ] Gates: full pytest green, ruff check+format on touched files, mypy at exact baseline parity
- [ ] PITFALLS check (loud-errors pattern applies); SUMMARY.md

## Test Plan (`tests/core/test_grade_registry.py`)

| Test | Asserts |
|------|---------|
| Default registry from stub domain | `from_context` succeeds; exactly `{reply, external}`; both empty |
| **Guardrail #3 conformance** | `strip(records, t, "reply")` on default registry returns records **equal** to input (and copies, not the same objects) — "reply strips nothing by default", stated and pinned |
| Strip applies global + per-table union | declared `StripSet(fields={a}, table_fields={t: {b}})` → both gone for `t`, only `a` gone for other tables |
| Inputs never mutated | original dicts retain stripped keys after the call |
| Unknown grade is loud | `strip(..., grade="internal")` raises `UnknownGradeError` naming `"internal"` and the registered names |
| Missing well-known grade | override returning only `{"reply": ...}` → `GradeRegistryError` at `register_domain` naming `external` |
| Global superset violation | `reply.fields={x}`, `external.fields=∅` → `GradeRegistryError` naming `x` |
| Per-table covered by external global | `reply.table_fields={t:{x}}`, `external.fields={x}` → **valid** |
| Per-table uncovered | `reply.table_fields={t:{x}}`, external lacking `x` everywhere → error naming `t` and `x` |
| Custom grade accepted | third grade with arbitrary sets registers fine; strippable |
| Zero-migration | `register_domain(StubDomainConfig)` (defaults) passes — also exercised implicitly by `conftest.py:243` on every suite run |
| Seam imports | `from alfred.context import GradeRegistry, StripSet, GRADE_REPLY, GRADE_EXTERNAL` resolve to the canonical objects |

Existing `test_import_isolation.py` stays as-is and must stay green (grades.py is
stdlib-only). Existing `test_protocol_split.py` updated as above — no other test edited.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| 1. Strip-set shape | `StripSet(fields, table_fields)` — global + per-table union | Ledge's real declaration is a cross-table base set (Finding 1); the Phase 1 audit is per-table. Both first-class, no `"*"` magic key, exact superset validation (Finding 3) |
| 2. Grade `"reply"` default | Empty strip set; **no bridge** to `get_strip_fields` | Guardrail #3: today's LLM-bound assembly strips nothing; `get_strip_fields("reply")` feeds the user-bound renderer only — bridging would silently change ledge's S1 LLM context (Finding 2) |
| 3. Override omits a well-known grade | Loud `GradeRegistryError`, no silent default-merge | Repo principle + PITFALLS `loud-errors-over-silent-fallbacks`; auto-filling `external=∅` against a non-empty reply would fail superset confusingly, and auto-filling reply hides intent. One explicit line per grade is cheap |
| 4. Method name | `get_audience_grades` | Mode-language §8.6's term of art ("audience grade"); `get_*` matches protocol convention |
| 5. Module home | `alfred/domain/grades.py`, re-exported by `alfred.context` | `register_domain` imports it without pulling `alfred.context`'s package init; seam path preserved; stdlib-only keeps isolation test green (Finding 7) |
| 6. Registry lifetime | Built per-use from `ctx`; never stored globally | A3 is state-free (E2/E5) — the chain takes `ctx` as a parameter; registration-time build is the validation gate, not a cache |
| 7. Freeze-test update | Same commit, `CONTEXT_MEMBERS` 34→35, documented | This IS the explicit compat decision the test forces (Finding 6); abstract set unchanged (defaulted method = zero migration) |
| 8. Error taxonomy | `GradeError(ValueError)` base; `GradeRegistryError` (registration), `UnknownGradeError` (call time) | Typed per seam §3; common base for catchability; `ValueError` parent matches PITFALLS guidance |
| 9. Primitive granularity | `strip(records, table, grade)` — list-in, list-out, pure | Matches the chain's per-set slot (seam §1); single-record callers map; purity makes Guardrail #3 testable as equality |
| 10. Grades are pure field removal | Transform dispositions (cents→dollars etc.) remain `post_read` middleware, grade-independent | Core-side half of the seam clarification recorded in SEAM_CONTRACT.md §3 (approval addition, 2026-06-11): in ledge's keep/strip/transform audit taxonomy, only *strip* flows into grade declarations; transforms apply before the strip step in the §1 chain |

## Error Handling

- **Registration:** any declaration defect (missing well-known grade, superset
  violation) raises `GradeRegistryError` at `register_domain` — app fails at startup,
  message names the domain, hook, grade, table, and exact fields. Never registers a
  domain with an invalid declaration.
- **Call time:** unregistered grade string raises `UnknownGradeError` naming the
  string and the registered set. There is no fallback grade and no silent passthrough.
- **No new silent defaults:** the only default is the well-known-empty declaration on
  the protocol itself, which is documented as "exactly today's behavior" — not a
  fallback, the contract.

## Files to Change

| File | Planned Change |
|------|---------------|
| `src/alfred/domain/grades.py` | NEW — constants, errors, `StripSet`, `GradeRegistry` (validate + strip) |
| `src/alfred/domain/context.py` | +`get_audience_grades()` default; import `StripSet`/constants from `grades` |
| `src/alfred/domain/__init__.py` | `register_domain` body: validation call; `__all__` += grade names |
| `src/alfred/context/__init__.py` | Re-export the 7 public grade names (seam path) |
| `tests/core/test_protocol_split.py` | Freeze update: +`get_audience_grades`, counts 34→35, A2 comment |
| `tests/core/test_grade_registry.py` | NEW — 12 tests per plan |

Out of scope (explicitly NOT touched): `graph/nodes/reply.py`, `get_strip_fields`,
`context/builders.py`, any A3 entrypoint, any assembly-time application.

## Definition of Done

- [ ] `pytest tests/ -v` — all green (221 pre-existing untouched except the freeze update + new file)
- [ ] `external ⊇ reply` enforced at `register_domain`; failures loud and named
- [ ] Unknown grade at call time raises `UnknownGradeError` — pinned by test
- [ ] Guardrail #3 pinned: default `"reply"` strip is a record-equality no-op
- [ ] `test_import_isolation.py` green unchanged (everything added is substrate-side)
- [ ] Kitchen/FPL/Stub zero-migration: no abstract added (`ABSTRACT_MEMBERS` unchanged)
- [ ] `ruff check` + `ruff format` clean on every touched file
- [ ] `mypy src/` at exact baseline parity (368 before → 368 after; new module contributes 0)
- [ ] PITFALLS Checks pass (`loud-errors-over-silent-fallbacks`, `unimported-module-rot` → compileall)
- [ ] Doc impact queued for A4's `/doc-review`: member count 78→79 (CLAUDE.md, core-domain-architecture.md §2, injection-map.md gains the new knob, core-public-api.md gains the grade exports)
