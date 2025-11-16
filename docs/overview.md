# 🚀 Pico-SQLAlchemy: Async-Native ORM

`pico-sqlalchemy` is a thin integration layer that connects **Pico-IoC**’s inversion-of-control container with **SQLAlchemy**’s async session and transaction management.

Its purpose is not to replace SQLAlchemy — but to ensure that repositories and domain services are executed inside explicit, async-native transactional boundaries, declared via annotations, and consistently managed through Pico-IoC.

## Key Features

* **Async-Native:** Built entirely on SQLAlchemy's async ORM (`AsyncSession`, `create_async_engine`).
* **Declarative Transactions:** Use `@transactional` on any `async def` method for automatic `await commit()` / `await rollback()`.
* **Dependency Injection:** Repositories are registered with `@repository` and injected directly into your services' `__init__` methods.
* **Clean Architecture:** Keeps your business logic (services) and persistence logic (repositories) completely separate from session management boilerplate.

---

## Example at a Glance

Here is a complete, runnable example of setting up an async service with a repository and declarative transactions.

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
    get_session,
)

# --- Imports from SQLAlchemy ---
from sqlalchemy import Integer, String, select


# --- 1. Model Definition ---
# Define a model using the declarative AppBase
class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True)


# --- 2. Database Initializer (Optional but recommended) ---
# A DatabaseConfigurer component that creates the tables on startup.
@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10

    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        # We must run the DDL in an async context
        async def setup_database():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)

        print("[Configurer] Running initial database setup...")
        asyncio.run(setup_database())
        print("[Configurer] Database setup complete.")


# --- 3. Repository Layer ---
# The @repository decorator marks this as a component.
# All methods are async.
@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        # Inject the SessionManager
        self._manager = manager

    @transactional(read_only=True)
    async def get_by_username(self, username: str) -> User | None:
        # get_session() provides the active AsyncSession
        session = get_session(self._manager)
        
        # Use SQLAlchemy 2.0 style async queries
        stmt = select(User).where(User.username == username)
        result = await session.scalars(stmt)
        return result.first()

    @transactional
    async def save(self, user: User) -> User:
        session = get_session(self._manager)
        session.add(user)
        # The @transactional wrapper will handle commit/rollback
        return user


# --- 4. Service Layer ---
# A standard pico-ioc component for business logic.
@component
class UserService:
    def __init__(self, user_repo: UserRepository):
        # Inject the repository
        self._user_repo = user_repo

    @transactional
    async def create_user(self, username: str) -> User:
        """
        A transactional method that checks for duplicates
        and saves a new user.
        """
        print(f"SERVICE: Checking if user '{username}' exists...")
        existing = await self._user_repo.get_by_username(username)
        if existing:
            raise ValueError(f"User '{username}' already exists.")
        
        print(f"SERVICE: Creating new user '{username}'...")
        new_user = User(username=username)
        
        # This call joins the existing transaction
        new_user = await self._user_repo.save(new_user)
        
        # We need to flush to get the ID
        session = get_session(self._user_repo._manager)
        await session.flush()
        await session.refresh(new_user)
        
        print(f"SERVICE: User created with ID {new_user.id}")
        return new_user

    async def get_user(self, username: str) -> User | None:
        """
        A non-transactional (at this level) read method.
        The underlying repo call will start its own read-only transaction.
        """
        print(f"SERVICE: Retrieving user '{username}'...")
        return await self._user_repo.get_by_username(username)


# --- 5. Main Application Entrypoint ---
async def main():
    print("Configuring container...")
    # Configure the database URL for the async aiosqlite driver
    config = configuration(DictSource({
        "database": {
            "url": "sqlite+aiosqlite:///:memory:",
            "echo": False
        }
    }))
    
    # Initialize the container, scanning this module and the library
    container = init(modules=[__name__, "pico_sqlalchemy"], config=config)

    print("Container initialized. Running application...")
    try:
        # Use await container.aget() to resolve async components
        user_service = await container.aget(UserService)
        
        # --- Run 1: Create a user (Success) ---
        user = await user_service.create_user("alice")
        
        # --- Run 2: Get the user ---
        retrieved_user = await user_service.get_user("alice")
        print(f"\nRetrieved: {retrieved_user.username} (ID: {retrieved_user.id})")
        assert user.id == retrieved_user.id

        # --- Run 3: Try to create a duplicate (should fail) ---
        print("\nAttempting to create duplicate user 'alice'...")
        await user_service.create_user("alice")

    except ValueError as e:
        print(f"Caught expected error: {e}")
    finally:
        # Clean up async resources (like the engine pool)
        print("\nCleaning up resources...")
        await container.cleanup_all_async()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
```

-----

## Core Concepts in this Example

1.  **`@repository`**: This decorator registers the `UserRepository` as a singleton component in the IoC container.
2.  **`@component`**: This registers the `UserService` and `TableCreationConfigurer` as components.
3.  **Constructor Injection**: `UserService` receives the `UserRepository` instance in its `__init__` automatically.
4.  **`@transactional`**: This decorator wraps the `async def` methods. It automatically starts an async transaction, provides an `AsyncSession`, and handles `await session.commit()` or `await session.rollback()` based on whether an exception was raised.
5.  **`get_session(manager)`**: This safely retrieves the active `AsyncSession` that `@transactional` created for the current async task.
6.  **`init(modules=...)`**: The `init` function scans the provided modules, finds all components, and wires them together.
7.  **`container.aget()`**: The asynchronous version of `get()`. It must be used to resolve any component (like `UserService`) that depends on an async resource (like the `SessionManager`).
8.  **`container.cleanup_all_async()`**: Gracefully shuts down all components, including the async database engine pool.

<!-- end list -->

