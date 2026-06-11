"""
Domain Configuration Protocol.

This module defines the abstract interface that all domain implementations
must satisfy. The DomainConfig protocol enables Alfred's orchestration
engine to work with any domain (kitchen, FPL, etc.) without hardcoding
domain-specific logic.

As of the protocol split (program roadmap A1 / substrate C-1), DomainConfig
is composed of two halves:
- DomainContext (alfred.domain.context): domain knowledge + data shaping —
  no LLM, no pipeline. Non-pipeline consumers depend on this half only.
- AgentConfig (alfred.domain.agent): pipeline-only — personas, prompts,
  modes, agents, conversation behavior, handoff.

Existing implementers subclass DomainConfig exactly as before — the composed
protocol (members, abstract set, defaults) is unchanged. Every symbol that
historically lived in this module is re-exported here, so existing import
paths keep working.

Key concepts:
- EntityDefinition: Configuration for a single entity type (recipe, player, etc.)
- SubdomainDefinition: Logical grouping of related tables
- DomainConfig: The main protocol with all domain-specific methods
"""

from __future__ import annotations

from alfred.domain.agent import (
    AgentConfig,
    ToolContext,
    ToolDefinition,
)
from alfred.domain.context import (
    CRUDMiddleware,
    DomainContext,
    EntityDefinition,
    ReadPreprocessResult,
    SubdomainDefinition,
)

__all__ = [
    "AgentConfig",
    "CRUDMiddleware",
    "DomainConfig",
    "DomainContext",
    "EntityDefinition",
    "ReadPreprocessResult",
    "SubdomainDefinition",
    "ToolContext",
    "ToolDefinition",
]


class DomainConfig(DomainContext, AgentConfig):
    """
    Protocol that domain implementations must satisfy.

    A DomainConfig provides all the domain-specific information that
    Alfred's orchestration engine needs:
    - Entity definitions (what types of things exist)
    - Subdomain organization (how tables are grouped)
    - Personas and examples (for LLM prompts)
    - Formatting rules (for output)
    - Schema information (for CRUD operations)

    Composed of DomainContext (knowledge + shaping, no LLM) and AgentConfig
    (pipeline-only). Full pipeline domains implement this composed class;
    substrate-only consumers implement DomainContext alone.

    Example implementation:
        class KitchenConfig(DomainConfig):
            @property
            def name(self) -> str:
                return "kitchen"

            @property
            def entities(self) -> dict[str, EntityDefinition]:
                return {
                    "recipes": EntityDefinition(
                        type_name="recipe",
                        table="recipes",
                        primary_field="name",
                        nested_relations=["recipe_ingredients"],
                    ),
                    ...
                }
    """
