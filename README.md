# 📦 pico-sqlalchemy

[![PyPI](https://img.shields.io/pypi/v/pico-sqlalchemy.svg)](https://pypi.org/project/pico-sqlalchemy/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/dperezcabrera/pico-sqlalchemy)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![CI (tox matrix)](https://github.com/dperezcabrera/pico-sqlalchemy/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy/branch/main/graph/badge.svg)](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)

# Pico-SQLAlchemy

**Pico-SQLAlchemy** integrates **[Pico-IoC](https://github.com/dperezcabrera/pico-ioc)** with **SQLAlchemy**, providing real inversion of control for your persistence layer, with declarative repositories, transactional boundaries, and clean architectural isolation.

It brings constructor-based dependency injection, transparent transaction management, and a repository pattern inspired by the elegance of Spring Data — but using pure Python, Pico-IoC, and SQLAlchemy’s ORM.

> 🐍 Requires Python 3.10+
> 🚀 **Async-Native:** Built entirely on SQLAlchemy's async ORM (`AsyncSession`, `create_async_engine`).
> 🧩 Works with SQLAlchemy 2.0+ ORM
> 🔄 Automatic async transaction management
> 🧪 Fully testable without a running DB

With Pico-SQLAlchemy you get the expressive power of SQLAlchemy with proper IoC, clean layering, and annotation-driven transactions.

---

## 🎯 Why pico-sqlalchemy

SQLAlchemy is powerful, but most applications end up with raw session handling, manual transaction scopes, or ad-hoc repository patterns.

Pico-SQLAlchemy provides:

* Constructor-injected repositories and services
* Declarative `@transactional` boundaries
* `REQUIRES_NEW`, `READ_ONLY`, `MANDATORY`, and all familiar propagation modes
* `SessionManager` that centralizes engine/session lifecycle
* Clean decoupling from frameworks (FastAPI, Flask, CLI, workers)

| Concern | SQLAlchemy Default | pico-sqlalchemy |
| :--- | :--- | :--- |
| Managing sessions | Manual `AsyncSession()` | Automatic |
| Transactions | Explicit `await commit()` / `await rollback()` | Declarative `@transactional` |
| Repository pattern | DIY, inconsistent | First-class `@repository` |
| Dependency injection | None | IoC-driven constructor injection |
| Testability | Manual setup | Container-managed + overrides |

---

## 🧱 Core Features

* Repository classes with `@repository`
* Declarative transactions via `@transactional`
* Full propagation semantics (`REQUIRED`, `REQUIRES_NEW`, `MANDATORY`, etc.)
* Automatic `AsyncSession` lifecycle
* Centralized `AsyncEngine` + session factory via `SessionManager`
* Transaction-aware `get_session()` for repository methods
* Plug-and-play integration with any Pico-IoC app (FastAPI, CLI tools, workers, event handlers)

---

## 📦 Installation

```bash
pip install pico-sqlalchemy
```

Also install `pico-ioc`, `sqlalchemy`, and an **async driver**:

```bash
pip install pico-ioc sqlalchemy
pip install aiosqlite  # For SQLite
# pip install asyncpg    # For PostgreSQL
```

-----

## 🚀 Quick Example

### Define your model:

```python
from sqlalchemy import Integer, String
from pico_sqlalchemy import AppBase, Mapped, mapped_column

class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
```

### Define a repository:

```python
from sqlalchemy.future import select
from pico_sqlalchemy import repository, transactional, get_session, SessionManager

@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @transactional
    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user

    @transactional(read_only=True)
    async def find_all(self) -> list[User]:
        session = get_session(self.manager)
        stmt = select(User).order_by(User.username)
        result = await session.scalars(stmt)
        return list(result.all())
```

### Define a service:

```python
from pico_ioc import component

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional
    async def create(self, name: str) -> User:
        user = User(username=name)
        user = await self.repo.save(user)
        
        session = get_session(self.repo.manager)
        await session.flush()
        await session.refresh(user)
        return user
```

### Initialize Pico-IoC and run:

```python
import asyncio
from pico_ioc import init, configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "sqlite+aiosqlite:///:memory:", # Async URL
        "echo": False
    }
}))

container = init(
    modules=["services", "repositories", "pico_sqlalchemy"],
    config=config,
)

async def main():
    # Use await container.aget() for async resolution
    service = await container.aget(UserService)
    
    # Await the async service method
    user = await service.create("alice")
    print(f"Created user: {user.id}")

    # Clean up async resources
    await container.cleanup_all_async()

if __name__ == "__main__":
    asyncio.run(main())
```

-----

## 🔄 Transaction Propagation Modes

Pico-SQLAlchemy supports the core Spring-inspired semantics:

| Mode | Behavior |
| :--- | :--- |
| `REQUIRED` | Join existing tx or create new |
| `REQUIRES_NEW` | Suspend parent and start new tx |
| `SUPPORTS` | Join if exists, else run without tx |
| `MANDATORY` | Requires existing tx |
| `NOT_SUPPORTED`| Run without tx, suspending parent |
| `NEVER` | Fail if a tx exists |

Example:

```python
@transactional(propagation="REQUIRES_NEW")
async def write_audit(self, entry: AuditEntry):
    ...
```

-----

## 🧪 Testing with Pico-IoC

You can override repositories, engines, or services easily:

```python
import pytest
import pytest_asyncio
from pico_ioc import init, configuration, DictSource
from pico_sqlalchemy import SessionManager, AppBase

# In conftest.py
@pytest_asyncio.fixture
async def container():
    cfg = configuration(DictSource({"database": {"url": "sqlite+aiosqlite:///:memory:"}}))
    c = init(modules=["pico_sqlalchemy", "myapp"], config=cfg)
    
    # Setup the in-memory database
    sm = await c.aget(SessionManager)
    async with sm.engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)

    yield c
    
    # Clean up all async components
    await c.cleanup_all_async()

# In your test
@pytest.mark.asyncio
async def test_my_service(container):
    service = await container.aget(UserService)
    user = await service.create("test")
    assert user.id is not None
```

-----

## 🧬 Example: Custom Database Configurer

```python
from pico_sqlalchemy import DatabaseConfigurer, AppBase
from pico_ioc import component
import asyncio

@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10
    def __init__(self, base: AppBase):
        self.base = base
        
    def configure(self, engine):
        # This configure method is called by the factory.
        # We need to run the async setup.
        async def setup():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        
        asyncio.run(setup())
```

Pico-SQLAlchemy will detect it and call `configure` during initialization.

-----

## ⚙️ How It Works

  * `SessionManager` is created by Pico-IoC (`SqlAlchemyFactory`)
  * A global session context is established via `contextvars`
  * `@transactional` automatically opens/closes async transactions
  * `@repository` registers a class as a singleton component
  * All dependencies (repositories, services, configurers) are resolved by Pico-IoC

No globals. No implicit singletons. No framework coupling.

-----

## 💡 Architecture Overview

```
                 ┌─────────────────────────────┐
                 │         Your App            │
                 └──────────────┬──────────────┘
                                │
                      Constructor Injection
                                │
                 ┌──────────────▼───────────────┐
                 │          Pico-IoC            │
                 └──────────────┬───────────────┘
                                │
                 SessionManager / SqlAlchemyFactory
                                │
                 ┌──────────────▼───────────────┐
                 │       pico-sqlalchemy        │
                 │ Transactional Decorators     │
                 │ Repository Metadata          │
                 └──────────────┬───────────────┘
                                │
                             SQLAlchemy
                           (Async ORM)
```

-----

## 📝 License

MIT

