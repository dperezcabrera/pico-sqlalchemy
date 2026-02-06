# Claude Code Skills

Pico-SQLAlchemy includes pre-designed skills for [Claude Code](https://claude.ai/claude-code) that enable AI-assisted development following pico-framework patterns and best practices.

## Available Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **Pico SQLAlchemy Repository** | `/pico-sqlalchemy` | Creates repositories integrated with pico-ioc |
| **Pico Test Generator** | `/pico-tests` | Generates tests for pico-framework components |

---

## Pico SQLAlchemy Repository

Creates SQLAlchemy models, repositories, and services with full DI integration.

### Model

```python
from sqlalchemy.orm import Mapped, mapped_column
from pico_sqlalchemy import AppBase

class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
```

### Repository

```python
from pico_sqlalchemy import repository, query, get_session, SessionManager

@repository(entity=User)
class UserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    async def save(self, user: User) -> User:
        session = get_session(self.manager)
        session.add(user)
        return user

    @query(expr="name = :name", unique=True)
    async def find_by_name(self, name: str) -> User | None:
        ...
```

### Service

```python
from pico_ioc import component
from pico_sqlalchemy import transactional

@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional
    async def create(self, name: str) -> User:
        existing = await self.repo.find_by_name(name)
        if existing:
            raise ValueError("User exists")
        return await self.repo.save(User(name=name))
```

---

## Pico Test Generator

Generates tests for any pico-framework component.

### Testing Repositories

```python
import pytest
from pico_ioc import init, configuration, DictSource

@pytest.mark.asyncio
async def test_service():
    config = configuration(DictSource({
        "database": {"url": "sqlite+aiosqlite:///:memory:"}
    }))
    container = init(modules=["pico_sqlalchemy", "__main__"], config=config)
    service = await container.aget(UserService)
    user = await service.create("test")
    assert user.id is not None
```

---

## Installation

```bash
# Project-level (recommended)
mkdir -p .claude/skills/pico-sqlalchemy
# Copy the skill YAML+Markdown to .claude/skills/pico-sqlalchemy/SKILL.md

mkdir -p .claude/skills/pico-tests
# Copy the skill YAML+Markdown to .claude/skills/pico-tests/SKILL.md

# Or user-level (available in all projects)
mkdir -p ~/.claude/skills/pico-sqlalchemy
mkdir -p ~/.claude/skills/pico-tests
```

## Usage

```bash
# Invoke directly in Claude Code
/pico-sqlalchemy User
/pico-tests UserRepository
```

See the full skill templates in the [pico-framework skill catalog](https://github.com/dperezcabrera/pico-sqlalchemy).
