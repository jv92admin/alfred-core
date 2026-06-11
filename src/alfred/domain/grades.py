"""
Audience-grade registry — substrate capability C-6 (program roadmap A2).

Named redaction grades for LLM-bound / external-bound context assembly.
Declare/enforce symmetry (seam contract §3, 0610-substrate.md §1): the domain
declares each grade as a ``StripSet`` via ``DomainContext.get_audience_grades()``;
core validates the ordering (``external ⊇ reply``) at ``register_domain()`` and
applies the strip during assembly. An unregistered grade at call time is a loud
typed error, never a silent passthrough.

Grades are PURE FIELD REMOVAL. Transform dispositions (cents→dollars, FK
values→display names) remain ``post_read`` middleware / fk_enrich —
grade-independent, applied before the strip step in the assembly chain
(seam contract §1: post_read → fk_enrich → strip(grade) → format → header).

Import discipline: this module is stdlib-only. It sits on the ``alfred.context``
and ``alfred.domain`` import paths whose isolation (no langgraph/instructor) is
enforced by tests/core/test_import_isolation.py.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from alfred.domain.context import DomainContext

# Well-known grades shipped by core (seam contract §3). Domains may declare
# any additional grade names; only these two are required and ordered.
GRADE_REPLY: Final[str] = "reply"
GRADE_EXTERNAL: Final[str] = "external"
WELL_KNOWN_GRADES: Final[frozenset[str]] = frozenset({GRADE_REPLY, GRADE_EXTERNAL})


class GradeError(ValueError):
    """Base for all grade-registry errors."""


class GradeRegistryError(GradeError):
    """Invalid grade declaration — raised at register_domain()."""


class UnknownGradeError(GradeError):
    """Unregistered grade string at call time — never a silent passthrough."""


@dataclass(frozen=True)
class StripSet:
    """
    Fields a grade removes from records.

    Field names are raw column names: fk_enrich replaces FK *values* with
    display names and never renames keys, so strip sets match record keys
    exactly.

    Attributes:
        fields: Stripped from EVERY table (the cross-table base set —
            e.g. internal sync blobs that recur on all tables).
        table_fields: Per-table extras, keyed by table name.
    """

    fields: frozenset[str] = frozenset()
    table_fields: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def fields_for(self, table: str) -> frozenset[str]:
        """Effective strip set for a table: global ∪ per-table."""
        return self.fields | self.table_fields.get(table, frozenset())


@dataclass(frozen=True)
class GradeRegistry:
    """
    A domain's validated grade → StripSet mapping.

    Built per-use from a ``DomainContext`` (never stored globally — the
    assembly chain is state-free, E2/E5); ``register_domain()`` builds one at
    registration purely as the validation gate.
    """

    grades: Mapping[str, StripSet]

    @classmethod
    def from_context(cls, ctx: DomainContext) -> GradeRegistry:
        """
        Build and validate the registry from ``ctx.get_audience_grades()``.

        Validation (seam contract §3, mechanically enforced):
        1. Both well-known grades present — no silent default-merge for an
           overridden declaration.
        2. ``external ⊇ reply`` per table: a globally-stripped reply field
           must be globally stripped by external (per-table entries cannot
           cover tables that don't exist yet); a per-table reply field may be
           covered by external's global set.

        Raises:
            GradeRegistryError: naming the domain, grade, table, and exact
                offending fields.
        """
        declared = ctx.get_audience_grades()

        missing = WELL_KNOWN_GRADES - declared.keys()
        if missing:
            raise GradeRegistryError(
                f"Domain '{ctx.name}': get_audience_grades() must declare the "
                f"well-known grade(s) {sorted(missing)}. Core ships no silent "
                f"default for an overridden declaration — declare each with an "
                f"empty StripSet() if it strips nothing."
            )

        reply = declared[GRADE_REPLY]
        external = declared[GRADE_EXTERNAL]

        uncovered_global = reply.fields - external.fields
        if uncovered_global:
            raise GradeRegistryError(
                f"Domain '{ctx.name}': grade '{GRADE_EXTERNAL}' must strip at "
                f"least everything '{GRADE_REPLY}' strips (external ⊇ reply, "
                f"seam contract §3). Globally-stripped reply fields not "
                f"globally stripped by external: {sorted(uncovered_global)}."
            )

        for table, table_strip in reply.table_fields.items():
            uncovered = table_strip - external.fields_for(table)
            if uncovered:
                raise GradeRegistryError(
                    f"Domain '{ctx.name}': external ⊇ reply violated for table "
                    f"'{table}': reply strips {sorted(uncovered)} but external "
                    f"does not."
                )

        return cls(grades=dict(declared))

    def strip(
        self, records: Sequence[Mapping[str, Any]], table: str, grade: str
    ) -> list[dict[str, Any]]:
        """
        Apply a grade's strip set to records — the strip(grade) link of the
        assembly chain (seam contract §1).

        Pure: returns new dicts; input records are never mutated. An empty
        strip set returns key-identical copies (grade "reply"'s default —
        Compatibility Guardrail #3).

        Raises:
            UnknownGradeError: for a grade not in the registry — never
                silently returns unstripped data.
        """
        strip_set = self.grades.get(grade)
        if strip_set is None:
            raise UnknownGradeError(
                f"Unknown grade '{grade}'. Registered grades: {sorted(self.grades)}."
            )
        drop = strip_set.fields_for(table)
        return [{k: v for k, v in record.items() if k not in drop} for record in records]
