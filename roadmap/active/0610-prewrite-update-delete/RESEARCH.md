# Research (STUB): `pre_write` middleware never fires on `db_update` / `db_delete`

**Goal:** Make middleware firing entry-path-independent for all write operations (serving-modes expectation E1).
**Type:** fix
**Date:** 2026-06-10
**Status:** STUB — defect confirmed, full research not yet done. No rush on a patch release; this folds into the structural serving-modes work.

## The Defect

`db_create` accepts a `middleware` parameter and fires `pre_write` and `deduplicate_batch`:

- `src/alfred/tools/crud.py:454` — `db_create(params, user_id, middleware=None)`
- `src/alfred/tools/crud.py:482` — `records = await middleware.pre_write(params.table, records)`
- `src/alfred/tools/crud.py:490` — `deduplicate_batch` (batch only)

`db_update` and `db_delete` **do not take a middleware parameter at all** — there is no code path on which `pre_write` can fire for updates or deletes:

- `src/alfred/tools/crud.py:501` — `db_update(params, user_id)`
- `src/alfred/tools/crud.py:529` — `db_delete(params, user_id)`

Originally surfaced as the ledge v28 Phase 3 finding; confirmed in this repo 2026-06-10 (see [0610-serving-modes.md](../0610-serving-modes.md), M5 + E1).

## Impact

- **Today (M1 chat path):** any domain relying on `pre_write` for validation/enrichment invariants gets unvalidated updates and deletes through the Act loop.
- **Future (serving modes):** gates M5 (bounded write) — "mechanical write" silently means "unvalidated write" until closed. E1 conformance ("middleware fires on every adapter path") cannot be asserted.

## Questions for Full Research (not yet answered)

1. **Protocol shape.** `pre_write(table, records)` takes a records list; `db_update` has `(data: dict, filters)` and `db_delete` has only filters. Reuse `pre_write` with a one-element list, or add dedicated `pre_update(table, data, filters)` / `pre_delete(table, filters)` hooks to `CRUDMiddleware` (`src/alfred/domain/base.py:141-215`)?
2. **`post_read` symmetry.** Update/delete return the affected rows — should `post_read` (or an equivalent) fire on those returns before ref translation?
3. **Call-site threading.** Where does the Act dispatch path construct middleware for create but not update/delete — is the gap in `crud.py` only, or also in the executor call sites?
4. **Loud-failure stance.** If a domain defines middleware and an update path can't honor it, should core error rather than silently proceed (repo principle: no silent failures in a public package)?
5. **Back-compat.** Existing domains (Kitchen, FPL, memories, ledge) — does adding hooks to the `CRUDMiddleware` protocol need defaults to avoid breaking implementers?
