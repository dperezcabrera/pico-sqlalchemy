# Transaction Management

Pico-SQLAlchemy provides a robust transaction management system inspired by enterprise frameworks (like Spring Data), but adapted for Python's `asyncio` ecosystem.

It supports **Implicit Transactions** (Zero-Boilerplate) and **Explicit Transactions** (Fine-grained control).

---

## 1. Implicit Transactions (Zero-Boilerplate)

To reduce code verbosity, `pico-sqlalchemy` applies transactional behavior automatically based on component types.

### Repositories (`@repository`)
By default, **any public async method** within a class decorated with `@repository` runs inside a **Read-Write** transaction.

* **Propagation:** `REQUIRED` (Joins existing or creates new).
* **Mode:** Read-Write.
* **Use Case:** Standard CRUD operations (`save`, `update`, `delete`).

```python
@repository
class UserRepository:
    # Implicitly transactional (Read-Write)
    async def save(self, user: User):
        ...
```

### Declarative Queries (`@query`)

Methods decorated with `@query` are automatically wrapped in a **Read-Only** transaction.

  * **Propagation:** `REQUIRED` (Joins existing or creates new).
  * **Mode:** Read-Only.
  * **Use Case:** Fetching data efficiently.

<!-- end list -->

```python
@repository(entity=User)
class UserRepository:
    # Implicitly transactional (Read-Only)
    @query(expr="active = true")
    async def find_active(self):
        ...
```

-----

## 2\. Configuration Priority

Since multiple rules can apply to a single method (e.g., a method in a repository that also has `@transactional`), the library follows a strict priority order (highest wins).

| Priority | Decorator | Default Behavior | Description |
| :--- | :--- | :--- | :--- |
| **1 (High)** | **`@transactional`** | User Defined | Explicit configuration always overrides implicit rules. |
| **2** | **`@query`** | `read_only=True` | Specific query definition implies read-only intent. |
| **3 (Low)** | **`@repository`** | `read_only=False` | General repository methods assume write capability by default. |

### Examples

**Scenario A: Overriding Repository Default**
You want a complex reporting method inside a repository to be Read-Only for performance, but it doesn't use `@query`.

```python
@repository
class ReportRepository:
    # Default is Read-Write...
    
    # Override to Read-Only!
    @transactional(read_only=True)
    async def generate_complex_stats(self):
        # ... logic ...
```

**Scenario B: Overriding Query Default**
Rare case where a `@query` (usually read-only) involves a stored procedure that writes data.

```python
@query(sql="CALL update_stats()")
@transactional(read_only=False)  # Force Read-Write
async def update_statistics(self):
    ...
```

-----

## 3\. The `@transactional` Decorator

Use `@transactional` when you need to define boundaries in your **Service Layer** or when you need to override defaults in Repositories.

```python
from pico_sqlalchemy import transactional

class UserService:
    @transactional(propagation="REQUIRES_NEW")
    async def create_user(self, name: str):
        # ...
```

### Configuration Options

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `propagation` | `str` | `"REQUIRED"` | Defines behavior regarding existing transactions. |
| `read_only` | `bool` | `False` | If `True`, avoids explicit commit (optimization). |
| `isolation_level` | `str` | `None` | Sets DB isolation (e.g., `"SERIALIZABLE"`). |
| `rollback_for` | `tuple` | `(Exception,)` | Exception types that trigger rollback. |
| `no_rollback_for` | `tuple` | `()` | Exception types that ignore rollback. |

-----

## 4\. Propagation Levels

The library implements strict propagation logic:

  * **`REQUIRED` (Default):** Joins an existing transaction or creates a new one.
  * **`REQUIRES_NEW`:** Suspends the current transaction (if any) and starts a fresh, independent transaction.
  * **`SUPPORTS`:** Joins an existing transaction if available; otherwise, executes without a transaction context.
  * **`MANDATORY`:** Requires an existing transaction; raises `RuntimeError` otherwise.
  * **`NEVER`:** Requires *no* active transaction; raises `RuntimeError` if one exists.
  * **`NOT_SUPPORTED`:** Suspends the current transaction and executes non-transactionally.

-----

## 5\. Rollback Rules

By default, **any exception** (inheriting from `Exception`) triggers a `rollback()`.

### Customizing Rollback

```python
@transactional(
    rollback_for=(MyCriticalError,),
    no_rollback_for=(ValidationWarning,)
)
async def business_logic():
    # ...
```

**Note:** If an exception matches `no_rollback_for`, the library skips the explicit `rollback()`, but the `commit()` is also skipped (the session closes naturally).

-----

## 6\. Accessing the Session

Within any transactional method (Implicit or Explicit), the `AsyncSession` is bound to the current context.

```python
from pico_sqlalchemy import SessionManager, get_session

@component
class MyService:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    @transactional
    async def do_work(self):
        # Safely retrieve the current session
        session = get_session(self.sm)
        # ... use session ...
```
