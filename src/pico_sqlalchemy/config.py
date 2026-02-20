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

    Implement this protocol and register the class as a ``@component``
    to have ``configure_database()`` called automatically during application
    startup, in ascending ``priority`` order.

    Typical uses include DDL creation, Alembic migrations, and seed
    data loading.

    Attributes:
        priority: Controls the execution order among multiple
            configurers.  Lower values run first.  Defaults to ``0``.

    Example::

        @component
        class SchemaSetup(DatabaseConfigurer):
            def __init__(self, base: AppBase):
                self.base = base

            @property
            def priority(self) -> int:
                return 0

            def configure_database(self, engine) -> None:
                import asyncio
                async def _create():
                    async with engine.begin() as conn:
                        await conn.run_sync(self.base.metadata.create_all)
                asyncio.run(_create())
    """

    @property
    def priority(self) -> int:
        return 0

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
    """

    url: str = "sqlite+aiosqlite:///./app.db"
    echo: bool = False
    pool_size: int = 5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
