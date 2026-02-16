# Frequently Asked Questions

## General

### What is Pico-SQLAlchemy?

Pico-SQLAlchemy provides seamless integration between Pico-IoC and SQLAlchemy, offering async support, declarative transaction management, and a clean repository pattern for data access.

### What Python versions are supported?

Pico-SQLAlchemy requires Python 3.11 or later.

### What SQLAlchemy versions are supported?

SQLAlchemy 2.0 or later is required for full async support.

## Configuration

### How do I configure the database connection?

Provide the database URL via configuration:

```python
from pico_ioc import init, configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "postgresql+asyncpg://user:pass@host/db",
        "echo": False,
        "pool_size": 10,
    }
}))

container = init(modules=["pico_sqlalchemy", "my_app"], config=config)
```

### What database drivers are supported?

Any async-compatible SQLAlchemy driver works:

- **PostgreSQL**: `asyncpg`
- **SQLite**: `aiosqlite`
- **MySQL**: `aiomysql`

## Transactions

### What propagation modes are available?

| Mode | Description |
|------|-------------|
| `REQUIRED` | Join existing or create new (default) |
| `REQUIRES_NEW` | Always create a new transaction |
| `MANDATORY` | Must have an existing transaction |
| `SUPPORTS` | Use existing if available, otherwise none |
| `NOT_SUPPORTED` | Suspend existing transaction |
| `NEVER` | Must NOT have an existing transaction |

### How do I use read-only transactions?

```python
@transactional(read_only=True)
async def get_users(repo: UserRepository):
    return await repo.find_all()
```

### Can I set isolation levels?

Yes, use the `isolation_level` parameter:

```python
@transactional(isolation_level="SERIALIZABLE")
async def critical_operation():
    ...
```

## Repositories

### What's the difference between SQL and expression mode?

- **SQL mode** (`sql=`): Write raw SQL queries
- **Expression mode** (`expr=`): Write WHERE clause expressions, table name is derived from entity

```python
# SQL mode - full control
@query(sql="SELECT * FROM users WHERE status = :status")
async def find_by_status(self, status: str): ...

# Expression mode - cleaner for simple queries
@query(expr="status = :status")
async def find_by_status(self, status: str): ...
```

### How do I implement pagination?

Use `paged=True` and pass a `PageRequest`:

```python
from pico_sqlalchemy import PageRequest, Sort

@query(expr="active = true", paged=True)
async def find_active(self, page: PageRequest): ...

# Usage
page_req = PageRequest(page=0, size=10, sorts=[Sort("name", "ASC")])
result = await repo.find_active(page=page_req)
print(result.content)  # List of items
print(result.total_elements)  # Total count
```

### Can I use dynamic sorting?

Dynamic sorting via `PageRequest.sorts` is only supported in expression mode. For SQL mode, include the ORDER BY clause in your SQL string.

---

## Troubleshooting

This section documents every error message raised by pico-sqlalchemy and how to resolve it.

---

### `RuntimeError: "No active transaction"`

**Source:** `get_session()` in `session.py`

**Cause:** You called `get_session(manager)` but there is no active `TransactionContext` on the current async task. This means the code is not executing inside a `@transactional`, `@repository`, or `manager.transaction()` block.

**Fix:** Ensure the calling method is wrapped in a transaction:

```python
# Option 1: Use @transactional on the method
@transactional
async def my_method(self):
    session = get_session(self.sm)  # Works

# Option 2: Use @repository on the class (implicit transactions)
@repository
class MyRepo:
    async def save(self, item):
        session = get_session(self.sm)  # Works

# Option 3: Use manager.transaction() directly
async with manager.transaction() as session:
    session.add(item)  # Works
```

---

### `RuntimeError: "MANDATORY propagation requires active transaction"`

**Source:** `SessionManager._propagation_mandatory()` in `session.py`

**Cause:** You used `propagation="MANDATORY"` but there is no existing transaction to join. MANDATORY requires that the caller already has an active transaction.

**Fix:** Either call from within a transaction, or change the propagation:

```python
# Correct: called from within an existing transaction
@transactional
async def outer(self):
    await self.inner()  # inner uses MANDATORY - works because outer has tx

@transactional(propagation="MANDATORY")
async def inner(self):
    ...

# Alternative: use REQUIRED instead (creates a new tx if none exists)
@transactional(propagation="REQUIRED")
async def inner(self):
    ...
```

---

### `RuntimeError: "NEVER propagation forbids active transaction"`

**Source:** `SessionManager._propagation_never()` in `session.py`

**Cause:** You used `propagation="NEVER"` but there IS an active transaction. NEVER requires that no transaction is active.

**Fix:** Do not call NEVER-propagated methods from within a transaction, or change the propagation mode:

```python
# Wrong: calling NEVER inside a transaction
@transactional
async def outer(self):
    await self.no_tx_method()  # Raises RuntimeError

@transactional(propagation="NEVER")
async def no_tx_method(self):
    ...

# Fix: call outside any transaction, or use NOT_SUPPORTED instead
@transactional(propagation="NOT_SUPPORTED")
async def no_tx_method(self):
    ...  # Suspends outer tx, runs without transaction
```

---

### `RuntimeError: "@query with expr requires @repository(entity=...) and an entity with __tablename__"`

**Source:** `RepositoryQueryInterceptor._validate_entity()` in `repository_interceptor.py`

