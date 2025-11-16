import contextvars
from contextlib import asynccontextmanager
from typing import Generator, Optional, Dict, Any

from sqlalchemy import Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker
from pico_ioc import component

_tx_context: contextvars.ContextVar["TransactionContext | None"] = contextvars.ContextVar(
    "pico_sqlalchemy_tx_context", default=None
)
_default_manager: Optional["SessionManager"] = None


def set_default_session_manager(manager: "SessionManager") -> None:
    global _default_manager
    _default_manager = manager


def get_default_session_manager() -> Optional["SessionManager"]:
    return _default_manager


class TransactionContext:
    __slots__ = ("session",)

    def __init__(self, session: AsyncSession):
        self.session = session


@component(scope="singleton")
class SessionManager:
    def __init__(
        self,
        url: str,
        echo: bool = False,
        pool_size: int = 5,
        pool_pre_ping: bool = True,
        pool_recycle: int = 3600,
    ):
        engine_kwargs: Dict[str, Any] = {"echo": echo}

        is_memory_sqlite = "sqlite" in url and ":memory:" in url

        if not is_memory_sqlite:
            engine_kwargs["pool_size"] = pool_size
            engine_kwargs["pool_pre_ping"] = pool_pre_ping
            engine_kwargs["pool_recycle"] = pool_recycle

        self._engine: AsyncEngine = create_async_engine(
            url, **engine_kwargs
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        set_default_session_manager(self)

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
    ) -> Generator[AsyncSession, None, None]:
        current = _tx_context.get()

        if propagation == "MANDATORY":
            if current is None:
                raise RuntimeError("MANDATORY propagation requires active transaction")
            yield current.session
            return

        if propagation == "NEVER":
            if current is not None:
                raise RuntimeError("NEVER propagation forbids active transaction")
            session = self.create_session()
            try:
                yield session
            finally:
                await session.close()
            return

        if propagation == "NOT_SUPPORTED":
            if current is not None:
                token = _tx_context.set(None)
                try:
                    session = self.create_session()
                    try:
                        yield session
                    finally:
                        await session.close()
                finally:
                    _tx_context.reset(token)
            else:
                session = self.create_session()
                try:
                    yield session
                finally:
                    await session.close()
            return

        if propagation == "SUPPORTS":
            if current is not None:
                yield current.session
                return
            session = self.create_session()
            try:
                yield session
            finally:
                await session.close()
            return

        if propagation == "REQUIRES_NEW":
            if current is not None:
                parent_token = _tx_context.set(None)
                try:
                    async with self._start_transaction(
                        read_only=read_only,
                        isolation_level=isolation_level,
                        rollback_for=rollback_for,
                        no_rollback_for=no_rollback_for,
                    ) as session:
                        yield session
                finally:
                    _tx_context.reset(parent_token)
            else:
                async with self._start_transaction(
                    read_only=read_only,
                    isolation_level=isolation_level,
                    rollback_for=rollback_for,
                    no_rollback_for=no_rollback_for,
                ) as session:
                    yield session
            return

        if propagation == "REQUIRED":
            if current is not None:
                yield current.session
                return
            async with self._start_transaction(
                read_only=read_only,
                isolation_level=isolation_level,
                rollback_for=rollback_for,
                no_rollback_for=no_rollback_for,
            ) as session:
                yield session
            return

        raise ValueError(f"Unknown propagation: {propagation}")

    @asynccontextmanager
    async def _start_transaction(
        self,
        read_only: bool,
        isolation_level: Optional[str],
        rollback_for: tuple[type[BaseException], ...],
        no_rollback_for: tuple[type[BaseException], ...],
    ) -> Generator[AsyncSession, None, None]:
        session = self.create_session()
        if isolation_level:
            await session.connection(
                execution_options={"isolation_level": isolation_level}
            )

        ctx = TransactionContext(session)
        token = _tx_context.set(ctx)
        try:
            yield session
            if not read_only:
                await session.commit()
        except BaseException as e:
            should_rollback = isinstance(e, rollback_for) and not isinstance(
                e, no_rollback_for
            )
            if should_rollback:
                await session.rollback()
            raise
        finally:
            _tx_context.reset(token)
            await session.close()


def get_session(manager: SessionManager) -> AsyncSession:
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("No active transaction")
    return session
