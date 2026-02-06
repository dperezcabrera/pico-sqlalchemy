# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.html).

---

## [0.2.0] - 2026-02-06

### Added
- **`@query` Decorator**: Declarative SQL/expression queries on repository methods via AOP interception.
- **`RepositoryQueryInterceptor`**: New `MethodInterceptor` that executes SQL text or SQLAlchemy expressions, with automatic pagination support.
- **Pagination**: `PageRequest`, `Page`, and `Sort` dataclasses for paginated and sorted query results.
- **Sort Validation**: `Sort.__post_init__` rejects invalid directions (only `"ASC"` / `"DESC"` allowed).
- **`@transactional` without parentheses**: Decorator now works both as `@transactional` and `@transactional(propagation=...)`.
- **Export**: `Sort` added to `__init__.py` and `__all__`.
- Full MkDocs documentation site with Material theme: quickstart, architecture, reference guides (configuration, declarative-base, repository, transactions), FAQ.
- `tests/test_pagination_sort.py`: Pagination and sorting tests.
- `tests/test_repository_interceptor_coverage.py`: Repository interceptor edge-case tests.
- `tests/test_repository_query.py`: Full query execution tests.
- GitHub Actions workflow for documentation deployment.

### Changed
- **Code Quality**: Major refactoring of `repository_interceptor.py` — extracted helper functions (`_extract_page_request`, `_build_order_by_clause`, `_execute_count_query`, `_execute_paginated_query`, `_execute_simple_query`).
- **Code Quality**: Refactored `session.py` — extracted `_build_engine_kwargs`, `_should_rollback`, split propagation modes into individual async generators via dispatch table.
- **Documentation**: Overhauled README and all reference docs.
- **CI/CD**: Unified documentation deployment workflow.
- Bumped `pico-ioc` dependency to `>= 2.2.0`.
- Dropped Python 3.10 from CI matrix.

### Fixed
- **Dynamic Sorting Safety**: Prevent dynamic column sorting in raw SQL mode to avoid injection.

---

## [0.1.1] - 2025-11-18

### Fixed
- **Architecture:** Removed the global `_default_manager` singleton ("Service Locator" anti-pattern). `SessionManager` is now purely managed by the IoC container.
- **Decorators:** Refactored `@transactional` to use `pico-ioc`'s AOP system (`@intercepted_by`) instead of manual function wrapping. This ensures proper dependency injection of the `SessionManager` into the interceptor, enabling support for multiple databases/managers in the future.
- **Cleanup:** Removed unused `REPOSITORIES` global set.
- Updated dependency requirement to `pico-ioc>=2.1.3`.

### Changed
- **Internal:** `SessionManager` no longer registers itself globally upon instantiation. Components needing a session manager must have it injected or be intercepted by `TransactionalInterceptor`.

---

## [0.1.0]

### Added

* Initial public release of `pico-sqlalchemy`.
* **Async-Native Core:** Built entirely on SQLAlchemy's async ORM (`AsyncSession`, `create_async_engine`).
* **`@transactional`** decorator providing Spring-style, async-native transactional method boundaries with propagation modes:
  `REQUIRED`, `REQUIRES_NEW`, `SUPPORTS`, `MANDATORY`, `NOT_SUPPORTED`, and `NEVER`.
* **`SessionManager`** singleton responsible for:
  * creating the SQLAlchemy `AsyncEngine`
  * managing `AsyncSession` instances
  * implementing async transaction semantics
  * `await commit()` / `await rollback()` behavior
* **`get_session()`** helper for retrieving the currently active `AsyncSession` inside transactional methods.
* **`TransactionalInterceptor`** implementing AOP-based async transaction handling for methods decorated with `@transactional`.
* **`DatabaseSettings`** dataclass for type-safe, IOC-managed configuration of SQLAlchemy (URL, pool options, echo).
* **`DatabaseConfigurer`** protocol for extensible, ordered database initialization hooks (e.g., migrations, DDL, seeding).
* **`SqlAlchemyFactory`** to register and wire the `SessionManager` and configuration into the IoC container.
* **`AppBase`**, `Mapped`, and `mapped_column` declarative base components registered for SQLAlchemy models.
* Async-native in-memory SQLite support (`aiosqlite`) out of the box (useful for testing).
* Test suite validating async `SessionManager` commit/rollback behavior and transactional propagation.
