"""AOP interceptor that executes declarative ``@query`` methods.

``RepositoryQueryInterceptor`` is the second link in the interceptor
chain for ``@query``-decorated methods.  By the time it runs, the
``TransactionalInterceptor`` has already ensured that a transaction
(and therefore an ``AsyncSession``) is active.

Two execution modes are supported:

* **Expression mode** (``@query(expr="...")``) -- generates
  ``SELECT * FROM <table> WHERE <expr>`` using the entity's
  ``__tablename__``.  Dynamic sorting via ``PageRequest.sorts`` is
  validated against the entity's column set to prevent injection.

* **SQL mode** (``@query(sql="...")``) -- executes the raw SQL string
  verbatim.  Dynamic sorting is **not** supported in this mode to
  prevent SQL injection.

Both modes support pagination (``paged=True``) with automatic
``COUNT(*)`` and ``LIMIT``/``OFFSET`` handling.
"""

import inspect
from typing import Any, Callable, Mapping

from pico_ioc import MethodCtx, MethodInterceptor, component
from sqlalchemy import text

from .decorators import QUERY_META, REPOSITORY_META
from .paging import Page, PageRequest
from .session import SessionManager, get_session


def _extract_page_request(params: dict[str, Any], paged: bool) -> PageRequest | None:
    """Extract and validate a ``PageRequest`` from *params*.

    When *paged* is ``True``, the parameter named ``"page"`` is popped
    from *params* and validated.

    Args:
        params: Bound method arguments (mutable -- ``"page"`` is removed).
        paged: Whether the query is paginated.

    Returns:
        The ``PageRequest`` instance, or ``None`` if *paged* is ``False``.

    Raises:
        TypeError: ``"Paged query requires a 'page: PageRequest'
            parameter"`` -- the ``"page"`` parameter is missing or is
            not a ``PageRequest``.
    """
    if not paged:
        return None
    page_req = params.pop("page", None)
    if not isinstance(page_req, PageRequest):
        raise TypeError("Paged query requires a 'page: PageRequest' parameter")
    return page_req


def _build_order_by_clause(page_req: PageRequest, valid_columns: set[str]) -> str:
    """Build an ``ORDER BY`` clause from ``PageRequest.sorts``.

    Each ``Sort.field`` is validated against *valid_columns* to prevent
    SQL injection.

    Args:
        page_req: The page request containing sort specifications.
        valid_columns: Set of allowed column names (from the entity's
            ``__table__.columns``).

    Returns:
        A string like ``" ORDER BY name ASC, id DESC"`` or ``""`` if
        there are no sorts.

    Raises:
        ValueError: ``"Invalid sort field: <field>"`` -- the requested
            sort field is not in *valid_columns*.
    """
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
    """Execute a ``COUNT(*)`` wrapper around *sql* and return the total.

    Args:
        session: The active ``AsyncSession``.
        sql: The base SQL query (without LIMIT/OFFSET).
        params: Bind parameters for the query.

    Returns:
        The total number of matching rows.
    """
    count_sql = f"SELECT COUNT(*) FROM ({sql}) AS sub"
    result = await session.execute(text(count_sql), params)
    return result.scalar_one()


async def _execute_paginated_query(
    session: Any,
    sql: str,
    params: dict[str, Any],
    page_req: PageRequest,
) -> Page:
    """Execute a paginated query and return a ``Page`` result.

    Internally runs a ``COUNT(*)`` sub-query for the total, then appends
    ``LIMIT`` and ``OFFSET`` to fetch the requested page.

    Args:
        session: The active ``AsyncSession``.
        sql: The base SQL query (may already include ``ORDER BY``).
        params: Bind parameters for the query.
        page_req: Pagination parameters (page number, page size).

    Returns:
        A ``Page`` containing the result rows, total element count,
        current page number, and page size.
    """
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
    """Execute a non-paginated query.

    Args:
        session: The active ``AsyncSession``.
        sql: The SQL query string.
        params: Bind parameters for the query.
        unique: If ``True``, return the first row (or ``None``).
            If ``False``, return all rows as a list.

    Returns:
        A single ``RowMapping`` (or ``None``) when *unique* is ``True``,
        otherwise a list of ``RowMapping`` objects.
    """
    result = await session.execute(text(sql), params)
    rows = result.mappings().all()
    if unique:
        return rows[0] if rows else None
    return rows


