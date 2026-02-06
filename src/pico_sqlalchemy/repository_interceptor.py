import inspect
from typing import Any, Callable, Mapping

from pico_ioc import MethodCtx, MethodInterceptor, component
from sqlalchemy import text

from .decorators import QUERY_META, REPOSITORY_META
from .session import SessionManager, get_session
from .paging import Page, PageRequest


def _extract_page_request(params: dict[str, Any], paged: bool) -> PageRequest | None:
    """Extract and validate PageRequest from params if paged query."""
    if not paged:
        return None
    page_req = params.pop("page", None)
    if not isinstance(page_req, PageRequest):
        raise TypeError("Paged query requires a 'page: PageRequest' parameter")
    return page_req


def _build_order_by_clause(page_req: PageRequest, valid_columns: set[str]) -> str:
    """Build ORDER BY clause from PageRequest sorts."""
    if not page_req or not page_req.sorts:
        return ""
    sort_parts = []
    for s in page_req.sorts:
        if s.field not in valid_columns:
            raise ValueError(f"Invalid sort field: {s.field}")
        direction = "DESC" if s.direction.upper() == "DESC" else "ASC"
        sort_parts.append(f"{s.field} {direction}")
    return " ORDER BY " + ", ".join(sort_parts) if sort_parts else ""


async def _execute_count_query(session: Any, sql: str, params: dict[str, Any]) -> int:
    """Execute count query and return total."""
    count_sql = f"SELECT COUNT(*) FROM ({sql}) AS sub"
    result = await session.execute(text(count_sql), params)
    return result.scalar_one()


async def _execute_paginated_query(
    session: Any,
    sql: str,
    params: dict[str, Any],
    page_req: PageRequest,
) -> Page:
    """Execute paginated query and return Page."""
    total = await _execute_count_query(session, sql, params)
    paginated_sql = f"{sql} LIMIT :_limit OFFSET :_offset"
    exec_params = {
        **params,
        "_limit": page_req.size,
        "_offset": page_req.offset,
    }
    result = await session.execute(text(paginated_sql), exec_params)
    rows = result.mappings().all()
    return Page(
        content=rows,
        total_elements=total,
        page=page_req.page,
        size=page_req.size,
    )


async def _execute_simple_query(
    session: Any,
    sql: str,
    params: dict[str, Any],
    unique: bool,
) -> Any:
    """Execute simple (non-paginated) query."""
    result = await session.execute(text(sql), params)
    rows = result.mappings().all()
    if unique:
        return rows[0] if rows else None
    return rows


@component
class RepositoryQueryInterceptor(MethodInterceptor):
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def invoke(self, ctx: MethodCtx, call_next: Callable[[MethodCtx], Any]) -> Any:
        func = getattr(ctx.cls, ctx.name, None)
        meta = getattr(func, QUERY_META, None)

        if meta is None:
            return await self._call_next_async(ctx, call_next)

        session = get_session(self.session_manager)
        params = self._bind_params(func, ctx.args, ctx.kwargs)
        repo_meta = getattr(ctx.cls, REPOSITORY_META, {}) or {}
        entity = repo_meta.get("entity")
        mode = meta.get("mode")

        if mode == "sql":
            return await self._execute_sql(session, meta, params)
        if mode == "expr":
            return await self._execute_expr(session, meta, params, entity)
        raise RuntimeError(f"Unsupported query mode: {mode!r}")

    async def _call_next_async(self, ctx: MethodCtx, call_next: Callable) -> Any:
        """Call next in chain, handling async results."""
        result = call_next(ctx)
        if inspect.isawaitable(result):
            result = await result
        return result

    def _bind_params(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Bind function arguments to parameter dict."""
        sig = inspect.signature(func)
        bound = sig.bind_partial(None, *args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        arguments.pop("self", None)
        return arguments

    async def _execute_sql(
        self,
        session: Any,
        meta: dict[str, Any],
        params: dict[str, Any],
    ) -> Any:
        """Execute SQL mode query."""
        sql = meta.get("sql")
        unique = meta.get("unique", False)
        paged = meta.get("paged", False)

        page_req = _extract_page_request(params, paged)
        if page_req and page_req.sorts:
            raise ValueError(
                "Dynamic sorting via PageRequest is not supported in SQL mode. "
                "Please add ORDER BY clause to your SQL string directly."
            )

        if paged:
            return await _execute_paginated_query(session, sql, params, page_req)
        return await _execute_simple_query(session, sql, params, unique)

    async def _execute_expr(
        self,
        session: Any,
        meta: dict[str, Any],
        params: dict[str, Any],
        entity: Any,
    ) -> Any:
        """Execute expression mode query."""
        expr = meta.get("expr")
        unique = meta.get("unique", False)
        paged = meta.get("paged", False)

        self._validate_entity(entity)
        base_sql = self._build_base_sql(entity, expr)

        page_req = _extract_page_request(params, paged)
        if page_req and page_req.sorts:
            valid_columns = {c.name for c in entity.__table__.columns}
            base_sql += _build_order_by_clause(page_req, valid_columns)

        if paged:
            return await _execute_paginated_query(session, base_sql, params, page_req)
        return await _execute_simple_query(session, base_sql, params, unique)

    def _validate_entity(self, entity: Any) -> None:
        """Validate that entity is properly configured."""
        if entity is None or not hasattr(entity, "__tablename__"):
            raise RuntimeError(
                "@query with expr requires @repository(entity=...) and an entity with __tablename__"
            )

    def _build_base_sql(self, entity: Any, expr: str | None) -> str:
        """Build base SQL query from entity and expression."""
        table_name = entity.__tablename__
        base_sql = f"SELECT * FROM {table_name}"
        if expr:
            base_sql += f" WHERE {expr}"
        return base_sql
