"""DomainConfig implementation.

This file implements all 23 abstract methods of DomainConfig.
Fill in the TODOs using answers from the domain questionnaire.

Questionnaire mapping:
  Q1 → name, get_system_prompt()
  Q2 → ENTITIES dict, get_fk_enrich_map(), get_uuid_fields(), get_user_owned_tables()
  Q3 → SUBDOMAINS dict, get_subdomain_registry(), get_subdomain_aliases()
  Q4 → get_persona()
  Q5 → get_examples(), get_subdomain_examples()
  Q6 → get_fallback_schemas()
  Q7 → get_semantic_notes(), get_field_enums()
  Q8 → get_empty_response()
"""

from pathlib import Path
from typing import Any, Callable

from alfred.domain.base import (
    DomainConfig,
    EntityDefinition,
    SubdomainDefinition,
)


# ---------------------------------------------------------------------------
# Entities (from Questionnaire Q2)
# ---------------------------------------------------------------------------

ENTITIES: dict[str, EntityDefinition] = {
    # TODO: one entry per table users interact with
    #
    # "things": EntityDefinition(
    #     type_name="thing",           # Ref prefix: thing_1, thing_2
    #     table="things",              # Database table name
    #     primary_field="name",        # Display field for labels
    #     fk_fields=["other_id"],      # FK columns (omit if none)
    #     complexity="high",           # "high" | "medium" | None
    #     label_fields=["name"],       # Fields for compute_entity_label()
    #     detail_tracking=True,        # Track summary vs full reads
    #     nested_relations=["child_table"],  # Auto-include in reads (omit if none)
    # ),
}


# ---------------------------------------------------------------------------
# Subdomains (from Questionnaire Q3)
# ---------------------------------------------------------------------------

SUBDOMAINS: dict[str, SubdomainDefinition] = {
    # TODO: one entry per user-facing activity (3-7 groups)
    #
    # "activity": SubdomainDefinition(
    #     name="activity",
    #     primary_table="main_table",
    #     related_tables=["other_table_1", "other_table_2"],
    #     description="What users do here. Example phrases: 'show my X', 'add Y'.",
    # ),
}


# ---------------------------------------------------------------------------
# DomainConfig
# ---------------------------------------------------------------------------

class DomainDomainConfig(DomainConfig):  # TODO: rename (e.g., FitnessConfig)

    # === Core Properties (3 abstract) ===

    @property
    def name(self) -> str:
        return "DOMAIN"  # TODO: your domain name (1 word, lowercase)

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        return ENTITIES

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        return SUBDOMAINS

    # === Prompt / Persona (2 abstract) — from Q4, Q5 ===

    def get_persona(self, subdomain: str, step_type: str) -> str:
        # TODO: one persona per subdomain (from Questionnaire Q4)
        personas = {
            # "activity": "You are a [role]. Focus on [priorities].",
        }
        return personas.get(subdomain, "You are a helpful assistant.")

    def get_examples(self, subdomain: str, step_type: str,
                     step_description: str = "", prev_subdomain: str | None = None) -> str:
        # TODO: 2-3 examples per subdomain (from Questionnaire Q5)
        # Show exact CRUD patterns: what user says → what action to take
        return ""

    # === Schema / FK (11 abstract) — from Q2, Q6, Q7, Q8 ===

    def get_table_format(self, table: str) -> dict[str, Any]:
        return {}  # Optional: custom column formatting per table

    def get_empty_response(self, subdomain: str) -> str:
        # TODO: one message per subdomain (from Questionnaire Q8)
        return {
            # "activity": "No results found. Try ...",
        }.get(subdomain, "No data found.")

    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        # TODO: UUID FK columns only (from Questionnaire Q2)
        # WARNING: integer FKs cause silent failure — use post_read middleware instead
        return {
            # "other_id": ("others", "name"),  # FK column → (target table, display column)
        }

    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        # TODO: categorical fields (from Questionnaire Q7)
        # WARNING: all values must be strings (even numeric: "0", "1")
        return {
            # "activity": {"position": ["GKP", "DEF", "MID", "FWD"]},
        }

    def get_semantic_notes(self) -> dict[str, str]:
        # TODO: keyed by SUBDOMAIN name, not topic (from Questionnaire Q7)
        return {
            # "activity": "Business rule the LLM must know.",
        }

    def get_fallback_schemas(self) -> dict[str, str]:
        # LOAD-BEARING if your Supabase doesn't have the get_table_columns RPC.
        # Without this, Act prompts show "Schema unavailable" and the LLM guesses.
        # TODO: provide column definitions (from Questionnaire Q6)
        return {
            # "things": "id (uuid PK), user_id (uuid), name (text), created_at (timestamptz)",
        }

    def get_scope_config(self) -> dict[str, dict]:
        # Optional: which subdomains can access each other's data
        return {}

    def get_user_owned_tables(self) -> set[str]:
        # TODO: tables with user_id column, auto-scoped per user (from Q2)
        return set()

    def get_uuid_fields(self) -> set[str]:
        # TODO: FK column names that hold UUIDs (from Q2)
        return set()

    def get_subdomain_registry(self) -> dict[str, dict]:
        return {
            name: {"tables": [sd.primary_table] + sd.related_tables}
            for name, sd in SUBDOMAINS.items()
        }

    def get_subdomain_examples(self) -> dict[str, str]:
        # TODO: quick routing examples (from Questionnaire Q5)
        # Must return dict[str, str], NOT dict[str, list[str]]
        return {}

    # === Entity Processing (4 abstract) ===

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        # TODO: given a generated artifact dict, guess the entity type
        # Look for distinctive fields to identify the type
        return list(ENTITIES.keys())[0] if ENTITIES else "unknown"

    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        # TODO: return a human-readable label for the entity
        # Use primary_field from the entity definition
        entity_def = ENTITIES.get(self.type_to_table.get(entity_type, ""))
        if entity_def:
            return record.get(entity_def.primary_field) or ref
        return record.get("name") or record.get("title") or ref

    def get_subdomain_aliases(self) -> dict[str, str]:
        # TODO: informal terms → subdomain name (from Questionnaire Q3, Q10)
        return {
            # "my team": "squad",
            # "buy": "transfers",
        }

    def get_subdomain_formatters(self) -> dict[str, Callable]:
        return {}  # Optional: custom record formatting per subdomain

    # === Mode / Agent (2 abstract) ===

    @property
    def bypass_modes(self) -> dict[str, type]:
        return {}  # Optional: interactive modes that skip the pipeline

    @property
    def default_agent(self) -> str:
        return "main"

    # === Handoff (1 abstract) ===

    def get_handoff_result_model(self) -> type:
        from alfred.modes.handoff import HandoffResult
        return HandoffResult  # Use base model unless you need custom fields

    # === Database (1 abstract) ===

    def get_db_adapter(self):
        from alfred_DOMAIN.db.client import get_client  # TODO: rename
        return get_client()


# Singleton — imported by __init__.py for registration
DOMAIN_CONFIG = DomainDomainConfig()  # TODO: rename
