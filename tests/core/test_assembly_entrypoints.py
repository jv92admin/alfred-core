"""
State-free assembly entrypoints — unit suite (A3 / E2 / C-5, seam contract §1–§2).

Golden consumer fixtures (the merge gate) live in test_assembly_fixtures.py;
this file covers the contract mechanics: payload shape, filter validation,
loud typed errors, truncation, grading, identity, value shaping, and the
E3 no-user-filter property.
"""

import dataclasses

import pytest

import alfred.context.assembly as assembly_module
from alfred.context import (
    SCHEMA_VERSION,
    FilterValidationError,
    RecordNotFoundError,
    ShapedPayload,
    TableNotInSubdomainError,
    UnknownEntityTypeError,
    UnknownSubdomainError,
    assemble_entity_context,
    assemble_subdomain_read,
    identity_drop_ids,
    identity_passthrough,
)
from alfred.context.assembly import NULL_DISPLAY, parse_filters
from alfred.domain.base import CRUDMiddleware
from alfred.domain.grades import GRADE_EXTERNAL, GRADE_REPLY, StripSet, UnknownGradeError

ITEM_1 = "11111111-1111-1111-1111-111111111111"
ITEM_2 = "22222222-2222-2222-2222-222222222222"
NOTE_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

ITEMS = [
    {"id": ITEM_1, "name": "Chicken Thighs", "category": "general", "quantity": 2},
    {"id": ITEM_2, "name": "Olive Oil", "category": "special", "quantity": None},
]
NOTES = [
    {"id": NOTE_1, "title": "Buy more", "item_id": ITEM_1, "body": None},
]


# ---------------------------------------------------------------------------
# ShapedPayload + seam canonicality
# ---------------------------------------------------------------------------


def test_shaped_payload_is_frozen_and_versioned():
    payload = ShapedPayload(
        header="",
        records=[],
        table="items",
        count=0,
        truncated=False,
        grade=GRADE_REPLY,
        schema_version=SCHEMA_VERSION,
    )
    assert SCHEMA_VERSION == "1"
    assert payload.schema_version == "1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        payload.count = 1  # type: ignore[misc]


def test_seam_import_path_is_canonical():
    """`from alfred.context import ...` (seam) is the same object as the module's."""
    assert assemble_entity_context is assembly_module.assemble_entity_context
    assert assemble_subdomain_read is assembly_module.assemble_subdomain_read
    assert ShapedPayload is assembly_module.ShapedPayload


# ---------------------------------------------------------------------------
# Filter contract — Mapping → FilterClause, loud pre-flight validation
# ---------------------------------------------------------------------------


def test_parse_filters_scalar_is_eq_shorthand():
    clauses = parse_filters({"status": "active"})
    assert len(clauses) == 1
    assert (clauses[0].field, clauses[0].op, clauses[0].value) == ("status", "=", "active")


def test_parse_filters_op_form_and_multi_op():
    clauses = parse_filters({"price": {"gte": 100, "lte": 500}, "name": {"ilike": "%oil%"}})
    assert {(c.field, c.op, c.value) for c in clauses} == {
        ("price", ">=", 100),
        ("price", "<=", 500),
        ("name", "ilike", "%oil%"),
    }


def test_parse_filters_unknown_op_is_loud_and_names_valid_ops():
    with pytest.raises(FilterValidationError) as exc:
        parse_filters({"price": {"between": (1, 2)}})
    assert "between" in str(exc.value)
    assert "eq" in str(exc.value)  # the valid op list is in the message


def test_parse_filters_similar_is_rejected():
    """'similar' needs pre_read middleware — not on the chain (E10 is the path)."""
    with pytest.raises(FilterValidationError) as exc:
        parse_filters({"_semantic": {"similar": "light summer dinner"}})
    assert "similar" in str(exc.value)
    assert "pre_read" in str(exc.value)


@pytest.mark.parametrize(
    "bad",
    [
        ["status", "active"],  # not a mapping
        "status=active",  # not a mapping
        {"status": {}},  # empty op mapping
        {1: "active"},  # non-string field
    ],
)
def test_parse_filters_bad_shapes_are_loud(bad):
    with pytest.raises(FilterValidationError):
        parse_filters(bad)


# ---------------------------------------------------------------------------
# assemble_entity_context
# ---------------------------------------------------------------------------


