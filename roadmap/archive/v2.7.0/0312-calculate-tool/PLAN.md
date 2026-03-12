# Plan: Safe Calculator Tool (`calculate`)

**Date:** 2026-03-12
**Based on:** RESEARCH.md

## Approach

Add `calculate` as a built-in analyze tool alongside `db_analyze`. It accepts a dict of labeled formulas, evaluates each via AST-safe parsing, and returns label→result. The tool slots into the existing `BUILTIN_ANALYZE` dispatch path — no new execution logic needed, just a new tool function and prompt documentation.

## Tasks

- [ ] 1. Add `CalculateParams` model + `calculate()` function in `tools/crud.py`
- [ ] 2. Add `"calculate"` to `BUILTIN_ANALYZE` set in `act.py`
- [ ] 3. Handle `calculate` in `_format_current_step_results()` in `act.py`
- [ ] 4. Add `calculate` to DECISION section in `injection.py`
- [ ] 5. Add "Exact Arithmetic" section to `prompts/templates/act/analyze.md`
- [ ] 6. Handle `calculate` dispatch in `execute_crud()` in `tools/crud.py`
- [ ] 7. Add prompt guardrail for number accuracy in `analyze.md`
- [ ] 8. Tests
- [ ] 9. Ruff + mypy clean

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Where does `calculate` live? | `tools/crud.py` alongside `db_analyze` | Same module, same dispatch path via `execute_crud()`. Not actually CRUD but follows the established pattern. |
| `table_name` in result tuple? | Use `"calculate"` as the label | `db_analyze` uses `params.get("table")` — `calculate` has no table, so use the tool name. See line 1522 pattern. |
| Result format? | `dict[str, float \| str]` — label→value or label→error string | No `id` field → existing analytical detection works. Per-formula errors keep the batch useful. |
| Formatting in prompt? | Dedicated branch in `_format_current_step_results` | Generic fallback (JSON dump) works but is noisy. A clean `**Calculated:** label=value` format matches `db_analyze`'s style and is easier for the LLM to reference. |
| AST ops allowed? | `+`, `-`, `*`, `/`, `//`, `%`, `**` | `//` (floor div) and `%` (modulo) are common enough. `**` with exponent cap. |
| Exponent cap? | Reject `**` with exponent > 100 | Prevents `2**999999999` memory/CPU hang. 100 covers any real analytical need. |

## Integration Details

### 1. `CalculateParams` + `calculate()` — `tools/crud.py`

```python
class CalculateParams(BaseModel):
    formulas: dict[str, str]  # label → expression

    @model_validator(mode="after")
    def _validate(self):
        if not self.formulas:
            raise ValueError("'formulas' must contain at least one entry")
        if len(self.formulas) > 20:
            raise ValueError("Maximum 20 formulas per call")
        return self

def _safe_eval(expr: str) -> float:
    """Evaluate arithmetic expression via AST whitelist. No eval()."""
    if len(expr) > 500:
        raise ValueError("Expression too long (max 500 chars)")
    tree = ast.parse(expr.strip(), mode="eval")
    # Walk and validate every node...
    return _eval_node(tree.body)

async def calculate(params: CalculateParams) -> dict[str, float | str]:
    results = {}
    for label, expr in params.formulas.items():
        try:
            results[label] = _safe_eval(expr)
        except Exception as e:
            results[label] = f"error: {e}"
    return results
```

No `user_id` needed — pure computation, no DB access.

### 2. `BUILTIN_ANALYZE` — `act.py:1371`

```python
BUILTIN_ANALYZE = {"db_analyze", "calculate"}
```

### 3. Dispatch in `execute_crud()` — `tools/crud.py:580`

Current code at line 580-582:
```python
if tool == "db_analyze":
    return await db_analyze(DbAnalyzeParams(**params), user_id)
```

Add:
```python
if tool == "calculate":
    return await calculate(CalculateParams(**params))
```

**Nuance:** `calculate` doesn't need `user_id`. The `execute_crud` signature already has it as a param — we just don't pass it through. Clean.

### 4. Result formatting — `act.py:725`

Current `db_analyze` formatting at line 725. Add `calculate` branch before the `elif tool_name == "db_read"` at line 742:

