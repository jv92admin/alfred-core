"""
Grade-registry conformance (program roadmap A2 / substrate C-6).

Pins the seam contract §3 guarantees: well-known grades, mechanically
enforced ``external ⊇ reply``, loud unknown-grade errors, and Compatibility
Guardrail #3 — the default "reply" grade strips nothing (today's assembly
output, byte-for-byte).
"""

import pytest

from alfred.context import (
    GRADE_EXTERNAL,
    GRADE_REPLY,
    GradeRegistry,
    GradeRegistryError,
    StripSet,
    UnknownGradeError,
)
from alfred.context import GradeRegistry as GradeRegistryFromSeam
from alfred.domain import register_domain
from alfred.domain.grades import GradeRegistry as GradeRegistryCanonical

from .conftest import StubDomainConfig

# ---------------------------------------------------------------------------
# Declaration helpers
# ---------------------------------------------------------------------------


class _GradedDomain(StubDomainConfig):
    """Stub domain with an overridable grade declaration."""

    def __init__(self, grades: dict[str, StripSet]):
        super().__init__()
        self._grades = grades

    def get_audience_grades(self) -> dict[str, StripSet]:
        return self._grades


RECORDS = [
    {"id": "u-1", "name": "Front yard", "company_id": "c-9", "amount_cents": 1200},
    {"id": "u-2", "name": "Back patio", "company_id": "c-9", "notes": None},
]


# ---------------------------------------------------------------------------
# Defaults & zero migration
# ---------------------------------------------------------------------------


def test_default_registry_has_exactly_the_well_known_grades(stub_domain):
    registry = GradeRegistry.from_context(stub_domain)
    assert set(registry.grades) == {GRADE_REPLY, GRADE_EXTERNAL}
    assert registry.grades[GRADE_REPLY] == StripSet()
    assert registry.grades[GRADE_EXTERNAL] == StripSet()


def test_default_reply_grade_strips_nothing(stub_domain):
    """Compatibility Guardrail #3: grade "reply" reproduces today's assembly
    output — for core's default that means key-identical record copies."""
    registry = GradeRegistry.from_context(stub_domain)
    stripped = registry.strip(RECORDS, "deals", GRADE_REPLY)
    assert stripped == RECORDS
    # Copies, not the same objects — the primitive is pure.
    assert all(s is not r for s, r in zip(stripped, RECORDS, strict=True))


def test_register_domain_accepts_default_declaration():
    """Zero migration: a domain that never heard of grades registers fine
    (also exercised by conftest's module-level registration on every run)."""
    register_domain(StubDomainConfig())


# ---------------------------------------------------------------------------
# The strip primitive
# ---------------------------------------------------------------------------


def _declared_registry() -> GradeRegistry:
    domain = _GradedDomain(
        {
            GRADE_REPLY: StripSet(),
            GRADE_EXTERNAL: StripSet(
                fields=frozenset({"company_id"}),
                table_fields={"deals": frozenset({"amount_cents"})},
            ),
        }
    )
    return GradeRegistry.from_context(domain)


def test_strip_applies_global_and_per_table_union():
    registry = _declared_registry()
    stripped = registry.strip(RECORDS, "deals", GRADE_EXTERNAL)
    assert stripped == [
        {"id": "u-1", "name": "Front yard"},
        {"id": "u-2", "name": "Back patio", "notes": None},
    ]


def test_strip_unknown_table_applies_global_set_only():
    """Tables are open-world: no per-table entry is not an error."""
    registry = _declared_registry()
    stripped = registry.strip(RECORDS, "clients", GRADE_EXTERNAL)
    assert stripped[0] == {"id": "u-1", "name": "Front yard", "amount_cents": 1200}


def test_strip_never_mutates_inputs():
    registry = _declared_registry()
    registry.strip(RECORDS, "deals", GRADE_EXTERNAL)
    assert "company_id" in RECORDS[0]
    assert "amount_cents" in RECORDS[0]


def test_unknown_grade_is_a_loud_typed_error():
    """Seam §3: unregistered grade at call time — never silent passthrough."""
    registry = _declared_registry()
    with pytest.raises(UnknownGradeError, match=r"internal.*external.*reply"):
        registry.strip(RECORDS, "deals", "internal")


# ---------------------------------------------------------------------------
# Registration-time validation (declare/enforce symmetry)
# ---------------------------------------------------------------------------


def test_missing_well_known_grade_fails_at_registration():
    domain = _GradedDomain({GRADE_REPLY: StripSet()})
    with pytest.raises(GradeRegistryError, match="external"):
        register_domain(domain)


def test_global_superset_violation_fails_at_registration():
    domain = _GradedDomain(
        {
            GRADE_REPLY: StripSet(fields=frozenset({"internal_score"})),
            GRADE_EXTERNAL: StripSet(),
        }
    )
    with pytest.raises(GradeRegistryError, match="internal_score"):
        register_domain(domain)


def test_per_table_reply_field_covered_by_external_global_is_valid():
    domain = _GradedDomain(
        {
            GRADE_REPLY: StripSet(table_fields={"deals": frozenset({"margin"})}),
            GRADE_EXTERNAL: StripSet(fields=frozenset({"margin"})),
        }
    )
    register_domain(domain)  # must not raise


def test_per_table_reply_field_uncovered_fails_naming_table_and_field():
    domain = _GradedDomain(
        {
            GRADE_REPLY: StripSet(table_fields={"deals": frozenset({"margin"})}),
            GRADE_EXTERNAL: StripSet(fields=frozenset({"company_id"})),
        }
    )
    with pytest.raises(GradeRegistryError, match=r"deals.*margin"):
        register_domain(domain)


def test_custom_grade_is_accepted_and_strippable():
    """Registry-over-enum rationale: extra grades need no core release and
    carry no ordering constraint."""
    domain = _GradedDomain(
        {
            GRADE_REPLY: StripSet(),
            GRADE_EXTERNAL: StripSet(),
            "board_pack": StripSet(fields=frozenset({"name"})),
        }
    )
    register_domain(domain)
    registry = GradeRegistry.from_context(domain)
    stripped = registry.strip(RECORDS, "deals", "board_pack")
    assert all("name" not in r for r in stripped)


# ---------------------------------------------------------------------------
# Seam import path
# ---------------------------------------------------------------------------


def test_seam_exports_are_the_canonical_objects():
    """`from alfred.context import ...` (seam) resolves to alfred.domain.grades."""
    assert GradeRegistryFromSeam is GradeRegistryCanonical
