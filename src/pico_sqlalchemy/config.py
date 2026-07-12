"""Database configuration types for pico-sqlalchemy.

* ``DatabaseSettings`` -- a ``@configured`` dataclass that is
  automatically populated from the ``"database"`` configuration prefix.
* ``DatabaseConfigurer`` -- a protocol for hooks that run against the
  ``AsyncEngine`` during startup (e.g. table creation, migrations).
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pico_ioc import configured


@runtime_checkable
class DatabaseConfigurer(Protocol):
    """Protocol for database startup hooks.

    Any ``@component`` with a ``configure_database(engine)`` method is
    collected and called during application startup — subclassing this
    protocol is optional. Hooks always run OFF the event loop (on a worker
    thread when the container boots under an ASGI server), so the
    ``asyncio.run()`` pattern below is safe in every context.

    Typical uses include DDL creation, Alembic migrations, and seed
    data loading.

    An optional ``priority`` attribute (int, default ``0``) controls the
    execution order among multiple configurers; lower values run first.

    Example::

        @component
        class SchemaSetup:
            def __init__(self, base: AppBase):
                self.base = base

            def configure_database(self, engine) -> None:
                import asyncio
                async def _create():
                    async with engine.begin() as conn:
                        await conn.run_sync(self.base.metadata.create_all)
                    await engine.dispose()  # asyncpg pools are loop-bound
                asyncio.run(_create())
    """

    def configure_database(self, engine) -> None:
        """Run configuration against the given ``AsyncEngine``.

        Args:
            engine: The ``AsyncEngine`` created by ``SessionManager``.
        """
        raise NotImplementedError


@configured(target="self", prefix="database", mapping="tree")
@dataclass
class DatabaseSettings:
    """Type-safe database connection settings.

    Populated automatically from the ``"database"`` configuration prefix
    via pico-ioc's ``@configured`` mechanism.  For example, with a
    ``DictSource``::

        configuration(DictSource({
            "database": {
                "url": "postgresql+asyncpg://user:pass@host/db",
                "echo": False,
                "pool_size": 10,
            }
        }))

    Attributes:
        url: SQLAlchemy connection URL (default: in-memory SQLite).
        echo: Log all SQL statements if ``True``.
        pool_size: Connection pool size.
        pool_pre_ping: Test connections before checkout.
        pool_recycle: Recycle connections after this many seconds.
        migrations_path: Alembic script directory (the one containing
            ``env.py``). Empty string (default) disables startup
            migrations. Requires ``pico-sqlalchemy[migrations]``.
        migrations_target: Alembic revision to upgrade to on startup.
    """

    url: str = "sqlite+aiosqlite:///./app.db"
    echo: bool = False
    pool_size: int = 5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    migrations_path: str = ""
    migrations_target: str = "head"
