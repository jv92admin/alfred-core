"""
DomainContext Protocol — the substrate half of the domain configuration split.

DomainContext holds domain knowledge + data shaping: everything a shape can
consume with no LLM machinery, no pipeline, no session. The bucket test for
membership (program roadmap A1, Compatibility Guardrail #4): "is it
knowledge/shaping with no LLM?" — audited against all five shapes (S1–S5),
never against a single consumer's read path.

Import discipline: this module (and everything it imports) must never import
langgraph, instructor, or any alfred.graph / alfred.llm module. The guarantee
is enforced by tests/core/test_import_isolation.py (seam contract §6 item 4).

Amendments of record (deliberate departures from CORE_RESTRUCTURE.md's bucket
table, argued in roadmap/active/0611-protocol-split/RESEARCH.md):
- CRUDMiddleware — including ``pre_write`` — lives here, not in AgentConfig:
  bounded writes (S4) have no pipeline and middleware must still fire on them
  (0610-mode-language.md §5.1, expectation E1).
- ``infer_entity_type_from_artifact``, ``compute_artifact_label``, and
  ``get_payload_compilers`` live here: artifact→type/label inference and
  payload compilation (substrate capability C-10) are structural knowledge
  needed by non-pipeline shapes that write generated artifacts.

The composed ``DomainConfig`` (alfred.domain.base) inherits this class;
existing domain implementations are unaffected.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from alfred.domain.grades import GRADE_EXTERNAL, GRADE_REPLY, StripSet

if TYPE_CHECKING:
    from alfred.db.adapter import DatabaseAdapter


@dataclass
class EntityDefinition:
    """
    Configuration for a single entity type.

    Each entity type in a domain (e.g., recipe, inventory item, player)
    is described by an EntityDefinition.

    Attributes:
        type_name: Short identifier used in refs (e.g., "recipe", "inv", "player")
        table: Database table name (e.g., "recipes", "inventory", "players")
        primary_field: Field used for display labels (e.g., "name", "title")
        fk_fields: Foreign key columns that reference other entities
        complexity: Think node complexity hint ("high", "medium", None)
        label_fields: Fields used to compute entity labels (e.g., ["name"] or ["date", "meal_type"])
        nested_relations: Related tables to include in reads (e.g., ["recipe_ingredients"])
        detail_tracking: Whether to track summary vs full reads (V7 pattern)
    """

    type_name: str
    table: str
    primary_field: str = "name"
    fk_fields: list[str] = field(default_factory=list)
    complexity: str | None = None
    label_fields: list[str] = field(default_factory=lambda: ["name"])
    nested_relations: list[str] | None = None
    detail_tracking: bool = False


@dataclass
class SubdomainDefinition:
    """
    Logical grouping of related tables.

    Subdomains help the Think node understand how to route requests
    and which tables to consider together.

    Attributes:
        name: Subdomain identifier (e.g., "recipes", "inventory", "transfers")
        primary_table: The main table for this subdomain
        related_tables: Other tables that belong to this subdomain
        description: Human-readable description for Think prompt guidance
    """

    name: str
    primary_table: str
    related_tables: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ReadPreprocessResult:
    """
    Result of CRUDMiddleware.pre_read() processing.

    Encapsulates all modifications the middleware wants applied to a read query.

    Attributes:
        params: Modified DbReadParams (filters may have been rewritten)
        select_additions: Extra clauses to append to SELECT (e.g., nested relations)
        pre_filter_ids: IDs to filter results by (e.g., from semantic search)
        or_conditions: Additional Supabase-format OR condition strings
        short_circuit_empty: If True, return [] without querying the database
    """

    params: Any  # DbReadParams — Any to avoid circular import
    select_additions: list[str] = field(default_factory=list)
    pre_filter_ids: list[str] | None = None
    or_conditions: list[str] | None = None
    short_circuit_empty: bool = False


class CRUDMiddleware:
    """
    Base class for domain-specific CRUD middleware.

    The middleware pattern separates domain intelligence (semantic search,
    ingredient lookup, auto-includes) from the generic CRUD executor.
    Core CRUD handles query building, filter application, and ref translation.
    The middleware transforms params before execution and records before writes.

    Override methods in domain-specific subclasses. Default implementations
    are pass-throughs (no modification).

    Note: ``pre_write`` lives on the DomainContext side of the protocol split
    by amendment of record — middleware firing is a core guarantee on every
    adapter path, including pipeline-less bounded writes (E1/S4).
    """

    async def pre_read(self, params: Any, user_id: str) -> ReadPreprocessResult:
        """
        Pre-process a read operation.

        Can modify params (rewrite filters, remove processed filters),
        add select clause additions, provide pre-filter IDs, or
        short-circuit with empty results.

        Args:
            params: DbReadParams instance
            user_id: Current user's ID

        Returns:
            ReadPreprocessResult with modifications to apply
        """
        return ReadPreprocessResult(params=params)

    async def pre_write(self, table: str, records: list[dict]) -> list[dict]:
        """
        Pre-process records before a write (create) operation.

        Can enrich records (e.g., add ingredient IDs) or validate them.

        Args:
            table: Target table name
            records: Records to be inserted

        Returns:
            Modified records list
        """
        return records

    async def post_read(self, records: list[dict], table: str, user_id: str) -> list[dict]:
        """
        Post-process records after a read operation.

        Can enrich records (e.g., translate integer FK IDs to names),
        filter results, or augment with computed fields.

        Args:
            records: Rows returned from the database query
            table: The table that was read
            user_id: Current user's ID

        Returns:
            Modified records list (may be same list or new)
        """
        return records

    def deduplicate_batch(self, table: str, records: list[dict]) -> list[dict]:
        """
        Remove duplicate records from a batch insert.

        Args:
            table: Target table name
            records: Records to deduplicate

        Returns:
            Deduplicated records list
        """
        return records


class DomainContext(ABC):
    """
    The substrate half of a domain configuration: knowledge + shaping, no LLM.

    A DomainContext provides everything needed to read, scope, enrich, label,
    redact, and format domain data — without any pipeline, prompt, persona,
    mode, or conversation concept. Non-pipeline consumers (MCP serving,
    one-shot modes, bounded writes, session preloads) depend on this half only.

    The pipeline half lives in AgentConfig (alfred.domain.agent); the composed
    DomainConfig (alfred.domain.base) is what full pipeline domains implement.
    """

    # =========================================================================
    # Core Properties
    # =========================================================================

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain name (e.g., 'kitchen', 'fpl')."""
        ...

    @property
    @abstractmethod
    def entities(self) -> dict[str, EntityDefinition]:
        """
        Entity definitions keyed by table name.

        Returns:
            Dict mapping table name to EntityDefinition
        """
        ...

    @property
    @abstractmethod
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        """
        Subdomain definitions keyed by subdomain name.

        Returns:
            Dict mapping subdomain name to SubdomainDefinition
        """
        ...

    # =========================================================================
    # Computed Lookups (auto-derived from entities)
    # =========================================================================

    @property
    def table_to_type(self) -> dict[str, str]:
        """
        Map table names to entity type names.

        Returns:
            Dict like {"recipes": "recipe", "inventory": "inv"}
        """
        return {e.table: e.type_name for e in self.entities.values()}

    @property
    def type_to_table(self) -> dict[str, str]:
        """
        Map entity type names to table names.

        Returns:
            Dict like {"recipe": "recipes", "inv": "inventory"}
        """
        return {e.type_name: e.table for e in self.entities.values()}

    # =========================================================================
    # Table Formatting Knowledge
    # =========================================================================

    @abstractmethod
    def get_table_format(self, table: str) -> dict[str, Any]:
        """
        Get formatting rules for a table.

        Used by the injection system to format table data for prompts.

        Args:
            table: The table name

        Returns:
            Dict with formatting configuration
        """
        ...

    # =========================================================================
    # Schema/FK Resolution
    # =========================================================================

    def get_fk_field_aliases(self) -> dict[str, str]:
        """
        Map non-standard FK field names to their standard equivalents.

        Standard pattern: {table_singular}_id -> look up {table_plural} entity.
        Aliases handle exceptions (e.g., parent_recipe_id -> recipe_id).

        Returns:
            Dict mapping non-standard FK field to standard equivalent.
        """
        return {}

    @abstractmethod
    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        """
        Get FK field enrichment mapping.

        Used by SessionIdRegistry for lazy FK enrichment.

        Returns:
            Dict mapping FK field name to (target_table, name_column)
            e.g., {"ingredient_id": ("ingredients", "name")}
        """
        ...

    @abstractmethod
    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        """
        Get categorical field values per subdomain.

        Used in Act prompts to show valid enum values.

        Returns:
            Dict like {"inventory": {"unit": ["kg", "g", "ml", ...]}}
        """
        ...

    @abstractmethod
    def get_semantic_notes(self) -> dict[str, str]:
        """
        Get subdomain-specific clarifications for the LLM.

        Returns:
            Dict mapping subdomain to semantic notes
        """
        ...

    @abstractmethod
    def get_fallback_schemas(self) -> dict[str, str]:
        """
        Get hardcoded schema fallbacks per subdomain.

        Used when database introspection fails. Keyed by **subdomain name**
        (not table name). Core does ``fallback_schemas.get(subdomain, schema)``
        — if keys don't match subdomain names, the fallback is silently ignored
        and Act prompts show "Schema unavailable".

        Include all tables for each subdomain in one string value.

        Returns:
            Dict mapping subdomain name to schema text
        """
        ...

    def get_scope_config(self) -> dict[str, dict]:
        """
        Get cross-subdomain relationship configuration.

        Defines which subdomains can access data from other subdomains.

        Returns:
            Dict with scope configuration
        """
        return {}

    # =========================================================================
    # CRUD Configuration
    # =========================================================================

    def get_crud_middleware(self) -> CRUDMiddleware | None:
        """
        Get domain-specific CRUD middleware.

        The middleware provides pre_read/pre_write hooks for domain-specific
        query intelligence (semantic search, auto-includes, ingredient lookup, etc.).

        Called once per CRUD operation by the executor (tools/crud.py).
        Core does NOT cache the returned instance between CRUD calls.

        - Stateless middleware: return a new instance each call (Kitchen pattern)
        - Stateful middleware: cache the instance as a class attribute and return
          the same object every call (FPL pattern — bridge dicts persist across calls)

        Returns:
            CRUDMiddleware instance, or None for raw CRUD without middleware
        """
        return None  # Default: no middleware

    @abstractmethod
    def get_user_owned_tables(self) -> set[str]:
        """
        Get tables that require user_id scoping.

        These tables have a user_id column and CRUD operations automatically
        filter/inject user_id for security.

        Returns:
            Set of table names (e.g., {"inventory", "recipes", "meal_plans"})
        """
        ...

    @abstractmethod
    def get_uuid_fields(self) -> set[str]:
        """
        Get FK field names that contain UUIDs.

        Used for sanitization (empty string → None) before database operations.
        LLMs sometimes output "" instead of null for optional FK fields.

        Returns:
            Set of field names (e.g., {"recipe_id", "ingredient_id", "meal_plan_id"})
        """
        ...

    @abstractmethod
    def get_subdomain_registry(self) -> dict[str, dict]:
        """
        Get subdomain-to-tables mapping for schema introspection.

        Returns:
            Dict mapping subdomain name to config dict with "tables" key
            e.g., {"recipes": {"tables": ["recipes", "recipe_ingredients"]}}
        """
        ...

    # =========================================================================
    # Entity Processing
    # =========================================================================

    @abstractmethod
    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        """
        Infer entity type from an artifact's structure.

        Used when the entity type isn't explicitly provided.

        Args:
            artifact: The artifact dict to analyze

        Returns:
            Entity type name (e.g., "recipe", "inv")
        """
        ...

    @abstractmethod
    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        """
        Compute a human-readable label for an entity.

        Args:
            record: The entity record from database
            entity_type: The entity type (e.g., "recipe", "meal")
            ref: The entity reference (e.g., "recipe_1")

        Returns:
            Human-readable label (e.g., "Chicken Tikka Masala")
        """
        ...

    def compute_entity_label_from_fks(
        self, entity_type: str, fk_labels: dict[str, str], ref: str
    ) -> str:
        """
        Build a label from resolved FK labels (post-translation fallback).

        Called when the primary label computation returned the ref (no label).
        Receives a dict mapping FK field names to their resolved labels
        (e.g., {"home_team_id": "ARS", "away_team_id": "BUR"}).

        Override for entities whose identity is defined by their FKs
        (e.g., fixtures: "ARS v BUR").

        Default: returns ref (no change).
        """
        return ref

    def get_entity_data_legend(self, entity_type: str) -> str | None:
        """
        Get explanatory legend for entity-specific data tracking.

        Used for entities with detail_tracking=True (e.g., recipes with
        summary vs full read levels).

        Args:
            entity_type: The entity type name (e.g., "recipe")

        Returns:
            Legend text explaining data tracking markers, or None
        """
        return None  # Default: no special legend

    def detect_detail_level(self, entity_type: str, record: dict) -> str | None:
        """
        Detect the detail level of a read record.

        For entities with detail_tracking=True, determines whether
        the returned record is "summary" or "full" based on which
        fields are present.

        Args:
            entity_type: The entity type name
            record: The database record

        Returns:
            "summary", "full", or None if not applicable
        """
        return None  # Default: no detail tracking

    def compute_artifact_label(self, artifact: dict, entity_type: str, index: int) -> str:
        """
        Extract a human-readable label from a generated artifact.

        Args:
            artifact: The generated artifact dict
            entity_type: Inferred entity type
            index: Index in the artifacts list

        Returns:
            Human-readable label
        """
        # Default: use name/title or fallback
        if artifact.get("name"):
            return artifact["name"]
        if artifact.get("title"):
            return artifact["title"]
        return f"item_{index + 1}"

    @abstractmethod
    def get_subdomain_aliases(self) -> dict[str, str]:
        """
        Get natural language aliases for subdomain normalization.

        Maps informal/approximate names to canonical subdomain names.

        Returns:
            Dict like {"pantry": "inventory", "groceries": "shopping"}
        """
        ...

    def get_entity_key_fields(self) -> list[str]:
        """
        Get key fields to display in generic entity context cards.

        These are the most useful fields to show inline when displaying
        entity data that doesn't have a custom formatter.

        Returns:
            List of field names
        """
        return []  # Default: no key fields

    # =========================================================================
    # Data Shaping (LLM-bound / external-bound)
    # =========================================================================

    def get_strip_fields(self, context: str = "injection") -> set[str]:
        """
        Get fields to strip from USER-BOUND reply rendering.

        Governs the user-facing path only: consumed by the reply renderer
        (graph/nodes/reply.py) when formatting records into the reply a human
        reads. It does NOT participate in LLM-bound / external-bound context
        assembly — that path is governed by ``get_audience_grades()``.

        Do not bridge the two: wiring this method's "reply" context into the
        assembly chain's "reply" grade would change what the LLM sees today
        (Compatibility Guardrail #3; 0611-grade-registry RESEARCH Finding 2).

        Args:
            context: "injection" or "reply" ("reply" is the only context core
                consumes today)

        Returns:
            Set of field names to strip
        """
        return set()  # Default: strip nothing

    def get_audience_grades(self) -> dict[str, StripSet]:
        """
        Declare named redaction grades for LLM-BOUND / EXTERNAL-BOUND assembly.

        Governs the context-assembly path (substrate capability C-6, seam
        contract §3): the assembly chain strips at the requested grade before
        formatting (post_read → fk_enrich → strip(grade) → format → header).
        Core validates the declaration at ``register_domain()`` — both
        well-known grades (GRADE_REPLY, GRADE_EXTERNAL) must be present and
        ``external ⊇ reply`` must hold (GradeRegistryError otherwise).

        Grades are pure field removal; transform dispositions (cents→dollars)
        remain post_read middleware, grade-independent.

        Distinct from ``get_strip_fields()``, which governs USER-BOUND reply
        rendering only — do not bridge the two (0611-grade-registry RESEARCH
        Finding 2). The default below strips nothing, reproducing today's
        assembly output byte-for-byte (Compatibility Guardrail #3).

        Returns:
            Dict mapping grade name → StripSet. Default: the well-known
            grades with empty strip sets — exactly today's behavior.
        """
        return {GRADE_REPLY: StripSet(), GRADE_EXTERNAL: StripSet()}

    def get_table_notes(self, table: str) -> str:
        """
        Per-table interpretation hint for assembled payloads (A3 / seam §2).

        Becomes ``ShapedPayload.header`` in the state-free assembly chain
        (alfred.context.assembly) — "shaped data + how to read it in one
        response". Override to declare table-level notes; external-serving
        domains declare their per-table slivers here (ledge Phase 1), not in
        ``get_semantic_notes()``.

        Default: the owning subdomain's semantic notes — the subdomain whose
        ``primary_table`` is ``table`` wins; otherwise the first subdomain
        listing it in ``related_tables``; ``""`` when no subdomain owns it.

        Args:
            table: The table name.

        Returns:
            Interpretation hint text, or "" when none is declared.
        """
        owner: str | None = None
        for sub in self.subdomains.values():
            if sub.primary_table == table:
                owner = sub.name
                break
            if owner is None and table in sub.related_tables:
                owner = sub.name
        if owner is None:
            return ""
        return self.get_semantic_notes().get(owner, "")

    def format_entity_for_context(
        self, entity_type: str, ref: str, label: str, data: dict, **kwargs: Any
    ) -> list[str]:
        """
        Format an entity's data for inclusion in Act context.

        Domain-specific formatting (e.g., recipe data with grouped ingredients).
        Returns markdown lines.

        Args:
            entity_type: The entity type (e.g., "recipe", "meal")
            ref: Entity reference (e.g., "recipe_1")
            label: Human-readable label
            data: The entity data dict
            **kwargs: Additional context (e.g., registry for ref lookup)

        Returns:
            List of formatted markdown lines
        """
        # Default: simple key-value dump
        lines = [f"### `{ref}`: {label} ({entity_type})"]
        for k, v in data.items():
            if v is not None:
                lines.append(f"  {k}: {v}")
        return lines

    def infer_table_from_record(self, record: dict) -> str | None:
        """
        Infer the table name from a record's field structure.

        Used when the table isn't known but the record contents
        can identify which entity it belongs to.

        Args:
            record: A database record dict

        Returns:
            Table name or None if unrecognizable
        """
        return None  # Default: can't infer

    def format_record_for_context(self, record: dict, table: str | None = None) -> str:
        """
        Format a single record for Act prompt context.

        Override for domain-specific rendering (e.g., table-aware formatting
        with quantity, location, cuisine fields).

        Args:
            record: A database record dict
            table: Optional table name for format lookup

        Returns:
            Formatted string (e.g., "  - Chicken Thighs (2 lbs) [fridge] id:inv_5")
        """
        if not record:
            return "  (empty)"
        name = record.get("name") or record.get("title") or "item"
        parts = [f"  - {name}"]
        if record.get("id"):
            parts.append(f"id:{record['id']}")
        return " ".join(parts)

    def format_records_for_context(
        self, records: list[dict], table: str | None = None
    ) -> list[str]:
        """
        Format a list of records for Act prompt context.

        Override for domain-specific grouping (e.g., recipe_ingredients
        grouped by recipe_id).

        Args:
            records: List of record dicts
            table: Optional table name for format lookup

        Returns:
            List of formatted strings, one per record or group
        """
        if not records:
            return ["  (no records)"]
        return [self.format_record_for_context(r, table) for r in records]

    # =========================================================================
    # Write-Side Shaping (substrate capability C-10)
    # =========================================================================

    def get_payload_compilers(self) -> list:
        """
        Get domain-specific payload compilers.

        Returns SubdomainCompiler instances that map generated artifacts
        to schema-ready payloads for database writes.

        Returns:
            List of SubdomainCompiler instances
        """
        return []  # Default: no compilers

    # --- User Context (profile, dashboard, guidance) ---

    async def get_user_profile(self, user_id: str) -> str:
        """
        Return formatted user profile text for prompt injection.

        Includes hard constraints (diet, allergies, household), capabilities,
        taste preferences, and recent activity. Used by Think and Act nodes.

        Returns:
            Markdown-formatted profile string, or empty string if unavailable.
        """
        return ""

    async def get_domain_snapshot(self, user_id: str) -> str:
        """
        Return formatted domain-state summary for Think node context.

        Provides a snapshot of the user's current domain state (e.g., inventory
        counts, saved items, upcoming plans). Used by Think node for planning.

        Returns:
            Markdown-formatted snapshot string, or empty string if unavailable.
        """
        return ""

    async def get_subdomain_guidance(self, user_id: str) -> dict[str, str]:
        """
        Return per-subdomain user preference/guidance text.

        Used by Think (all subdomains) and Act (specific subdomain) nodes
        to inject user preferences into prompts.

        Returns:
            Dict mapping subdomain name to guidance text.
        """
        return {}

    # --- Database Access ---

    @abstractmethod
    def get_db_adapter(self) -> DatabaseAdapter:
        """
        Return a database adapter for CRUD operations.

        Called per-request by the CRUD executor. The returned adapter
        must support .table() and .rpc() methods. For Supabase domains,
        this wraps get_client() which handles auth token from request context.

        Returns:
            A DatabaseAdapter-compatible object.
        """
        ...