**Cause:** You used `@query(expr="...")` (expression mode) but the class is not decorated with `@repository(entity=Model)`, or the entity does not have a `__tablename__` attribute.

**Fix:** Add the entity to the `@repository` decorator:

```python
# Wrong: no entity specified
@repository
class UserRepo:
    @query(expr="name = :name")
    async def find(self, name: str): ...

# Correct: entity specified
@repository(entity=User)
class UserRepo:
    @query(expr="name = :name")
    async def find(self, name: str): ...
```

---

### `TypeError: "Paged query requires a 'page: PageRequest' parameter"`

**Source:** `_extract_page_request()` in `repository_interceptor.py`

**Cause:** You used `@query(..., paged=True)` but the method does not have a parameter named `page` of type `PageRequest`.

**Fix:** Add a `page: PageRequest` parameter:

```python
# Wrong: missing page parameter
@query(expr="active = true", paged=True)
async def find_active(self): ...

# Correct
@query(expr="active = true", paged=True)
async def find_active(self, page: PageRequest): ...
```

---

### `ValueError: "Dynamic sorting via PageRequest is not supported in SQL mode"`

**Source:** `RepositoryQueryInterceptor._execute_sql()` in `repository_interceptor.py`

**Cause:** You passed a `PageRequest` with non-empty `sorts` to a `@query(sql="...")` method. Dynamic sorting is forbidden in SQL mode to prevent SQL injection.

**Fix:** Move the ORDER BY into the SQL string, or use expression mode:

```python
# Wrong: dynamic sorts with raw SQL
@query(sql="SELECT * FROM users", paged=True)
async def find_all(self, page: PageRequest): ...
# called with: PageRequest(page=0, size=10, sorts=[Sort("name")])

# Fix option 1: add ORDER BY to the SQL
@query(sql="SELECT * FROM users ORDER BY name ASC", paged=True)
async def find_all(self, page: PageRequest): ...
# called with: PageRequest(page=0, size=10)  # no sorts

# Fix option 2: use expression mode (sorts are validated and safe)
@query(expr="1=1", paged=True)
async def find_all(self, page: PageRequest): ...
# called with: PageRequest(page=0, size=10, sorts=[Sort("name")])
```

---

### `ValueError: "Invalid sort field: <field>"`

**Source:** `_build_order_by_clause()` in `repository_interceptor.py`

**Cause:** A `Sort.field` in `PageRequest.sorts` does not match any column name on the entity's `__table__`. This validation exists to prevent SQL injection.

**Fix:** Use only column names that exist on the entity model:

```python
class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))

# Wrong: "username" is not a column on User
PageRequest(page=0, size=10, sorts=[Sort("username")])

# Correct: "name" is a valid column
PageRequest(page=0, size=10, sorts=[Sort("name")])
```

---

### `ValueError: "Invalid sort direction: <value> (expected 'ASC' or 'DESC')"`

**Source:** `Sort.__post_init__()` in `paging.py`

**Cause:** The `direction` argument to `Sort` is not `"ASC"` or `"DESC"`.

**Fix:**

```python
# Wrong
Sort("name", "ASCENDING")

# Correct
Sort("name", "ASC")
Sort("name", "DESC")
```

---

### `ValueError: "Invalid propagation: <value>"`

**Source:** `transactional()` in `decorators.py`

**Cause:** The `propagation` argument is not one of the six valid modes.

**Fix:** Use one of: `REQUIRED`, `REQUIRES_NEW`, `SUPPORTS`, `MANDATORY`, `NOT_SUPPORTED`, `NEVER`.

```python
# Wrong
@transactional(propagation="NESTED")

# Correct
@transactional(propagation="REQUIRES_NEW")
```

---

### `ValueError: "Unknown propagation: <value>"`

**Source:** `SessionManager._get_propagation_handler()` in `session.py`

**Cause:** Same as above but raised at runtime when using `manager.transaction(propagation=...)` directly with an invalid mode.

**Fix:** Use one of the six valid propagation strings.

---

### `ValueError: "query decorator requires either 'expr' or 'sql'"`

**Source:** `query()` in `decorators.py`

**Cause:** You called `@query()` without providing either `expr` or `sql`.

**Fix:**

```python
# Wrong
@query()
async def find(self): ...

# Correct
@query(expr="active = true")
async def find(self): ...
```

---

### `ValueError: "query decorator cannot use both 'expr' and 'sql'"`

**Source:** `query()` in `decorators.py`

**Cause:** You provided both `expr` and `sql` to `@query`. These modes are mutually exclusive.

**Fix:** Use only one:

```python
# Wrong
@query(expr="active = true", sql="SELECT * FROM users")

# Correct
@query(expr="active = true")
# or
@query(sql="SELECT * FROM users WHERE active = true")
```

---

### `RuntimeError: "Unsupported query mode: <mode>"`

**Source:** `RepositoryQueryInterceptor.invoke()` in `repository_interceptor.py`

**Cause:** Internal error. The query metadata has an unrecognised `mode` value. This should not occur under normal use.

**Fix:** Ensure you are using `@query(expr=...)` or `@query(sql=...)` -- do not set query metadata manually.

---

### Connection pool exhausted

**Cause:** Too many concurrent connections for the configured pool size.

**Fix:** Increase pool size in the database configuration:

```python
config = configuration(DictSource({
    "database": {
        "url": "postgresql+asyncpg://user:pass@host/db",
        "pool_size": 20,
        "pool_recycle": 3600,
    }
}))
```
