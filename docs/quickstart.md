# Quick Start Guide

This guide will walk you through creating a complete, runnable application using `pico-sqlalchemy` with its **Zero-Boilerplate** features.

## Prerequisites

```bash
pip install pico-sqlalchemy aiosqlite
```

## 1\. Define the Data Model

Inherit from `AppBase` to ensure your models share the same registry.

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from pico_sqlalchemy import AppBase

class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
```

## 2\. Create a Repository

Repositories in `pico-sqlalchemy` are **transactional by default**.

  * Standard methods (`save`) are **Read-Write**.
  * `@query` methods are **Read-Only** and executed automatically.

<!-- end list -->

```python
from pico_sqlalchemy import repository, query, SessionManager, get_session

@repository(entity=User)
class UserRepository:
    def __init__(self, session_manager: SessionManager):
        self.sm = session_manager

    # 1. Implicit Read-Write Transaction
    # No @transactional needed. Just get the session and work.
    async def save(self, name: str) -> User:
        session = get_session(self.sm)
        user = User(name=name)
        session.add(user)
        return user

    # 2. Declarative Read-Only Query
    # No body needed. The library executes the SQL expression.
    @query(expr="name = :name")
    async def find_by_name(self, name: str) -> list[User]:
        ...
```

## 3\. Create a Service Layer

Services define your business logic boundaries. Use `@transactional` here to wrap multiple repository calls into a single unit of work.

```python
from pico_ioc import component
from pico_sqlalchemy import transactional

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional
    async def register_user(self, name: str) -> User:
        # 1. Reuse repository logic (joins current transaction)
        existing = await self.repo.find_by_name(name)
        if existing:
            print(f"User {name} already seen!")
        
        # 2. Save new user
        return await self.repo.save(name)
```

## 4\. Configure the Database

Use `DatabaseConfigurer` to create tables on startup automatically.

```python
import asyncio
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer

@component
class SchemaSetup(DatabaseConfigurer):
    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine) -> None:
        async def run_ddl():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        
        asyncio.run(run_ddl())
```

## 5\. Wire it Up

Initialize the container and run the app.

```python
import asyncio
from pico_ioc import init, configuration, DictSource

async def main():
    # Configuration
    cfg = configuration(
        DictSource({
            "database": {
                "url": "sqlite+aiosqlite:///:memory:",
                "echo": False
            }
        })
    )

    # Initialize container
    container = init(
        modules=["pico_sqlalchemy", "__main__"],
        config=cfg
    )

    # Use the service
    service = await container.aget(UserService)
    
    print("--- Registering Alice ---")
    await service.register_user("Alice")
    
    print("--- Registering Alice again (Check logic) ---")
    await service.register_user("Alice")
    
    # Cleanup
    await container.cleanup_all_async()

if __name__ == "__main__":
    asyncio.run(main())
```
