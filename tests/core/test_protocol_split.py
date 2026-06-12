"""
Protocol-split conformance (program roadmap A1 / substrate C-1).

Freezes the DomainContext/AgentConfig bucket sort decided in
roadmap/active/0611-protocol-split/RESEARCH.md so it cannot drift silently,
and proves the composed DomainConfig is unchanged for existing implementers
(zero-migration / additive release posture).
"""

from alfred.context import DomainContext as DomainContextFromSeam
from alfred.domain import get_current_domain
from alfred.domain.agent import AgentConfig
from alfred.domain.base import (
    CRUDMiddleware,
    DomainConfig,
    EntityDefinition,
    SubdomainDefinition,
)
from alfred.domain.context import DomainContext

# ---------------------------------------------------------------------------
# The bucket sort of record (RESEARCH.md). A member added to the wrong half —
# or to DomainConfig directly — fails these tests with the stray names listed.
# ---------------------------------------------------------------------------

CONTEXT_MEMBERS = {
    # Core properties + computed lookups
    "name",
    "entities",
    "subdomains",
    "table_to_type",
    "type_to_table",
    # Table formatting knowledge
    "get_table_format",
    # Schema/FK resolution
    "get_fk_field_aliases",
    "get_fk_enrich_map",
    "get_field_enums",
    "get_semantic_notes",
    "get_fallback_schemas",
    "get_scope_config",
    # CRUD configuration
    "get_crud_middleware",
    "get_user_owned_tables",
    "get_uuid_fields",
    "get_subdomain_registry",
    # Entity processing
    "infer_entity_type_from_artifact",
    "compute_entity_label",
    "compute_entity_label_from_fks",
    "get_entity_data_legend",
    "detect_detail_level",
    "compute_artifact_label",
    "get_subdomain_aliases",
    "get_entity_key_fields",
    # Data shaping (LLM-bound / external-bound)
    "get_strip_fields",
    # A2 (0611-grade-registry): audience-grade declaration — the deliberate
    # 34→35 member addition this freeze exists to force into the open.
    # Defaulted (well-known grades, empty strip sets), so ABSTRACT_MEMBERS
    # is unchanged — zero migration for existing domains.
    "get_audience_grades",
    # A3 (0612-assembly-entrypoints): per-table header for ShapedPayload —
    # the deliberate 35→36 addition (P4). Defaulted (owning subdomain's
    # semantic notes), so ABSTRACT_MEMBERS is unchanged — zero migration.
    "get_table_notes",
    "format_entity_for_context",
    "infer_table_from_record",
    "format_record_for_context",
    "format_records_for_context",
    # Write-side shaping (C-10)
    "get_payload_compilers",
    # User context
    "get_user_profile",
    "get_domain_snapshot",
    "get_subdomain_guidance",
    # Database
    "get_db_adapter",
}

AGENT_MEMBERS = {
    # Prompt/persona
    "get_persona",
    "get_examples",
    "get_act_subdomain_header",
    "get_empty_response",
    # Entity context configuration (turn-based)
    "get_entity_recency_window",
    # Act prompt configuration
    "get_tool_enabled_step_types",
    "get_custom_tools",
    "get_crud_reference",
    "get_act_step_template",
    # LLM observability
    "get_prompt_log_adapter",
    "get_subdomain_examples",
    # Pipeline archive / conversation tracking
    "get_archive_key_for_description",
    "get_archive_keys_for_subdomain",
    "get_bold_skip_words",
    "get_generated_content_markers",
    "get_generated_content_label",
    "get_relevant_entity_types",
    "get_tracked_entity_types",
    "get_item_tracking_keys",
    # Reply rendering (user-bound)
    "get_subdomain_formatters",
    "get_system_prompt",
    "get_quick_write_confirmation",
    "get_priority_fields",
    "format_records_for_reply",
    # Mode/agent registration
    "bypass_modes",
    "default_agent",
    "agents",
    "agent_router",
    "get_mode_llm_config",
    "get_reply_prompt_content",
    "get_act_prompt_content",
    "get_act_prompt_injection",
    "get_think_prompt_content",
    "get_understand_prompt_content",
    "get_understand_system_prompt",
    "get_filter_schema",
    "get_summarize_system_prompts",
    "get_think_domain_context",
    "get_think_planning_guide",
    "get_reply_continuity_guidance",
    "get_reply_subdomain_guide",
    "get_router_prompt_injection",
    "get_handoff_system_prompts",
    "get_handoff_result_model",
}

# AgentConfig re-declares these structural members (its defaults derive from
# them); the declarations merge with DomainContext's in DomainConfig's MRO.
AGENT_REDECLARED = {"name", "entities"}

# The composed abstract surface — frozen. Changing it is a compatibility
# decision that requires a deliberate release call, not a side effect.
ABSTRACT_MEMBERS = {
    "name",
    "entities",
    "subdomains",
    "get_persona",
    "get_examples",
    "get_table_format",
    "get_empty_response",
    "get_fk_enrich_map",
    "get_field_enums",
    "get_semantic_notes",
    "get_fallback_schemas",
    "get_user_owned_tables",
    "get_uuid_fields",
    "get_subdomain_registry",
    "get_subdomain_examples",
    "infer_entity_type_from_artifact",
    "compute_entity_label",
    "get_subdomain_aliases",
    "get_subdomain_formatters",
    "bypass_modes",
    "default_agent",
    "get_handoff_result_model",
    "get_db_adapter",
}


