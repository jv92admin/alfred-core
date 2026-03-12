# Summary: Safe Calculator Tool (`calculate`)

**Date:** 2026-03-12

## What Was Done

- Added `CalculateParams` model, `_eval_node()`, `_safe_eval()`, `calculate()` to `tools/crud.py`
- Added `calculate` dispatch in `execute_crud()` — pure arithmetic, no DB, no registry
- Added `"calculate"` to `BUILTIN_ANALYZE` set in `act.py`
- Added dedicated formatting branch in `_format_current_step_results()` for clean `**Calculated:** label=value` output
- Added `calculate` to DECISION section in `injection.py` for analyze steps
- Added "Exact Arithmetic" section to `analyze.md` — analyze now has three modes (query, arithmetic, reasoning)
- Added `calculate` row to `crud.md` tools reference table
- Updated `base.py` docstring for `get_tool_enabled_step_types()`
- Propagated changes across 6 architecture/bridge docs
- 22 new tests: AST safety, params validation, batch evaluation, per-formula errors, dispatch

## Decisions Made During Execution

| Decision | Choice | Why |
|----------|--------|-----|
| API shape | `{"formulas": {"label": "expr"}}` → `{"label": result}` | LLM writes formulas (good at structured output), tool evaluates (LLM bad at arithmetic). One call, N formulas. |
| Safety | AST whitelist via `ast.parse` — no `eval`/`exec` | Whitelist only `Constant(int\|float)`, `BinOp`, `UnaryOp`. Rejects functions, variables, imports, strings. |
| Error handling | Per-formula errors as strings in result dict | One bad formula doesn't kill the batch. LLM sees the error and can adjust. |
| Exponent cap | Reject `**` with exponent > 100 | Prevents CPU/memory DoS from `2**999999999`. |
| Float cleanup | Round to 10dp, strip trailing zeros | Avoids `0.30000000000000004` in user-facing answers. |

## Deviations from Plan

None.

## Files Changed

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py` | `CalculateParams`, `_eval_node`, `_safe_eval`, `calculate`, dispatch |
| `src/alfred/graph/nodes/act.py` | `BUILTIN_ANALYZE` set, formatting branch, table_name fix |
| `src/alfred/prompts/injection.py` | `calculate` in DECISION section |
| `src/alfred/prompts/templates/act/analyze.md` | Three-mode guidance, calculate docs, guardrail |
| `src/alfred/prompts/templates/act/crud.md` | `calculate` in tools table |
| `src/alfred/domain/base.py` | Docstring update |
| `tests/core/test_crud.py` | 22 new tests |
| `docs/architecture/*.md` | 5 docs updated |
| `docs/bridge/alfred-domain-design-guide.md` | Updated analytical patterns |

## Shipped

- **Version:** 2.7.0
- **Commits:** a899bf0
- **Date:** 2026-03-12
