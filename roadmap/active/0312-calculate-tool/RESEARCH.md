# Research: Safe Calculator Tool (`calculate`)

**Goal:** Add a `calculate` tool for analyze steps that evaluates arithmetic expressions exactly — LLM writes formulas (good at), tool evaluates them (LLM bad at).
**Type:** feat
**Date:** 2026-03-12

## Context

Analyze steps currently have two modes: `db_analyze` (aggregate queries) and reasoning mode (LLM does math in-text). The gap: LLMs occasionally botch arithmetic evaluation even when they construct the correct formula. The `calculate` tool fills this by letting the LLM write expressions and having Python evaluate them safely.

Key insight from discussion: LLMs are great at *writing* formulas and *naming* results — they're unreliable at *evaluating* them. The tool does only the part the LLM is bad at.

## Function Chain

| Stage | Function/File | What Happens | Domain Hook |
|-------|--------------|--------------|-------------|
| Plan | `graph/nodes/think.py` | Emits step with `step_type: "analyze"` | `get_planning_prompt_injection()` |
| Prompt | `prompts/injection.py:272-315` | Builds "Data Available" section (no schema) | `get_act_prompt_injection("analyze")` |
| System | `prompts/templates/act/analyze.md` | Documents db_analyze + reasoning modes | `get_act_prompt_content("analyze")` |
| Dispatch | `graph/nodes/act.py:1371` | `BUILTIN_ANALYZE = {"db_analyze"}` — **add `"calculate"` here** | — |
| Execute | `graph/nodes/act.py:1514-1536` | No middleware, no registry, raw execution | — |
| CRUD | `tools/crud.py:273-343` | `db_analyze()` function — **add `calculate()` alongside** | — |
| Format | `graph/nodes/act.py:725-741` | Formats analytical results for next LLM call | — |

## Defaults vs Customizable

| Touchpoint | Current Default | Override Method | Gap? |
|------------|----------------|-----------------|------|
| Tool availability | `{"read", "write", "analyze"}` step types get tools | `get_tool_enabled_step_types()` | No — `calculate` available whenever analyze steps have tools |
| BUILTIN_ANALYZE set | `{"db_analyze"}` hardcoded in act.py | None (hardcoded) | No gap — just add `"calculate"` to the set |
| Prompt docs | `analyze.md` documents db_analyze + reasoning | `get_act_prompt_content("analyze")` can override | No — we add a section to analyze.md |
| Result formatting | Analytical results detected by absence of `id` field | Hardcoded in act.py | No — calculate returns `{"label": value}` dicts, no `id` field, same pattern |

## Findings

### API Design (refined through discussion)

**Input:** `{"formulas": {"label": "expression", ...}}` — dict of named expressions.

```json
{
  "action": "tool_call",
  "tool": "calculate",
  "params": {
    "formulas": {
      "rep_a_growth": "((450 - 360) / 360) * 100",
      "rep_b_growth": "((320 - 280) / 280) * 100",
      "margin_diff": "(0.42 - 0.38) * 100"
    }
  }
}
```

**Output:** `{"rep_a_growth": 25.0, "rep_b_growth": 14.29, "margin_diff": 4.0}`

**Per-formula errors:** `{"rep_a_growth": 25.0, "rep_d_growth": "error: division by zero"}`

### Safety — AST Whitelist

Use `ast.parse(expr, mode="eval")` then walk the tree. Whitelist:
- `ast.Expression` (top-level wrapper)
- `ast.Constant` with `isinstance(value, (int, float))` — no strings, no booleans
- `ast.BinOp` with ops: `Add`, `Sub`, `Mult`, `Div`, `Mod`, `Pow`
- `ast.UnaryOp` with ops: `USub`, `UAdd` (negative/positive numbers)

Reject everything else — no names, no calls, no attributes, no imports.

### Guardrails

- **Expression length cap:** ~500 chars per expression (generous but prevents abuse)
- **Formula count cap:** ~20 formulas per call
- **Division by zero:** caught per-formula, returns error string
- **Floating point display:** round to 10 decimal places, strip trailing zeros
- **Pow limit:** reject exponents > 1000 to prevent `2**999999999` hanging

### Prompt Guardrail

Add to analyze.md: "When using `calculate`, copy numbers exactly as they appear in prior step results. Double-check labels match the correct values."

### Integration Points

1. **`tools/crud.py`** — new `CalculateParams` model + `calculate()` function
2. **`graph/nodes/act.py:1371`** — add `"calculate"` to `BUILTIN_ANALYZE`
3. **`prompts/templates/act/analyze.md`** — new "Mode 3: Exact Arithmetic" section
4. **`graph/nodes/act.py:725-741`** — result formatting (may work as-is since calculate returns label:value dicts without `id` field)

### Why This Design Works

- **Same dispatch path as `db_analyze`** — no new execution code in act.py needed
- **One call, N formulas** — no multi-step chaining, no parallel tool call complexity
- **LLM writes the formula** (structured output, good at this) → **tool evaluates** (exact) → **LLM reviews result** (reasoning, good at this)
- **Composable with `db_analyze`**: `db_analyze` → raw numbers → `calculate` → derived values → LLM formats answer
- **No variable binding needed** — LLM hardcodes numbers from prior results, which is actually better for auditability (you can read the expression and verify the numbers)

## Open Questions

None — design is well-scoped from discussion. Ready to plan.
