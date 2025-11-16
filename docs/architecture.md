# Architecture Overview — pico-sqlalchemy

`pico-sqlalchemy` is a thin integration layer that connects **Pico-IoC**’s inversion-of-control container with **SQLAlchemy**’s async session and transaction management.
Its purpose is not to replace SQLAlchemy — but to ensure that **repositories and domain services are executed inside explicit, async-native transactional boundaries**, declared via annotations, consistently managed through Pico-IoC.

---

## 1. High-Level Design

```

```
             ┌─────────────────────────────┐
             │         SQLAlchemy          │
             │ (AsyncEngine / AsyncSession)│
             └──────────────┬──────────────┘
                            │
                  Async Transaction Wrapping
                            │
             ┌──────────────▼───────────────┐
             │       pico-sqlalchemy       │
             │ (@transactional, @repository)│
             └──────────────┬───────────────┘
                            │
                     IoC Resolution
                            │
             ┌──────────────▼───────────────┐
             │           Pico-IoC          │
             │ (Container / Scopes / DI)   │
             └──────────────┬───────────────┘
                            │
               Async Domain Services, Repos,
                    Aggregates, Logic
```

```

---

## 2. Data Flow (Transactional Execution)

```

Async repository or service method called
│
▼
┌──────────────────────────────────────┐
│ AOP Interceptor detects @transactional│
└──────────────────────────────────────┘
│
▼
┌────────────────────────────────────────────┐
│ SessionManager enters an async transaction │
│ - `async with manager.transaction(...)`    │
│ - REQUIRED / REQUIRES\_NEW / SUPPORTS       │
│ - read-only or read-write                  │
│ - automatic `await commit()` / `await rollback()`│
└────────────────────────────────────────────┘
│
▼
Async Repository / domain method executes (`await`)
│
▼
Commit or rollback (`await`)
│
▼
Transaction scope disposed, session closed (`await`)

```

### Key guarantees

| Concern | Solution |
| :--- | :--- |
| No implicit global session | `AsyncSession` instances are created per-transaction |
| Constructor-based DI | Repositories and services resolved via IoC |
| Controlled transactions | Declarative semantics (`REQUIRED`, `REQUIRES_NEW`, etc.) |
| Async-native | `contextvars` + `async/await` ensure per-task isolation |

---

## 3. Repository Model

Repositories are **plain Python classes** declared with `@repository`.
They:

* receive dependencies via `__init__`
* run their methods inside transactional decorators (which must now be `async def`)
* access the active async session using `get_session()`

```python
from sqlalchemy.future import select

@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @transactional(read_only=True)
    async def find_all(self) -> list[User]:
        session = get_session(self.manager)
        stmt = select(User).order_by(User.username)
        result = await session.scalars(stmt)
        return list(result.all())

    @transactional
    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user
```

No transactional code inside the repository.
No global sessions.
No shared state.

-----

## 4\. Transaction Registration Strategy

At startup:

1.  `@repository` registers the class as a transactional component.
2.  `pico-sqlalchemy` automatically applies an `async` MethodInterceptor to all its methods.
3.  During execution:
      * The interceptor reads the method’s metadata (`@transactional`)
      * It opens, joins, suspends, or creates a new transaction
        depending on the propagation mode
      * It executes the `async def` method inside an `async with` transactional context

Equivalent to Spring Data or JPA-style declarative transactions.

-----

## 5\. Transaction Propagation Model

Supported propagation levels:

| Propagation | Behavior |
| :--- | :--- |
| `REQUIRED` | Join existing or start new |
| `REQUIRES_NEW` | Suspend current, always start new |
| `SUPPORTS` | Join if exists, else run without transaction |
| `MANDATORY` | Must already be in a transaction |
| `NOT_SUPPORTED` | Suspend any transaction and run non-transactional |
| `NEVER` | Error if a transaction is active |

Session lifecycle is fully deterministic:

```
begin → await work → await commit or await rollback → await close
```

Rollback logic is selective via:

  * `rollback_for=(...)`
  * `no_rollback_for=(...)`

-----

## 6\. Scoping Model

`pico-sqlalchemy` does **not** introduce custom scopes.
Instead, it relies on transaction boundaries:

| Scope | Meaning |
| :--- | :--- |
| Transaction (implicit) | `AsyncSession` lifetime |
| Singleton | `SessionManager`, config, factories |
| Request-specific (optional) | Available if combined with `pico-fastapi` |
| Custom IoC scopes | Fully supported if user defines them |

Unlike `pico-fastapi`, there is no middleware layer.
The container itself drives the entire lifecycle.

-----

## 7\. Cleanup & Session Lifecycle

`SessionManager` ensures:

  * `AsyncSession` instances are always closed (`await session.close()`)
  * transactions are always committed or rolled back
  * suspended transactions (REQUIRES\_NEW, NOT\_SUPPORTED) are properly restored

All cleanup is deterministic and safe, with no global state or leaked sessions.

-----

## 8\. Architectural Intent

**pico-sqlalchemy exists to:**

  * Provide declarative, Spring-style **async** transaction management for Python
  * Replace ad-hoc `session = AsyncSession()` scattered across repositories
  * Centralize `AsyncSession` creation and lifecycle in a single place
  * Make transactional semantics explicit and testable
  * Ensure business logic is clean and free from persistence boilerplate

It does *not* attempt to:

  * Replace SQLAlchemy Async ORM or `AsyncEngine`
  * Change SQLAlchemy’s session model
  * Hide transaction boundaries
  * Provide implicit magic or auto-scanning

-----

## 9\. When to Use

Use `pico-sqlalchemy` if:

✔ Your application uses the SQLAlchemy Async ORM
✔ You want clean repository/service layers
✔ You prefer declarative transactions
✔ You want deterministic `AsyncSession` lifecycle
✔ You value testability and DI patterns

Avoid `pico-sqlalchemy` if:

✖ You are not using `asyncio` or the SQLAlchemy async extensions
✖ You prefer manual session management
✖ You only use SQLAlchemy Core with no ORM session lifecycle

-----

## 10\. Summary

`pico-sqlalchemy` is a **structural async transaction management tool**:
It lets SQLAlchemy focus on persistence and mapping,
while **Pico-IoC** owns composition, lifecycle, and transactional semantics.

> SQLAlchemy Async ORM stays pure.
> Your domain stays clean.
> Dependencies stay explicit.

