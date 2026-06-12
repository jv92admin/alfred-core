"""
Golden consumer fixtures — the Compatibility Guardrail merge gate (A3).

Three non-ledge fixture recipes against the assembly chain (program roadmap,
"Compatibility Guardrail"): (a) an S1 ref-translated read, (b) a memories-shaped
multi-fetch S3 recipe, (c) a kitchen-brainstorm S5 preload. None ships a
consumer; each proves the layer can express that shape WITHOUT bypass. A Track-A
feature that breaks one of these does not merge.

The chain composed here is the public substrate surface
(alfred.context.assembly links); the seam entrypoints are merely two S2-flavored
consumers of it — these fixtures are the other three shapes.
"""

import re

from alfred.context.assembly import (
    FilterClause,
    apply_post_read,
    enrich_fk_values,
    identity_passthrough,
    read_table,
)

# The fixture imports session machinery; the assembly module must NOT
# (enforced by test_import_isolation.py). That asymmetry is the point of (a).
from alfred.core.id_registry import SessionIdRegistry
from alfred.domain.base import CRUDMiddleware
from alfred.domain.grades import GRADE_REPLY, GradeRegistry

UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

ITEM_1 = "11111111-1111-1111-1111-111111111111"
ITEM_2 = "22222222-2222-2222-2222-222222222222"
NOTE_1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


# ---------------------------------------------------------------------------
# (a) S1 ref-translated read — fast-mode shaped
#
# Proves the identity-policy seat composes with the session registry WITHOUT
# the assembly module importing it: `translate_read_output` slots in as a
# caller-supplied IdentityPolicy.
# ---------------------------------------------------------------------------


async def test_s1_fixture_session_registry_is_the_identity_step(assembly_ctx_factory):
    ctx, _ = assembly_ctx_factory(
        {
            "items": [
                {"id": ITEM_1, "name": "Chicken Thighs", "quantity": 2},
                {"id": ITEM_2, "name": "Olive Oil", "quantity": 1},
            ],
            "notes": [],
        }
    )
    registry = SessionIdRegistry()

    # The S1-shaped chain: read → post_read → identity(registry) → strip(reply)
    # → STRING tail (format_records_for_context — S1/S3's formatter, not S2's).
    rows, _ = await read_table(ctx, "items", [])
    rows = await apply_post_read(ctx, rows, "items")
    rows = registry.translate_read_output(rows, "items")  # the IdentityPolicy seat
    rows = GradeRegistry.from_context(ctx).strip(rows, "items", GRADE_REPLY)
    context_block = "\n".join(ctx.format_records_for_context(rows, "items"))

    # Refs, not UUIDs — S1's invariant holds through the new chain.
    assert {r["id"] for r in rows} == {"item_1", "item_2"}
    assert "id:item_1" in context_block
    assert not UUID_PATTERN.search(context_block)
    # Grade reply strips nothing (Guardrail #3): every original field survived.
    assert all({"id", "name", "quantity"} <= r.keys() for r in rows)
    # And the registry holds the translation for the rest of the session (S1).
    assert registry.ref_to_uuid["item_1"] == ITEM_1


# ---------------------------------------------------------------------------
# (b) S3 recipe — memories-shaped multi-fetch
#
# Proves per-set chain calls compose into one context block without re-reading
# config (grade registry built once), with the string tail serving LLM-bound
# output.
# ---------------------------------------------------------------------------


async def test_s3_fixture_multi_fetch_recipe_composes_one_context_block(assembly_ctx_factory):
    ctx, adapter = assembly_ctx_factory(
        {
            "items": [
                {"id": ITEM_1, "name": "Chicken Thighs", "quantity": 2},
                {"id": ITEM_2, "name": "Olive Oil", "quantity": 1},
            ],
            "notes": [
                {"id": NOTE_1, "title": "Buy more", "item_id": ITEM_1, "body": None},
            ],
        }
    )
    grade_registry = GradeRegistry.from_context(ctx)  # built ONCE for the whole recipe

    sections = []
    for table, heading in (("items", "## Items"), ("notes", "## Notes")):
        rows, _ = await read_table(ctx, table, [])
        rows = await apply_post_read(ctx, rows, table)
        rows = await enrich_fk_values(ctx, rows)
        rows = identity_passthrough(rows, table)
        rows = grade_registry.strip(rows, table, GRADE_REPLY)
        lines = ctx.format_records_for_context(rows, table)
        sections.append(heading + "\n" + "\n".join(lines))
    recipe_context = "\n\n".join(sections)

    assert "## Items" in recipe_context and "## Notes" in recipe_context
    assert "Chicken Thighs" in recipe_context
    assert "Buy more" in recipe_context
    # FK enrichment resolved through the chain: the note's item_id is a name now.
    note_row = [q for q in adapter.queries_for("items") if ("in", "id", [ITEM_1]) in q.calls]
    assert note_row, "fk_enrich should have batch-fetched the note's item name"
    # Exactly 3 adapter reads: items, notes, one enrich batch — no per-row N+1.
    assert len(adapter.queries) == 3


