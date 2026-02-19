"""
Alfred Domain Configuration System.

This module provides the abstraction layer that enables Alfred's orchestration
engine to work with different domains (kitchen, FPL, etc.).

The key abstraction is DomainConfig - a protocol that each domain implements
to provide its entities, subdomains, personas, and formatting rules.

Usage:
    from alfred.domain import register_domain, get_current_domain, DomainConfig

    # At app startup:
    register_domain(my_domain)

    # Anywhere in core:
    domain = get_current_domain()
"""

from alfred.domain.base import (
    DomainConfig,
    EntityDefinition,
    SubdomainDefinition,
)

_current_domain: DomainConfig | None = None


def register_domain(domain: DomainConfig) -> None:
    """
    Register the active domain configuration.

    Must be called at app startup before any core functions are used.
    Each domain application (kitchen, FPL, etc.) calls this once.

    Args:
        domain: The DomainConfig implementation to use
    """
    global _current_domain
    _current_domain = domain


def get_current_domain() -> DomainConfig:
    """
    Get the currently registered domain.

    Returns:
        The active DomainConfig implementation

    Raises:
        RuntimeError: If no domain has been registered via register_domain()
    """
    if _current_domain is None:
        raise RuntimeError(
            "No domain registered. Call register_domain() at app startup."
        )
    return _current_domain


__all__ = [
    "DomainConfig",
    "EntityDefinition",
    "SubdomainDefinition",
    "register_domain",
    "get_current_domain",
]
