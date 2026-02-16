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
```

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

**Features:**

  * Automatic `SELECT * FROM table` generation.
  * Supports **Dynamic Sorting** via `PageRequest`.

<!-- end list -->

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

**Features:**

  * Full control over the SQL string.
  * **Does NOT support Dynamic Sorting** via `PageRequest`. You must write the `ORDER BY` clause yourself.

**Usage:**

You can use the standard `@query(sql="...")` syntax or the **`@query.sql("...")`** shortcut.

```python
@repository
class StatsRepository:

    # Option 1: Standard syntax
    @query(sql="SELECT count(*) as total FROM users")
    async def count_users(self) -> int:
        ...

    # Option 2: Shortcut syntax (Cleaner)
    @query.sql(
        "SELECT u.name, p.title FROM users u "
        "JOIN posts p ON u.id = p.user_id "
        "WHERE u.id = :uid "
        "ORDER BY u.name"
    )
    async def get_user_posts(self, uid: int) -> list[dict]:
        ...
```

-----

## 3\. Pagination & Sorting

Pico-SQLAlchemy provides built-in support for offset-based pagination and dynamic sorting.

### Basic Pagination

1.  Set `paged=True` in the `@query` decorator.
2.  Add a parameter **explicitly named** `page` of type `PageRequest` to your method signature.
3.  Set the return type to `Page[T]`.

The library automatically generates the count query and applies limits/offsets.

> **Important:** The argument **must** be named `page`. Using other names (e.g., `req`, `pagination`) will result in a runtime error or ignored pagination.

```python
from pico_sqlalchemy import Page, PageRequest

@repository(entity=User)
class UserRepository:

    @query(expr="active = true", paged=True)
    async def find_active_paged(self, page: PageRequest) -> Page[User]:
        ...

# Usage: Get page 0, size 10
# await repo.find_active_paged(PageRequest(page=0, size=10))
```

### Dynamic Sorting

You can request dynamic sorting by passing a list of `Sort` objects within the `PageRequest`.

> **⚠️ Warning: Expression Mode Only**
>
> Dynamic sorting (injecting `ORDER BY` clauses based on `PageRequest`) works **only** in **Expression Mode (`expr`)**.
>
> If you use **SQL Mode (`sql`)** and provide a `PageRequest` with sorts, the library will raise a **`ValueError`**. This is a security measure to prevent ambiguity and injection risks in raw SQL.

**Security Note:** To prevent SQL Injection, dynamic sorting in `expr` mode validates that the requested sort fields exist in the underlying SQLAlchemy model columns. If a field is invalid, a `ValueError` is raised.

```python
from pico_sqlalchemy import PageRequest, Sort

# Usage: Sort by name ASC, then age DESC
request = PageRequest(
    page=0, 
    size=20, 
    sorts=[
        Sort(field="name", direction="ASC"),
        Sort(field="age", direction="DESC")
    ]
)

# Works automatically because this method uses @query(expr=...)
await repo.find_active_paged(request)
```

| Parameter | Description |
| :--- | :--- |
| `field` | The name of the column in the model (e.g., `"username"`). |
| `direction` | `"ASC"` (default) or `"DESC"`. |

-----

## 4\. Return Types & Mapping

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