def _public_members(cls: type) -> set[str]:
    """Public methods/properties defined directly on a class."""
    return {
        n
        for n, v in vars(cls).items()
        if not n.startswith("_") and (callable(v) or isinstance(v, property))
    }


# ---------------------------------------------------------------------------
# Sort-freeze
# ---------------------------------------------------------------------------


def test_domain_context_defines_exactly_the_context_bucket():
    actual = _public_members(DomainContext)
    assert actual == CONTEXT_MEMBERS, (
        f"DomainContext drifted from the sort of record.\n"
        f"Unexpected: {sorted(actual - CONTEXT_MEMBERS)}\n"
        f"Missing: {sorted(CONTEXT_MEMBERS - actual)}"
    )


def test_agent_config_defines_exactly_the_agent_bucket():
    actual = _public_members(AgentConfig)
    expected = AGENT_MEMBERS | AGENT_REDECLARED
    assert actual == expected, (
        f"AgentConfig drifted from the sort of record.\n"
        f"Unexpected: {sorted(actual - expected)}\n"
        f"Missing: {sorted(expected - actual)}"
    )


def test_buckets_are_disjoint():
    assert CONTEXT_MEMBERS & AGENT_MEMBERS == set()


def test_domain_config_defines_nothing_itself():
    """Every member lives in exactly one half; the composed class only composes."""
    assert _public_members(DomainConfig) == set(), (
        f"members defined directly on DomainConfig bypass the split: "
        f"{sorted(_public_members(DomainConfig))}"
    )


def test_member_count_matches_research():
    # A1 sort of record: 34/44 (78). A2 added get_audience_grades → 35/44 (79).
    # A3 added get_table_notes → 36/44 (80).
    assert len(CONTEXT_MEMBERS) == 36
    assert len(AGENT_MEMBERS) == 44


# ---------------------------------------------------------------------------
# Composition & zero migration
# ---------------------------------------------------------------------------


def test_domain_config_is_composed_of_both_halves():
    assert issubclass(DomainConfig, DomainContext)
    assert issubclass(DomainConfig, AgentConfig)


def test_existing_implementer_satisfies_all_three_protocols():
    """StubDomainConfig (untouched) is the zero-migration proof."""
    domain = get_current_domain()
    assert isinstance(domain, DomainConfig)
    assert isinstance(domain, DomainContext)
    assert isinstance(domain, AgentConfig)


def test_composed_abstract_set_unchanged():
    actual = set(DomainConfig.__abstractmethods__)
    assert actual == ABSTRACT_MEMBERS, (
        f"DomainConfig's abstract surface changed — this is a release-compat "
        f"decision, not a refactor side effect.\n"
        f"Added: {sorted(actual - ABSTRACT_MEMBERS)}\n"
        f"Removed: {sorted(ABSTRACT_MEMBERS - actual)}"
    )


def test_seam_import_path_is_the_same_class():
    """`from alfred.context import DomainContext` (seam) is the canonical class."""
    assert DomainContextFromSeam is DomainContext


def test_pre_write_lives_in_domain_context_module():
    """Amendment of record: middleware (incl. pre_write) is substrate-side.

    E1/S4 — bounded writes have no pipeline and pre_write must fire on them
    (0610-mode-language.md §5.1; overrides CORE_RESTRUCTURE's bucket table).
    """
    assert CRUDMiddleware.__module__ == "alfred.domain.context"
    assert "pre_write" in vars(CRUDMiddleware)


# ---------------------------------------------------------------------------
# The narrow half is independently implementable (what a substrate-only
# consumer like the ledge MCP server does)
# ---------------------------------------------------------------------------


class _ContextOnly(DomainContext):
    """Minimal DomainContext-only implementation — its 15 abstracts, no more."""

    @property
    def name(self) -> str:
        return "context-only"

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        return {"things": EntityDefinition(type_name="thing", table="things")}

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        return {"things": SubdomainDefinition(name="things", primary_table="things")}

    def get_table_format(self, table: str) -> dict:
        return {}

    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        return {}

    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        return {}

    def get_semantic_notes(self) -> dict[str, str]:
        return {}

    def get_fallback_schemas(self) -> dict[str, str]:
        return {"things": "CREATE TABLE things (id uuid, name text);"}

    def get_user_owned_tables(self) -> set[str]:
        return {"things"}

    def get_uuid_fields(self) -> set[str]:
        return set()

    def get_subdomain_registry(self) -> dict[str, dict]:
        return {"things": {"tables": ["things"]}}

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        return "thing"

    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        return str(record.get("name", ref))

    def get_subdomain_aliases(self) -> dict[str, str]:
        return {}

    def get_db_adapter(self):
        raise NotImplementedError("no database in this test")


def test_domain_context_alone_is_implementable():
    """A DomainContext-only implementer instantiates without any AgentConfig member."""
    ctx = _ContextOnly()
    assert isinstance(ctx, DomainContext)
    assert not isinstance(ctx, DomainConfig)
    # Shaping defaults inherited and functional with zero pipeline machinery:
    assert ctx.table_to_type == {"things": "thing"}
    assert ctx.format_record_for_context({"name": "Widget", "id": "thing_1"}) == (
        "  - Widget id:thing_1"
    )
