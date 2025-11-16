# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.html).

---

## [Unreleased]

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