@component
class RepositoryQueryInterceptor(MethodInterceptor):
    """Executes declarative queries for ``@query``-decorated methods.

    This interceptor runs **after** ``TransactionalInterceptor`` in the
    AOP chain.  It checks for ``QUERY_META`` on the target method; if
    absent, it simply delegates to ``call_next``.  When present, the
    method body is **never executed** -- instead the interceptor builds
    and runs the SQL query, binding method parameters automatically.

    Two execution modes:

    * ``expr`` -- generates ``SELECT * FROM <table> WHERE <expr>`` using
      the entity from ``@repository(entity=...)``.
    * ``sql`` -- executes the provided raw SQL verbatim.

    Both modes support pagination (``paged=True``) and unique result
    (``unique=True``).

    Args:
        session_manager: The ``SessionManager`` singleton, used to
            obtain the current ``AsyncSession`` via ``get_session()``.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def invoke(self, ctx: MethodCtx, call_next: Callable[[MethodCtx], Any]) -> Any:
        """Intercept the method and execute the declarative query if applicable.

        Args:
            ctx: The AOP method context.
            call_next: Callback to the next interceptor or the original
                method.

        Returns:
            Query results -- a ``Page``, a list of ``RowMapping``, or a
            single ``RowMapping`` / ``None`` depending on query options.

        Raises:
            RuntimeError: ``"@query with expr requires @repository(entity=...)"``
                if expression mode is used without an entity.
            TypeError: ``"Paged query requires a 'page: PageRequest' parameter"``
                if ``paged=True`` but no ``PageRequest`` argument is found.
            ValueError: ``"Dynamic sorting via PageRequest is not supported
                in SQL mode"`` if sorts are provided in SQL mode.
            ValueError: ``"Invalid sort field: <field>"`` if a sort field
                is not a valid column on the entity.
        """
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
        """Invoke the next interceptor or method, awaiting if needed."""
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
        """Bind positional and keyword arguments to a named parameter dict.

        Uses ``inspect.signature`` to map *args* and *kwargs* onto the
        method's declared parameters (excluding ``self``).

        Args:
            func: The original method (unbound).
            args: Positional arguments from the invocation.
            kwargs: Keyword arguments from the invocation.

        Returns:
            A ``dict`` mapping parameter names to their values, suitable
            for use as SQLAlchemy bind parameters.
        """
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
        """Execute a raw-SQL-mode query.

        Dynamic sorting via ``PageRequest.sorts`` is rejected in this
        mode to prevent SQL injection.

        Raises:
            ValueError: If ``PageRequest.sorts`` is non-empty.
        """
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
        """Execute an expression-mode query.

        Builds ``SELECT * FROM <table> WHERE <expr>`` using the entity's
        ``__tablename__``.  Dynamic sorting is supported and validated
        against the entity's column set.

        Raises:
            RuntimeError: If *entity* is ``None`` or lacks
                ``__tablename__``.
            ValueError: If a sort field is not a valid column.
        """
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
        """Ensure *entity* is set and has a ``__tablename__`` attribute.

        Raises:
            RuntimeError: ``"@query with expr requires @repository(entity=...)
                and an entity with __tablename__"``
        """
        if entity is None or not hasattr(entity, "__tablename__"):
            raise RuntimeError("@query with expr requires @repository(entity=...) and an entity with __tablename__")

    def _build_base_sql(self, entity: Any, expr: str | None) -> str:
        """Build the base ``SELECT`` query from the entity and optional expression.

        Args:
            entity: The SQLAlchemy model class (must have ``__tablename__``).
            expr: Optional WHERE-clause expression (e.g. ``"name = :name"``).

        Returns:
            A SQL string like ``"SELECT * FROM users WHERE name = :name"``.
        """
        table_name = entity.__tablename__
        base_sql = f"SELECT * FROM {table_name}"
        if expr:
            base_sql += f" WHERE {expr}"
        return base_sql
