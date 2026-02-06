# Pico-SQLAlchemy

Seamless integration between Pico-IoC and SQLAlchemy with async support, transaction management, and repository pattern.

## Features

- **Async Support**: Full async/await support with SQLAlchemy 2.0
- **Transaction Management**: Declarative transactions with propagation control
- **Repository Pattern**: Clean data access layer with query decorators
- **Pico-IoC Integration**: Automatic dependency injection and component scanning
- **Pagination**: Built-in support for paginated queries

## Quick Start

```python
from pico_ioc import init, configuration, DictSource, component
from pico_sqlalchemy import repository, query, transactional, SessionManager, get_session

# Define a repository
@repository(entity=User)
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @query(expr="id = :user_id", unique=True)
    async def find_by_id(self, user_id: int): ...

    @query(expr="email = :email", unique=True)
    async def find_by_email(self, email: str): ...

    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user

# Use transactional in services
@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional
    async def create_user(self, name: str, email: str) -> User:
        return await self.repo.save(User(username=name, email=email))

# Bootstrap
config = configuration(DictSource({
    "database": {"url": "sqlite+aiosqlite:///:memory:"}
}))
container = init(modules=["pico_sqlalchemy", "__main__"], config=config)
```

## Installation

```bash
pip install pico-sqlalchemy
```

You will also need an async database driver:

```bash
pip install aiosqlite   # SQLite
pip install asyncpg     # PostgreSQL
```

## Requirements

- Python 3.11+
- SQLAlchemy 2.0+
- pico-ioc >= 2.2.0

## Documentation

- [Getting Started](quickstart.md) - Installation and basic usage
- [Overview](overview.md) - Core concepts and features
- [Architecture](architecture.md) - Design and implementation details

### Reference

- [Configuration](reference/configuration.md) - Configuration options
- [Declarative Base](reference/declarative-base.md) - Entity definitions
- [Repositories](reference/repository.md) - Repository pattern usage
- [Transactions](reference/transactions.md) - Transaction management

### Development

- [Project Tooling](development/project-tooling.md) - Development setup

## License

MIT License - see LICENSE file for details.
