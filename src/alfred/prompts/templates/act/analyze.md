# Act - ANALYZE Step Mechanics

## Purpose

Run analytical queries against the database OR reason over data from previous steps.

Analyze steps have three modes:
1. **Query mode** — use `db_analyze` to get counts, sums, averages, min/max from the database
2. **Arithmetic mode** — use `calculate` for exact arithmetic over numbers from prior steps or `db_analyze` results
3. **Reasoning mode** — reason over data from prior steps (comparisons, decisions, filtering)

---

## db_analyze — Analytical Queries

Use `db_analyze` when you need a NUMBER from the database. One aggregate per call.

### Supported Aggregates

| Function | What It Does | Example Use |
|----------|-------------|-------------|
| `count` | Count rows | "How many active deals?" |
| `sum` | Sum a numeric column | "Total deal value?" |
| `avg` | Average a numeric column | "Average order size?" |
| `min` | Minimum value | "Cheapest item?" |
| `max` | Maximum value | "Largest deal?" |

### Parameters

| Param | Required | Description |
|-------|----------|-------------|
| `table` | Yes | Table to query |
| `aggregate` | Yes | `count`, `sum`, `avg`, `min`, `max` |
| `aggregate_field` | For sum/avg/min/max | Column to aggregate |
| `filters` | No | WHERE filters (same syntax as db_read) |
| `or_filters` | No | OR-combined filters |
| `group_by` | No | Column to group results by |
| `order_by` | No | Column to sort by |
| `order_dir` | No | `asc` or `desc` (default: `desc`) |
| `limit` | No | Max rows returned |

### Examples

**Count all rows:**
```json
{"table": "deals", "aggregate": "count"}
```
→ `[{"count": 42}]`

**Sum with filter:**
```json
{"table": "deals", "aggregate": "sum", "aggregate_field": "value",
 "filters": [{"field": "status", "op": "=", "value": "won"}]}
```
→ `[{"sum": 150000}]`

**Group by (totals by category):**
```json
{"table": "deals", "aggregate": "sum", "aggregate_field": "value", "group_by": "sales_rep"}
```
→ `[{"sales_rep": "Alice", "sum": 80000}, {"sales_rep": "Bob", "sum": 70000}]`

**Top N (largest deals):**
```json
{"table": "deals", "aggregate": "max", "aggregate_field": "value",
 "group_by": "name", "order_by": "max", "order_dir": "desc", "limit": 5}
```

---

## calculate — Exact Arithmetic

Use `calculate` when you need precise arithmetic over numbers from prior steps or `db_analyze` results. **ALWAYS use `calculate` for arithmetic — do not compute numbers in your response text.**

**IMPORTANT:** Copy numbers exactly as they appear in prior step results. Double-check labels match the correct values.

### Parameters

| Param | Required | Description |
|-------|----------|-------------|
| `formulas` | Yes | Dict of `"label": "expression"` — one or more labeled arithmetic expressions |

### Supported Operators

`+`, `-`, `*`, `/`, `//` (floor division), `%` (modulo), `**` (power, max exponent 100), `()` (grouping)

### Examples

**Single calculation:**
```json
{"formulas": {"growth_pct": "((450 - 360) / 360) * 100"}}
```
→ `{"growth_pct": 25.0}`

**Multiple calculations in one call:**
```json
{"formulas": {"rep_a_growth": "((450 - 360) / 360) * 100", "rep_b_growth": "((320 - 280) / 280) * 100", "margin": "(120 - 85) / 120 * 100"}}
```
→ `{"rep_a_growth": 25.0, "rep_b_growth": 14.29, "margin": 29.17}`

**Typical flow:** `db_analyze` → raw numbers → `calculate` → derived values → format answer

---

## Reasoning Over Prior Step Data

When prior steps have already fetched data, you can reason over it directly — no tool call needed.

Use reasoning mode for comparisons, decisions, and filtering — but **use `calculate` for any arithmetic** (percentages, differences, ratios).

### Common Patterns

| Pattern | How |
|---------|-----|
| Compare two values | `db_analyze` or prior steps → `calculate` for the math → reason about meaning |
| Filter a list | Prior step has records → pick the ones matching criteria |
| Find overlap | Two lists from prior steps → identify common items |
| Make a decision | Data available → reason and decide |

---

## Data Source Rules

**CRITICAL:** Only use data from "Previous Step Results", "Data to Analyze", `db_analyze` results, or `calculate` results.

- If data shows `[]` (empty), report "No data to analyze"
- Do NOT invent or hallucinate data
- Do NOT use entity references as data sources — they're only for ID reference

---

## Output Format

```json
{
  "action": "step_complete",
  "result_summary": "Total deal value: $150,000 across 42 deals",
  "data": {
    "total_value": 150000,
    "deal_count": 42
  },
  "note_for_next_step": "Total value computed for reply"
}
```

---

## When You Need User Input

If your analysis hits an ambiguity or requires a decision only the user can make, use `ask_user`. **Always include your partial analysis** — show what you've figured out so far.

```json
{
  "action": "ask_user",
  "question": "I found 6 options that work. Should I prioritize X or Y?",
  "data": {
    "partial_analysis": {
      "viable_options": 6,
      "decision_needed": "priority"
    }
  }
}
```

---

## What NOT to do

- Use `db_read` in an analyze step — use `db_analyze` for queries, or reason over prior step data
- Invent data not shown in previous results or tool results
- Use "Active Entities" as a data source (only for ID reference)
- Report analysis on empty data as if data existed
