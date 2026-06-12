"""
Core test fixtures — StubDomainConfig, no kitchen dependency.

These fixtures enable testing Alfred's orchestration engine in isolation,
proving that src/alfred/ has zero dependency on src/alfred_kitchen/.
"""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Set test environment before importing alfred modules
os.environ["ALFRED_ENV"] = "development"
os.environ["ALFRED_USE_ADVANCED_MODELS"] = "false"
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

from alfred.domain import register_domain
from alfred.domain.base import (
    DomainConfig,
    EntityDefinition,
    SubdomainDefinition,
)
from alfred.domain.context import DomainContext

# ---------------------------------------------------------------------------
# StubDomainConfig — minimal implementation for core-only tests
# ---------------------------------------------------------------------------

# NOTE: The stub domain is registered at module level (below the class def)
# so it's available during test collection. The autouse fixture re-registers
# it before each test to ensure a clean slate.


class StubDomainConfig(DomainConfig):
    """
    Minimal DomainConfig for testing core without kitchen.

    2 entities, 2 subdomains, no real DB, no bypass modes.
    Proves that core functions work with any domain, not just kitchen.
    """

    @property
    def name(self) -> str:
        return "stub"

    @property
    def entities(self) -> dict[str, EntityDefinition]:
        return {
            "items": EntityDefinition(
                type_name="item",
                table="items",
                primary_field="name",
                fk_fields=[],
                complexity="medium",
                label_fields=["name"],
            ),
            "notes": EntityDefinition(
                type_name="note",
                table="notes",
                primary_field="title",
                fk_fields=["item_id"],
                complexity=None,
                label_fields=["title"],
            ),
        }

    @property
    def subdomains(self) -> dict[str, SubdomainDefinition]:
        return {
            "items": SubdomainDefinition(
                name="items",
                primary_table="items",
                related_tables=["notes"],
                description="Item management",
            ),
            "notes": SubdomainDefinition(
                name="notes",
                primary_table="notes",
                related_tables=[],
                description="Note management",
            ),
        }

    def get_persona(self, subdomain: str, step_type: str) -> str:
        return f"You are a helpful {subdomain} assistant."

    def get_examples(
        self,
        subdomain: str,
        step_type: str,
        step_description: str = "",
        prev_subdomain: str | None = None,
    ) -> str:
        return ""

    def get_table_format(self, table: str) -> dict:
        return {}

    def get_empty_response(self, subdomain: str) -> str:
        return f"No {subdomain} found."

    def get_fk_enrich_map(self) -> dict[str, tuple[str, str]]:
        return {"item_id": ("items", "name")}

    def get_field_enums(self) -> dict[str, dict[str, list[str]]]:
        return {"items": {"category": ["general", "special"]}}

    def get_semantic_notes(self) -> dict[str, str]:
        return {}

    def get_fallback_schemas(self) -> dict[str, str]:
        return {
            "items": "CREATE TABLE items (id uuid, name text, category text);",
            "notes": "CREATE TABLE notes (id uuid, title text, item_id uuid);",
        }

    def get_scope_config(self) -> dict[str, dict]:
        return {}

    def get_user_owned_tables(self) -> set[str]:
        return {"items", "notes"}

    def get_uuid_fields(self) -> set[str]:
        return {"item_id"}

    def get_subdomain_registry(self) -> dict[str, dict]:
        return {
            "items": {"tables": ["items", "notes"]},
            "notes": {"tables": ["notes"]},
        }

    def get_subdomain_examples(self) -> dict[str, list[str]]:
        return {
            "items": ["Add a new item", "Show my items"],
            "notes": ["Add a note", "Show notes"],
        }

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        if "title" in artifact:
            return "note"
        return "item"

    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        return record.get("name") or record.get("title") or ref

    def get_subdomain_aliases(self) -> dict[str, str]:
        return {"stuff": "items"}

    def get_subdomain_formatters(self) -> dict:
        return {}

    @property
    def bypass_modes(self) -> dict[str, type]:
        return {}

    @property
    def default_agent(self) -> str:
        return "main"

    def get_handoff_result_model(self) -> type:
        from pydantic import BaseModel

        class StubHandoffResult(BaseModel):
            summary: str = ""
            action: str = "close"
            action_detail: str = ""

        return StubHandoffResult

    def get_db_adapter(self):
        """Return a mock DB adapter for tests."""
        return make_mock_db()


# ---------------------------------------------------------------------------
# Reusable mock DB adapter — supports all PostgREST filter methods
# ---------------------------------------------------------------------------


