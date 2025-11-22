# Database Configuration

This reference covers the database configuration extension points exposed by the project: the `DatabaseConfigurer` protocol and the `DatabaseSettings` dataclass. Together, they provide a consistent way to define default database connection settings and to hook into the database engine initialization to apply project-specific configuration.

## What is this?

- `DatabaseSettings` (dataclass)
  - Holds the default database connection settings for the project.
  - Annotated with pico_ioc metadata so it can be provided via dependency injection and overridden as needed (e.g., per environment).
  - Treat this as the single source of truth for connection-related parameters in your application.

- `DatabaseConfigurer` (protocol)
  - A small extension point for customizing the database engine after it is created.
  - Methods:
    - `priority(self)`: Returns a numeric value used to order multiple configurers. The framework uses this to sort configurers before applying them.
    - `configure(self, engine)`: Applies configuration to the database engine. Implementations can mutate the engine, attach listeners, or wrap it, depending on your engine type.

These are designed to work with an IoC container (pico_ioc), where `DatabaseSettings` and one or more `DatabaseConfigurer` implementations can be registered and discovered at runtime.

## How do I use it?

### 1) Provide or override DatabaseSettings

Create and register a `DatabaseSettings` instance that reflects your environment. The exact fields are defined in your codebase; typical values include a connection URL/DSN and optional engine options.

Example (using a generic container):

```python
from pico_ioc import Container

# Assume DatabaseSettings is imported from your project module
from myapp.config import DatabaseSettings

container = Container()

# Construct settings appropriate for your environment.
# Replace ... with the actual fields defined in DatabaseSettings.
settings = DatabaseSettings(
    # e.g. url="postgresql+psycopg://user:pass@host:5432/dbname",
    #      options={"pool_size": 5, "echo": False}
)

# Make the settings available for injection
container.register_instance(DatabaseSettings, settings)
```

You can also bind settings from environment variables or configuration files before registering them.

### 2) Implement a DatabaseConfigurer

Create one or more classes that implement the `DatabaseConfigurer` protocol. Use these to apply engine-level behavior, such as enabling logging, setting pragmas, or registering connection hooks.

Example: Enabling SQL echo for SQLAlchemy (if you are using SQLAlchemy)

```python
# Example only; adapt to your engine type.
from myapp.config import DatabaseConfigurer

class EnableSqlEcho(DatabaseConfigurer):
    def priority(self) -> int:
        # Lower numbers or higher numbers may apply earlier, depending on your system.
        # Use consistent ranges to coordinate ordering among configurers.
        return 10

    def configure(self, engine):
        # For SQLAlchemy Engine, you can re-create or wrap with echo enabled.
        try:
            # If you build engines via a factory, you may need to rebuild here.
            engine.echo = True  # Works if the engine exposes this attribute.
        except AttributeError:
            # Fallback for engines without an echo attribute
            pass
```

Example: Setting SQLite PRAGMA on connect (SQLAlchemy)

```python
from sqlalchemy import event
from myapp.config import DatabaseConfigurer

class SQLitePragmaConfigurer(DatabaseConfigurer):
    def priority(self) -> int:
        return 50

    def configure(self, engine):
        # Attach an event to set PRAGMAs when a DBAPI connection is made.
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
```

Register your configurers with the container:

```python
container.register(DatabaseConfigurer, EnableSqlEcho())
container.register(DatabaseConfigurer, SQLitePragmaConfigurer())
```

### 3) Build and initialize the engine using the configurers

Create your engine from `DatabaseSettings`, then apply all registered `DatabaseConfigurer` instances in priority order.

```python
from typing import Iterable
from myapp.config import DatabaseSettings, DatabaseConfigurer

def build_engine(settings: DatabaseSettings):
    # Pseudocode. Replace with your actual engine construction.
    engine = create_engine_from(settings)  # e.g., SQLAlchemy create_engine(settings.url, **settings.options)
    return engine

def init_database(container) -> object:
    settings = container.resolve(DatabaseSettings)
    engine = build_engine(settings)

    configurers: Iterable[DatabaseConfigurer] = container.resolve_all(DatabaseConfigurer)

    # Sort by priority and apply in order
    for cfg in sorted(configurers, key=lambda c: c.priority()):
        result = cfg.configure(engine)
        # If a configurer returns a replacement/wrapped engine, prefer it
        engine = result or engine

    return engine

engine = init_database(container)
```

Notes:
- Some engines are immutable or do not expose mutators. In those cases, your `configure` implementation can wrap the engine or attach hooks rather than mutate state.
- If your `configure` returns a new engine object (e.g., a wrapped instance), be sure to use the returned value.

### Ordering and composition

- Use `priority()` to define the order in which configurers run. This helps avoid conflicts (e.g., attaching events before enabling logging).
- Coordinate priority values across your project and extensions to ensure deterministic behavior. For example:
  - 0–49: Core configurers
  - 50–99: Database-specific tweaks
  - 100+: Application-specific policies

### API surface

- DatabaseSettings
  - Dataclass containing database connection configuration. Provided via pico_ioc for injection, and can be overridden per environment.
- DatabaseConfigurer
  - priority(self) -> int: Defines ordering among multiple configurers.
  - configure(self, engine) -> Optional[object]: Applies configuration to the engine. May mutate in place or return a replacement/wrapped engine.

### Best practices

- Keep `DatabaseSettings` focused on connection-related parameters; avoid embedding runtime objects.
- Write small, composable `DatabaseConfigurer` implementations, each doing one thing well.
- Document assumptions about the engine type (e.g., SQLAlchemy) in each configurer, and guard against missing features.
- Always sort and apply configurers consistently in your initialization path to ensure deterministic startup.