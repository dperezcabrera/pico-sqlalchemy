Read and follow ./AGENTS.md for project conventions.

## Pico Ecosystem Context

pico-sqlalchemy provides SQLAlchemy integration for pico-ioc. It uses:
- `@factory` + `@provides` for SessionManager creation
- `@configured` for DatabaseSettings
- `MethodInterceptor` for both `TransactionalInterceptor` and `RepositoryQueryInterceptor`
- Auto-discovered via `pico_boot.modules` entry point

## Key Reminders

- pico-ioc dependency: `>= 2.2.0`
- **NEVER change `version_scheme`** in pyproject.toml. It MUST remain `"post-release"`. Changing it to `"guess-next-dev"` causes `.dev0` versions to leak to PyPI. This was already fixed once — do not revert it.
- requires-python >= 3.11
- Commit messages: one line only
- `@transactional` works both with and without parentheses (like `@repository`)
- `SessionManager` has NO `@component` decorator - it's created by the factory
- `_tx_context` ContextVar is for session propagation, NOT the same as pico-ioc's "transaction" scope
