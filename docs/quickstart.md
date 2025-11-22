# Quick Start Guide

This guide will walk you through creating a complete, runnable application using `pico-sqlalchemy`. We will build a simple user management system with an in-memory SQLite database.

## Prerequisites

Ensure you have installed the package:

```bash
pip install pico-sqlalchemy aiosqlite
```

## 1\. Define the Data Model

First, define your database models by inheriting from `AppBase`. This ensures all your models share the same SQLAlchemy `MetaData` and registry.

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

Repositories are responsible for direct database interactions. Use the `@repository` decorator to register them in the IoC container. Note that we do not commit transactions here; we just operate on the session.

```python
from sqlalchemy import select
from pico_sqlalchemy import repository, SessionManager, get_session

@repository
class UserRepository:
    def __init__(self, session_manager: SessionManager):
        self.sm = session_manager

    async def save(self, name: str) -> User:
        # get_session() retrieves the context-local async session
        session = get_session(self.sm)
        user = User(name=name)
        session.add(user)
        return user

    async def list_all(self) -> list[User]:
        session = get_session(self.sm)
        stmt = select(User)
        result = await session.scalars(stmt)
        return list(result.all())
```

## 3\. Create a Service Layer

Services contain your business logic and define transaction boundaries using `@transactional`.

```python
from pico_ioc import component
from pico_sqlalchemy import transactional

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional(propagation="REQUIRED")
    async def register_user(self, name: str) -> User:
        # This runs inside a transaction.
        # Commit happens automatically if this method returns successfully.
        return await self.repo.save(name)

    @transactional(read_only=True)
    async def show_users(self):
        users = await self.repo.list_all()
        for u in users:
            print(f"User: {u.name}")
```

## 4\. Configure the Database

We use `DatabaseConfigurer` to create tables on startup.

```python
import asyncio
from pico_ioc import component
from pico_sqlalchemy import DatabaseConfigurer

@component
class SchemaSetup(DatabaseConfigurer):
    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine) -> None:
        # Simple async table creation hook
        async def run_ddl():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        
        # Schedule the coroutine
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(run_ddl())
        else:
            asyncio.run(run_ddl())
```

## 5\. Wire it Up

Finally, initialize the `pico_ioc` container with your configuration and modules.

```python
import asyncio
from pico_ioc import init, configuration, DictSource

async def main():
    # Configuration for the database connection
    cfg = configuration(
        DictSource({
            "database": {
                "url": "sqlite+aiosqlite:///:memory:",
                "echo": True
            }
        })
    )

    # Initialize container
    container = init(
        modules=["pico_sqlalchemy", "__main__"],
        config=cfg
    )

    # Retrieve and use the service
    service = container.get(UserService)
    await service.register_user("Alice")
    await service.show_users()

if __name__ == "__main__":
    asyncio.run(main())
```

