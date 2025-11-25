# 🚀 Pico-SQLAlchemy: Async-Native ORM

`pico-sqlalchemy` is a thin integration layer that connects **Pico-IoC**’s inversion-of-control container with **SQLAlchemy**’s async session and transaction management.

Its purpose is not to replace SQLAlchemy — but to ensure that repositories and domain services are executed inside explicit, async-native transactional boundaries, declared via annotations, and consistently managed through Pico-IoC.

## Key Features

* **Async-Native:** Built entirely on SQLAlchemy's async ORM (`AsyncSession`, `create_async_engine`).
* **Zero-Boilerplate Repositories:** Methods inside `@repository` are **transactional by default**.
* **Declarative Queries:** Use `@query` to execute SQL or expressions automatically.
* **Dependency Injection:** Repositories are registered components injected directly into your services.
* **Clean Architecture:** Keeps your business logic (services) and persistence logic (repositories) completely separate from session management code.

---

## Example at a Glance

Here is a complete, runnable example of setting up an async service with a repository using **implicit transactions** and **declarative queries**.

```python
import asyncio
from dataclasses import dataclass

# --- Imports from pico-ioc ---
from pico_ioc import init, component, configuration, DictSource

# --- Imports from pico-sqlalchemy ---
from pico_sqlalchemy import (
    AppBase,
    Mapped,
    mapped_column,
    DatabaseConfigurer,
    SessionManager,
    repository,
    transactional,
    query,
    get_session,
)

# --- Imports from SQLAlchemy ---
from sqlalchemy import Integer, String


# --- 1. Model Definition ---
# Define a model using the declarative AppBase
class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)


# --- 2. Database Initializer (Optional) ---
@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10

    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        async def setup_database():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        asyncio.run(setup_database())


# --- 3. Repository Layer (The "Magic" Part) ---
# We define 'entity=User' to allow simplified @query expressions.
@repository(entity=User)
class UserRepository:
    def __init__(self, manager: SessionManager):
        self._manager = manager

    # DECLARATIVE QUERY:
    # No body needed. The library opens a Read-Only transaction,
    # binds :username, executes the query, and maps the result to User.
    @query(expr="username = :username", unique=True)
    async def get_by_username(self, username: str) -> User | None:
        ...

    # IMPLICIT TRANSACTION:
    # No @transactional decorator needed. 
    # Repositories are Read-Write transactional by default.
    async def save(self, user: User) -> User:
        session = get_session(self._manager)
        session.add(user)
        # Commit is handled automatically when this method returns
        return user


# --- 4. Service Layer ---
# Use @transactional here to define business logic boundaries.
@component
class UserService:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    @transactional
    async def create_user(self, username: str) -> User:
        """
        A transactional method that checks for duplicates
        and saves a new user.
        """
        print(f"SERVICE: Checking if user '{username}' exists...")
        
        # This call runs in the current transaction (propagation=REQUIRED)
        existing = await self._user_repo.get_by_username(username)
        
        if existing:
            raise ValueError(f"User '{username}' already exists.")
        
        print(f"SERVICE: Creating new user '{username}'...")
        new_user = User(username=username)
        
        # This call also joins the current transaction
        new_user = await self._user_repo.save(new_user)
        
        # We flush to get the ID immediately (optional)
        session = get_session(self._user_repo._manager)
        await session.flush()
        
        print(f"SERVICE: User created with ID {new_user.id}")
        return new_user


# --- 5. Main Application Entrypoint ---
async def main():
    config = configuration(DictSource({
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
            "echo": False
        }
    }))
    
    container = init(modules=[__name__, "pico_sqlalchemy"], config=config)

    try:
        user_service = await container.aget(UserService)
        
        # --- Run 1: Create a user ---
        user = await user_service.create_user("alice")
        
        # --- Run 2: Try to create a duplicate ---
        try:
            await user_service.create_user("alice")
        except ValueError as e:
            print(f"Caught expected error: {e}")

    finally:
        await container.cleanup_all_async()

if __name__ == "__main__":
    asyncio.run(main())
```

-----

## Core Concepts in this Example

1.  **`@repository`**: Registers the class as a component. Crucially, it wraps all public async methods in a **Read-Write transaction** by default.
2.  **`@query`**: Allows you to define queries (via SQL or simplified expressions) that are executed automatically in a **Read-Only transaction**.
3.  **`@transactional`**: Used in the Service layer to group multiple repository calls into a single atomic unit of work.
4.  **Implicit vs Explicit**: The repository methods don't need decorators for standard CRUD (`save`), but you can still use `@transactional` if you need specific settings (like `propagation="REQUIRES_NEW"`).

<!-- end list -->
