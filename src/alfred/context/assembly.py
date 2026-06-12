"""
State-free assembly entrypoints — substrate capability C-5 (program roadmap A3).

The seam-contract deliverable (SEAM_CONTRACT.md §1–§2): ``assemble_entity_context``
and ``assemble_subdomain_read`` produce a ``ShapedPayload`` by composing the
per-record/per-set assembly chain:

    adapter read → post_read middleware → state-free fk_enrich → identity policy
    → strip(grade) → dict value-shaping ("(not set)" NULL signalling) → header

The two entrypoints are thin S2-flavored *consumers* of that chain, not the chain
itself (Compatibility Guardrail #1) — richer callers (S3 recipes, S5 preloads,
S1's read path via D7) compose the links below directly. Identity is a policy
parameter, never a payload property (Guardrail #2 / E9): grade ``external`` drops
the record's own ``id`` (the consuming AI re-finds entities by name/search);
other grades pass it through; callers may supply any
``(records, table) -> records`` callable (S1 slots the session registry's
``translate_read_output`` into this seat from outside — this module never
imports session machinery).

State-free guarantees (E2/E5, enforced by tests/core/test_import_isolation.py):
no ``AlfredState``, no session, no ``ContextVar``, no LLM call, no module-global
domain — the adapter comes only from ``ctx.get_db_adapter()`` (E3: the caller
establishes auth/tenant context per request).

Tenant scoping: this chain applies NO user filter. Row scoping is the adapter's
job (RLS behind a request-scoped adapter). A consumer holding a service-role
adapter must scope explicitly — pass a real ``user_id`` to ``apply_post_read``
and an explicit filter clause to ``read_table`` (the S5 golden fixture
demonstrates the pattern). The seam entrypoints pass ``user_id=""`` to
``post_read`` by design: seam §1 carries no user identity (E3).

``schema_version`` bump policy: ``SCHEMA_VERSION`` is the version of the
``ShapedPayload`` shape as an external contract (E6). Core bumps it on any
shape-breaking change — field removed/renamed/retyped, value-shaping semantics
changed (e.g. the NULL signal), or redaction semantics weakened. Additive,
non-breaking fields do not bump it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from alfred.domain.grades import GRADE_EXTERNAL, GradeRegistry, UnknownGradeError
from alfred.tools.crud import FilterClause, apply_filter

if TYPE_CHECKING:
    from alfred.domain.context import DomainContext

# Version of the ShapedPayload external contract (seam §2, amendment A1).
# Bump policy in the module docstring.
SCHEMA_VERSION: Final[str] = "1"

# Display value for NULLs after value-shaping (seam §2 "(not set)" signalling).
NULL_DISPLAY: Final[str] = "(not set)"


# =============================================================================
# Errors — loud and typed, never a silent empty read (seam §1, amendment A2)
# =============================================================================


class AssemblyError(ValueError):
    """Base for all assembly-chain errors."""


class FilterValidationError(AssemblyError):
    """Invalid filter mapping, unknown op, or adapter-rejected read."""


class UnknownEntityTypeError(AssemblyError):
    """entity_type not declared by the domain's entity definitions."""


class UnknownSubdomainError(AssemblyError):
    """subdomain not declared by the domain."""


class TableNotInSubdomainError(AssemblyError):
    """table exists but does not belong to the requested subdomain."""


class RecordNotFoundError(AssemblyError):
    """A specifically-requested entity returned no visible row.

    Loud by design: an empty payload for an entity the caller named would be
    the silent-failure shape.
    """


# =============================================================================
# ShapedPayload (seam §2, field-for-field)
# =============================================================================


@dataclass(frozen=True)
class ShapedPayload:
    """Shaped, graded, self-describing read result (seam contract §2).

    ``records`` values are display-ready: FK values are display names (or
    ``"(not set)"`` when unresolvable), NULLs are signalled, internal fields
    are stripped per ``grade``. The payload self-describes its redaction level
    so a consumer or audit can verify it without reaching back into config.
    """

    header: str
    records: list[dict[str, Any]]
    table: str
    count: int
    truncated: bool
    grade: str
    schema_version: str


# =============================================================================
# Filter contract — Mapping[str, Any] → validated FilterClause list
# =============================================================================

