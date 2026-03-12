# CRUD Tools Reference

## Tools

| Tool | Purpose | Available In | Params |
|------|---------|-------------|--------|
| `db_read` | Fetch entity rows (tracked with refs) | read, write | `table`, `filters`, `or_filters`, `columns`, `limit`, `order_by`, `order_dir` |
| `db_create` | Insert row(s) | read, write | `table`, `data` (dict or array of dicts) |
| `db_update` | Modify rows | read, write | `table`, `filters`, `data` (dict, applied to ALL matches) |
| `db_delete` | Remove rows | read, write | `table`, `filters` |
| `db_analyze` | Analytical query (aggregate + GROUP BY) | analyze | `table`, `aggregate`, `aggregate_field`, `filters`, `or_filters`, `group_by`, `order_by`, `order_dir`, `limit` |
| `calculate` | Exact arithmetic evaluation (safe, no eval) | analyze | `formulas` (dict of `"label": "expression"`) |

---

## Filter Syntax

Each filter: `{"field": "...", "op": "...", "value": "..."}`

**Operators:**

| Operator | Purpose | Example |
|----------|---------|---------|
| `=` | Exact match | `{"field": "id", "op": "=", "value": "item_1"}` |
| `!=` | Not equal | `{"field": "status", "op": "!=", "value": "expired"}` |
| `>`, `<`, `>=`, `<=` | Comparisons | `{"field": "quantity", "op": ">", "value": 0}` |
| `in` | Match any in list | `{"field": "id", "op": "in", "value": ["item_1", "item_2"]}` |
| `not_in` | Exclude list | `{"field": "id", "op": "not_in", "value": ["item_5"]}` |
| `ilike` | Fuzzy text | `{"field": "name", "op": "ilike", "value": "%chicken%"}` |
| `is_null` | Field is null | `{"field": "due_date", "op": "is_null", "value": true}` |
| `contains` | Array contains | `{"field": "occasions", "op": "contains", "value": ["weeknight"]}` |
| `similar` | Semantic search (domain middleware required) | `{"field": "_semantic", "op": "similar", "value": "light summer dinner"}` |

**Note:** Use simple refs like `item_1`, `item_5`. System translates to UUIDs automatically.

**Semantic search:** The `similar` operator uses `field: "_semantic"` (not a real column). It is handled by domain middleware (`CRUDMiddleware.pre_read()`), which runs vector/embedding search and returns matching IDs. Other filters are applied AFTER semantic narrowing. If the domain has not implemented semantic search, this operator will error.

---

## Sorting (db_read and db_analyze)

| Param | Type | Default | Example |
|-------|------|---------|---------|
| `order_by` | column name | none (DB order) | `"order_by": "total_points"` |
| `order_dir` | `"asc"` or `"desc"` | `"desc"` | `"order_dir": "asc"` |

When `order_by` is set, results are sorted by that column. Default direction is **descending** (highest first) — omit `order_dir` for "top N" queries.

---

## Column Selection

Don't pass `columns` unless you have a specific reason. Omitting it returns all fields including `id` (required for entity tracking). If you DO pass `columns`, you **must** include `id`.

---

## Schema = Your Tables

Only access tables shown in the schema section. Query results are facts — 0 records means empty.
