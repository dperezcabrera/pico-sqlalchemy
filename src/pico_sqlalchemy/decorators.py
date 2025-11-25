from typing import Any, Callable, Optional, ParamSpec, TypeVar
from pico_ioc import component, intercepted_by

P = ParamSpec("P")
R = TypeVar("R")

TRANSACTIONAL_META = "_pico_sqlalchemy_transactional_meta"
REPOSITORY_META = "_pico_sqlalchemy_repository_meta"
QUERY_META = "_pico_sqlalchemy_query_meta"


def transactional(
    *,
    propagation: str = "REQUIRED",
    read_only: bool = False,
    isolation_level: Optional[str] = None,
    rollback_for: tuple[type[BaseException], ...] = (Exception,),
    no_rollback_for: tuple[type[BaseException], ...] = (),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    valid = {
        "REQUIRED",
        "REQUIRES_NEW",
        "SUPPORTS",
        "MANDATORY",
        "NOT_SUPPORTED",
        "NEVER",
    }
    if propagation not in valid:
        raise ValueError(f"Invalid propagation: {propagation}")
    metadata: dict[str, Any] = {
        "propagation": propagation,
        "read_only": read_only,
        "isolation_level": isolation_level,
        "rollback_for": rollback_for,
        "no_rollback_for": no_rollback_for,
    }

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        setattr(func, TRANSACTIONAL_META, metadata)
        from .interceptor import TransactionalInterceptor
        return intercepted_by(TransactionalInterceptor)(func)

    return decorator


def query(
    expr: str | None = None,
    *,
    sql: str | None = None,
    paged: bool = False,
    unique: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if expr is None and sql is None:
        raise ValueError("query decorator requires either 'expr' or 'sql'")
    if expr is not None and sql is not None:
        raise ValueError("query decorator cannot use both 'expr' and 'sql'")

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        mode = "sql" if sql is not None else "expr"
        meta: dict[str, Any] = {
            "mode": mode,
            "expr": expr,
            "sql": sql,
            "paged": paged,
            "unique": unique,
        }
        setattr(func, QUERY_META, meta)
        from .repository_interceptor import RepositoryQueryInterceptor
        return intercepted_by(RepositoryQueryInterceptor)(func)

    return decorator


def _query_sql(sql_text: str, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    return query(expr=None, sql=sql_text, **kwargs)


setattr(query, "sql", _query_sql)


def repository(
    cls: Optional[type[Any]] = None,
    *,
    scope: str = "singleton",
    **kwargs: Any,
) -> Callable[[type[Any]], type[Any]] | type[Any]:
    def decorate(c: type[Any]) -> type[Any]:
        setattr(c, REPOSITORY_META, kwargs)
        return component(c, scope=scope)

    if cls is not None:
        return decorate(cls)

    return decorate
