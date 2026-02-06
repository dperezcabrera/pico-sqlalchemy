# Database Configuration

This reference covers the database configuration extension points exposed by the project: the `DatabaseConfigurer` protocol and the `DatabaseSettings` dataclass. Together, they provide a consistent way to define default database connection settings and to hook into the database engine initialization to apply project-specific configuration.

## What is this?

- `DatabaseSettings` (dataclass)
  - Holds the database connection settings for the project.
  - Annotated with pico_ioc metadata so it can be provided via dependency injection.
  - Acts as the single source of truth for connection parameters (URL, pooling, echo).

- `DatabaseConfigurer` (protocol)
  - A small extension point for customizing the database engine after it is created.
  - Methods:
    - `priority(self)`: Returns a numeric value used to order multiple configurers.
    - `configure(self, engine)`: Applies configuration to the database engine.

## 1. DatabaseSettings

The `DatabaseSettings` class is a standard Python dataclass used to configure the `SessionManager`. You should register an instance of this class in your container.

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

### Example Registration

Create and register a `DatabaseSettings` instance that reflects your environment.

```python
from pico_ioc import Container
from pico_sqlalchemy import DatabaseSettings

container = Container()

# Construct settings using flat arguments (not a dict)
settings = DatabaseSettings(
    url="postgresql+asyncpg://user:pass@localhost:5432/dbname",
    echo=True,
    pool_size=10,
    pool_pre_ping=True
)

# Make the settings available for injection
container.register_instance(DatabaseSettings, settings)
````

## 2\. DatabaseConfigurer

Create one or more classes that implement the `DatabaseConfigurer` protocol to apply engine-level behavior customization.

**Ordering:** Configurers are executed in **Ascending Order** based on their priority. Lower numbers run first.

### Example: Enable SQL Echo (Dynamic)

```python
from pico_sqlalchemy import DatabaseConfigurer

class EnableSqlEcho(DatabaseConfigurer):
    def priority(self) -> int:
        return 10  # Runs early

    def configure(self, engine):
        # Mutate the engine if supported, or attach listeners
        engine.echo = True
```

### Example: SQLite Pragmas

```python
from sqlalchemy import event
from pico_sqlalchemy import DatabaseConfigurer

class SQLitePragmaConfigurer(DatabaseConfigurer):
    def priority(self) -> int:
        return 50  # Runs after basic setup

    def configure(self, engine):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
```

## 3\. Initialization Logic

When the `SessionManager` starts up (via `SqlAlchemyFactory`), it performs the following:

1.  Creates the `AsyncEngine` using values from `DatabaseSettings`.
2.  Resolves all components implementing `DatabaseConfigurer`.
3.  Sorts them by `priority()` (Ascending).
4.  Calls `configure(engine)` on each one sequentially.

This ensures that your specific database tuning (like pragmas or connection pool listeners) is applied reliably before the application starts accepting traffic.

