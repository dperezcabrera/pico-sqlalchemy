# pico-sqlalchemy

SQLAlchemy async integration for pico-ioc. Spring-style transactions, declarative queries, repository pattern.

## Commands

```bash
pip install -e ".[test]" aiosqlite   # Install in dev mode
pytest tests/ -v                      # Run tests
pytest --cov=pico_sqlalchemy --cov-report=term-missing tests/  # Coverage
tox                                   # Full matrix (3.11-3.14)
mkdocs serve -f mkdocs.yml           # Local docs
```

## Project Structure

```
src/pico_sqlalchemy/
  __init__.py              # Public API exports (including Sort)
  session.py               # SessionManager, TransactionContext, _tx_context ContextVar
  interceptor.py           # TransactionalInterceptor (AOP)
  repository_interceptor.py # RepositoryQueryInterceptor (query execution)
  decorators.py            # @transactional, @repository, @query
  config.py                # DatabaseSettings, DatabaseConfigurer protocol
  factory.py               # SqlAlchemyFactory, PicoSqlAlchemyLifecycle
  base.py                  # AppBase (DeclarativeBase), Mapped, mapped_column
  paging.py                # Page[T], PageRequest, Sort
```

## Key Concepts

- **`@transactional`**: Marks methods for transaction management. Works with and without parentheses. Uses `TransactionalInterceptor` (AOP)
- **`@repository(entity=Model)`**: Class decorator. All async methods get implicit read-write transactions
- **`@query(expr="...", sql="...", paged=True, unique=True)`**: Declarative queries. `expr` mode requires entity. `sql` mode is raw SQL
- **Propagation modes**: REQUIRED, REQUIRES_NEW, MANDATORY, NEVER, NOT_SUPPORTED, SUPPORTS
- **Priority chain**: `@transactional` > `@query` (read-only) > `@repository` (read-write)
- **`SessionManager`**: Created by `SqlAlchemyFactory` (not `@component`). Manages engine, sessions, transactions
- **`_tx_context` ContextVar**: Holds `TransactionContext` (the session) for propagation across nested calls — the *session* side of a transaction
- **`"transaction"` DI scope**: `TransactionalInterceptor` activates pico-ioc's `"transaction"` scope (with `cleanup=True`) whenever a *new* transaction starts (REQUIRES_NEW, or REQUIRED with no enclosing tx). So a `scope="transaction"` component is one instance per transaction (Unit-of-Work / identity-map), released with its `@cleanup` hooks when the tx ends. The session ContextVar and the DI scope are two facets of one boundary
- **`get_session(manager)`**: Returns current session from active transaction context
- **Non-transactional paths** (NEVER, NOT_SUPPORTED, SUPPORTS without tx): Still set `TransactionContext` so `get_session()` works, but open no DI `"transaction"` scope (resolving a `scope="transaction"` component there raises `ScopeError`)

## Code Style

- Python 3.11+
- Async-first (`AsyncSession`, `create_async_engine`)
- `Sort.direction` validated: only "ASC" or "DESC"
- `Page[T]` is generic, frozen dataclass
- No `@component` on `SessionManager` - only `@provides` in factory

## Testing

- pytest + pytest-asyncio (mode=strict)
- `aiosqlite` for in-memory SQLite tests
- Direct `SessionManager(url="sqlite+aiosqlite:///:memory:")` for unit tests
- `init(modules=["pico_sqlalchemy", __name__])` for integration tests
- Target: >95% coverage

## Boundaries

- Do not modify `_version.py`
- Do not add `@component` to `SessionManager` (factory creates it)
- `_tx_context` (session propagation) and the pico-ioc `"transaction"` DI scope are bound to one boundary by `TransactionalInterceptor` — keep them coordinated; do not reintroduce a second, independent transaction concept
