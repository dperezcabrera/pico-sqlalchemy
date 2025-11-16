from typing import List
from pico_ioc import configure, factory, provides, component
from .config import DatabaseConfigurer, DatabaseSettings
from .session import SessionManager, set_default_session_manager


def _priority_of(obj):
    try:
        return int(getattr(obj, "priority", 0))
    except Exception:
        return 0


@component
class PicoSqlAlchemyLifecycle:
    @configure
    def setup_database(
        self,
        session_manager: SessionManager,
        configurers: List[DatabaseConfigurer],
    ) -> None:
        valid = [
            c
            for c in configurers
            if isinstance(c, DatabaseConfigurer)
            and callable(getattr(c, "configure", None))
        ]
        ordered = sorted(valid, key=_priority_of)
        for cfg in ordered:
            cfg.configure(session_manager.engine)


@factory
class SqlAlchemyFactory:
    @provides(SessionManager, scope="singleton")
    def create_session_manager(self, settings: DatabaseSettings) -> SessionManager:
        manager = SessionManager(
            url=settings.url,
            echo=settings.echo,
            pool_size=settings.pool_size,
            pool_pre_ping=settings.pool_pre_ping,
            pool_recycle=settings.pool_recycle,
        )
        set_default_session_manager(manager)
        return manager

