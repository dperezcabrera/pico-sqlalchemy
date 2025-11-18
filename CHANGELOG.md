# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.html).

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
