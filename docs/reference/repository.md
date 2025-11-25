# Declarative Repositories & Queries

Pico-SQLAlchemy provides a powerful repository pattern that combines **Implicit Transactions** with **Declarative Query Execution**.

This allows you to write data access layers with minimal boilerplate, focusing only on the query logic or the business operation.

---

## 1. The `@repository` Decorator

The `@repository` decorator marks a class as a Pico-IoC component (singleton by default).

### Automatic Transaction Management
Crucially, **any public `async` method** defined in a `@repository` class is automatically wrapped in a **Read-Write Transaction** (`propagation="REQUIRED"`).

This means you do **not** need to manually add `@transactional` to your CRUD methods.

```python
from pico_sqlalchemy import repository, SessionManager, get_session

@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    # Implicitly transactional (Read-Write)
    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user
````

### Entity Binding

You can optionally bind a repository to a specific SQLAlchemy model using the `entity` parameter. This is required if you want to use **Expression Mode** in `@query`.

```python
@repository(entity=User)
class UserRepository:
    ...
```

-----

## 2\. Declarative Queries (`@query`)

The `@query` decorator allows you to define database queries declaratively.

  * **No Implementation Needed:** The method body is ignored. The library intercepts the call, binds arguments, executes the query, and maps the result.
  * **Implicit Read-Only Transaction:** All `@query` methods run automatically in a **Read-Only** transaction for performance safety.

### Mode A: Expression Mode (`expr`)

This is the most concise mode. It requires `@repository(entity=Model)`. You only provide the `WHERE` clause.

```python
@repository(entity=User)
class UserRepository:
    
    # Effectively runs: SELECT * FROM users WHERE username = :username
    @query(expr="username = :username", unique=True)
    async def find_by_username(self, username: str) -> User | None:
        ...

    # Effectively runs: SELECT * FROM users WHERE active = true
    @query(expr="active = true")
    async def find_all_active(self) -> list[User]:
        ...
```

### Mode B: SQL Mode (`sql`)

Use this for full control, joins, raw SQL, or complex projections. It does **not** require an `entity` binding on the repository.

```python
@repository
class StatsRepository:

    @query(sql="SELECT count(*) as total FROM users")
    async def count_users(self) -> int:
        ...

    @query(sql="SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.user_id WHERE u.id = :uid")
    async def get_user_posts(self, uid: int) -> list[dict]:
        ...
```

-----

## 3\. Pagination

Pico-SQLAlchemy has built-in support for offset-based pagination.

1.  Set `paged=True` in the `@query` decorator.
2.  Add a parameter of type `PageRequest` to your method signature.
3.  Set the return type to `Page[T]`.

The library automatically generates a count query (e.g., `SELECT COUNT(*) FROM (...)`) and the paginated data query (`LIMIT ... OFFSET ...`).

```python
from pico_sqlalchemy import Page, PageRequest

@repository(entity=User)
class UserRepository:

    @query(expr="active = true", paged=True)
    async def find_active_paged(self, page: PageRequest) -> Page[User]:
        ...

# Usage:
# await repo.find_active_paged(PageRequest(page=0, size=10))
```

-----

## 4\. Return Types & mapping

The `@query` interceptor is smart about return types:

  * **`unique=True`**: Returns a single scalar/object or `None` (uses `result.scalars().first()` or mappings).
  * **Default (List)**: Returns a list of scalars/objects (uses `result.scalars().all()` or mappings).
  * **Raw SQL**: If the query returns multiple columns (not a mapped entity), it returns dictionary-like mappings.

-----

## 5\. Summary of Behavior

| Decorator | Transaction Mode | Execution Logic |
| :--- | :--- | :--- |
| **`@repository` (Plain Method)** | **Read-Write** | Executes your Python code body. |
| **`@query`** | **Read-Only** | **Ignores** body; executes SQL/Expr automatically. |
| **`@transactional`** | **Explicit** | Executes your Python code body with custom config. |