def make_mock_db(data=None):
    """
    Create a mock DB adapter with full PostgREST fluent chaining.

    Every filter/builder method returns the same mock_table so calls
    can be chained freely.  ``execute()`` returns ``MagicMock(data=...)``.

    Args:
        data: Default rows returned by ``execute()``.  Defaults to ``[]``.
    """
    if data is None:
        data = []

    mock = MagicMock()
    mock_table = MagicMock()

    # Builder / CRUD starters
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table

    # Filter methods (all return mock_table for chaining)
    mock_table.eq.return_value = mock_table
    mock_table.neq.return_value = mock_table
    mock_table.gt.return_value = mock_table
    mock_table.lt.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.ilike.return_value = mock_table
    mock_table.in_.return_value = mock_table
    mock_table.is_.return_value = mock_table
    mock_table.contains.return_value = mock_table
    mock_table.or_.return_value = mock_table

    # not_ proxy — supports not_.in_() and not_.is_()
    not_proxy = MagicMock()
    not_proxy.in_.return_value = mock_table
    not_proxy.is_.return_value = mock_table
    mock_table.not_ = not_proxy

    # Ordering and limiting
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table

    # Terminal
    mock_table.execute.return_value = MagicMock(data=data)

    mock.table.return_value = mock_table
    mock.rpc.return_value = MagicMock(data=[], execute=MagicMock(return_value=MagicMock(data=[])))
    return mock


# ---------------------------------------------------------------------------
# Module-level registration (needed for test collection)
# ---------------------------------------------------------------------------

# Register at module level so imports during collection can resolve domain.
# The autouse fixture below re-registers before each test for a clean slate.
_STUB_DOMAIN = StubDomainConfig()
register_domain(_STUB_DOMAIN)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def register_stub_domain():
    """Register StubDomainConfig before each core test."""
    domain = StubDomainConfig()
    register_domain(domain)
    yield domain
    # Reset to None after test (clean slate)
    import alfred.domain as _mod

    _mod._current_domain = None


@pytest.fixture
def stub_domain(register_stub_domain):
    """Explicitly access the StubDomainConfig instance."""
    return register_stub_domain


# ---------------------------------------------------------------------------
# A3 assembly-chain test infrastructure (0612-assembly-entrypoints)
#
# FakeTableAdapter — an HONEST per-table fake (unlike make_mock_db, which
# returns the same data for every table): filters actually filter, limit
# actually limits, and errors defer to execute() exactly as PostgREST does
# (builders never raise; .execute() does). Shared by the unit suite and the
# golden consumer fixtures.
# ---------------------------------------------------------------------------


class _FakeNotProxy:
    """Supports query.not_.in_() / query.not_.is_() like the PostgREST builder."""

    def __init__(self, query):
        self._query = query

    def in_(self, field, values):
        self._query.calls.append(("not_in", field, values))
        vals = {str(v) for v in values}
        self._query._rows = [r for r in self._query._rows if str(r.get(field)) not in vals]
        return self._query

    def is_(self, field, value):
        self._query.calls.append(("not_is", field, value))
        if value == "null":
            self._query._rows = [r for r in self._query._rows if r.get(field) is not None]
        return self._query


class FakeQuery:
    """PostgREST-ish query over canned rows. Errors are deferred to execute()."""

    def __init__(self, table, rows, columns):
        self.table = table
        self._rows = [dict(r) for r in rows]
        self._columns = columns  # None = unknown (empty table): no column checks
        self._limit = None
        self._error = None
        self.calls = []
        self.not_ = _FakeNotProxy(self)

    def _check_column(self, field):
        if self._columns is not None and field not in self._columns and self._error is None:
            self._error = RuntimeError(
                f'column "{field}" of relation "{self.table}" does not exist'
            )

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, field, value):
        self.calls.append(("eq", field, value))
        self._check_column(field)
        self._rows = [r for r in self._rows if str(r.get(field)) == str(value)]
        return self

    def neq(self, field, value):
        self.calls.append(("neq", field, value))
        self._check_column(field)
        self._rows = [r for r in self._rows if str(r.get(field)) != str(value)]
        return self

    def _compare(self, field, value, keep):
        self._check_column(field)
        kept = []
        for r in self._rows:
            try:
                if r.get(field) is not None and keep(r.get(field), value):
                    kept.append(r)
            except TypeError:
                pass
        self._rows = kept
        return self

    def gt(self, field, value):
        self.calls.append(("gt", field, value))
        return self._compare(field, value, lambda a, b: a > b)

    def lt(self, field, value):
        self.calls.append(("lt", field, value))
        return self._compare(field, value, lambda a, b: a < b)

    def gte(self, field, value):
        self.calls.append(("gte", field, value))
        return self._compare(field, value, lambda a, b: a >= b)

    def lte(self, field, value):
        self.calls.append(("lte", field, value))
        return self._compare(field, value, lambda a, b: a <= b)

    def in_(self, field, values):
        self.calls.append(("in", field, values))
        self._check_column(field)
        vals = {str(v) for v in values}
        self._rows = [r for r in self._rows if str(r.get(field)) in vals]
        return self

    def ilike(self, field, value):
        self.calls.append(("ilike", field, value))
        self._check_column(field)
        needle = str(value).replace("%", "").lower()
        self._rows = [r for r in self._rows if needle in str(r.get(field, "")).lower()]
        return self

    def is_(self, field, value):
        self.calls.append(("is", field, value))
        self._check_column(field)
        if value == "null":
            self._rows = [r for r in self._rows if r.get(field) is None]
        return self

    def contains(self, field, values):
        self.calls.append(("contains", field, values))
        self._check_column(field)
        self._rows = [
            r
            for r in self._rows
            if isinstance(r.get(field), list) and all(v in r[field] for v in values)
        ]
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, n):
        self.calls.append(("limit", n))
        self._limit = n
        return self

    def execute(self):
        if self._error is not None:
            raise self._error
        rows = self._rows[: self._limit] if self._limit is not None else self._rows
        return SimpleNamespace(data=[dict(r) for r in rows])