# Seam filter op names (PostgREST-style, seam §1) → FilterClause symbols
# (tools/crud.py). "similar" is deliberately absent: it is implemented by
# pre_read middleware, which is not on this chain — accepting it would be a
# silent-empty-read generator. Semantic matching returns as candidate
# retrieval (E10/D6), not as a seam filter.
_FILTER_OPS: Final[dict[str, str]] = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "in": "in",
    "not_in": "not_in",
    "ilike": "ilike",
    "is_null": "is_null",
    "is_not_null": "is_not_null",
    "contains": "contains",
}


def _make_clause(field: str, op_name: str, value: Any) -> FilterClause:
    if op_name == "similar":
        raise FilterValidationError(
            f"Filter op 'similar' (field '{field}') is not available on the "
            f"assembly chain: semantic matching requires pre_read middleware, "
            f"which does not run here. Use candidate retrieval (E10) instead."
        )
    symbol = _FILTER_OPS.get(op_name)
    if symbol is None:
        raise FilterValidationError(
            f"Unknown filter op '{op_name}' for field '{field}'. Valid ops: {sorted(_FILTER_OPS)}."
        )
    return FilterClause(field=field, op=symbol, value=value)  # type: ignore[arg-type]


def parse_filters(filters: Mapping[str, Any]) -> list[FilterClause]:
    """Validate and convert a seam filter mapping to FilterClause list.

    Accepted value forms per field:
    - scalar → equality shorthand: ``{"status": "active"}``
    - mapping of op → value (multiple ops AND-combined):
      ``{"price": {"gte": 100, "lte": 500}}``

    Raises:
        FilterValidationError: non-mapping input, non-string field, empty
            op-mapping, or unknown/unsupported op — always pre-flight, before
            any adapter call.
    """
    if not isinstance(filters, Mapping):
        raise FilterValidationError(
            f"filters must be a mapping of field -> value or field -> "
            f"{{op: value}}; got {type(filters).__name__}."
        )
    clauses: list[FilterClause] = []
    for field, spec in filters.items():
        if not isinstance(field, str):
            raise FilterValidationError(f"Filter field names must be strings; got {field!r}.")
        if isinstance(spec, Mapping):
            if not spec:
                raise FilterValidationError(
                    f"Filter for field '{field}' is an empty mapping — "
                    f"specify at least one op, e.g. {{'eq': value}}."
                )
            for op_name, value in spec.items():
                clauses.append(_make_clause(field, str(op_name), value))
        else:
            clauses.append(_make_clause(field, "eq", spec))
    return clauses


# =============================================================================
# The chain links (public substrate surface — compose freely)
# =============================================================================


