"""Decorators for declarative transaction management and query execution.

* ``@transactional`` -- marks a method for AOP transaction wrapping.
* ``@repository`` -- marks a class as a repository; all public async
  methods get implicit read-write transactions.
* ``@query`` / ``@query.sql`` -- declares a method whose body is
  replaced by an automatically executed SQL or expression query.

Metadata constants (``TRANSACTIONAL_META``, ``REPOSITORY_META``,
``QUERY_META``) are used by the interceptors to discover decorator
configuration at runtime.
"""

import inspect
from typing import Any, Callable, Optional, ParamSpec, TypeVar

from pico_ioc import component, intercepted_by

P = ParamSpec("P")
R = TypeVar("R")

TRANSACTIONAL_META = "_pico_sqlalchemy_transactional_meta"
"""Attribute name used to store ``@transactional`` metadata on a method."""

REPOSITORY_META = "_pico_sqlalchemy_repository_meta"
"""Attribute name used to store ``@repository`` metadata on a class."""

QUERY_META = "_pico_sqlalchemy_query_meta"
"""Attribute name used to store ``@query`` metadata on a method."""


def transactional(
    _func: Optional[Callable[P, R]] = None,
    *,
    propagation: str = "REQUIRED",
    read_only: bool = False,
    isolation_level: Optional[str] = None,
    rollback_for: tuple[type[BaseException], ...] = (Exception,),
    no_rollback_for: tuple[type[BaseException], ...] = (),
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """Mark a method for declarative transaction management.

    Can be used with or without parentheses::

        @transactional
        async def method_a(self): ...

        @transactional(propagation="REQUIRES_NEW", read_only=True)
        async def method_b(self): ...

    The decorated method is wrapped by ``TransactionalInterceptor`` via
    pico-ioc's AOP system (``@intercepted_by``).

    Args:
        _func: The decorated function (when used without parentheses).
            Do **not** pass this explicitly.
        propagation: Transaction propagation mode.  One of
            ``"REQUIRED"``, ``"REQUIRES_NEW"``, ``"SUPPORTS"``,
            ``"MANDATORY"``, ``"NOT_SUPPORTED"``, ``"NEVER"``.
        read_only: If ``True``, the transaction is not committed at the
            end of the block.
        isolation_level: Optional database isolation level string
            (e.g. ``"SERIALIZABLE"``).
        rollback_for: Tuple of exception types that trigger a rollback.
        no_rollback_for: Tuple of exception types excluded from rollback.

    Returns:
        The decorated function (or a decorator if called with
        parentheses).

    Raises:
        ValueError: ``"Invalid propagation: <value>"`` if *propagation*
            is not one of the six supported modes.

    Example::

        @component
        class OrderService:
            @transactional(propagation="REQUIRES_NEW")
            async def place_order(self, order: Order) -> Order:
                ...
    """
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

    if _func is not None:
        return decorator(_func)
    return decorator


def query(
    expr: str | None = None,
    *,
    sql: str | None = None,
    paged: bool = False,
    unique: bool = False,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Declare a method as an automatically executed query.

    The method body is **never called**.  Instead,
    ``RepositoryQueryInterceptor`` builds and executes a SQL query from
    the decorator arguments, binding method parameters automatically.

    Two mutually exclusive modes are available:

    * **Expression mode** (``expr=...``) -- generates
      ``SELECT * FROM <table> WHERE <expr>``.  Requires
      ``@repository(entity=Model)`` on the class.
    * **SQL mode** (``sql=...``) -- executes the raw SQL string.
      Does **not** require an entity binding.

    A shorthand ``@query.sql("SELECT ...")`` is available for SQL mode.

    Args:
        expr: A WHERE-clause expression with ``:param`` placeholders
            (e.g. ``"username = :username"``).
        sql: A complete SQL query string.
        paged: If ``True``, the method must accept a ``page: PageRequest``
            parameter and returns a ``Page`` result.
        unique: If ``True``, return only the first matching row (or
            ``None``).  Ignored when ``paged=True``.

    Returns:
        A decorator that attaches query metadata and registers the
        ``TransactionalInterceptor`` and ``RepositoryQueryInterceptor``.

    Raises:
        ValueError: If neither *expr* nor *sql* is provided, or if both
            are provided.

    Example::

        @repository(entity=User)
        class UserRepository:
            @query(expr="email = :email", unique=True)
            async def find_by_email(self, email: str) -> User | None:
                ...  # body is never executed

            @query.sql("SELECT * FROM users WHERE active = true", paged=True)
            async def find_active(self, page: PageRequest) -> Page:
                ...
    """
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
        from .interceptor import TransactionalInterceptor
        from .repository_interceptor import RepositoryQueryInterceptor

        step_1 = intercepted_by(TransactionalInterceptor)(func)
        return intercepted_by(RepositoryQueryInterceptor)(step_1)

    return decorator


def _query_sql(sql_text: str, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Shorthand for ``query(sql=sql_text, ...)``.

    Attached as ``query.sql`` so that callers can write::

        @query.sql("SELECT * FROM users WHERE active = true")
        async def find_active(self): ...

    Args:
        sql_text: The raw SQL query string.
        **kwargs: Forwarded to ``query()`` (e.g. ``paged``, ``unique``).

    Returns:
        A decorator (same as ``query(sql=...)``.
    """
    return query(expr=None, sql=sql_text, **kwargs)


setattr(query, "sql", _query_sql)


def repository(
    cls: Optional[type[Any]] = None,
    *,
    scope: str = "singleton",
    **kwargs: Any,
) -> Callable[[type[Any]], type[Any]] | type[Any]:
    """Mark a class as a repository with implicit transactions.

    The decorator:

    1. Stores repository metadata (including ``entity``) on the class.
    2. Wraps every public async method with
       ``@intercepted_by(TransactionalInterceptor)`` so that each call
       runs inside a ``REQUIRED`` read-write transaction by default.
    3. Registers the class as a pico-ioc ``@component``.

    Can be used with or without parentheses::

        @repository
        class SimpleRepo: ...

        @repository(entity=User, scope="singleton")
        class UserRepo: ...

    Args:
        cls: The class being decorated (when used without parentheses).
        scope: The pico-ioc scope for the component
            (default ``"singleton"``).
        **kwargs: Additional metadata stored on the class.  The most
            important keyword is ``entity`` -- the SQLAlchemy model class
            required for ``@query(expr=...)`` methods.

    Returns:
        The decorated class (registered as a component), or a decorator
        if called with keyword arguments.

    Example::

        @repository(entity=User)
        class UserRepository:
            def __init__(self, sm: SessionManager):
                self.sm = sm

            async def save(self, user: User) -> User:
                session = get_session(self.sm)
                session.add(user)
                return user
    """
    def decorate(c: type[Any]) -> type[Any]:
        setattr(c, REPOSITORY_META, kwargs)
        from .interceptor import TransactionalInterceptor

        for name, method in inspect.getmembers(c):
            if name.startswith("_"):
                continue

            if inspect.iscoroutinefunction(method):
                wrapped_method = intercepted_by(TransactionalInterceptor)(method)
                setattr(c, name, wrapped_method)

        return component(c, scope=scope)

    if cls is not None:
        return decorate(cls)

    return decorate
