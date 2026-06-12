"""
Alfred V2 - Tools Package.

Provides generic CRUD tools and schema generation.

Tools:
- db_read: Fetch rows with filters
- db_create: Insert new records
- db_update: Update existing records
- db_delete: Delete records

Schema:
- SUBDOMAIN_REGISTRY: Maps subdomains to tables
- get_schema_with_fallback: Get schema for a subdomain
"""

from typing import Any

from alfred.tools.crud import (
    DbCreateParams,
    DbDeleteParams,
    DbReadParams,
    DbUpdateParams,
    FilterClause,
    db_create,
    db_delete,
    db_read,
    db_update,
    execute_crud,
)
from alfred.tools.schema import (
    get_complexity_rules,
    get_schema_with_fallback,
    get_subdomain_tables,
    schema_cache,
)


def __getattr__(name: str) -> Any:
    """Lazy access for domain-backed names.

    SUBDOMAIN_REGISTRY resolves through the registered domain
    (schema.__getattr__ → get_current_domain). Importing it eagerly here
    would (a) require a registered domain just to import this package —
    breaking the seam guarantee that `import alfred.context` (which imports
    alfred.tools.crud) is domain-free — and (b) freeze a stale snapshot at
    import time. Lazy access keeps `from alfred.tools import
    SUBDOMAIN_REGISTRY` working, resolved fresh at use time.
    """
    if name == "SUBDOMAIN_REGISTRY":
        from alfred.tools import schema

        return schema.SUBDOMAIN_REGISTRY
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # CRUD tools
    "db_read",
    "db_create",
    "db_update",
    "db_delete",
    "execute_crud",
    # Parameter models
    "DbReadParams",
    "DbCreateParams",
    "DbUpdateParams",
    "DbDeleteParams",
    "FilterClause",
    # Schema
    "SUBDOMAIN_REGISTRY",
    "get_schema_with_fallback",
    "get_subdomain_tables",
    "get_complexity_rules",
    "schema_cache",
]
