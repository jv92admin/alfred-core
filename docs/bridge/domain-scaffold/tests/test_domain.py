"""Smoke tests — verify domain is wired correctly.

Tests are organized in two groups:
  1. Basic wiring (domain registered, entities/subdomains defined)
  2. Contract enforcement (catches implicit contract violations from Section 11
     of the domain implementation guide — the ones that fail silently at runtime)
"""

from alfred.domain import get_current_domain


# ---------------------------------------------------------------------------
# Basic wiring
# ---------------------------------------------------------------------------

def test_domain_registered():
    """Domain registration worked."""
    domain = get_current_domain()
    assert domain.name == "DOMAIN"  # TODO: your domain name


def test_entities_defined():
    """At least one entity exists."""
    domain = get_current_domain()
    assert len(domain.entities) > 0


def test_subdomains_defined():
    """At least one subdomain exists."""
    domain = get_current_domain()
    assert len(domain.subdomains) > 0


def test_subdomain_registry_matches():
    """Every subdomain has a registry entry with tables."""
    domain = get_current_domain()
    registry = domain.get_subdomain_registry()
    for name in domain.subdomains:
        assert name in registry, f"Subdomain '{name}' missing from registry"
        assert "tables" in registry[name]
        assert len(registry[name]["tables"]) > 0


def test_personas_not_empty():
    """Every subdomain has a non-empty persona."""
    domain = get_current_domain()
    for name in domain.subdomains:
        persona = domain.get_persona(name, "read")
        assert persona, f"Subdomain '{name}' has empty persona"


def test_empty_responses_not_generic():
    """Every subdomain has a specific empty response."""
    domain = get_current_domain()
    for name in domain.subdomains:
        msg = domain.get_empty_response(name)
        assert msg != "No data found.", f"Subdomain '{name}' using generic empty response"


# ---------------------------------------------------------------------------
# Contract enforcement — implicit contracts from core
# ---------------------------------------------------------------------------

def test_fk_enrich_map_targets_exist():
    """FK enrichment targets exist as entity tables."""
    domain = get_current_domain()
    fk_map = domain.get_fk_enrich_map()
    known_tables = {e.table for e in domain.entities.values()}
    for fk_field, (target_table, _) in fk_map.items():
        assert target_table in known_tables, (
            f"FK '{fk_field}' targets '{target_table}' which is not a known entity table"
        )


def test_fk_enrich_map_no_integer_fks():
    """FK enrichment map must only contain UUID FK fields.

    Core does WHERE id IN (values) on a UUID column. Integer FKs cause
    silent failure — no error, no enrichment. Use post_read middleware
    for integer FK enrichment instead.
    """
    domain = get_current_domain()
    fk_map = domain.get_fk_enrich_map()
    uuid_fields = domain.get_uuid_fields()
    for fk_field in fk_map:
        assert fk_field in uuid_fields, (
            f"FK '{fk_field}' is in get_fk_enrich_map() but NOT in get_uuid_fields(). "
            f"If this is an integer FK, it will silently fail. Move it to post_read middleware."
        )


def test_field_enum_values_are_strings():
    """All field enum values must be strings (core does ', '.join).

    Integer or boolean values cause TypeError at runtime.
    """
    domain = get_current_domain()
    for subdomain, fields in domain.get_field_enums().items():
        for field_name, values in fields.items():
            for v in values:
                assert isinstance(v, str), (
                    f"Enum value {v!r} for {subdomain}.{field_name} is not a string. "
                    f"Use \"{v}\" instead."
                )


def test_subdomain_examples_are_strings():
    """Subdomain examples must be strings, not lists.

    Core does parts.append(examples) where examples is a single string.
    A list here causes the prompt to contain "['example1', 'example2']".
    """
    domain = get_current_domain()
    for subdomain, examples in domain.get_subdomain_examples().items():
        assert isinstance(examples, str), (
            f"Subdomain example for '{subdomain}' is {type(examples).__name__}, not str. "
            f"Join your examples into a single string."
        )


def test_semantic_notes_keyed_by_subdomain():
    """Semantic notes must be keyed by subdomain name.

    Core does .get(subdomain, "") — direct lookup. Notes keyed by topic
    (e.g., "budget_rules") will never be found.
    """
    domain = get_current_domain()
    notes = domain.get_semantic_notes()
    valid_subdomains = set(domain.subdomains.keys())
    for key in notes:
        assert key in valid_subdomains, (
            f"Semantic note key '{key}' is not a subdomain name. "
            f"Valid subdomains: {valid_subdomains}"
        )


def test_type_name_matches_table_depluralization():
    """type_name must match table.rstrip("s") for core's fallback mapping.

    Core's table_to_type fallback strips trailing "s": "players" → "player".
    If your table has an irregular plural (e.g., "analyses"), the fallback
    produces the wrong type and refs break.
    """
    domain = get_current_domain()
    for table_name, entity_def in domain.entities.items():
        expected = entity_def.table.rstrip("s")
        if entity_def.type_name != expected:
            # Not necessarily wrong — but the domain must be aware.
            # Check that table_to_type actually resolves correctly.
            actual = domain.table_to_type.get(entity_def.table)
            assert actual == entity_def.type_name, (
                f"Entity '{table_name}': type_name='{entity_def.type_name}' but "
                f"table '{entity_def.table}'.rstrip('s') = '{expected}'. "
                f"Core's table_to_type resolved to '{actual}'. "
                f"If this is an irregular plural, verify table_to_type mapping."
            )


def test_label_fields_in_fallback_schemas():
    """label_fields must appear in fallback schemas (if schemas are provided).

    If middleware returns a column subset that doesn't include label_fields,
    entity labels silently regress to bare refs. This test catches the case
    where fallback schemas don't even list the label fields.
    """
    domain = get_current_domain()
    schemas = domain.get_fallback_schemas()
    if not schemas:
        return  # No fallback schemas — using RPC instead, skip this check

    for table_name, entity_def in domain.entities.items():
        if not entity_def.label_fields:
            continue
        schema_str = schemas.get(entity_def.table, "")
        if not schema_str:
            continue  # No schema for this table
        for label_field in entity_def.label_fields:
            assert label_field in schema_str, (
                f"Entity '{table_name}': label_field '{label_field}' not found in "
                f"fallback schema for table '{entity_def.table}'. Labels will regress "
                f"to bare refs when this table is read."
            )


def test_fallback_schemas_include_id():
    """Fallback schemas must include 'id' column for every table.

    Core's translate_read_output() uses record["id"] for entity registration.
    Missing "id" causes UnboundLocalError.
    """
    domain = get_current_domain()
    schemas = domain.get_fallback_schemas()
    if not schemas:
        return  # No fallback schemas — using RPC instead

    for table, schema_str in schemas.items():
        assert "id" in schema_str, (
            f"Fallback schema for '{table}' does not mention 'id'. "
            f"Core requires an 'id' column (uuid PK) on every table."
        )


def test_middleware_singleton():
    """If middleware is defined, get_crud_middleware() must return same instance.

    Core calls get_crud_middleware() once per CRUD operation. Without caching,
    stateful middleware loses its state between calls.
    """
    domain = get_current_domain()
    mw1 = domain.get_crud_middleware()
    mw2 = domain.get_crud_middleware()
    if mw1 is None:
        return  # No middleware defined
    assert mw1 is mw2, (
        "get_crud_middleware() returns a new instance on each call. "
        "Cache the instance: store in _middleware class attribute and return it."
    )
