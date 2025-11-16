# 📦 pico-sqlalchemy

[![PyPI](https://img.shields.io/pypi/v/pico-sqlalchemy.svg)](https://pypi.org/project/pico-sqlalchemy/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/dperezcabrera/pico-sqlalchemy)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
![CI (tox matrix)](https://github.com/dperezcabrera/pico-ioc/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy/branch/main/graph/badge.svg)](https://codecov.io/gh/dperezcabrera/pico-sqlalchemy)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=dperezcabrera_pico-sqlalchemy\&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=dperezcabrera_pico-sqlalchemy)

# Pico-SQLAlchemy

**Pico-SQLAlchemy** integrates **[Pico-IoC](https://github.com/dperezcabrera/pico-ioc)** with **SQLAlchemy**, providing real inversion of control for your persistence layer, with declarative repositories, transactional boundaries, and clean architectural isolation.

It brings constructor-based dependency injection, transparent transaction management, and a repository pattern inspired by the elegance of Spring Data — but using pure Python, Pico-IoC, and SQLAlchemy’s ORM.

> 🐍 Requires Python 3.10+
> 🧩 Works with SQLAlchemy ORM
> 🔄 Automatic transaction management
> 🧪 Fully testable without a running DB
> 🧵 Supports synchronous and asynchronous workflows (async ORM planned)

With Pico-SQLAlchemy you get the expressive power of SQLAlchemy with proper IoC, clean layering, and annotation-driven transactions.

---

## 🎯 Why pico-sqlalchemy

SQLAlchemy is powerful, but most applications end up with raw session handling, manual transaction scopes, or ad-hoc repository patterns.

Pico-SQLAlchemy provides:

* Constructor-injected repositories and services
* Declarative `@transactional` boundaries
* `REQUIRES_NEW`, `READ_ONLY`, `MANDATORY`, and all familiar propagation modes
* `SessionManager` that centralizes engine/session lifecycle
* Clean decoupling from frameworks (FastAPI, Flask, CLI, workers)

| Concern              | SQLAlchemy Default                 | pico-sqlalchemy                  |
| -------------------- | ---------------------------------- | -------------------------------- |
| Managing sessions    | Manual                             | Automatic                        |
| Transactions         | Explicit `commit()` / `rollback()` | Declarative `@transactional`     |
| Repository pattern   | DIY, inconsistent                  | First-class `@repository`        |
| Dependency injection | None                               | IoC-driven constructor injection |
| Testability          | Manual setup                       | Container-managed + overrides    |

---

## 🧱 Core Features

* Repository classes with `@repository`
* Declarative transactions via `@transactional`
* Full propagation semantics (`REQUIRED`, `REQUIRES_NEW`, `MANDATORY`, etc.)
* Automatic session lifecycle
* Centralized engine + session factory via `SessionManager`
* Transaction-aware `get_session()` for repository methods
* Plug-and-play integration with any Pico-IoC app (FastAPI, CLI tools, workers, event handlers)

---

## 📦 Installation

```bash
pip install pico-sqlalchemy
```

Also install:

```bash
pip install pico-ioc sqlalchemy
```

---

## 🚀 Quick Example

### Define your model:

```python
from sqlalchemy import Column, Integer, String
from pico_sqlalchemy import AppBase

class User(AppBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
```

### Define a repository:

```python
from pico_sqlalchemy import repository, transactional, get_session, SessionManager

@repository
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @transactional
    def save(self, user: User):
        session = get_session(self.manager)
        session.add(user)
        session.flush()
        return user

    @transactional(read_only=True)
    def find_all(self):
        session = get_session(self.manager)
        return session.query(User).all()
```

### Define a service:

```python
from pico_ioc import component

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def create(self, name: str):
        return self.repo.save(User(username=name))
```

### Initialize Pico-IoC and run:

```python
from pico_ioc import init, configuration, DictSource

config = configuration(DictSource({
    "database": {
        "url": "sqlite:///demo.db",
        "echo": False
    }
}))

container = init(
    modules=["services", "repositories", "pico_sqlalchemy"],
    config=config,
)

service = container.get(UserService)
service.create("alice")
```

---

## 🔄 Transaction Propagation Modes

Pico-SQLAlchemy supports the core Spring-inspired semantics:

| Mode            | Behavior                            |
| --------------- | ----------------------------------- |
| `REQUIRED`      | Join existing tx or create new      |
| `REQUIRES_NEW`  | Suspend parent and start new tx     |
| `SUPPORTS`      | Join if exists, else run without tx |
| `MANDATORY`     | Requires existing tx                |
| `NOT_SUPPORTED` | Run without tx, suspending parent   |
| `NEVER`         | Fail if a tx exists                 |

Example:

```python
@transactional(propagation="REQUIRES_NEW")
def write_audit(self, entry: AuditEntry):
    ...
```

---

## 🧪 Testing with Pico-IoC

You can override repositories, engines, or services easily:

```python
from pico_ioc import init
from pico_sqlalchemy import SessionManager

class FakeManager(SessionManager):
    def __init__(self):
        super().__init__("sqlite:///:memory:")

container = init(
    modules=["pico_sqlalchemy", "services"],
    overrides={SessionManager: FakeManager()},
)

service = container.get(UserService)
```

Or use pytest fixtures:

```python
@pytest.fixture
def container():
    cfg = configuration(DictSource({"database": {"url": "sqlite:///:memory:"}}))
    c = init(modules=["pico_sqlalchemy", "myapp"], config=cfg)
    yield c
    c.cleanup_all()
```

---

## 🧬 Example: Custom Database Configurer

```python
from pico_sqlalchemy import DatabaseConfigurer, AppBase
from pico_ioc import component

@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10
    def __init__(self, base: AppBase):
        self.base = base
    def configure(self, engine):
        self.base.metadata.create_all(engine)
```

Pico-SQLAlchemy will detect it and call it during initialization.

---

## ⚙️ How It Works

* `SessionManager` is created by Pico-IoC (`SqlAlchemyFactory`)
* A global session context is established via contextvars
* `@transactional` automatically opens/closes transactions
* `@repository` registers a class as a singleton component
* All dependencies (repositories, services, configurers) are resolved by Pico-IoC

No globals. No implicit singletons. No framework coupling.

---

## 💡 Architecture Overview

```
             ┌─────────────────────────────┐
             │         Your App            │
             └──────────────┬──────────────┘
                            │
                   Constructor Injection
                            │
             ┌──────────────▼───────────────┐
             │         Pico-IoC             │
             └──────────────┬───────────────┘
                            │
                   SessionManager / Factory
                            │
             ┌──────────────▼───────────────┐
             │         pico-sqlalchemy      │
             │ Transactional Decorators     │
             │ Repository Metadata          │
             └──────────────┬───────────────┘
                            │
                         SQLAlchemy
```

---

## 📝 License

MIT

