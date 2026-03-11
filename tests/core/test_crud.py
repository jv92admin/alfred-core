"""
Tests for CRUD tools — filter operators, db_read/create/update/delete,
execute_crud dispatcher, registry integration.

Uses StubDomainConfig (no kitchen dependency).
Mock DB adapter verifies correct PostgREST method calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from alfred.tools.crud import (
    FilterClause,
    DbReadParams,
    DbAnalyzeParams,
    DbCreateParams,
    DbUpdateParams,
    DbDeleteParams,
    apply_filter,
    db_read,
    db_analyze,
    db_create,
    db_update,
    db_delete,
    execute_crud,
    _sanitize_uuid_fields,
    _sanitize_payload,
)
from tests.core.conftest import make_mock_db


# =============================================================================
# apply_filter — 14 operators + unknown
# =============================================================================


class TestApplyFilter:
    """Each operator maps to the correct PostgREST query builder method."""

    def _make_query(self):
        """Fresh mock query with all filter methods."""
        q = MagicMock()
        q.eq.return_value = q
        q.neq.return_value = q
        q.gt.return_value = q
        q.lt.return_value = q
        q.gte.return_value = q
        q.lte.return_value = q
        q.ilike.return_value = q
        q.in_.return_value = q
        q.is_.return_value = q
        q.contains.return_value = q
        not_proxy = MagicMock()
        not_proxy.in_.return_value = q
        not_proxy.is_.return_value = q
        q.not_ = not_proxy
        return q

    def test_eq_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="name", op="=", value="milk"))
        q.eq.assert_called_once_with("name", "milk")

    def test_neq_operator_symbol(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="name", op="!=", value="milk"))
        q.neq.assert_called_once_with("name", "milk")

    def test_neq_operator_word(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="name", op="neq", value="milk"))
        q.neq.assert_called_once_with("name", "milk")

    def test_gt_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="quantity", op=">", value=5))
        q.gt.assert_called_once_with("quantity", 5)

    def test_lt_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="quantity", op="<", value=5))
        q.lt.assert_called_once_with("quantity", 5)

    def test_gte_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="quantity", op=">=", value=5))
        q.gte.assert_called_once_with("quantity", 5)

    def test_lte_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="quantity", op="<=", value=5))
        q.lte.assert_called_once_with("quantity", 5)

    def test_in_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="category", op="in", value=["a", "b"]))
        q.in_.assert_called_once_with("category", ["a", "b"])

    def test_not_in_operator_with_list(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="category", op="not_in", value=["a", "b"]))
        q.not_.in_.assert_called_once_with("category", ["a", "b"])

    def test_not_in_operator_scalar_wraps_in_list(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="category", op="not_in", value="a"))
        q.not_.in_.assert_called_once_with("category", ["a"])

    def test_ilike_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="name", op="ilike", value="%milk%"))
        q.ilike.assert_called_once_with("name", "%milk%")

    def test_is_null_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="item_id", op="is_null", value=True))
        q.is_.assert_called_once_with("item_id", "null")

    def test_is_not_null_operator(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="item_id", op="is_not_null", value=True))
        q.not_.is_.assert_called_once_with("item_id", "null")

    def test_contains_operator_string_wraps_in_list(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="tags", op="contains", value="vegan"))
        q.contains.assert_called_once_with("tags", ["vegan"])

    def test_contains_operator_list_passes_through(self):
        q = self._make_query()
        apply_filter(q, FilterClause(field="tags", op="contains", value=["vegan", "quick"]))
        q.contains.assert_called_once_with("tags", ["vegan", "quick"])

    def test_unknown_operator_raises_value_error(self):
        q = self._make_query()
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            apply_filter(q, FilterClause(field="x", op="similar", value="y"))


# =============================================================================
# db_read
# =============================================================================


class TestDbRead:
    """Test db_read query building and middleware integration."""

    @pytest.fixture
    def mock_db(self):
        return make_mock_db(data=[{"id": "uuid-1", "name": "Widget"}])

    async def test_basic_read_no_filters(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_read(
                DbReadParams(table="items"), user_id="user-1"
            )
        assert result == [{"id": "uuid-1", "name": "Widget"}]
        mock_db.table.assert_called_with("items")
        mock_db.table().select.assert_called_once_with("*")

    async def test_read_with_columns(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items", columns=["name", "category"]),
                user_id="user-1",
            )
        # id is auto-prepended when LLM omits it
        mock_db.table().select.assert_called_once_with("id,name,category")

    async def test_read_with_columns_id_already_present(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items", columns=["id", "name"]),
                user_id="user-1",
            )
        # id not duplicated when already present
        mock_db.table().select.assert_called_once_with("id,name")

    async def test_read_with_order_desc(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items", order_by="name", order_dir="desc"),
                user_id="user-1",
            )
        mock_db.table().order.assert_called_once_with("name", desc=True)

    async def test_read_with_order_asc(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items", order_by="name", order_dir="asc"),
                user_id="user-1",
            )
        mock_db.table().order.assert_called_once_with("name", desc=False)

    async def test_read_with_limit(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items", limit=5), user_id="user-1"
            )
        mock_db.table().limit.assert_called_once_with(5)

    async def test_read_user_owned_table_auto_filters(self, mock_db):
        """User-owned tables get an automatic user_id filter."""
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items"), user_id="user-1"
            )
        # items is user-owned in StubDomainConfig
        mock_db.table().eq.assert_any_call("user_id", "user-1")

    async def test_read_non_user_owned_no_auto_filter(self):
        """Non-user-owned tables don't get user_id filter."""
        mock_db = make_mock_db(data=[])
        # Temporarily make items not user-owned
        with (
            patch("alfred.tools.crud._get_client", return_value=mock_db),
            patch("alfred.tools.crud._get_domain") as mock_domain,
        ):
            mock_domain.return_value.get_user_owned_tables.return_value = set()
            await db_read(DbReadParams(table="items"), user_id="user-1")
        # eq should not be called with user_id
        for call in mock_db.table().eq.call_args_list:
            assert call[0][0] != "user_id"

    async def test_read_with_and_filters(self, mock_db):
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(
                    table="items",
                    filters=[
                        FilterClause(field="category", op="=", value="general"),
                        FilterClause(field="quantity", op=">", value=0),
                    ],
                ),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("category", "general")
        mock_db.table().gt.assert_called_once_with("quantity", 0)

    async def test_read_or_filters_build_string(self, mock_db):
        """OR filters are converted to PostgREST OR string syntax."""
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(
                    table="items",
                    or_filters=[
                        FilterClause(field="name", op="=", value="milk"),
                        FilterClause(field="name", op="ilike", value="%cheese%"),
                    ],
                ),
                user_id="user-1",
            )
        mock_db.table().or_.assert_called_once()
        or_string = mock_db.table().or_.call_args[0][0]
        assert "name.eq.milk" in or_string
        assert "name.ilike.%cheese%" in or_string

    async def test_read_middleware_short_circuit(self, mock_db):
        """Middleware can short-circuit to return empty immediately."""
        from alfred.domain.base import ReadPreprocessResult

        middleware = MagicMock()
        middleware.pre_read = AsyncMock(
            return_value=ReadPreprocessResult(
                params=DbReadParams(table="items"),
                short_circuit_empty=True,
            )
        )
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_read(
                DbReadParams(table="items"), user_id="user-1", middleware=middleware
            )
        assert result == []
        mock_db.table().execute.assert_not_called()

    async def test_read_middleware_pre_filter_ids(self, mock_db):
        """Middleware can provide pre-filter IDs (e.g., from semantic search)."""
        from alfred.domain.base import ReadPreprocessResult

        middleware = MagicMock()
        middleware.pre_read = AsyncMock(
            return_value=ReadPreprocessResult(
                params=DbReadParams(table="items"),
                pre_filter_ids=["uuid-1", "uuid-2"],
            )
        )
        middleware.post_read = AsyncMock(side_effect=lambda records, table, uid: records)
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_read(
                DbReadParams(table="items"), user_id="user-1", middleware=middleware
            )
        mock_db.table().in_.assert_any_call("id", ["uuid-1", "uuid-2"])


