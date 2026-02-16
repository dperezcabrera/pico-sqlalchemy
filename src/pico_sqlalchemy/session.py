"""Session and transaction management for pico-sqlalchemy.

This module contains the core runtime components:

* ``_tx_context`` -- a ``ContextVar`` that holds the active
  ``TransactionContext`` for the current async task.  This is **separate**
  from pico-ioc's ``"transaction"`` scope (which controls DI caching).
  ``_tx_context`` exists solely for session propagation across nested
  ``@transactional`` / ``@repository`` calls.

* ``TransactionContext`` -- lightweight wrapper around an ``AsyncSession``.

* ``SessionManager`` -- owns the ``AsyncEngine`` and session factory;
  implements all six propagation modes.  **It has no ``@component``
  decorator** -- it is instantiated by ``SqlAlchemyFactory`` via
  ``@provides(SessionManager, scope="singleton")``.

* ``get_session`` -- convenience helper to retrieve the current
  ``AsyncSession`` from the active ``TransactionContext``.
"""

import contextvars
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_tx_context: contextvars.ContextVar["TransactionContext | None"] = contextvars.ContextVar(
    "pico_sqlalchemy_tx_context", default=None
)
"""Per-async-task variable holding the active ``TransactionContext``.

This ``ContextVar`` is the mechanism used to propagate the current
``AsyncSession`` across nested service / repository calls within the
same async task.  It is **not** the same as pico-ioc's ``"transaction"``
scope -- that scope controls DI instance caching, whereas ``_tx_context``
controls SQLAlchemy session propagation and transaction boundaries.
"""


class TransactionContext:
    """Lightweight wrapper holding the ``AsyncSession`` for the current transaction.

    Stored in ``_tx_context`` so that ``get_session()`` and the interceptors
    can locate the active session without explicit parameter passing.

    Attributes:
        session: The ``AsyncSession`` bound to this transaction context.
    """

    __slots__ = ("session",)

    def __init__(self, session: AsyncSession):
        self.session = session


def _build_engine_kwargs(
    url: str,
    echo: bool,
    pool_size: int,
    pool_pre_ping: bool,
    pool_recycle: int,
) -> Dict[str, Any]:
    """Build keyword arguments for ``create_async_engine``.

    Pool-related options (``pool_size``, ``pool_pre_ping``,
    ``pool_recycle``) are omitted when the URL targets an in-memory
    SQLite database because SQLite's ``StaticPool`` does not support them.

    Args:
        url: Database connection URL (e.g.
            ``"postgresql+asyncpg://user:pass@host/db"``).
        echo: If ``True``, log all SQL statements.
        pool_size: Number of connections to keep in the pool.
        pool_pre_ping: If ``True``, test connections before use.
        pool_recycle: Seconds after which a connection is recycled.

    Returns:
        A ``dict`` of keyword arguments suitable for
        ``create_async_engine()``.
    """
    kwargs: Dict[str, Any] = {"echo": echo}
    is_memory_sqlite = "sqlite" in url and ":memory:" in url
    if not is_memory_sqlite:
        kwargs["pool_size"] = pool_size
        kwargs["pool_pre_ping"] = pool_pre_ping
        kwargs["pool_recycle"] = pool_recycle
    return kwargs


