# How to Configure Multiple Database Connections

pico-sqlalchemy supports multiple database connections by creating separate `SessionManager` instances via custom factories. Each database gets its own configuration, engine, session factory, and (optionally) its own repositories.

---

## Architecture Overview

```text
Container
  |
  +-- SqlAlchemyFactory (default)
  |     +-- @provides(SessionManager)   <-- "primary" database
  |
  +-- SecondaryDbFactory (your code)
        +-- @provides(SecondarySessionManager)  <-- "secondary" database
```

Each database has:

1. Its own `DatabaseSettings`-like configuration.
2. Its own `SessionManager` instance (or a subclass / alias).
3. Its own repositories that inject the correct manager.

---

## Step 1: Define a Secondary SessionManager Type

Create a distinct type so pico-ioc can differentiate the two managers:

```python
from pico_sqlalchemy import SessionManager


class SecondarySessionManager(SessionManager):
    """SessionManager for the secondary database.

    This subclass exists solely for type-based DI disambiguation.
    It inherits all behavior from SessionManager.
    """
    pass
```

## Step 2: Define Secondary Settings

```python
from dataclasses import dataclass
from pico_ioc import configured


@configured(target="self", prefix="database_secondary", mapping="tree")
@dataclass
class SecondaryDatabaseSettings:
    url: str = "sqlite+aiosqlite:///./secondary.db"
    echo: bool = False
    pool_size: int = 5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
```

## Step 3: Create a Factory

```python
from pico_ioc import factory, provides


@factory
class SecondaryDbFactory:
    @provides(SecondarySessionManager, scope="singleton")
    def create_secondary_manager(
        self, settings: SecondaryDatabaseSettings
    ) -> SecondarySessionManager:
        return SecondarySessionManager(
            url=settings.url,
            echo=settings.echo,
            pool_size=settings.pool_size,
            pool_pre_ping=settings.pool_pre_ping,
            pool_recycle=settings.pool_recycle,
        )
```

## Step 4: Provide Configuration

```python
from pico_ioc import configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "postgresql+asyncpg://user:pass@primary-host/primary_db",
        "echo": False,
        "pool_size": 10,
    },
    "database_secondary": {
        "url": "postgresql+asyncpg://user:pass@secondary-host/secondary_db",
        "echo": False,
        "pool_size": 5,
    },
}))
```

## Step 5: Create Repositories for Each Database

### Primary Database Repository

```python
from pico_sqlalchemy import repository, get_session, SessionManager


@repository(entity=User)
class UserRepository:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    async def save(self, user: User) -> User:
        session = get_session(self.sm)
        session.add(user)
        return user
```

### Secondary Database Repository

```python
from pico_sqlalchemy import repository, get_session


@repository(entity=AuditLog)
class AuditRepository:
    def __init__(self, sm: SecondarySessionManager):
        # Injects the secondary manager by type
        self.sm = sm

    async def log(self, entry: AuditLog) -> AuditLog:
        session = get_session(self.sm)
        session.add(entry)
        return entry
```

## Step 6: Schema Setup for Both Databases

```python
import asyncio
from pico_ioc import component
from pico_sqlalchemy import AppBase, DatabaseConfigurer


@component
class PrimarySchemaSetup(DatabaseConfigurer):
    def __init__(self, base: AppBase):
        self.base = base

    @property
    def priority(self) -> int:
        return 0

    def configure(self, engine) -> None:
        async def run():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        asyncio.run(run())
```

For the secondary database, you may need to call `configure()` manually or create a separate lifecycle component that is wired to `SecondarySessionManager`.

---

## Step 7: Wire It Up

```python
from pico_ioc import init

container = init(
    modules=["pico_sqlalchemy", "my_app"],
    config=config,
)
```

pico-ioc resolves each repository's constructor parameter by type:

- `SessionManager` --> primary database
- `SecondarySessionManager` --> secondary database

---

## Alternative: Using `Qualifier`

If you prefer not to subclass `SessionManager`, use pico-ioc's `Qualifier`:

```python
from typing import Annotated
from pico_ioc import Qualifier

@repository(entity=AuditLog)
class AuditRepository:
    def __init__(
        self,
        sm: Annotated[SessionManager, Qualifier("secondary")],
    ):
        self.sm = sm
```

And in the factory:

```python
@factory
class SecondaryDbFactory:
    @provides(SessionManager, scope="singleton", qualifier="secondary")
    def create(self, settings: SecondaryDatabaseSettings) -> SessionManager:
        return SessionManager(url=settings.url, ...)
```

---

## Notes

- Each `SessionManager` has its own `AsyncEngine` and connection pool.
- Transaction propagation via `_tx_context` is per-async-task, so transactions from different managers do **not** interfere.
- For Alembic with multiple databases, maintain separate `alembic.ini` and `env.py` configurations per database (see [Alembic Guide](alembic.md)).