```python
elif tool_name == "calculate":
    if isinstance(result, dict) and result:
        lines.append("**Calculated:**")
        for label, value in result.items():
            lines.append(f"  **{label}**: {value}")
    else:
        lines.append(f"Result: `{result}`")
```

This gives the LLM clean labeled values to reference in its analysis and copy into `step_complete.data`.

### 5. DECISION section — `injection.py:436-439`

After the `db_analyze` entry, add:

```python
if step_type == "analyze":
    tool_lines.append(
        '- Run analytical query → ...'  # existing
    )
    tool_lines.append(
        '- Exact arithmetic → `{"action": "tool_call", "tool": "calculate", "params": {"formulas": {"label": "expression", ...}}}`'
    )
```

### 6. `analyze.md` — new section + guardrail

Add after "Reasoning Over Prior Step Data":

```markdown
## calculate — Exact Arithmetic

Use `calculate` when you need precise arithmetic over numbers from prior steps or `db_analyze` results.

**IMPORTANT:** Copy numbers exactly as they appear in prior step results. Double-check labels match the correct values.

### Parameters

| Param | Required | Description |
|-------|----------|-------------|
| `formulas` | Yes | Dict of `"label": "expression"` — one or more labeled arithmetic expressions |

### Supported Operators

`+`, `-`, `*`, `/`, `//` (floor division), `%` (modulo), `**` (power, max exponent 100), `()` (grouping)

### Example

```json
{"formulas": {"growth_pct": "((450 - 360) / 360) * 100", "margin": "(120 - 85) / 120 * 100"}}
```
→ `{"growth_pct": 25.0, "margin": 29.17}`
```

Update the "Reasoning mode" section (line 72-74) to redirect:

```markdown
**For arithmetic, ALWAYS use `calculate`** — do not compute numbers in your response text.
You may still reason over data (comparisons, decisions, filtering) without a tool call.
```

### 7. Step complete — no changes needed

The existing flow at lines 1634-1641 already handles this correctly:
- After `calculate` returns, results go into `current_step_tool_results`
- LLM sees them in "This Step" section on next iteration
- LLM calls `step_complete` with `decision.data` containing its analysis
- `decision.data` becomes the cached step result (line 1638-1639)
- Ref touching at line 1645-1649 works as-is

No step_complete changes required.

### 8. `table_name` in result tuple — minor adaptation

Line 1522: `table_name = decision.params.get("table", "unknown")`

For `calculate`, there's no `table` param, so this falls back to `"unknown"`. That's fine — the tuple is `("calculate", "unknown", result)` — and the formatting branch (task 4) matches on `tool_name == "calculate"`, not on `table_name`.

Actually, cleaner to handle it:
```python
if decision.tool == "calculate":
    table_name = "calculate"
else:
    table_name = decision.params.get("table", "unknown")
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid expression (syntax error) | Per-formula: `"error: invalid syntax"` |
| Division by zero | Per-formula: `"error: division by zero"` |
| Disallowed AST node (function call, variable, import) | Per-formula: `"error: unsupported operation"` |
| Expression > 500 chars | Per-formula: `"error: Expression too long (max 500 chars)"` |
| > 20 formulas | Pydantic validation error → `BlockedAction` with `TOOL_FAILURE` |
| Empty formulas dict | Pydantic validation error → `BlockedAction` with `TOOL_FAILURE` |
| Exponent > 100 | Per-formula: `"error: exponent too large (max 100)"` |

All per-formula errors are strings in the result dict — the LLM sees them and can adjust or report to the user. Batch-level errors (empty/too many) fail the whole tool call and trigger `BlockedAction` → replan.

## Files to Change

| File | Change |
|------|--------|
| `src/alfred/tools/crud.py` | Add `CalculateParams`, `_safe_eval()`, `_eval_node()`, `calculate()`. Add dispatch in `execute_crud()`. |
| `src/alfred/graph/nodes/act.py` | Add `"calculate"` to `BUILTIN_ANALYZE`. Add formatting branch. Fix `table_name` for calculate. |
| `src/alfred/prompts/injection.py` | Add `calculate` to DECISION section for analyze steps. |
| `src/alfred/prompts/templates/act/analyze.md` | Add "Exact Arithmetic" section. Update reasoning mode to redirect to `calculate`. Add number accuracy guardrail. |
| `tests/` | Unit tests for `_safe_eval`, `calculate`, integration test for dispatch. |
