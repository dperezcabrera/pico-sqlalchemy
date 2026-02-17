# Declarative Base (AppBase)

This module defines the project's canonical SQLAlchemy declarative base (`AppBase`) and re-exports the `Mapped` and `mapped_column` helpers to standardize ORM model definitions across the codebase.

## Overview

- `AppBase` is a **Singleton Component** subclassing `sqlalchemy.orm.DeclarativeBase`.
- All ORM models in the project must subclass `AppBase`.
- It acts as the central registry for your database schema (`MetaData`).
- It is integrated with **Pico-IoC**, allowing you to inject the registry into other components (like database configurers).

## 1. Defining Models

You should define your models by inheriting from `AppBase`. Use the re-exported `Mapped` and `mapped_column` for clean, typed definitions compatible with SQLAlchemy 2.0.

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import relationship

# Import from the library
from pico_sqlalchemy import AppBase, Mapped, mapped_column

class User(AppBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    
    posts: Mapped[list["Post"]] = relationship(back_populates="author")

class Post(AppBase):
    __tablename__ = "posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(String)
    
    author: Mapped["User"] = relationship(back_populates="posts")
```

## 2\. Dependency Injection & Schema Management

Unlike standard SQLAlchemy apps where you might access `Base.metadata` globally, `pico-sqlalchemy` registers `AppBase` as a **Singleton Component**.

This allows you to inject it into your `DatabaseConfigurer` to perform schema operations (like creating tables) during startup.

### Example: Creating Tables on Startup

```python
import asyncio
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer, AppBase

@component
class TableCreationConfigurer(DatabaseConfigurer):
    # 1. Inject AppBase (The singleton registry)
    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        async def init_schema():
            async with engine.begin() as conn:
                # 2. Access metadata through the injected instance
                await conn.run_sync(self.base.metadata.create_all)
        
        asyncio.run(init_schema())
```

## 3\. Best Practices

  * **Inheritance:** Always subclass `AppBase` for your entities. Do not create your own `DeclarativeBase`.
  * **Imports:** Import `Mapped` and `mapped_column` from `pico_sqlalchemy` to ensure version consistency.
  * **Injection over Globals:** While `AppBase.metadata` is technically accessible statically, prefer injecting `AppBase` into services or configurers that need access to the schema registry. This makes your components easier to test and mock.

## 4\. Migrations (Alembic)

For external tools like Alembic which run outside the IoC container context, you can still access the metadata statically.

In your `alembic/env.py`:

```python
from pico_sqlalchemy import AppBase
from myapp.models import User, Post  # Import models to register them

# Point Alembic to the shared metadata
target_metadata = AppBase.metadata
```

---

## Auto-generated API

::: pico_sqlalchemy.base