# ---------------------------------------------------------------------------
# (c) S5 preload — brainstorm-shaped
#
# Proves the chain serves session preloads: profile + snapshot + multi-table
# reads → ONE frozen prompt string, passthrough identity, grade reply — grades
# and external identity don't interfere. Also the EXPLICIT-SCOPING pattern of
# record: this consumer runs a service-role-style adapter (no RLS), so it
# scopes with a real user_id — an explicit filter clause on the read and a
# real user_id through post_read. The seam entrypoints do neither by design
# (their adapter carries the tenant); copy THIS pattern when yours doesn't.
# ---------------------------------------------------------------------------

S5_GOLDEN = """\
## User Profile
Vegetarian household of 3.

## Kitchen Snapshot
2 items in inventory, 1 open note.

## Inventory
  - Chicken Thighs id:itm-1
  - Olive Oil id:itm-2

## Notes
  - Buy more id:nt-1"""


async def test_s5_fixture_preload_builds_frozen_prompt_with_explicit_scoping(
    assembly_ctx_factory,
):
    user = "user-A"
    post_read_user_ids = []

    class ScopeWitnessMiddleware(CRUDMiddleware):
        """Records the user_id the chain hands to post_read (must be the real one)."""

        async def post_read(self, records, table, user_id):
            post_read_user_ids.append(user_id)
            return records

    ctx, adapter = assembly_ctx_factory(
        {
            # Service-role view: rows for BOTH users are visible to the adapter.
            "items": [
                {"id": "itm-1", "name": "Chicken Thighs", "user_id": "user-A"},
                {"id": "itm-2", "name": "Olive Oil", "user_id": "user-A"},
                {"id": "itm-3", "name": "Secret Sauce", "user_id": "user-B"},
            ],
            "notes": [
                {"id": "nt-1", "title": "Buy more", "item_id": "itm-1", "user_id": "user-A"},
            ],
        },
        fk_enrich={},  # brainstorm preload shows items by name; no FK display needed
        middleware=ScopeWitnessMiddleware(),
        user_profile="Vegetarian household of 3.",
        domain_snapshot="2 items in inventory, 1 open note.",
    )
    grade_registry = GradeRegistry.from_context(ctx)
    scope = FilterClause(field="user_id", op="=", value=user)  # explicit scoping

    async def preload_section(table: str) -> list[str]:
        rows, _ = await read_table(ctx, table, [scope])
        rows = await apply_post_read(ctx, rows, table, user_id=user)  # real user_id
        rows = identity_passthrough(rows, table)  # ids stay — internal preload
        rows = grade_registry.strip(rows, table, GRADE_REPLY)
        rows = [{k: v for k, v in r.items() if k != "user_id"} for r in rows]
        return ctx.format_records_for_context(rows, table)

    prompt = "\n\n".join(
        [
            "## User Profile\n" + await ctx.get_user_profile(user),
            "## Kitchen Snapshot\n" + await ctx.get_domain_snapshot(user),
            "## Inventory\n" + "\n".join(await preload_section("items")),
            "## Notes\n" + "\n".join(await preload_section("notes")),
        ]
    )

    assert prompt == S5_GOLDEN  # frozen — the preload is deterministic
    assert "Secret Sauce" not in prompt  # explicit scoping excluded user-B rows
    assert "id:itm-1" in prompt  # passthrough identity: grades didn't interfere
    assert post_read_user_ids == [user, user]  # the REAL user_id flowed to post_read
