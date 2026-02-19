"""Supabase client wrapper.

The Supabase client already satisfies Alfred's DatabaseAdapter protocol —
it has .table() and .rpc() methods. No wrapper class needed.
"""

from supabase import create_client

_client = None


def get_client():
    """Return Supabase client (matches DatabaseAdapter protocol)."""
    global _client
    if _client is None:
        from alfred_DOMAIN.config import settings  # TODO: rename
        _client = create_client(settings.supabase_url, settings.supabase_anon_key)
    return _client
