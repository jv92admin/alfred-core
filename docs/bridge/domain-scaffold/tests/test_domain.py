"""Smoke tests — verify domain is wired correctly."""

from alfred.domain import get_current_domain


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


def test_fk_enrich_map_valid():
    """FK enrichment targets exist as entity tables."""
    domain = get_current_domain()
    fk_map = domain.get_fk_enrich_map()
    known_tables = {e.table for e in domain.entities.values()}
    for fk_field, (target_table, _) in fk_map.items():
        assert target_table in known_tables, (
            f"FK '{fk_field}' targets '{target_table}' which is not a known entity table"
        )


def test_field_enum_values_are_strings():
    """All field enum values must be strings (core does ', '.join)."""
    domain = get_current_domain()
    for subdomain, fields in domain.get_field_enums().items():
        for field_name, values in fields.items():
            for v in values:
                assert isinstance(v, str), (
                    f"Enum value {v!r} for {subdomain}.{field_name} is not a string"
                )
