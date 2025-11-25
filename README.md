# 📦 pico-sqlalchemy

[![PyPI](https://img.shields.io/pypi/v/pico-sqlalchemy.svg)](https://pypi.org/project/pico-sqlalchemy/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/dperezcabrera/pico-sqlalchemy)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![CI (tox matrix)](https://github.com/dperezcabrera/pico-sqlalchemy/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy/branch/main/graph/badge.svg)](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Docs](https://img.shields.io/badge/Docs-pico--sqlalchemy-blue?style=flat&logo=readthedocs&logoColor=white)](https://dperezcabrera.github.io/pico-sqlalchemy/)

# Pico-SQLAlchemy

**Pico-SQLAlchemy** integrates **[Pico-IoC](https://github.com/dperezcabrera/pico-ioc)** with **SQLAlchemy**, providing a true inversion of control persistence layer with **Spring Data-style** declarative features.

It brings constructor-based dependency injection, **implicit transaction management**, and powerful **declarative queries** using pure Python and SQLAlchemy’s Async ORM.

> 🐍 **Requires Python 3.10+**
> 🚀 **Async-Native:** Built entirely on `AsyncSession` and `create_async_engine`.
> ✨ **Zero-Boilerplate:** Repositories are transactional by default.
> 🔍 **Declarative Queries:** Define SQL or expressions in decorators; the library executes them for you.

---

## 🎯 Why pico-sqlalchemy?

Most Python apps suffer from manual session handling (`async with session...`), scattered transaction logic, and verbose repository patterns.

**Pico-SQLAlchemy** solves this by offering:

| Feature | SQLAlchemy Default | pico-sqlalchemy |
| :--- | :--- | :--- |
| **Transactions** | Manual `commit()` / `rollback()` | **Implicit** (Auto-managed) |
| **Repositories** | DIY Classes | **`@repository`** (Transactional by default) |
| **Queries** | Manual implementation | **`@query`** (Declarative execution) |
| **Injection** | None / Global variables | **Constructor Injection** (IoC) |
| **Pagination** | Manual calculation | **Automatic** (`PageRequest` / `Page`) |

---

## 🧱 Core Features

* **Implicit Transactions:** Methods inside `@repository` are automatically **Read-Write** transactional.
* **Declarative Queries:** Use `@query` to run SQL or Expressions automatically (defaults to **Read-Only**).
* **AOP-Based Propagation:** `REQUIRED`, `REQUIRES_NEW`, `MANDATORY`, `NEVER`, etc.
* **Session Lifecycle:** Centralized `SessionManager` handles engine creation and cleanup.
* **Pagination:** Built-in support for paged results via `@query(paged=True)`.

---

## 📦 Installation

```bash
pip install pico-sqlalchemy
```

You will also need an async driver (e.g., `aiosqlite` or `asyncpg`):

```bash
pip install pico-ioc sqlalchemy aiosqlite
```

-----

## 🚀 Quick Example

### 1\. Define Model

```python
from sqlalchemy import Integer, String
from pico_sqlalchemy import AppBase, Mapped, mapped_column

class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
```

### 2\. Define Repository (The "Magic" Part)

Notice we don't need `@transactional` here.

  * `save`: Automatically runs in a **Read-Write** transaction.
  * `find_by_name`: Automatically runs in a **Read-Only** transaction and executes the query logic.

<!-- end list -->

```python
from pico_sqlalchemy import repository, query, SessionManager, get_session

@repository(entity=User)
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    # IMPLICIT: Read-Write Transaction
    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user

    # DECLARATIVE: Read-Only Transaction + Auto-Execution
    @query(expr="username = :username", unique=True)
    async def find_by_name(self, username: str) -> User | None:
        ... # Body is ignored; the library executes the query
```

### 3\. Define Service

Use `@transactional` here to define business logic boundaries.

```python
from pico_ioc import component
from pico_sqlalchemy import transactional

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional
    async def create(self, name: str) -> User:
        # 1. Check existence (Read-Only tx from repo)
        existing = await self.repo.find_by_name(name)
        if existing:
            raise ValueError("User exists")
            
        # 2. Save new user (Joins current transaction)
        return await self.repo.save(User(username=name))
```

### 4\. Run it

```python
import asyncio
from pico_ioc import init, configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "sqlite+aiosqlite:///:memory:",
        "echo": False
    }
}))

async def main():
    container = init(modules=["pico_sqlalchemy", "__main__"], config=config)
    service = await container.aget(UserService)
    
    user = await service.create("alice")
    print(f"Created: {user.id}")
    
    await container.cleanup_all_async()

if __name__ == "__main__":
    asyncio.run(main())
```

-----

## ⚡ Transaction Hierarchy & Rules

Pico-SQLAlchemy applies a "Best Effort" strategy to determine transaction configuration. The priority order (highest wins) is:

| Priority | Decorator | Default Mode | Use Case |
| :--- | :--- | :--- | :--- |
| **1 (High)** | **`@transactional(...)`** | Explicit Config | Overriding defaults, Service layer logic. |
| **2** | **`@query(...)`** | **Read-Only** | Efficient data fetching. |
| **3 (Base)** | **`@repository`** | **Read-Write** | Default for CRUD (saves, updates, deletes). |

### Example Scenarios

1.  **Plain Method in Repository:**

    ```python
    async def update_user(self): ...
    ```

    👉 **Result:** Active Read-Write Transaction (Implicit from `@repository`).

2.  **Query Method:**

    ```python
    @query("SELECT ...")
    async def get_data(self): ...
    ```

    👉 **Result:** Active Read-Only Transaction (Implicit from `@query`).

3.  **Manual Override:**

    ```python
    @transactional(read_only=True)
    async def complex_report(self): ...
    ```

    👉 **Result:** Active Read-Only Transaction (Explicit override).

-----

## 🔍 Declarative Queries in Depth

The `@query` decorator eliminates boilerplate for common fetches.

### Expression Mode (`expr`)

Requires `@repository(entity=Model)`. Injects the expression into a `SELECT * FROM table WHERE ...`.

```python
@query(expr="age > :min_age", unique=False)
async def find_adults(self, min_age: int) -> list[User]: ...
```

### SQL Mode (`sql`)

Executes raw SQL. Useful for complex joins or specific DTOs.

```python
@query(sql="SELECT count(*) as cnt FROM users")
async def count_users(self) -> int: ...
```

### Automatic Pagination

Just add `paged=True` and a `page: PageRequest` parameter.

```python
from pico_sqlalchemy import Page, PageRequest

@query(expr="active = true", paged=True)
async def find_active(self, page: PageRequest) -> Page[User]: ...
```

-----

## 🧪 Testing

Testing is simple because you can override the configuration or the components easily using Pico-IoC.

```python
@pytest.mark.asyncio
async def test_service():
    # Setup container with in-memory DB
    container = ... 
    
    service = await container.aget(UserService)
    user = await service.create("test")
    
    assert user.id is not None
```

-----

## 💡 Architecture Overview

```
                 ┌─────────────────────────────┐
                 │          Your App           │
                 └──────────────┬──────────────┘
                                │
                        Constructor Injection
                                │
                 ┌──────────────▼───────────────┐
                 │          Pico-IoC            │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │       pico-sqlalchemy        │
                 │ 1. Implicit Repo Transactions│
                 │ 2. Declarative @query        │
                 │ 3. Explicit @transactional   │
                 └──────────────┬───────────────┘
                                │
                           SQLAlchemy
                           (Async ORM)
```

-----

## 📝 License

MIT