async def test_entity_context_external_drops_id_and_enriches_fks(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    payload = await assemble_entity_context(ctx, "note", NOTE_1, grade=GRADE_EXTERNAL)
    assert payload.table == "notes"
    assert payload.count == 1
    assert payload.truncated is False
    assert payload.grade == GRADE_EXTERNAL
    record = payload.records[0]
    assert "id" not in record  # identity_drop_ids at external (E9)
    assert record["item_id"] == "Chicken Thighs"  # FK value → display name
    assert record["body"] == NULL_DISPLAY  # NULL signalling
    assert payload.header == "Notes attach to items."  # owning subdomain's notes


async def test_entity_context_reply_passes_id_through(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    payload = await assemble_entity_context(ctx, "item", ITEM_1, grade=GRADE_REPLY)
    assert payload.records[0]["id"] == ITEM_1  # passthrough identity at reply


async def test_entity_context_unknown_type_is_loud(assembly_ctx_factory):
    ctx, adapter = assembly_ctx_factory({"items": ITEMS})
    with pytest.raises(UnknownEntityTypeError) as exc:
        await assemble_entity_context(ctx, "deal", ITEM_1, grade=GRADE_REPLY)
    assert "item" in str(exc.value) and "note" in str(exc.value)  # names valid types
    assert adapter.queries == []  # failed before any read


async def test_entity_context_not_found_is_loud_not_empty(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    with pytest.raises(RecordNotFoundError) as exc:
        await assemble_entity_context(
            ctx, "item", "99999999-9999-9999-9999-999999999999", grade=GRADE_REPLY
        )
    assert "item" in str(exc.value)


async def test_unknown_grade_fails_fast_before_any_read(assembly_ctx_factory):
    ctx, adapter = assembly_ctx_factory({"items": ITEMS})
    with pytest.raises(UnknownGradeError):
        await assemble_entity_context(ctx, "item", ITEM_1, grade="board_deck")
    assert adapter.queries == []  # loud BEFORE touching the adapter


# ---------------------------------------------------------------------------
# assemble_subdomain_read
# ---------------------------------------------------------------------------


async def test_subdomain_read_filters_and_self_describes(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    payload = await assemble_subdomain_read(
        ctx, "items", "items", {"category": "general"}, grade=GRADE_REPLY
    )
    assert payload.table == "items"
    assert payload.count == 1
    assert payload.records[0]["name"] == "Chicken Thighs"
    assert payload.records[0]["quantity"] == 2
    assert payload.grade == GRADE_REPLY
    assert payload.schema_version == SCHEMA_VERSION
    assert payload.header == "Items are physical things."


async def test_subdomain_read_unknown_subdomain_is_loud(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS})
    with pytest.raises(UnknownSubdomainError) as exc:
        await assemble_subdomain_read(ctx, "crm", "items", {}, grade=GRADE_REPLY)
    assert "items" in str(exc.value)  # names valid subdomains


async def test_subdomain_read_table_outside_subdomain_is_loud(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS})
    with pytest.raises(TableNotInSubdomainError) as exc:
        await assemble_subdomain_read(ctx, "notes", "items", {}, grade=GRADE_REPLY)
    assert "notes" in str(exc.value)


async def test_truncated_via_limit_plus_one(assembly_ctx_factory):
    rows = [{"id": f"id-{i}", "name": f"Item {i}", "category": "general"} for i in range(3)]
    ctx, adapter = assembly_ctx_factory({"items": rows, "notes": []})

    clipped = await assemble_subdomain_read(ctx, "items", "items", {}, grade=GRADE_REPLY, limit=2)
    assert clipped.count == 2
    assert clipped.truncated is True
    # The honest signal: the adapter was asked for limit + 1.
    assert ("limit", 3) in adapter.queries_for("items")[0].calls

    exact = await assemble_subdomain_read(ctx, "items", "items", {}, grade=GRADE_REPLY, limit=3)
    assert exact.count == 3
    assert exact.truncated is False


async def test_limit_below_one_is_loud(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS})
    with pytest.raises(FilterValidationError):
        await assemble_subdomain_read(ctx, "items", "items", {}, grade=GRADE_REPLY, limit=0)


async def test_adapter_rejection_surfaces_as_typed_error_with_cause(assembly_ctx_factory):
    """Unknown column: the adapter's loud error is wrapped, never an empty read."""
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    with pytest.raises(FilterValidationError) as exc:
        await assemble_subdomain_read(
            ctx, "items", "items", {"no_such_column": "x"}, grade=GRADE_REPLY
        )
    assert exc.value.__cause__ is not None
    assert "no_such_column" in str(exc.value.__cause__)


async def test_no_user_filter_is_ever_applied(assembly_ctx_factory):
    """E3: row scoping is the adapter's job — the chain adds no user filter."""
    ctx, adapter = assembly_ctx_factory({"items": ITEMS, "notes": NOTES})
    await assemble_subdomain_read(ctx, "items", "items", {"category": "general"}, grade=GRADE_REPLY)
    for query in adapter.queries:
        assert not any(call[0] in ("eq", "in") and call[1] == "user_id" for call in query.calls), (
            f"user filter injected on '{query.table}': {query.calls}"
        )


# ---------------------------------------------------------------------------
# Grading, shaping, middleware
# ---------------------------------------------------------------------------


def _graded(fields):
    return {GRADE_REPLY: StripSet(), GRADE_EXTERNAL: StripSet(fields=frozenset(fields))}


async def test_stripped_null_field_does_not_resurrect_as_not_set(assembly_ctx_factory):
    """Strip runs BEFORE shaping: a stripped NULL field must vanish, not show '(not set)'."""
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES}, grades=_graded({"body"}))
    payload = await assemble_entity_context(ctx, "note", NOTE_1, grade=GRADE_EXTERNAL)
    record = payload.records[0]
    assert "body" not in record  # stripped — gone entirely
    assert NULL_DISPLAY not in record.values()  # 'body' was the only NULL on the row


