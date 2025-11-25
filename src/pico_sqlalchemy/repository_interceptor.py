import inspect
from typing import Any, Callable, Mapping

from pico_ioc import MethodCtx, MethodInterceptor, component
from sqlalchemy import text

from .decorators import QUERY_META, REPOSITORY_META
from .session import SessionManager, get_session
from .paging import Page, PageRequest


@component
class RepositoryQueryInterceptor(MethodInterceptor):
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def invoke(self, ctx: MethodCtx, call_next: Callable[[MethodCtx], Any]) -> Any:
        func = getattr(ctx.cls, ctx.name, None)
        meta = getattr(func, QUERY_META, None)
        if meta is None:
            result = call_next(ctx)
            if inspect.isawaitable(result):
                result = await result
            return result
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

    def _bind_params(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: Mapping[str, Any],
    ) -> dict[str, Any]:
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
        sql = meta.get("sql")
        unique = meta.get("unique", False)
        paged = meta.get("paged", False)
        page_req = None
        if paged:
            page_req = params.pop("page", None)
            if not isinstance(page_req, PageRequest):
                raise TypeError("Paged SQL query requires a 'page: PageRequest' parameter")
        if paged:
            count_sql = f"SELECT COUNT(*) FROM ({sql}) AS sub"
            total_result = await session.execute(text(count_sql), params)
            total = total_result.scalar_one()
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
        result = await session.execute(text(sql), params)
        rows = result.mappings().all()
        if unique:
            return rows[0] if rows else None
        return rows

    async def _execute_expr(
        self,
        session: Any,
        meta: dict[str, Any],
        params: dict[str, Any],
        entity: Any,
    ) -> Any:
        expr = meta.get("expr")
        unique = meta.get("unique", False)
        paged = meta.get("paged", False)
        if entity is None or not hasattr(entity, "__tablename__"):
            raise RuntimeError(
                "@query with expr requires @repository(entity=...) and an entity with __tablename__"
            )
        table_name = entity.__tablename__
        base_sql = f"SELECT * FROM {table_name}"
        if expr:
            base_sql += f" WHERE {expr}"
        
        page_req = None
        if paged:
            page_req = params.pop("page", None)
            if not isinstance(page_req, PageRequest):
                raise TypeError("Paged expr query requires a 'page: PageRequest' parameter")

        if page_req and page_req.sorts:
            valid_columns = {c.name for c in entity.__table__.columns}
            sort_parts = []
            for s in page_req.sorts:
                if s.field not in valid_columns:
                    raise ValueError(f"Invalid sort field: {s.field}")
                direction = "DESC" if s.direction.upper() == "DESC" else "ASC"
                sort_parts.append(f"{s.field} {direction}")
            if sort_parts:
                base_sql += " ORDER BY " + ", ".join(sort_parts)

        if paged:
            count_sql = f"SELECT COUNT(*) FROM ({base_sql}) AS sub"
            total_result = await session.execute(text(count_sql), params)
            total = total_result.scalar_one()
            paginated_sql = f"{base_sql} LIMIT :_limit OFFSET :_offset"
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
        result = await session.execute(text(base_sql), params)
        rows = result.mappings().all()
        if unique:
            return rows[0] if rows else None
        return rows