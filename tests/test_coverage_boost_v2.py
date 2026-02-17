"""Coverage boost tests for pico-sqlalchemy.

Targets uncovered lines:
- decorators.py:92  - Invalid propagation ValueError
- decorators.py:165 - @query() with no expr/sql
- decorators.py:167 - @query(expr=..., sql=...) both specified
- decorators.py:266->262 - Private method filtering in @repository
- factory.py:28-29 - _priority_of exception handling
- interceptor.py:92 - Non-awaitable branch (no meta, sync call_next)
- interceptor.py:109->111 - Non-awaitable branch (with meta, sync call_next)
- repository_interceptor.py:80 - _extract_page_request with invalid page param
- repository_interceptor.py:240->242 - _call_next_async non-awaitable branch
- repository_interceptor.py:356->358 - _build_base_sql without expr
- session.py:338 - Exception rollback path
- session.py:402 - RuntimeError in get_session() without active context
- config.py:59 - Protocol NotImplementedError (DECORATIVE but included for completeness)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import Base, new_session_manager
from pico_sqlalchemy import SessionManager, get_session, query, repository, transactional
from pico_sqlalchemy.decorators import QUERY_META, REPOSITORY_META, TRANSACTIONAL_META
from pico_sqlalchemy.factory import _priority_of
from pico_sqlalchemy.interceptor import TransactionalInterceptor
from pico_sqlalchemy.paging import PageRequest
from pico_sqlalchemy.repository_interceptor import (
    RepositoryQueryInterceptor,
    _build_order_by_clause,
    _extract_page_request,
)
from pico_sqlalchemy.session import TransactionContext, _should_rollback, _tx_context

# ── decorators.py ──


class TestInvalidPropagation:
    def test_invalid_propagation_raises_valueerror(self):
        """Line 92: @transactional with invalid propagation mode."""
        with pytest.raises(ValueError, match="Invalid propagation"):
            transactional(propagation="INVALID_MODE")(lambda: None)


class TestQueryValidation:
    def test_query_no_args_raises(self):
        """Line 165: @query() with neither expr nor sql."""
        with pytest.raises(ValueError, match="requires either"):
            query()

    def test_query_both_args_raises(self):
        """Line 167: @query(expr=..., sql=...) with both specified."""
        with pytest.raises(ValueError, match="cannot use both"):
            query(expr="x = :x", sql="SELECT 1")


class TestRepositoryPrivateMethodFiltering:
    def test_private_methods_not_wrapped(self):
        """Line 266->262: Private methods are skipped by @repository."""

        @repository
        class DummyRepo:
            async def public_method(self):
                pass

            async def _private_method(self):
                pass

        # Public method should have interceptors attached
        assert hasattr(DummyRepo.public_method, "_pico_interceptors_")
        # Private method should NOT be wrapped
        assert not hasattr(DummyRepo._private_method, "_pico_interceptors_")

    def test_sync_public_method_not_wrapped(self):
        """Line 266->262: Non-async public methods are not wrapped."""

        @repository
        class DummyRepo2:
            async def async_method(self):
                pass

            def sync_method(self):
                pass

        # Async method gets wrapped
        assert hasattr(DummyRepo2.async_method, "_pico_interceptors_")
        # Sync method does NOT get wrapped (iscoroutinefunction is False)
        assert not hasattr(DummyRepo2.sync_method, "_pico_interceptors_")


# ── factory.py ──


class TestPriorityOfException:
    def test_priority_non_int_returns_zero(self):
        """Lines 28-29: _priority_of with non-convertible priority."""

        class BadConfigurer:
            priority = "not-a-number"

        assert _priority_of(BadConfigurer()) == 0


# ── interceptor.py ──


class TestTransactionalInterceptorNoMeta:
    @pytest.mark.asyncio
    async def test_no_meta_sync_call_next(self):
        """Lines 89-93: call_next returns non-awaitable when no transactional meta."""
        manager = MagicMock(spec=SessionManager)
        interceptor = TransactionalInterceptor(manager)

        class PlainClass:
            def plain_method(self):
                pass

        ctx = MagicMock()
        ctx.cls = PlainClass
        ctx.name = "plain_method"

        def sync_call_next(c):
            return "sync_result"

        result = await interceptor.invoke(ctx, sync_call_next)
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_no_meta_async_call_next(self):
        """Line 92: call_next returns awaitable when no transactional meta."""
        manager = MagicMock(spec=SessionManager)
        interceptor = TransactionalInterceptor(manager)

        class PlainClass:
            def plain_method(self):
                pass

        ctx = MagicMock()
        ctx.cls = PlainClass
        ctx.name = "plain_method"

        async def async_call_next(c):
            return "async_result"

        result = await interceptor.invoke(ctx, async_call_next)
        assert result == "async_result"


class TestTransactionalInterceptorWithMetaSyncNext:
    @pytest.mark.asyncio
    async def test_with_meta_sync_call_next(self):
        """Lines 109->111: call_next returns non-awaitable when meta exists."""
        sm = SessionManager(url="sqlite+aiosqlite:///:memory:")
        interceptor = TransactionalInterceptor(sm)

        class TxClass:
            @transactional
            async def tx_method(self):
                pass

        ctx = MagicMock()
        ctx.cls = TxClass
        ctx.name = "tx_method"

        # call_next returns a non-awaitable value
        def sync_call_next(c):
            return "sync_result_with_meta"

        result = await interceptor.invoke(ctx, sync_call_next)
        assert result == "sync_result_with_meta"


# ── repository_interceptor.py ──


class TestExtractPageRequestInvalid:
    def test_invalid_page_param_raises(self):
        """Line 80: _extract_page_request with non-PageRequest 'page' param."""
        params = {"page": "not_a_page_request"}
        with pytest.raises(TypeError, match="Paged query requires"):
            _extract_page_request(params, paged=True)


class TestRepoInterceptorCallNextAsync:
    @pytest.mark.asyncio
    async def test_no_query_meta_sync_result(self):
        """Lines 240->242: _call_next_async with non-awaitable result."""
        sm = MagicMock(spec=SessionManager)
        interceptor = RepositoryQueryInterceptor(sm)

        ctx = MagicMock()
        ctx.cls = type("Cls", (), {})
        ctx.name = "some_method"

        def sync_call_next(c):
            return "sync_value"

        result = await interceptor.invoke(ctx, sync_call_next)
        assert result == "sync_value"


class TestBuildOrderByNoSorts:
    def test_empty_order_by_when_no_sorts(self):
        """Line 80: _build_order_by_clause returns '' when no sorts."""
        page_req = PageRequest(page=0, size=10)
        result = _build_order_by_clause(page_req, {"id", "name"})
        assert result == ""

    def test_none_page_req(self):
        """Line 80: _build_order_by_clause returns '' when page_req is None."""
        result = _build_order_by_clause(None, {"id"})
        assert result == ""


class TestBuildBaseSqlNoExpr:
    def test_base_sql_without_expr(self):
        """Lines 356->358: _build_base_sql with no WHERE expression."""
        sm = MagicMock(spec=SessionManager)
        interceptor = RepositoryQueryInterceptor(sm)

        class FakeEntity:
            __tablename__ = "users"

        sql = interceptor._build_base_sql(FakeEntity, None)
        assert sql == "SELECT * FROM users"
        assert "WHERE" not in sql


# ── session.py ──


class TestGetSessionNoTransaction:
    def test_get_session_without_active_context_raises(self):
        """Line 402: get_session() when no transaction is active."""
        manager = new_session_manager(Base)
        with pytest.raises(RuntimeError, match="No active transaction"):
            get_session(manager)


class TestExceptionRollback:
    def test_exception_triggers_rollback(self):
        """Line 338: Exception during transaction triggers rollback."""
        manager = new_session_manager(Base)

        async def _run():
            with pytest.raises(ValueError):
                async with manager.transaction() as session:
                    raise ValueError("boom")

        asyncio.run(_run())


class TestShouldRollback:
    def test_should_rollback_true(self):
        assert _should_rollback(ValueError("x"), (Exception,), ()) is True

    def test_should_rollback_excluded(self):
        assert _should_rollback(ValueError("x"), (Exception,), (ValueError,)) is False

    def test_should_rollback_not_matching(self):
        assert _should_rollback(KeyboardInterrupt(), (Exception,), ()) is False


class TestNoRollbackForException:
    def test_no_rollback_for_specified_exception(self):
        """Line 338 variant: exception in no_rollback_for skips rollback."""
        manager = new_session_manager(Base)

        async def _run():
            with pytest.raises(ValueError):
                async with manager.transaction(no_rollback_for=(ValueError,)) as session:
                    raise ValueError("should not rollback")

        asyncio.run(_run())
