from typing import Any, Callable, Optional, ParamSpec, TypeVar
from pico_ioc import component, intercepted_by

P = ParamSpec("P")
R = TypeVar("R")

TRANSACTIONAL_META = "_pico_sqlalchemy_transactional_meta"
REPOSITORY_META = "_pico_sqlalchemy_repository_meta"

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

    metadata = {
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

def repository(
    cls: Optional[type[Any]] = None,
    *,
    scope: str = "singleton",
    **kwargs: Any,
) -> Callable[[type[Any]], type[Any]] | type[Any]:
    def decorate(c: type[Any]) -> type[Any]:
        setattr(c, REPOSITORY_META, kwargs)
        return component(c, scope=scope, **kwargs)

    if cls is not None:
        return decorate(cls)

    return decorate
