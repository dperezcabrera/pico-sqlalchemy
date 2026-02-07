import contextvars
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

_tx_context: contextvars.ContextVar["TransactionContext | None"] = contextvars.ContextVar(
    "pico_sqlalchemy_tx_context", default=None
)


class TransactionContext:
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
    """Build engine kwargs, excluding pool options for in-memory SQLite."""
    kwargs: Dict[str, Any] = {"echo": echo}
    is_memory_sqlite = "sqlite" in url and ":memory:" in url
    if not is_memory_sqlite:
        kwargs["pool_size"] = pool_size
        kwargs["pool_pre_ping"] = pool_pre_ping
        kwargs["pool_recycle"] = pool_recycle
    return kwargs


class SessionManager:
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
        return self._engine

    def create_session(self) -> AsyncSession:
        return self._session_factory()

    def get_current_session(self) -> Optional[AsyncSession]:
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
        """Manage transaction with specified propagation behavior."""
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
        """Get the handler for the specified propagation mode."""
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
        """MANDATORY: Must have active transaction."""
        if current is None:
            raise RuntimeError("MANDATORY propagation requires active transaction")
        yield current.session

    async def _propagation_never(self, current, tx_params):
        """NEVER: Must NOT have active transaction."""
        if current is not None:
            raise RuntimeError("NEVER propagation forbids active transaction")
        async for session in self._yield_non_transactional_session():
            yield session

    async def _propagation_not_supported(self, current, tx_params):
        """NOT_SUPPORTED: Suspend current transaction if exists."""
        if current is not None:
            token = _tx_context.set(None)
            try:
                async for session in self._yield_non_transactional_session():
                    yield session
            finally:
                _tx_context.reset(token)
        else:
            async for session in self._yield_non_transactional_session():
                yield session

    async def _propagation_supports(self, current, tx_params):
        """SUPPORTS: Use current transaction if exists, otherwise non-transactional."""
        if current is not None:
            yield current.session
        else:
            async for session in self._yield_non_transactional_session():
                yield session

    async def _propagation_requires_new(self, current, tx_params):
        """REQUIRES_NEW: Always create new transaction."""
        if current is not None:
            parent_token = _tx_context.set(None)
            try:
                async with self._start_transaction(**tx_params) as session:
                    yield session
            finally:
                _tx_context.reset(parent_token)
        else:
            async with self._start_transaction(**tx_params) as session:
                yield session

    async def _propagation_required(self, current, tx_params):
        """REQUIRED: Join current transaction or create new one."""
        if current is not None:
            yield current.session
        else:
            async with self._start_transaction(**tx_params) as session:
                yield session

    async def _yield_non_transactional_session(self):
        """Yield a non-transactional session."""
        session = self.create_session()
        ctx = TransactionContext(session)
        token = _tx_context.set(ctx)
        try:
            yield session
        finally:
            _tx_context.reset(token)
            await session.close()

    @asynccontextmanager
    async def _start_transaction(
        self,
        read_only: bool,
        isolation_level: Optional[str],
        rollback_for: tuple[type[BaseException], ...],
        no_rollback_for: tuple[type[BaseException], ...],
    ) -> AsyncGenerator[AsyncSession, None]:
        """Start a new transaction with the given parameters."""
        session = self.create_session()
        if isolation_level:
            await session.connection(execution_options={"isolation_level": isolation_level})
        ctx = TransactionContext(session)
        token = _tx_context.set(ctx)
        try:
            yield session
            if not read_only:
                await session.commit()
        except BaseException as e:
            if _should_rollback(e, rollback_for, no_rollback_for):
                await session.rollback()
            raise
        finally:
            _tx_context.reset(token)
            await session.close()


def _should_rollback(
    exc: BaseException,
    rollback_for: tuple[type[BaseException], ...],
    no_rollback_for: tuple[type[BaseException], ...],
) -> bool:
    """Determine if the transaction should be rolled back for the given exception."""
    return isinstance(exc, rollback_for) and not isinstance(exc, no_rollback_for)


def get_session(manager: SessionManager) -> AsyncSession:
    """Get the current session from the active transaction."""
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("No active transaction")
    return session
