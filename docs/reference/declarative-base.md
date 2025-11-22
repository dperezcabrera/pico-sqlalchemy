# Declarative Base (AppBase)

This module defines the project's canonical SQLAlchemy declarative base (`AppBase`) and re-exports the `Mapped` and `mapped_column` helpers to standardize ORM model definitions across the codebase.

## Overview

- `AppBase` is a singleton subclass of `sqlalchemy.orm.DeclarativeBase`. All ORM models in the project should subclass `AppBase`.
- `Mapped` and `mapped_column` are re-exported for consistent imports and typed SQLAlchemy 2.0-style mappings.
- Using a single base keeps one `MetaData` for the entire project, simplifies migrations, and avoids table duplication issues.

## What is this?

- A single, shared declarative base (`AppBase`) used to declare all SQLAlchemy ORM models.
- Helper re-exports:
  - `Mapped[T]`: a generic type hint for mapped attributes (SQLAlchemy 2.0).
  - `mapped_column(...)`: the column factory used in typed class attributes.

Why a singleton base?

- Ensures a single `MetaData` object for the application.
- Prevents accidental multiple table registries and conflicts.
- Provides a consistent point of integration for migrations (e.g., Alembic) and schema generation.

## How do I use it?

1. Import `AppBase`, `Mapped`, and `mapped_column`.
2. Define each ORM model as a subclass of `AppBase`.
3. Use `Mapped[T]` with `mapped_column(...)` for typed columns and `relationship(...)` for associations.
4. Use `AppBase.metadata` for schema operations (e.g., `create_all`, Alembic migrations).

Example:

```python
from datetime import datetime
from sqlalchemy import create_engine, String, ForeignKey, func, text
from sqlalchemy.orm import relationship, Session

# Import from the project's declarative base module.
# Adjust the import path to match your package structure.
from app.db.base import AppBase, Mapped, mapped_column


class User(AppBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="author")


class Post(AppBase):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String)

    author: Mapped["User"] = relationship(back_populates="posts")


# Create an engine and materialize the schema (in non-migration contexts).
engine = create_engine("postgresql+psycopg://user:pass@localhost/dbname", echo=True)

# Use the shared metadata carried by AppBase.
AppBase.metadata.create_all(engine)

# Basic CRUD with a typed session.
with Session(engine) as session:
    user = User(email="dev@example.com")
    post = Post(author=user, title="Hello", body="First post")
    session.add_all([user, post])
    session.commit()
```

## Migrations

When configuring Alembic (or similar), point `target_metadata` at the shared metadata:

```python
# alembic/env.py
from app.db.base import AppBase

target_metadata = AppBase.metadata
```

This ensures migrations see all models that subclass `AppBase`.

## Best practices

- Always subclass `AppBase` for project ORM models. Do not create additional declarative bases.
- Import `Mapped` and `mapped_column` from the same module to keep typing and configuration consistent.
- Use SQLAlchemy 2.0-style typed mappings (`Mapped[T]` + `mapped_column`) for better editor and type-checker support.
- Use `AppBase.metadata` wherever a `MetaData` reference is required (DDL, migrations, schema inspection).