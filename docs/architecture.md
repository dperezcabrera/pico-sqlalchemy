# Architecture Overview — pico-sqlalchemy

`pico-sqlalchemy` is a thin integration layer that connects **Pico-IoC**’s inversion-of-control container with **SQLAlchemy**’s session and transaction management.
Its purpose is not to replace SQLAlchemy — but to ensure that **repositories and domain services are executed inside explicit transactional boundaries**, declared via annotations, consistently managed through Pico-IoC.

---

## 1. High-Level Design

```
            ┌─────────────────────────────┐
            │         SQLAlchemy          │
            │   (Engine / Sessions / ORM) │
            └──────────────┬──────────────┘
                           │
                 Transaction Wrapping
                           │
            ┌──────────────▼───────────────┐
            │       pico-sqlalchemy        │
            │ (@transactional, @repository)│
            └──────────────┬───────────────┘
                           │
                    IoC Resolution
                           │
            ┌──────────────▼───────────────┐
            │           Pico-IoC           │
            │  (Container / Scopes / DI)   │
            └──────────────┬───────────────┘
                           │
                 Domain Services, Repos,
                      Aggregates, Logic
```

---

## 2. Data Flow (Transactional Execution)

```
Repository or service method called
                │
                ▼
┌──────────────────────────────────────┐
│ AOP Interceptor detects @transactional│
└──────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────┐
│ SessionManager enters a transaction block   │
│ - REQUIRED / REQUIRES_NEW / SUPPORTS        │
│ - read-only or read-write                   │
│ - automatic commit / rollback               │
└────────────────────────────────────────────┘
                │
                ▼
Repository / domain method executes
                │
                ▼
Commit or rollback
                │
                ▼
Transaction scope disposed, session closed
```

### Key guarantees

| Concern                    | Solution                                                 |
| -------------------------- | -------------------------------------------------------- |
| No implicit global session | Sessions are created per-transaction                     |
| Constructor-based DI       | Repositories and services resolved via IoC               |
| Controlled transactions    | Declarative semantics (`REQUIRED`, `REQUIRES_NEW`, etc.) |
| Async-safe                 | `contextvars` ensure per-task session isolation          |

---

## 3. Repository Model

Repositories are **plain Python classes** declared with `@repository`.
They:

* receive dependencies via `__init__`
* run their methods inside transactional decorators
* access the active session using `get_session()`

```python
@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @transactional(read_only=True)
    def find_all(self):
        session = get_session(self.manager)
        return session.query(User).all()

    @transactional
    def save(self, user: User):
        session = get_session(self.manager)
        session.add(user)
        return user
```

No transactional code inside the repository.
No global sessions.
No shared state.

---

## 4. Transaction Registration Strategy

At startup:

1. `@repository` registers the class as a transactional component.
2. pico-sqlalchemy automatically applies a MethodInterceptor to all its methods.
3. During execution:

   * The interceptor reads the method’s metadata (`@transactional`)
   * It opens, joins, suspends, or creates a new transaction
     depending on the propagation mode
   * It executes the method inside a transactional context

Equivalent to Spring Data or JPA-style declarative transactions.

---

## 5. Transaction Propagation Model

Supported propagation levels:

| Propagation     | Behavior                                          |
| --------------- | ------------------------------------------------- |
| `REQUIRED`      | Join existing or start new                        |
| `REQUIRES_NEW`  | Suspend current, always start new                 |
| `SUPPORTS`      | Join if exists, else run without transaction      |
| `MANDATORY`     | Must already be in a transaction                  |
| `NOT_SUPPORTED` | Suspend any transaction and run non-transactional |
| `NEVER`         | Error if a transaction is active                  |

Session lifecycle is fully deterministic:

```
begin → work → commit or rollback → close
```

Rollback logic is selective via:

* `rollback_for=(...)`
* `no_rollback_for=(...)`

---

## 6. Scoping Model

pico-sqlalchemy does **not** introduce custom scopes.
Instead, it relies on transaction boundaries:

| Scope                       | Meaning                                 |
| --------------------------- | --------------------------------------- |
| Transaction (implicit)      | Session lifetime                        |
| Singleton                   | SessionManager, config, factories       |
| Request-specific (optional) | Available if combined with pico-fastapi |
| Custom IoC scopes           | Fully supported if user defines them    |

Unlike pico-fastapi, there is no middleware layer.
The container itself drives the entire lifecycle.

---

## 7. Cleanup & Session Lifecycle

`SessionManager` ensures:

* sessions are always closed
* transactions are always committed or rolled back
* suspended transactions (REQUIRES_NEW, NOT_SUPPORTED) are properly restored

All cleanup is deterministic and safe, with no global state or leaked sessions.

---

## 8. Architectural Intent

**pico-sqlalchemy exists to:**

* Provide declarative, Spring-style transaction management for Python
* Replace ad-hoc `session = Session()` scattered across repositories
* Centralize session creation and lifecycle in a single place
* Make transactional semantics explicit and testable
* Ensure business logic is clean and free from persistence boilerplate

It does *not* attempt to:

* Replace SQLAlchemy ORM or engine
* Change SQLAlchemy’s session model
* Hide transaction boundaries
* Provide implicit magic or auto-scanning

---

## 9. When to Use

Use pico-sqlalchemy if:

✔ Your application uses SQLAlchemy ORM
✔ You want clean repository/service layers
✔ You prefer declarative transactions
✔ You want deterministic session lifecycle
✔ You value testability and DI patterns

Avoid pico-sqlalchemy if:

✖ You rely heavily on SQLAlchemy's Session-injection via Depends
✖ You prefer manual session management
✖ You only use SQLAlchemy Core with no ORM session lifecycle

---

## 10. Summary

`pico-sqlalchemy` is a **structural transaction management tool**:
It lets SQLAlchemy focus on persistence and mapping,
while **Pico-IoC** owns composition, lifecycle, and transactional semantics.

> SQLAlchemy stays pure.
> Your domain stays clean.
> Dependencies stay explicit.