class SessionManager:
    """Owns the SQLAlchemy ``AsyncEngine`` and manages session/transaction lifecycle.

    **Important:** ``SessionManager`` does **not** carry a ``@component``
    decorator.  It is created by ``SqlAlchemyFactory`` via
    ``@provides(SessionManager, scope="singleton")`` so that construction
    is driven by ``DatabaseSettings``.

    The ``_tx_context`` ``ContextVar`` used internally is **separate** from
    pico-ioc's ``"transaction"`` scope.  ``_tx_context`` provides session
    propagation semantics (``REQUIRED``, ``REQUIRES_NEW``, etc.) that do
    not map to pico-ioc's DI scope lifecycle.

    Example::

        # Standalone (e.g. in tests)
        manager = SessionManager(url="sqlite+aiosqlite:///:memory:")

        async with manager.transaction() as session:
            session.add(User(name="Alice"))
        # session is committed and closed here

    Args:
        url: Database connection URL.
        echo: If ``True``, log all SQL statements.
        pool_size: Connection pool size (ignored for in-memory SQLite).
        pool_pre_ping: Test connections before checkout.
        pool_recycle: Recycle connections after this many seconds.
    """

    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 5,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ):
        engine_kwargs = _build_engine_kwargs(url, echo, pool_size, pool_pre_ping, pool_recycle)
        self._engine: AsyncEngine = create_async_engine(url, **engine_kwargs)
        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        """The underlying ``AsyncEngine`` instance."""
        return self._engine

    def create_session(self) -> AsyncSession:
        """Create a new, unmanaged ``AsyncSession``.

        The caller is responsible for closing the returned session.
        Prefer ``transaction()`` for managed lifecycle.

        Returns:
            A fresh ``AsyncSession`` bound to this manager's engine.
        """
        return self._session_factory()

    def get_current_session(self) -> Optional[AsyncSession]:
        """Return the ``AsyncSession`` from the active ``TransactionContext``.

        Returns:
            The current session, or ``None`` if no transaction is active.
        """
        ctx = _tx_context.get()
        return ctx.session if ctx is not None else None

    @asynccontextmanager
    async def transaction(
        self,
        propagation: str = "REQUIRED",
        read_only: bool = False,
        isolation_level: Optional[str] = None,
        rollback_for: tuple[type[BaseException], ...] = (Exception,),
        no_rollback_for: tuple[type[BaseException], ...] = (),
    ) -> AsyncGenerator[AsyncSession, None]:
        """Open a transactional context with the given propagation semantics.

        This is an async context manager that yields the ``AsyncSession``
        to use inside the transaction boundary.

        Args:
            propagation: One of ``"REQUIRED"``, ``"REQUIRES_NEW"``,
                ``"SUPPORTS"``, ``"MANDATORY"``, ``"NOT_SUPPORTED"``,
                ``"NEVER"``.
            read_only: If ``True``, skip the commit at the end of the block.
            isolation_level: Optional database isolation level
                (e.g. ``"SERIALIZABLE"``).
            rollback_for: Exception types that trigger a rollback.
            no_rollback_for: Exception types excluded from rollback even if
                they match ``rollback_for``.

        Yields:
            The ``AsyncSession`` for the transaction.

        Raises:
            RuntimeError: If ``MANDATORY`` is used without an active
                transaction, or ``NEVER`` is used with one.
            ValueError: If ``propagation`` is not a recognised mode.
        """
        current = _tx_context.get()
        tx_params = {
            "read_only": read_only,
            "isolation_level": isolation_level,
            "rollback_for": rollback_for,
            "no_rollback_for": no_rollback_for,
        }

        handler = self._get_propagation_handler(propagation)
        async for session in handler(current, tx_params):
            yield session

    def _get_propagation_handler(self, propagation: str):
        """Return the async-generator handler for *propagation*.

        Raises:
            ValueError: If *propagation* is not one of the six supported
                modes.
        """
        handlers = {
            "MANDATORY": self._propagation_mandatory,
            "NEVER": self._propagation_never,
            "NOT_SUPPORTED": self._propagation_not_supported,
            "SUPPORTS": self._propagation_supports,
            "REQUIRES_NEW": self._propagation_requires_new,
            "REQUIRED": self._propagation_required,
        }
        handler = handlers.get(propagation)
        if handler is None:
            raise ValueError(f"Unknown propagation: {propagation}")
        return handler

    async def _propagation_mandatory(self, current, tx_params):
        """MANDATORY -- fail if there is no active transaction.

        Raises:
            RuntimeError: ``"MANDATORY propagation requires active transaction"``
        """
        if current is None:
            raise RuntimeError("MANDATORY propagation requires active transaction")
        yield current.session

    async def _propagation_never(self, current, tx_params):
        """NEVER -- fail if there **is** an active transaction.

        Raises:
            RuntimeError: ``"NEVER propagation forbids active transaction"``
        """
        if current is not None:
            raise RuntimeError("NEVER propagation forbids active transaction")
        async for session in self._yield_non_transactional_session():
            yield session

    async def _propagation_not_supported(self, current, tx_params):
        """NOT_SUPPORTED -- suspend the current transaction (if any) and
        run non-transactionally."""
        if current is not None:
            _tx_context.set(None)
            try:
                async for session in self._yield_non_transactional_session():
                    yield session
            finally:
                _tx_context.set(current)
        else:
            async for session in self._yield_non_transactional_session():
                yield session

    async def _propagation_supports(self, current, tx_params):
        """SUPPORTS -- join the current transaction if one exists, otherwise
        run non-transactionally."""
        if current is not None:
            yield current.session
        else:
            async for session in self._yield_non_transactional_session():
                yield session

    async def _propagation_requires_new(self, current, tx_params):
        """REQUIRES_NEW -- suspend any current transaction and always start
        a fresh one.  The suspended transaction is restored after the new
        one completes."""
        if current is not None:
            _tx_context.set(None)
            try:
                async with self._start_transaction(**tx_params) as session:
                    yield session
            finally:
                _tx_context.set(current)
        else:
            async with self._start_transaction(**tx_params) as session:
                yield session

    async def _propagation_required(self, current, tx_params):
        """REQUIRED (default) -- join the current transaction if one exists,
        otherwise start a new one."""
        if current is not None:
            yield current.session
        else:
            async with self._start_transaction(**tx_params) as session:
                yield session

    async def _yield_non_transactional_session(self):
        """Yield a non-transactional session.

        A ``TransactionContext`` is still created so that
        ``get_session()`` works, but no ``commit`` is issued at the end.
        """
        session = self.create_session()
        old = _tx_context.get()
        _tx_context.set(TransactionContext(session))
        try:
            yield session
        finally:
            _tx_context.set(old)
            await session.close()

    @asynccontextmanager
    async def _start_transaction(
        self,
        read_only: bool,
        isolation_level: Optional[str],
        rollback_for: tuple[type[BaseException], ...],
        no_rollback_for: tuple[type[BaseException], ...],
    ) -> AsyncGenerator[AsyncSession, None]:
        """Start a brand-new transaction with the given parameters.

        The session is committed on normal exit (unless ``read_only``),
        rolled back on matching exceptions, and always closed in the
        ``finally`` block.
        """
        session = self.create_session()
        if isolation_level:
            await session.connection(execution_options={"isolation_level": isolation_level})
        old = _tx_context.get()
        _tx_context.set(TransactionContext(session))
        try:
            yield session
            if not read_only:
                await session.commit()
        except BaseException as e:
            if _should_rollback(e, rollback_for, no_rollback_for):
                await session.rollback()
            raise
        finally:
            _tx_context.set(old)
            await session.close()


