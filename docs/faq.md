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

## Troubleshooting

### "No active transaction" error

This error occurs when calling repository methods outside a transaction context. Ensure your method is decorated with `@transactional` or called from within a transaction.

### "MANDATORY propagation requires active transaction"

You're using `propagation="MANDATORY"` but there's no existing transaction. Either call from within a transaction or change the propagation mode.

### Connection pool exhausted

Increase pool size in the database configuration:

```python
config = configuration(DictSource({
    "database": {
        "url": "postgresql+asyncpg://user:pass@host/db",
        "pool_size": 20,
        "pool_recycle": 3600,
    }
}))
```