class FakeTableAdapter:
    """DatabaseAdapter fake with per-table canned rows and query recording."""

    def __init__(self, tables):
        self._tables = {name: [dict(r) for r in rows] for name, rows in tables.items()}
        self.queries = []  # every FakeQuery handed out, in order, for assertions

    def table(self, name):
        rows = self._tables.get(name)
        columns = None
        if rows:
            columns = set()
            for r in rows:
                columns |= r.keys()
        query = FakeQuery(name, rows or [], columns)
        if rows is None:
            query._error = RuntimeError(f'relation "{name}" does not exist')
        self.queries.append(query)
        return query

    def rpc(self, function_name, params):
        raise NotImplementedError("the assembly chain must not call rpc()")

    def queries_for(self, table):
        return [q for q in self.queries if q.table == table]


class AssemblyTestContext(DomainContext):
    """
    DomainContext-ONLY implementation (no AgentConfig half) for assembly tests.

    Entity/subdomain shape mirrors StubDomainConfig (items/notes) so the
    module-level registered stub domain — which session machinery like
    SessionIdRegistry reads globally — agrees with what this ctx declares.
    The assembly chain itself only ever sees this instance (state-free, E2).
    """

    def __init__(
        self,
        adapter,
        *,
        semantic_notes=None,
        fk_enrich=None,
        grades=None,
        middleware=None,
        user_profile="",
        domain_snapshot="",
    ):
        self._adapter = adapter
        self._semantic_notes = (
            semantic_notes
            if semantic_notes is not None
            else {"items": "Items are physical things.", "notes": "Notes attach to items."}
        )
        self._fk_enrich = fk_enrich if fk_enrich is not None else {"item_id": ("items", "name")}
        self._grades = grades
        self._middleware = middleware
        self._user_profile = user_profile
        self._domain_snapshot = domain_snapshot

    @property
    def name(self) -> str:
        return "assembly-stub"

    @property
    def entities(self) -> dict:
        return {
            "items": EntityDefinition(type_name="item", table="items"),
            "notes": EntityDefinition(
                type_name="note",
                table="notes",
                primary_field="title",
                fk_fields=["item_id"],
                label_fields=["title"],
            ),
        }

    @property
    def subdomains(self) -> dict:
        return {
            "items": SubdomainDefinition(
                name="items", primary_table="items", related_tables=["notes"]
            ),
            "notes": SubdomainDefinition(name="notes", primary_table="notes"),
        }

    def get_table_format(self, table: str) -> dict:
        return {}

    def get_fk_enrich_map(self) -> dict:
        return self._fk_enrich

    def get_field_enums(self) -> dict:
        return {}

    def get_semantic_notes(self) -> dict:
        return self._semantic_notes

    def get_fallback_schemas(self) -> dict:
        return {}

    def get_user_owned_tables(self) -> set:
        return {"items", "notes"}

    def get_uuid_fields(self) -> set:
        return {"item_id"}

    def get_subdomain_registry(self) -> dict:
        return {"items": {"tables": ["items", "notes"]}, "notes": {"tables": ["notes"]}}

    def infer_entity_type_from_artifact(self, artifact: dict) -> str:
        return "note" if "title" in artifact else "item"

    def compute_entity_label(self, record: dict, entity_type: str, ref: str) -> str:
        return record.get("name") or record.get("title") or ref

    def get_subdomain_aliases(self) -> dict:
        return {}

    def get_crud_middleware(self):
        return self._middleware

    def get_audience_grades(self) -> dict:
        if self._grades is not None:
            return self._grades
        return super().get_audience_grades()

    async def get_user_profile(self, user_id: str) -> str:
        return self._user_profile

    async def get_domain_snapshot(self, user_id: str) -> str:
        return self._domain_snapshot

    def get_db_adapter(self):
        return self._adapter


@pytest.fixture
def assembly_ctx_factory():
    """Factory: (tables, **ctx_options) -> (AssemblyTestContext, FakeTableAdapter)."""

    def _make(tables, **options):
        adapter = FakeTableAdapter(tables)
        return AssemblyTestContext(adapter, **options), adapter

    return _make


@pytest.fixture
def mock_openai():
    """Mock OpenAI client for unit tests."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content='{"action": "step_complete"}'))]
    mock_client.chat.completions.create.return_value = mock_completion
    return mock_client
