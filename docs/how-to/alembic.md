# How to Use Alembic Migrations with pico-sqlalchemy

This guide shows how to integrate [Alembic](https://alembic.sqlalchemy.org/) database migrations with pico-sqlalchemy.

---

## Prerequisites

```bash
pip install alembic
```

## 1. Initialize Alembic

```bash
alembic init alembic
```

This creates an `alembic/` directory and an `alembic.ini` file.

## 2. Configure `alembic/env.py`

Replace the contents of `alembic/env.py` to use `AppBase.metadata` and your async engine:

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from pico_sqlalchemy import AppBase

# Import ALL your model modules so their tables are registered
import my_app.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use AppBase.metadata so Alembic sees all your models
target_metadata = AppBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## 3. Set the Database URL in `alembic.ini`

```ini
[alembic]
sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/mydb
```

Alternatively, read the URL from an environment variable in `env.py`:

```python
import os
url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
config.set_main_option("sqlalchemy.url", url)
```

## 4. Create a Migration

```bash
alembic revision --autogenerate -m "create users table"
```

Review the generated file in `alembic/versions/` before applying.

## 5. Apply Migrations

```bash
alembic upgrade head
```

## 6. Run Migrations at Startup via `DatabaseConfigurer`

To run Alembic migrations automatically when the application starts:

```python
from alembic import command
from alembic.config import Config
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer


@component
class AlembicMigrator(DatabaseConfigurer):
    """Run Alembic migrations on application startup."""

    @property
    def priority(self) -> int:
        # Run before any seed-data configurers
        return -10

    def configure(self, engine) -> None:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
```

**Note:** Set a low `priority` value so that migrations run before other configurers that may depend on the schema being up to date.

## 7. Downgrade

```bash
alembic downgrade -1   # Roll back one revision
alembic downgrade base # Roll back to initial state
```

---

## Tips

- Always import your model modules in `env.py` so Alembic's `--autogenerate` detects all tables.
- Use `AppBase.metadata` (not a custom `Base`) to stay consistent with pico-sqlalchemy.
- For multi-database setups, create separate Alembic configurations per database (see [Multiple Databases](multiple-databases.md)).
