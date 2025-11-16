import contextvars
import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from pico_ioc import component

log = logging.getLogger(__name__)

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

    def __init__(self, session: Session):
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
        self._engine: Engine = create_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            pool_pre_ping=pool_pre_ping,
            pool_recycle=pool_recycle,
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        set_default_session_manager(self)

    @property
    def engine(self) -> Engine:
        return self._engine

    def create_session(self) -> Session:
        return self._session_factory()

    def get_current_session(self) -> Optional[Session]:
        ctx = _tx_context.get()
        return ctx.session if ctx is not None else None

    @contextmanager
    def transaction(
        self,
        propagation: str = "REQUIRED",
        read_only: bool = False,
        isolation_level: Optional[str] = None,
        rollback_for: tuple[type[BaseException], ...] = (Exception,),
        no_rollback_for: tuple[type[BaseException], ...] = (),
    ) -> Generator[Session, None, None]:
        current = _tx_context.get()
        log.debug(
            f"SessionManager.transaction: Requesting propagation={propagation}. "
            f"Current context: {'ACTIVE' if current else 'NONE'}"
        )

        if propagation == "MANDATORY":
            if current is None:
                log.error("SessionManager: MANDATORY propagation requires active transaction")
                raise RuntimeError("MANDATORY propagation requires active transaction")
            log.debug("SessionManager: MANDATORY: Active context found, yielding session.")
            yield current.session
            return

        if propagation == "NEVER":
            if current is not None:
                log.error("SessionManager: NEVER propagation forbids active transaction")
                raise RuntimeError("NEVER propagation forbids active transaction")
            log.debug("SessionManager: NEVER: No active transaction, creating session.")
            session = self.create_session()
            try:
                yield session
            finally:
                session.close()
            return

        if propagation == "NOT_SUPPORTED":
            if current is not None:
                log.debug("SessionManager: NOT_SUPPORTED: Suspending active transaction.")
                token = _tx_context.set(None)
                try:
                    session = self.create_session()
                    try:
                        yield session
                    finally:
                        session.close()
                finally:
                    log.debug("SessionManager: NOT_SUPPORTED: Resuming active transaction.")
                    _tx_context.reset(token)
            else:
                log.debug(
                    "SessionManager: NOT_SUPPORTED: No active transaction, creating session."
                )
                session = self.create_session()
                try:
                    yield session
                finally:
                    session.close()
            return

        if propagation == "SUPPORTS":
            if current is not None:
                log.debug("SessionManager: SUPPORTS: Joining active transaction.")
                yield current.session
                return
            log.debug("SessionManager: SUPPORTS: No active transaction, creating session.")
            session = self.create_session()
            try:
                yield session
            finally:
                session.close()
            return

        if propagation == "REQUIRES_NEW":
            if current is not None:
                log.debug(
                    "SessionManager: REQUIRES_NEW: Suspending current transaction."
                )
                parent_token = _tx_context.set(None)
                try:
                    with self._start_transaction(
                        read_only=read_only,
                        isolation_level=isolation_level,
                        rollback_for=rollback_for,
                        no_rollback_for=no_rollback_for,
                    ) as session:
                        yield session
                finally:
                    log.debug("SessionManager: REQUIRES_NEW: Resuming parent transaction.")
                    _tx_context.reset(parent_token)
            else:
                log.debug(
                    "SessionManager: REQUIRES_NEW: No active transaction, starting new one."
                )
                with self._start_transaction(
                    read_only=read_only,
                    isolation_level=isolation_level,
                    rollback_for=rollback_for,
                    no_rollback_for=no_rollback_for,
                ) as session:
                    yield session
            return

        if propagation == "REQUIRED":
            if current is not None:
                log.debug("SessionManager: REQUIRED: Joining active transaction.")
                yield current.session
                return
            log.debug("SessionManager: REQUIRED: No active transaction, starting new one.")
            with self._start_transaction(
                read_only=read_only,
                isolation_level=isolation_level,
                rollback_for=rollback_for,
                no_rollback_for=no_rollback_for,
            ) as session:
                yield session
            return

        raise ValueError(f"Unknown propagation: {propagation}")

    @contextmanager
    def _start_transaction(
        self,
        read_only: bool,
        isolation_level: Optional[str],
        rollback_for: tuple[type[BaseException], ...],
        no_rollback_for: tuple[type[BaseException], ...],
    ) -> Generator[Session, None, None]:
        session = self.create_session()
        log.debug(f"SessionManager._start_transaction: New transaction started. Session: {id(session)}")
        if isolation_level:
            session.connection(execution_options={"isolation_level": isolation_level})

        ctx = TransactionContext(session)
        token = _tx_context.set(ctx)
        try:
            yield session
            if not read_only:
                log.debug(f"SessionManager._start_transaction: Committing transaction. Session: {id(session)}")
                session.commit()
        except BaseException as e:
            should_rollback = isinstance(e, rollback_for) and not isinstance(
                e, no_rollback_for
            )
            if should_rollback:
                log.warning(
                    f"SessionManager._start_transaction: Rolling back transaction due to {e.__class__.__name__}. Session: {id(session)}"
                )
                session.rollback()
            else:
                log.debug(
                    f"SessionManager._start_transaction: Exception caught, but not rolling back. Session: {id(session)}"
                )
            raise
        finally:
            log.debug(f"SessionManager._start_transaction: Closing session. Session: {id(session)}")
            _tx_context.reset(token)
            session.close()


def get_session(manager: SessionManager) -> Session:
    session = manager.get_current_session()
    if session is None:
        raise RuntimeError("No active transaction")
    return session