# =============================================================================
# db_analyze — analytical queries
# =============================================================================


class TestDbAnalyze:
    """Test db_analyze aggregate queries (count, sum, avg, min, max, group_by)."""

    async def test_count_no_field(self):
        mock_db = make_mock_db(data=[{"count": 5}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="count"),
                user_id="user-1",
            )
        assert result == [{"count": 5}]
        mock_db.table().select.assert_called_once_with("count()")

    async def test_count_with_field(self):
        mock_db = make_mock_db(data=[{"count": 4}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="count", aggregate_field="category"),
                user_id="user-1",
            )
        assert result == [{"count": 4}]
        mock_db.table().select.assert_called_once_with("category.count()")

    async def test_sum(self):
        mock_db = make_mock_db(data=[{"sum": 150}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="sum", aggregate_field="quantity"),
                user_id="user-1",
            )
        assert result == [{"sum": 150}]
        mock_db.table().select.assert_called_once_with("quantity.sum()")

    async def test_avg(self):
        mock_db = make_mock_db(data=[{"avg": 12.5}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="avg", aggregate_field="price"),
                user_id="user-1",
            )
        assert result == [{"avg": 12.5}]
        mock_db.table().select.assert_called_once_with("price.avg()")

    async def test_min(self):
        mock_db = make_mock_db(data=[{"min": 3}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="min", aggregate_field="price"),
                user_id="user-1",
            )
        assert result == [{"min": 3}]
        mock_db.table().select.assert_called_once_with("price.min()")

    async def test_max(self):
        mock_db = make_mock_db(data=[{"max": 99}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(table="items", aggregate="max", aggregate_field="price"),
                user_id="user-1",
            )
        assert result == [{"max": 99}]
        mock_db.table().select.assert_called_once_with("price.max()")

    async def test_group_by(self):
        """GROUP BY generates mixed select — PostgREST auto-groups."""
        mock_db = make_mock_db(data=[
            {"category": "A", "sum": 100},
            {"category": "B", "sum": 200},
        ])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(
                    table="items", aggregate="sum",
                    aggregate_field="quantity", group_by="category",
                ),
                user_id="user-1",
            )
        assert len(result) == 2
        mock_db.table().select.assert_called_once_with("quantity.sum(),category")

    async def test_count_group_by(self):
        """Count with group_by uses count + group column."""
        mock_db = make_mock_db(data=[
            {"status": "active", "count": 10},
            {"status": "inactive", "count": 3},
        ])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_analyze(
                DbAnalyzeParams(
                    table="items", aggregate="count", group_by="status",
                ),
                user_id="user-1",
            )
        assert len(result) == 2
        mock_db.table().select.assert_called_once_with("count(),status")

    async def test_filters_applied(self):
        mock_db = make_mock_db(data=[{"count": 3}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_analyze(
                DbAnalyzeParams(
                    table="items", aggregate="count",
                    filters=[FilterClause(field="status", op="=", value="active")],
                ),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("status", "active")

    async def test_order_by_and_limit(self):
        """ORDER BY + LIMIT work for 'top N' queries."""
        mock_db = make_mock_db(data=[{"category": "A", "sum": 500}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_analyze(
                DbAnalyzeParams(
                    table="items", aggregate="sum",
                    aggregate_field="quantity", group_by="category",
                    order_by="sum", order_dir="desc", limit=5,
                ),
                user_id="user-1",
            )
        mock_db.table().order.assert_called_once_with("sum", desc=True)
        mock_db.table().limit.assert_called_once_with(5)

    async def test_sum_requires_aggregate_field(self):
        with pytest.raises(ValueError, match="requires 'aggregate_field'"):
            DbAnalyzeParams(table="items", aggregate="sum")

    async def test_avg_requires_aggregate_field(self):
        with pytest.raises(ValueError, match="requires 'aggregate_field'"):
            DbAnalyzeParams(table="items", aggregate="avg")

    async def test_min_requires_aggregate_field(self):
        with pytest.raises(ValueError, match="requires 'aggregate_field'"):
            DbAnalyzeParams(table="items", aggregate="min")

    async def test_max_requires_aggregate_field(self):
        with pytest.raises(ValueError, match="requires 'aggregate_field'"):
            DbAnalyzeParams(table="items", aggregate="max")

    async def test_user_id_auto_filter(self):
        """User-owned tables still get user_id filter."""
        mock_db = make_mock_db(data=[{"count": 5}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_analyze(
                DbAnalyzeParams(table="items", aggregate="count"),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("user_id", "user-1")

    async def test_no_entity_tracking(self):
        """db_analyze through execute_crud produces no entity refs."""
        from alfred.core.id_registry import SessionIdRegistry

        registry = SessionIdRegistry()
        mock_db = make_mock_db(data=[{"count": 7}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_analyze",
                {"table": "items", "aggregate": "count"},
                user_id="user-1",
                registry=registry,
            )
        assert result == [{"count": 7}]
        assert len(registry.ref_to_uuid) == 0

    async def test_or_filters(self):
        """OR filters work in db_analyze."""
        mock_db = make_mock_db(data=[{"count": 8}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_analyze(
                DbAnalyzeParams(
                    table="items", aggregate="count",
                    or_filters=[
                        FilterClause(field="status", op="=", value="active"),
                        FilterClause(field="status", op="=", value="pending"),
                    ],
                ),
                user_id="user-1",
            )
        mock_db.table().or_.assert_called_once()
        or_string = mock_db.table().or_.call_args[0][0]
        assert "status.eq.active" in or_string
        assert "status.eq.pending" in or_string


# =============================================================================
# db_create
# =============================================================================


class TestDbCreate:
    """Test db_create insert logic, sanitization, middleware."""

    async def test_create_single_record(self):
        mock_db = make_mock_db(data=[{"id": "uuid-new", "name": "Widget"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_create(
                DbCreateParams(table="items", data={"name": "Widget"}),
                user_id="user-1",
            )
        assert isinstance(result, dict)
        assert result["name"] == "Widget"
        mock_db.table().insert.assert_called_once()

    async def test_create_batch_records(self):
        mock_db = make_mock_db(
            data=[{"id": "uuid-1", "name": "A"}, {"id": "uuid-2", "name": "B"}]
        )
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_create(
                DbCreateParams(table="items", data=[{"name": "A"}, {"name": "B"}]),
                user_id="user-1",
            )
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_create_user_owned_injects_user_id(self):
        mock_db = make_mock_db(data=[{"id": "uuid-new", "name": "Widget", "user_id": "user-1"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_create(
                DbCreateParams(table="items", data={"name": "Widget"}),
                user_id="user-1",
            )
        # The inserted record should include user_id
        insert_args = mock_db.table().insert.call_args[0][0]
        assert insert_args[0]["user_id"] == "user-1"

    async def test_create_uuid_field_sanitization(self):
        """Empty string UUID fields become None."""
        result = _sanitize_uuid_fields({"name": "Widget", "item_id": ""})
        assert result["item_id"] is None
        assert result["name"] == "Widget"

    async def test_create_uuid_field_preserves_valid(self):
        result = _sanitize_uuid_fields({"name": "Widget", "item_id": "uuid-123"})
        assert result["item_id"] == "uuid-123"

    async def test_create_null_byte_sanitization(self):
        result = _sanitize_payload({"name": "Widget\x00Extra", "tags": ["a\x00b"]})
        assert result["name"] == "WidgetExtra"
        assert result["tags"] == ["ab"]

    async def test_create_middleware_pre_write(self):
        mock_db = make_mock_db(data=[{"id": "uuid-new", "name": "Enriched"}])
        middleware = MagicMock()
        middleware.pre_write = AsyncMock(
            return_value=[{"name": "Enriched", "extra": True}]
        )
        middleware.deduplicate_batch = MagicMock(side_effect=lambda t, r: r)
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_create(
                DbCreateParams(table="items", data={"name": "Raw"}),
                user_id="user-1",
                middleware=middleware,
            )
        middleware.pre_write.assert_called_once()

    async def test_create_batch_deduplication(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1", "name": "A"}])
        middleware = MagicMock()
        middleware.pre_write = AsyncMock(side_effect=lambda t, r: r)
        middleware.deduplicate_batch = MagicMock(
            return_value=[{"name": "A", "user_id": "user-1"}]
        )
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_create(
                DbCreateParams(table="items", data=[{"name": "A"}, {"name": "A"}]),
                user_id="user-1",
                middleware=middleware,
            )
        middleware.deduplicate_batch.assert_called_once()

    async def test_create_single_not_deduplicated(self):
        """Single record insert should NOT call deduplicate_batch."""
        mock_db = make_mock_db(data=[{"id": "uuid-new", "name": "A"}])
        middleware = MagicMock()
        middleware.pre_write = AsyncMock(side_effect=lambda t, r: r)
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_create(
                DbCreateParams(table="items", data={"name": "A"}),
                user_id="user-1",
                middleware=middleware,
            )
        middleware.deduplicate_batch.assert_not_called()


# =============================================================================
# db_update
# =============================================================================


class TestDbUpdate:
    """Test db_update filter application and security."""

    async def test_update_with_filters(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1", "name": "Updated"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_update(
                DbUpdateParams(
                    table="items",
                    filters=[FilterClause(field="name", op="=", value="Old")],
                    data={"name": "Updated"},
                ),
                user_id="user-1",
            )
        assert result == [{"id": "uuid-1", "name": "Updated"}]
        mock_db.table().update.assert_called_once_with({"name": "Updated"})
        mock_db.table().eq.assert_any_call("name", "Old")

    async def test_update_user_owned_auto_filter(self):
        mock_db = make_mock_db(data=[])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_update(
                DbUpdateParams(
                    table="items",
                    filters=[FilterClause(field="id", op="=", value="uuid-1")],
                    data={"name": "X"},
                ),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("user_id", "user-1")

    async def test_update_multiple_filters(self):
        mock_db = make_mock_db(data=[])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_update(
                DbUpdateParams(
                    table="items",
                    filters=[
                        FilterClause(field="category", op="=", value="general"),
                        FilterClause(field="quantity", op=">=", value=10),
                    ],
                    data={"name": "X"},
                ),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("category", "general")
        mock_db.table().gte.assert_called_once_with("quantity", 10)


# =============================================================================
# db_delete
# =============================================================================


class TestDbDelete:
    """Test db_delete filter application and safety."""

    async def test_delete_with_filters(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1", "name": "Gone"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_delete(
                DbDeleteParams(
                    table="items",
                    filters=[FilterClause(field="id", op="=", value="uuid-1")],
                ),
                user_id="user-1",
            )
        assert result == [{"id": "uuid-1", "name": "Gone"}]
        mock_db.table().delete.assert_called_once()

    async def test_delete_user_owned_auto_filter(self):
        mock_db = make_mock_db(data=[])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            await db_delete(
                DbDeleteParams(
                    table="items",
                    filters=[FilterClause(field="id", op="=", value="uuid-1")],
                ),
                user_id="user-1",
            )
        mock_db.table().eq.assert_any_call("user_id", "user-1")

    async def test_delete_empty_filters_non_user_table_raises(self):
        """Empty filters on non-user-owned table must raise ValueError."""
        mock_db = make_mock_db()
        with (
            patch("alfred.tools.crud._get_client", return_value=mock_db),
            patch("alfred.tools.crud._get_domain") as mock_domain,
        ):
            mock_domain.return_value.get_user_owned_tables.return_value = set()
            with pytest.raises(ValueError, match="Cannot delete"):
                await db_delete(
                    DbDeleteParams(table="other_table", filters=[]),
                    user_id="user-1",
                )

    async def test_delete_empty_filters_user_owned_ok(self):
        """User-owned table with empty filters is allowed (user_id provides safety)."""
        mock_db = make_mock_db(data=[])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await db_delete(
                DbDeleteParams(table="items", filters=[]),
                user_id="user-1",
            )
        assert result == []
        mock_db.table().eq.assert_any_call("user_id", "user-1")


# =============================================================================
# execute_crud — dispatcher, registry integration
# =============================================================================


class TestExecuteCrud:
    """Test the top-level dispatcher and registry translation."""

    async def test_dispatch_db_read(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1", "name": "Widget"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_read", {"table": "items"}, user_id="user-1"
            )
        assert isinstance(result, list)

    async def test_dispatch_db_create(self):
        mock_db = make_mock_db(data=[{"id": "uuid-new", "name": "New"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_create",
                {"table": "items", "data": {"name": "New"}},
                user_id="user-1",
            )
        assert isinstance(result, dict)

    async def test_dispatch_db_update(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1", "name": "Updated"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_update",
                {
                    "table": "items",
                    "filters": [{"field": "id", "op": "=", "value": "uuid-1"}],
                    "data": {"name": "Updated"},
                },
                user_id="user-1",
            )
        assert isinstance(result, list)

    async def test_dispatch_db_delete(self):
        mock_db = make_mock_db(data=[{"id": "uuid-1"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_delete",
                {
                    "table": "items",
                    "filters": [{"field": "id", "op": "=", "value": "uuid-1"}],
                },
                user_id="user-1",
            )
        assert isinstance(result, list)

    async def test_dispatch_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            await execute_crud("db_magic", {"table": "items"}, user_id="user-1")

    async def test_read_with_registry_translates_output(self):
        """Registry translates UUIDs to refs in output."""
        from alfred.core.id_registry import SessionIdRegistry

        mock_db = make_mock_db(data=[{"id": "uuid-aaa", "name": "Widget"}])
        registry = SessionIdRegistry()

        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_read", {"table": "items"}, user_id="user-1", registry=registry
            )
        # Output should have ref, not UUID
        assert result[0]["id"] == "item_1"
        assert registry.get_uuid("item_1") == "uuid-aaa"

    async def test_read_with_registry_translates_input_filters(self):
        """Registry translates refs to UUIDs in input filters."""
        from alfred.core.id_registry import SessionIdRegistry

        # Pre-populate registry with a known mapping
        registry = SessionIdRegistry()
        registry.translate_read_output(
            [{"id": "uuid-aaa", "name": "Widget"}], "items"
        )

        mock_db = make_mock_db(data=[{"id": "uuid-aaa", "name": "Widget"}])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_read",
                {
                    "table": "items",
                    "filters": [{"field": "id", "op": "=", "value": "item_1"}],
                },
                user_id="user-1",
                registry=registry,
            )
        # The filter should have been translated to UUID for the DB call
        mock_db.table().eq.assert_any_call("id", "uuid-aaa")

    async def test_read_reroutes_gen_ref(self):
        """gen_* refs with registry data are returned without DB lookup."""
        from alfred.core.id_registry import SessionIdRegistry

        registry = SessionIdRegistry()
        registry.register_generated(
            "item", "Test Widget", {"name": "Test Widget", "category": "general"}
        )

        mock_db = make_mock_db(data=[])
        with patch("alfred.tools.crud._get_client", return_value=mock_db):
            result = await execute_crud(
                "db_read",
                {
                    "table": "items",
                    "filters": [{"field": "id", "op": "=", "value": "gen_item_1"}],
                },
                user_id="user-1",
                registry=registry,
            )
        # Should return from registry, not from DB
        assert len(result) == 1
        assert result[0]["name"] == "Test Widget"
        # DB should NOT have been queried
        mock_db.table().execute.assert_not_called()
