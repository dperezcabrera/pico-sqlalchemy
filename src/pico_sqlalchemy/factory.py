"""Factory and lifecycle components that wire pico-sqlalchemy into pico-ioc.

* ``SqlAlchemyFactory`` -- a ``@factory`` that creates the
  ``SessionManager`` singleton from ``DatabaseSettings``.
* ``PicoSqlAlchemyLifecycle`` -- a ``@component`` with a ``@configure``
  hook that discovers all ``DatabaseConfigurer`` implementations and
  calls their ``configure()`` methods in priority order.

These are auto-discovered when ``"pico_sqlalchemy"`` is listed in the
``modules`` argument of ``pico_ioc.init()``.
"""

from typing import List

from pico_ioc import component, configure, factory, provides

from .config import DatabaseConfigurer, DatabaseSettings
from .session import SessionManager


def _priority_of(obj):
    """Return the ``priority`` of *obj* as an ``int``, defaulting to ``0``.

    Gracefully handles missing or non-integer ``priority`` attributes.
    """
    try:
        return int(getattr(obj, "priority", 0))
    except Exception:
        return 0


@component
class PicoSqlAlchemyLifecycle:
    """Runs ``DatabaseConfigurer`` hooks during container startup.

    The ``@configure``-annotated ``setup_database`` method is called
    automatically by pico-ioc after all components have been registered.
    It collects every ``DatabaseConfigurer`` bean, sorts them by
    ``priority`` (ascending), and calls ``configure(engine)`` on each.
    """

    @configure
    def setup_database(
        self,
        session_manager: SessionManager,
        configurers: List[DatabaseConfigurer],
    ) -> None:
        """Invoke all ``DatabaseConfigurer`` hooks in priority order.

        Args:
            session_manager: The ``SessionManager`` singleton (injected).
            configurers: All ``DatabaseConfigurer`` implementations
                discovered by the container (injected as a list).
        """
        valid = [
            c for c in configurers if isinstance(c, DatabaseConfigurer) and callable(getattr(c, "configure", None))
        ]
        ordered = sorted(valid, key=_priority_of)
        for cfg in ordered:
            cfg.configure(session_manager.engine)


@factory
class SqlAlchemyFactory:
    """Factory that creates the ``SessionManager`` singleton.

    ``SessionManager`` has **no** ``@component`` decorator on its class.
    Instead, this factory uses ``@provides(SessionManager, scope="singleton")``
    to construct it from ``DatabaseSettings``.  This design ensures that
    the ``SessionManager`` constructor receives configuration values and
    that the container manages its lifecycle.
    """

    @provides(SessionManager, scope="singleton")
    def create_session_manager(self, settings: DatabaseSettings) -> SessionManager:
        """Create and return the ``SessionManager``.

        Args:
            settings: Database configuration populated from the
                ``"database"`` configuration prefix.

        Returns:
            A new ``SessionManager`` configured with the connection URL,
            pool options, and echo setting from *settings*.
        """
        manager = SessionManager(
            url=settings.url,
            echo=settings.echo,
            pool_size=settings.pool_size,
            pool_pre_ping=settings.pool_pre_ping,
            pool_recycle=settings.pool_recycle,
        )
        return manager
