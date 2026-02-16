# Database Configuration

This reference covers the database configuration extension points: the `DatabaseSettings` dataclass and the `DatabaseConfigurer` protocol. Together, they provide a consistent way to define default database connection settings and to hook into the database engine initialization to apply project-specific configuration.

## What is this?

- `DatabaseSettings` (dataclass)
  - A `@configured` dataclass that holds the database connection settings.
  - Automatically loaded from configuration sources (YAML, env, dict) via the `database` prefix.
  - Acts as the single source of truth for connection parameters (URL, pooling, echo).

- `DatabaseConfigurer` (protocol)
  - A small extension point for customizing the database engine after it is created.
  - Members:
    - `priority`: int attribute (or property) used to order multiple configurers. Lower numbers run first.
    - `configure(self, engine)`: Applies configuration to the database engine.

## 1. DatabaseSettings

The `DatabaseSettings` class is a `@configured` dataclass. It is automatically populated from your configuration source and injected where needed by the container.

### Supported Fields

The following fields map directly to the underlying SQLAlchemy `create_async_engine` parameters:

| Field | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| **`url`** | `str` | `"sqlite+aiosqlite:///./app.db"` | The SQLAlchemy connection URL (DSN). Must use an async driver (e.g., `postgresql+asyncpg`). |
| **`echo`** | `bool` | `False` | If `True`, the engine will log all SQL statements to stdout. |
| **`pool_size`** | `int` | `5` | The number of connections to keep open inside the connection pool. |
| **`pool_pre_ping`** | `bool` | `True` | If `True`, tests connections for liveness upon checkout (prevents "MySQL server has gone away" errors). |
| **`pool_recycle`** | `int` | `3600` | Recycle connections after this many seconds to prevent timeouts from the database side. |

> **Note:** `pool_size`, `pool_pre_ping`, and `pool_recycle` are ignored if using SQLite with `:memory:`.

### Providing Settings

Settings are loaded automatically from a configuration source with the `database` prefix:

```python
from pico_ioc import init, configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "postgresql+asyncpg://user:pass@localhost:5432/dbname",
        "echo": True,
        "pool_size": 10,
    }
}))

container = init(modules=["pico_sqlalchemy", "myapp"], config=config)
```

Or via YAML:

```yaml
# application.yaml
database:
  url: postgresql+asyncpg://user:pass@localhost:5432/dbname
  echo: false
  pool_size: 10
  pool_pre_ping: true
  pool_recycle: 3600
```

## 2. DatabaseConfigurer

Create one or more classes that implement the `DatabaseConfigurer` protocol to apply engine-level behavior customization.

**Ordering:** Configurers are executed in **ascending order** based on their `priority` attribute. Lower numbers run first.

### Example: Enable SQL Echo (Dynamic)

```python
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer

@component
class EnableSqlEcho(DatabaseConfigurer):
    priority = 10  # Runs early

    def configure(self, engine):
        engine.echo = True
```

### Example: SQLite Pragmas

```python
from sqlalchemy import event
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer

@component
class SQLitePragmaConfigurer(DatabaseConfigurer):
    priority = 50  # Runs after basic setup

    def configure(self, engine):
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
```

### Example: Create Tables on Startup

```python
import asyncio
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer, AppBase

@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 100

    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        async def init_schema():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        asyncio.run(init_schema())
```

## 3. Initialization Logic

The startup sequence involves two separate components:

1. **`SqlAlchemyFactory`** creates the `SessionManager` singleton from `DatabaseSettings` (creates the `AsyncEngine` and session factory).
2. **`PicoSqlAlchemyLifecycle`** (via `@configure`) collects all `DatabaseConfigurer` implementations, sorts them by `priority` (ascending), and calls `configure(engine)` on each.

This ensures that your specific database tuning (like pragmas or connection pool listeners) is applied reliably before the application starts accepting traffic.