async def read_table(
    ctx: DomainContext,
    table: str,
    clauses: Sequence[FilterClause],
    *,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Adapter read with limit+1 truncation detection.

    Applies NO user filter — row scoping is the adapter's job (RLS behind a
    request-scoped adapter, E3). Non-RLS callers scope explicitly with a
    filter clause. Fetches ``limit + 1`` rows and reports
    ``truncated = more rows existed than limit`` (PostgREST returns no total
    count on a plain limited select — this is the honest signal).

    Returns:
        (rows, truncated) — at most ``limit`` rows.

    Raises:
        FilterValidationError: limit < 1, unsupported filter op, or the
            adapter rejected the query (e.g. unknown column) — the adapter's
            own loud error is chained, never swallowed into an empty result.
    """
    if limit is not None and limit < 1:
        raise FilterValidationError(f"limit must be >= 1, got {limit}.")
    query = ctx.get_db_adapter().table(table).select("*")
    for clause in clauses:
        try:
            query = apply_filter(query, clause)
        except ValueError as e:
            raise FilterValidationError(str(e)) from e
    if limit is not None:
        query = query.limit(limit + 1)
    try:
        result = query.execute()
    except Exception as e:
        raise FilterValidationError(
            f"Read of table '{table}' was rejected by the database adapter "
            f"(check filter fields/values): {e}"
        ) from e
    rows: list[dict[str, Any]] = list(result.data or [])
    truncated = limit is not None and len(rows) > limit
    return (rows[:limit] if limit is not None else rows), truncated


async def apply_post_read(
    ctx: DomainContext,
    records: list[dict[str, Any]],
    table: str,
    user_id: str = "",
) -> list[dict[str, Any]]:
    """Fire the domain's post_read middleware (transform dispositions).

    Per the seam §3 clarification, value transforms (cents→dollars, derived
    display values) live here, grade-independent — the chain applies them
    before the strip step. ``user_id`` defaults to ``""`` (the seam
    entrypoints carry no user identity, E3); callers that scope explicitly
    (S5-style preloads on a service-role adapter) pass a real one.
    """
    middleware = ctx.get_crud_middleware()
    if middleware is None:
        return records
    return await middleware.post_read(records, table, user_id)


async def enrich_fk_values(
    ctx: DomainContext,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """State-free fk_enrich: replace FK UUID values with display names.

    For each field in ``ctx.get_fk_enrich_map()``, batch-fetches display names
    by UUID (one ``in`` read per target table via ``ctx.get_db_adapter()``)
    and replaces the value. No counters, no session, no registry.

    An FK value that does not resolve (RLS-hidden row, dangling reference)
    becomes ``None`` — deliberately. Under RLS, an FK pointing at a row this
    adapter cannot see must render as "(not set)" rather than leak a raw UUID
    (E9: redaction-positive degradation).

    Returns new record dicts; inputs are never mutated.
    """
    enrich_map = ctx.get_fk_enrich_map()
    if not enrich_map or not records:
        return [dict(r) for r in records]

    pending: dict[tuple[str, str], set[str]] = {}
    for record in records:
        for fk_field, (target_table, name_col) in enrich_map.items():
            value = record.get(fk_field)
            if value:
                pending.setdefault((target_table, name_col), set()).add(str(value))

    names: dict[tuple[str, str], dict[str, Any]] = {}
    adapter = ctx.get_db_adapter()
    for (target_table, name_col), uuids in pending.items():
        result = (
            adapter.table(target_table).select(f"id,{name_col}").in_("id", sorted(uuids)).execute()
        )
        names[(target_table, name_col)] = {
            str(row["id"]): row.get(name_col) for row in (result.data or [])
        }

    enriched: list[dict[str, Any]] = []
    for record in records:
        new_record = dict(record)
        for fk_field, (target_table, name_col) in enrich_map.items():
            value = new_record.get(fk_field)
            if value:
                new_record[fk_field] = names.get((target_table, name_col), {}).get(str(value))
        enriched.append(new_record)
    return enriched


# Identity policy (E9): how a record's own ``id`` crosses the boundary.
# (records, table) -> records. The chain takes this as a parameter; the seam
# entrypoints select by grade. S1 slots the session registry's
# ``translate_read_output`` into this seat (golden fixture) — composability,
# not import.
IdentityPolicy = Callable[[list[dict[str, Any]], str], list[dict[str, Any]]]


def identity_passthrough(records: list[dict[str, Any]], table: str) -> list[dict[str, Any]]:
    """Internal-grade identity: ids pass through unchanged (new dicts)."""
    return [dict(r) for r in records]


def identity_drop_ids(records: list[dict[str, Any]], table: str) -> list[dict[str, Any]]:
    """External-grade identity: drop the record's own ``id``.

    There is no session registry across the seam, so there is no ref to
    translate to; the consuming AI re-finds entities by name/search (ledge's
    tool design assumes this). FK values are handled by ``enrich_fk_values``,
    not here.
    """
    return [{k: v for k, v in r.items() if k != "id"} for r in records]


def shape_record_values(record: Mapping[str, Any]) -> dict[str, Any]:
    """Dict value-shaping: NULL → "(not set)" signalling (seam §2).

    Runs AFTER strip(grade), so stripped fields never resurrect as
    "(not set)". Value transforms are post_read middleware (§3) and have
    already been applied — this step stays minimal and grade-independent.
    """
    return {k: (NULL_DISPLAY if v is None else v) for k, v in record.items()}


# =============================================================================
# The seam entrypoints (§1 + the async amendment) — thin compositions
# =============================================================================


def _validated_grade_registry(ctx: DomainContext, grade: str) -> GradeRegistry:
    """Build the per-call grade registry and fail fast on an unknown grade.

    Validating before the adapter read keeps the loud error pre-I/O; the
    strip step would also raise, but only after a wasted query.
    """
    registry = GradeRegistry.from_context(ctx)
    if grade not in registry.grades:
        raise UnknownGradeError(
            f"Unknown grade '{grade}'. Registered grades: {sorted(registry.grades)}."
        )
    return registry


async def _shape_records(
    ctx: DomainContext,
    table: str,
    rows: list[dict[str, Any]],
    *,
    grade: str,
    registry: GradeRegistry,
    identity: IdentityPolicy,
    user_id: str = "",
) -> list[dict[str, Any]]:
    """The chain tail shared by both entrypoints (post-read onward)."""
    rows = await apply_post_read(ctx, rows, table, user_id)
    rows = await enrich_fk_values(ctx, rows)
    rows = identity(rows, table)
    rows = registry.strip(rows, table, grade)
    return [shape_record_values(r) for r in rows]


def _identity_for_grade(grade: str) -> IdentityPolicy:
    return identity_drop_ids if grade == GRADE_EXTERNAL else identity_passthrough


async def assemble_entity_context(
    ctx: DomainContext,
    entity_type: str,
    entity_id: str,
    *,
    grade: str,
) -> ShapedPayload:
    """Assemble one entity's shaped context (seam contract §1).

    Row scoping is the adapter's job — this function adds NO user filter.
    ``ctx.get_db_adapter()`` must carry the request's auth/tenant context
    (E3); a service-role adapter sees across tenants and must not be handed
    to this function without that understanding.

    Args:
        ctx: The substrate half of the domain protocol (no LLM imports).
        entity_type: Domain entity key, e.g. "deal".
        entity_id: The record's UUID (raw — there is no session registry here).
        grade: Named grade from the domain's grade registry (seam §3).

    Raises:
        UnknownEntityTypeError: entity_type not declared by the domain.
        UnknownGradeError: grade not in the domain's registry.
        RecordNotFoundError: no visible row with that id (loud, never an
            empty payload for a specifically-requested entity).
        FilterValidationError: the adapter rejected the read.
    """
    table = ctx.type_to_table.get(entity_type)
    if table is None:
        raise UnknownEntityTypeError(
            f"Unknown entity type '{entity_type}' for domain '{ctx.name}'. "
            f"Declared types: {sorted(ctx.type_to_table)}."
        )
    registry = _validated_grade_registry(ctx, grade)
    clauses = [FilterClause(field="id", op="=", value=entity_id)]
    rows, _ = await read_table(ctx, table, clauses, limit=1)
    if not rows:
        raise RecordNotFoundError(
            f"No '{entity_type}' record with id '{entity_id}' is visible to "
            f"this adapter (table '{table}')."
        )
    records = await _shape_records(
        ctx,
        table,
        rows,
        grade=grade,
        registry=registry,
        identity=_identity_for_grade(grade),
    )
    return ShapedPayload(
        header=ctx.get_table_notes(table),
        records=records,
        table=table,
        count=len(records),
        truncated=False,
        grade=grade,
        schema_version=SCHEMA_VERSION,
    )


async def assemble_subdomain_read(
    ctx: DomainContext,
    subdomain: str,
    table: str,
    filters: Mapping[str, Any],
    *,
    grade: str,
    limit: int = 25,
) -> ShapedPayload:
    """Assemble a shaped, graded table read (seam contract §1).

    Row scoping is the adapter's job — this function adds NO user filter.
    ``ctx.get_db_adapter()`` must carry the request's auth/tenant context
    (E3); a service-role adapter sees across tenants and must not be handed
    to this function without that understanding.

    Args:
        ctx: The substrate half of the domain protocol (no LLM imports).
        subdomain: Declared subdomain name, e.g. "crm".
        table: Table within that subdomain, e.g. "deals".
        filters: Field → value (eq shorthand) or field → {op: value} mapping;
            core validates (amendment A2) — invalid filter is a loud typed
            error, never a silent empty read.
        grade: Named grade from the domain's grade registry (seam §3).
        limit: Max records returned; ``truncated=True`` when clipped.

    Raises:
        UnknownSubdomainError / TableNotInSubdomainError: bad target.
        UnknownGradeError: grade not in the domain's registry.
        FilterValidationError: invalid filter shape/op, bad limit, or the
            adapter rejected the read.
    """
    sub = ctx.subdomains.get(subdomain)
    if sub is None:
        raise UnknownSubdomainError(
            f"Unknown subdomain '{subdomain}' for domain '{ctx.name}'. "
            f"Declared subdomains: {sorted(ctx.subdomains)}."
        )
    allowed = {sub.primary_table, *sub.related_tables}
    if table not in allowed:
        raise TableNotInSubdomainError(
            f"Table '{table}' is not part of subdomain '{subdomain}'. "
            f"Its tables: {sorted(allowed)}."
        )
    registry = _validated_grade_registry(ctx, grade)
    clauses = parse_filters(filters)
    rows, truncated = await read_table(ctx, table, clauses, limit=limit)
    records = await _shape_records(
        ctx,
        table,
        rows,
        grade=grade,
        registry=registry,
        identity=_identity_for_grade(grade),
    )
    return ShapedPayload(
        header=ctx.get_table_notes(table),
        records=records,
        table=table,
        count=len(records),
        truncated=truncated,
        grade=grade,
        schema_version=SCHEMA_VERSION,
    )
