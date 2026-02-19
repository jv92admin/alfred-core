"""
Alfred - Database Layer.

Provides the DatabaseAdapter protocol for domain-agnostic DB access.
Each domain provides its own DB client via DomainConfig.get_db_adapter().
"""

from alfred.db.adapter import DatabaseAdapter

__all__ = [
    "DatabaseAdapter",
]
