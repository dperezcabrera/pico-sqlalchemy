from typing import Any, Callable, Optional, ParamSpec, TypeVar, Set
from pico_ioc import component
import inspect

from .session import get_default_session_manager

P = ParamSpec("P")
R = TypeVar("R")

TRANSACTIONAL_META = "_pico_sqlalchemy_transactional_meta"
REPOSITORY_META = "_pico_sqlalchemy_repository_meta"
REPOSITORIES: Set[type] = set()


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

        if inspect.iscoroutinefunction(func):

            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                manager = get_default_session_manager()
                if manager is None:
                    return await func(*args, **kwargs)
                async with manager.transaction(
                    propagation=propagation,
                    read_only=read_only,
                    isolation_level=isolation_level,
                    rollback_for=rollback_for,
                    no_rollback_for=no_rollback_for,
                ):
                    return await func(*args, **kwargs)

            setattr(async_wrapper, TRANSACTIONAL_META, metadata)
            return async_wrapper

        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            raise TypeError(
                f"Cannot apply @transactional to sync function '{func.__name__}' "
                "when using an async SessionManager."
            )

        setattr(sync_wrapper, TRANSACTIONAL_META, metadata)
        return sync_wrapper

    return decorator


def repository(
    cls: Optional[type[Any]] = None,
    *,
    scope: str = "singleton",
    **kwargs: Any,
) -> Callable[[type[Any]], type[Any]] | type[Any]:
    def decorate(c: type[Any]) -> type[Any]:
        setattr(c, REPOSITORY_META, kwargs)
        REPOSITORIES.add(c)
        return component(c, scope=scope, **kwargs)

    if cls is not None:
        return decorate(cls)

    return decorate
