# Transaction Management

This library provides declarative transaction management via decorators, integrating strict propagation rules similar to enterprise frameworks (e.g., Spring).

## The `@transactional` Decorator

The primary entry point is the `transactional` decorator. It relies on `pico_ioc` code interception to wrap method calls in an asyncio-compatible SQLAlchemy session.

```python
from pico_sqlalchemy import transactional

class UserService:
    @transactional
    async def create_user(self, name: str):
        # A session is automatically active here
        ...
```

### Configuration Options

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `propagation` | `str` | `"REQUIRED"` | Defines how the transaction boundaries behave when called within another transaction. |
| `read_only` | `bool` | `False` | If `True`, the session will explicitly avoid calling `commit()` at the end. |
| `isolation_level` | `str` | `None` | Sets the database isolation level (e.g., `"SERIALIZABLE"`). |
| `rollback_for` | `tuple` | `(Exception,)` | Exception types that trigger a rollback. |
| `no_rollback_for` | `tuple` | `()` | Exception types that should **not** trigger an explicit rollback. |

-----

## Propagation Levels

The library implements strict propagation logic. The behavior depends on whether an active transaction context already exists.

### 1\. REQUIRED (Default)

  * **Existing Transaction:** Joins the existing transaction.
  * **No Transaction:** Creates a new transaction.
  * **Use Case:** Default behavior for most service methods.

### 2\. REQUIRES\_NEW

  * **Existing Transaction:** Suspends the current transaction context, creates a completely new (independent) transaction, and resumes the parent context afterwards.
  * **No Transaction:** Creates a new transaction.
  * **Use Case:** Audit logging or independent operations that must succeed even if the outer transaction fails.

### 3\. SUPPORTS

  * **Existing Transaction:** Joins the existing transaction.
  * **No Transaction:** Executes without a transactional context (session created but strictly scoped locally without strict commit guarantees/context binding).
  * **Use Case:** Read-only operations that can adapt to the caller's context.

### 4\. MANDATORY

  * **Existing Transaction:** Joins the existing transaction.
  * **No Transaction:** Raises `RuntimeError`.
  * **Use Case:** Methods that strictly rely on an upstream transaction ensuring data consistency.

### 5\. NEVER

  * **Existing Transaction:** Raises `RuntimeError`.
  * **No Transaction:** Executes without a transactional context.
  * **Use Case:** Operations that must explicitly avoid transactional overhead or potential deadlocks.

### 6\. NOT\_SUPPORTED

  * **Existing Transaction:** Suspends the current transaction and executes non-transactionally.
  * **No Transaction:** Executes non-transactionally.
  * **Use Case:** Long-running operations or external API calls where holding a database lock is undesirable.

-----

## Rollback Rules

By default, any exception inheriting from `Exception` triggers a `rollback()`.

### Customizing Rollback

You can define specific exceptions to trigger or ignore rollback.

```python
@transactional(
    rollback_for=(MyCustomError,),
    no_rollback_for=(ValueError,)
)
async def business_logic():
    # ...
```

**Important Note on `no_rollback_for`:**
If an exception matches `no_rollback_for`, the library skips the explicit `session.rollback()` call. However, because the execution flow was interrupted by an exception, the `session.commit()` is **also skipped**. The session is simply closed. This usually results in the database discarding the changes (implicit rollback), depending on the driver, but avoids the overhead of an explicit rollback command.

## Accessing the Session

To access the underlying SQLAlchemy `AsyncSession` manually within a transactional method:

```python
from pico_sqlalchemy import SessionManager, get_session

@component
class MyRepository:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    async def save(self, entity):
        # Retrieves the session bound to the current context contextvar
        session = get_session(self.sm)
        session.add(entity)
```

