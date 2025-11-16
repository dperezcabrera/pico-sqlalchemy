# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.html).

---

## [0.1.0] — 2025-11-15

### Added

* Initial public release of `pico-sqlalchemy`.
* **`@transactional`** decorator providing Spring-style transactional method boundaries with propagation modes:
  `REQUIRED`, `REQUIRES_NEW`, `SUPPORTS`, `MANDATORY`, `NOT_SUPPORTED`, and `NEVER`.
* **`SessionManager`** singleton responsible for:

  * creating the SQLAlchemy engine
  * managing sessions
  * implementing transaction semantics
  * commit/rollback behavior
* **`get_session()`** helper for retrieving the currently active SQLAlchemy session inside transactional methods.
* **`TransactionalInterceptor`** implementing AOP-based transaction handling for methods decorated with `@transactional`.
* **`DatabaseSettings`** dataclass for type-safe, IOC-managed configuration of SQLAlchemy (URL, pool options, echo).
* **`DatabaseConfigurer`** protocol for extensible, ordered database initialization hooks (e.g., migrations, DDL, seeding).
* **`SqlAlchemyFactory`** to register and wire the `SessionManager` and configuration into the IoC container.
* **`AppBase`** declarative base class registered as a singleton for SQLAlchemy models.
* In-memory SQLite support out of the box (useful for testing).
* Basic test suite validating `SessionManager` commit/rollback behavior.