def _should_rollback(
    exc: BaseException,
    rollback_for: tuple[type[BaseException], ...],
    no_rollback_for: tuple[type[BaseException], ...],
) -> bool:
    """Decide whether to rollback for the given exception.

    A rollback happens when *exc* is an instance of a type in
    *rollback_for* **and** is **not** an instance of a type in
    *no_rollback_for*.

    Args:
        exc: The exception that was raised.
        rollback_for: Tuple of exception types that trigger a rollback.
        no_rollback_for: Tuple of exception types that suppress a rollback
            even when matched by *rollback_for*.

    Returns:
        ``True`` if the transaction should be rolled back.
    """
    return isinstance(exc, rollback_for) and not isinstance(exc, no_rollback_for)


def get_session(manager: SessionManager) -> AsyncSession:
    """Return the ``AsyncSession`` from the active transaction context.

    This is the primary way repositories and services obtain the current
    session inside a ``@transactional`` or ``@repository`` boundary.

    Args:
        manager: The ``SessionManager`` to query.

    Returns:
        The ``AsyncSession`` associated with the current
        ``TransactionContext``.

    Raises:
        RuntimeError: ``"No active transaction"`` -- there is no
            ``TransactionContext`` on the current async task.  This
            typically means the calling code is not wrapped in a
            ``@transactional`` decorator or otherwise inside a
            ``manager.transaction()`` block.

    Example::

        @repository
        class UserRepository:
            def __init__(self, sm: SessionManager):
                self.sm = sm

            async def save(self, user: User) -> User:
                session = get_session(self.sm)
                session.add(user)
                return user
    """
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("No active transaction")
    return session