async def test_custom_grade_strips_and_reply_does_not(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": NOTES}, grades=_graded({"quantity"}))
    external = await assemble_entity_context(ctx, "item", ITEM_1, grade=GRADE_EXTERNAL)
    assert "quantity" not in external.records[0]
    reply = await assemble_entity_context(ctx, "item", ITEM_1, grade=GRADE_REPLY)
    assert reply.records[0]["quantity"] == 2


async def test_post_read_middleware_fires_with_empty_user_id_at_seam(assembly_ctx_factory):
    """Transforms (§3: cents→dollars) are middleware; the seam passes user_id=''."""
    seen = {}

    class TransformMiddleware(CRUDMiddleware):
        async def post_read(self, records, table, user_id):
            seen["user_id"] = user_id
            return [
                {**r, "price": f"${r['price_cents'] / 100:.2f}"} if "price_cents" in r else r
                for r in records
            ]

    rows = [{"id": ITEM_1, "name": "Olive Oil", "category": "special", "price_cents": 1250}]
    ctx, _ = assembly_ctx_factory({"items": rows, "notes": []}, middleware=TransformMiddleware())
    payload = await assemble_entity_context(ctx, "item", ITEM_1, grade=GRADE_REPLY)
    assert payload.records[0]["price"] == "$12.50"  # transform applied before strip/shape
    assert seen["user_id"] == ""  # seam carries no user identity (E3)


async def test_unresolved_fk_becomes_not_set_never_a_uuid(assembly_ctx_factory):
    """RLS-hidden / dangling FK degrades redaction-positively (E9)."""
    dangling = "deadbeef-dead-dead-dead-deaddeaddead"
    notes = [{"id": NOTE_1, "title": "Orphan", "item_id": dangling, "body": "x"}]
    ctx, _ = assembly_ctx_factory({"items": ITEMS, "notes": notes})
    payload = await assemble_entity_context(ctx, "note", NOTE_1, grade=GRADE_EXTERNAL)
    assert payload.records[0]["item_id"] == NULL_DISPLAY
    assert dangling not in str(payload.records)


# ---------------------------------------------------------------------------
# Identity policies (chain-level units)
# ---------------------------------------------------------------------------


def test_identity_policies_are_pure_and_minimal():
    records = [{"id": "abc", "name": "Widget", "item_id": "xyz"}]
    passed = identity_passthrough(records, "items")
    assert passed == records
    assert passed[0] is not records[0]  # new dicts — purity
    dropped = identity_drop_ids(records, "items")
    assert dropped == [{"name": "Widget", "item_id": "xyz"}]  # only the record's own id
    assert records[0]["id"] == "abc"  # input untouched
