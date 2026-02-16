# Migration Guide: 0.1.x to 0.2.0

This guide documents all changes required when upgrading from pico-sqlalchemy 0.1.x to 0.2.0.

---

## Summary of Changes

| Area | What changed |
|------|-------------|
| **`@query` decorator** | New declarative query system (expression and SQL modes) |
| **`RepositoryQueryInterceptor`** | New interceptor for query execution |
| **Pagination** | New `PageRequest`, `Page[T]`, `Sort` data types |
| **`@transactional` without parens** | Now works as `@transactional` (no parentheses) |
| **pico-ioc dependency** | Bumped to `>= 2.2.0` |
| **Python support** | Dropped Python 3.10 |
| **`Sort` export** | Added to `__init__.py` and `__all__` |

---

## Required Changes

### 1. Update pico-ioc Dependency

pico-sqlalchemy 0.2.0 requires pico-ioc >= 2.2.0. Update your `pyproject.toml` or `requirements.txt`:

```
pico-ioc>=2.2.0
pico-sqlalchemy>=0.2.0
```

### 2. Python Version

Python 3.10 is no longer supported. Ensure you are running Python >= 3.11.

---

## Optional Migrations (New Features)

### 3. Adopt `@query` for Declarative Queries

The biggest new feature in 0.2.0 is the `@query` decorator. It replaces hand-written query logic in repositories with declarative, interceptor-executed queries.

#### Before (0.1.x): Manual query in repository method

```python
from sqlalchemy import select
from pico_sqlalchemy import repository, SessionManager, get_session

@repository
class UserRepository:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    async def find_by_email(self, email: str) -> User | None:
        session = get_session(self.sm)
        stmt = select(User).where(User.email == email)
        result = await session.scalars(stmt)
        return result.first()

    async def find_active(self) -> list[User]:
        session = get_session(self.sm)
        stmt = select(User).where(User.active == True)
        result = await session.scalars(stmt)
        return list(result.all())
```

#### After (0.2.0): Declarative `@query`

```python
from pico_sqlalchemy import repository, query, SessionManager, get_session

@repository(entity=User)
class UserRepository:
    def __init__(self, sm: SessionManager):
        self.sm = sm

    # Expression mode: generates SELECT * FROM users WHERE email = :email
    @query(expr="email = :email", unique=True)
    async def find_by_email(self, email: str) -> User | None:
        ...  # Body is never executed

    # Expression mode: generates SELECT * FROM users WHERE active = true
    @query(expr="active = true")
    async def find_active(self) -> list[User]:
        ...  # Body is never executed
```

**Key differences:**

- Add `entity=User` to the `@repository` decorator (required for expression mode).
- Replace the method body with `...` (Ellipsis) -- the body is never executed.
- The `@query` decorator handles session access, query building, and result mapping.
- `unique=True` returns a single result or `None` (like `.first()`).

### 4. Adopt `@query.sql` for Raw SQL

For complex queries that cannot be expressed as a simple WHERE clause:

#### Before (0.1.x)

```python
async def count_posts_by_user(self) -> list:
    session = get_session(self.sm)
    result = await session.execute(text(
        "SELECT u.name, count(p.id) as post_count "
        "FROM users u JOIN posts p ON u.id = p.user_id "
        "GROUP BY u.name"
    ))
    return result.mappings().all()
```

#### After (0.2.0)

```python
@query.sql(
    "SELECT u.name, count(p.id) as post_count "
    "FROM users u JOIN posts p ON u.id = p.user_id "
    "GROUP BY u.name"
)
async def count_posts_by_user(self):
    ...
```

### 5. Adopt Pagination

#### Before (0.1.x): Manual pagination

```python
async def find_paginated(self, offset: int, limit: int) -> tuple[list[User], int]:
    session = get_session(self.sm)
    count_result = await session.execute(
        text("SELECT COUNT(*) FROM users WHERE active = true")
    )
    total = count_result.scalar_one()

    result = await session.execute(
        text("SELECT * FROM users WHERE active = true LIMIT :limit OFFSET :offset"),
        {"limit": limit, "offset": offset},
    )
    rows = result.mappings().all()
    return rows, total
```

#### After (0.2.0): Declarative pagination

```python
from pico_sqlalchemy import query, PageRequest, Page, Sort

@query(expr="active = true", paged=True)
async def find_active(self, page: PageRequest) -> Page:
    ...

# Usage:
page_req = PageRequest(page=0, size=20, sorts=[Sort("name", "ASC")])
result = await repo.find_active(page=page_req)
# result.content       -> list of rows
# result.total_elements -> total count
# result.total_pages    -> computed
# result.is_first       -> True
# result.is_last        -> depends on total
```

### 6. Simplify `@transactional` (No Parentheses)

#### Before (0.1.x)

```python
@transactional()
async def my_method(self):
    ...
```

#### After (0.2.0): Both forms work

```python
# Without parentheses (new in 0.2.0)
@transactional
async def my_method(self):
    ...

# With parentheses (still works)
@transactional(propagation="REQUIRES_NEW")
async def my_method(self):
    ...
```

---

## Backward Compatibility

All 0.1.x patterns continue to work in 0.2.0:

- Manual query methods in `@repository` classes still run inside implicit transactions.
- `@transactional()` with parentheses still works.
- `SessionManager`, `get_session()`, and all propagation modes are unchanged.

The new `@query` decorator and pagination types are purely additive. You can adopt them incrementally, one repository method at a time.
