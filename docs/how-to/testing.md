# How to Test Repositories and Services

This guide covers testing patterns for pico-sqlalchemy applications, including in-memory SQLite fixtures, transaction testing, and integration tests with the IoC container.

---

## Prerequisites

```bash
pip install pytest pytest-asyncio aiosqlite
```

In your `pyproject.toml` or `pytest.ini`, enable strict async mode:

```toml
[tool.pytest.ini_options]
asyncio_mode = "strict"
```

---

## 1. Standalone SessionManager Tests (No IoC)

The simplest approach uses `SessionManager` directly with an in-memory SQLite database. No container, no component scanning.

### Define a Test Base and Model

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String

class TestBase(DeclarativeBase):
    pass

class User(TestBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
```

### Create a Helper to Build a SessionManager

```python
import asyncio
from pico_sqlalchemy import SessionManager

def new_test_manager(base) -> SessionManager:
    """Create an in-memory SessionManager and run DDL."""
    manager = SessionManager(url="sqlite+aiosqlite:///:memory:", echo=False)

    async def create_tables():
        async with manager.engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    asyncio.run(create_tables())
    return manager
```

### Write a Test

```python
import pytest
from sqlalchemy import select

@pytest.mark.asyncio
async def test_commit_and_read():
    manager = new_test_manager(TestBase)

    # Write
    async with manager.transaction() as session:
        session.add(User(name="Alice"))

    # Read back
    async with manager.transaction(read_only=True) as session:
        users = list((await session.scalars(select(User))).all())
        assert len(users) == 1
        assert users[0].name == "Alice"
```

---

## 2. Testing Rollback Behavior

```python
@pytest.mark.asyncio
async def test_rollback_on_exception():
    manager = new_test_manager(TestBase)

    try:
        async with manager.transaction() as session:
            session.add(User(name="Bob"))
            raise ValueError("Simulated failure")
    except ValueError:
        pass

    # Bob should NOT be persisted
    async with manager.transaction(read_only=True) as session:
        users = list((await session.scalars(select(User))).all())
        assert len(users) == 0
```

---

## 3. Testing Propagation Modes

### REQUIRES_NEW

```python
@pytest.mark.asyncio
async def test_requires_new_survives_outer_rollback():
    manager = new_test_manager(TestBase)

    try:
        async with manager.transaction() as outer_session:
            outer_session.add(User(name="outer"))

            # Inner transaction commits independently
            async with manager.transaction(propagation="REQUIRES_NEW") as inner_session:
                inner_session.add(User(name="inner"))

            raise RuntimeError("outer fails")
    except RuntimeError:
        pass

    async with manager.transaction(read_only=True) as session:
        names = [u.name for u in (await session.scalars(select(User))).all()]
        assert "inner" in names
        assert "outer" not in names
```

### MANDATORY

```python
@pytest.mark.asyncio
async def test_mandatory_fails_without_transaction():
    manager = new_test_manager(TestBase)

    with pytest.raises(RuntimeError, match="MANDATORY propagation requires active transaction"):
        async with manager.transaction(propagation="MANDATORY"):
            pass
```

### NEVER

```python
@pytest.mark.asyncio
async def test_never_fails_with_transaction():
    manager = new_test_manager(TestBase)

    with pytest.raises(RuntimeError, match="NEVER propagation forbids active transaction"):
        async with manager.transaction() as session:
            async with manager.transaction(propagation="NEVER"):
                pass
```

---

## 4. Integration Tests with the IoC Container

For full end-to-end tests that exercise interceptors, use `pico_ioc.init()`:

```python
import os
import pytest
from pico_ioc import DictSource, component, configuration, init
from pico_sqlalchemy import (
    AppBase, Mapped, mapped_column, SessionManager,
    get_session, repository, transactional, DatabaseConfigurer,
)
from sqlalchemy import Integer, String, select
import asyncio


class Item(AppBase):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


@component
class SetupDB(DatabaseConfigurer):
    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine) -> None:
        async def run():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        asyncio.run(run())


@repository
class ItemRepository:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    async def save(self, item: Item) -> Item:
        session = get_session(self.sm)
        session.add(item)
        return item


@component
class ItemService:
    def __init__(self, repo: ItemRepository):
        self.repo = repo

    @transactional
    async def create(self, name: str) -> Item:
        return await self.repo.save(Item(name=name))


@pytest.fixture(scope="session")
def container():
    cfg = configuration(DictSource({
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
            "echo": False,
        }
    }))
    c = init(modules=["pico_sqlalchemy", __name__], config=cfg)
    try:
        yield c
    finally:
        c.cleanup_all()


@pytest.fixture
def item_service(container):
    return container.get(ItemService)


@pytest.fixture
def session_manager(container):
    return container.get(SessionManager)


@pytest.mark.asyncio
async def test_service_commits(item_service, session_manager):
    await item_service.create("Widget")

    async with session_manager.transaction(read_only=True) as session:
        items = list((await session.scalars(select(Item))).all())
        assert any(i.name == "Widget" for i in items)
```

---

## 5. Testing `@query` Methods

```python
from pico_sqlalchemy import query, repository, PageRequest, Sort

@repository(entity=Item)
class QueryItemRepo:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    @query(expr="name = :name", unique=True)
    async def find_by_name(self, name: str):
        ...

    @query(expr="1=1", paged=True)
    async def find_all_paged(self, page: PageRequest):
        ...


# In the test (requires IoC container fixture as shown above):
@pytest.mark.asyncio
async def test_query_find_by_name(container):
    repo = container.get(QueryItemRepo)
    # ... seed data via a transactional service, then:
    result = await repo.find_by_name(name="Widget")
    assert result is not None
```

---

## Tips

- Use **in-memory SQLite** (`sqlite+aiosqlite:///:memory:`) for fast, isolated tests.
- Use `scope="session"` on the container fixture to avoid re-initializing the container for every test.
- For tests that modify data, consider using `REQUIRES_NEW` or manual cleanup to keep tests independent.
- Set the `DATABASE_URL` environment variable to run the same tests against a real database in CI.
