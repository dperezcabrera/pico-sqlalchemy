import os
import pytest
import pytest_asyncio
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from pico_ioc import init, configuration, DictSource, component

from pico_sqlalchemy import (
    AppBase,
    Mapped,
    mapped_column,
    SessionManager,
    transactional,
    repository,
    get_session,
    DatabaseConfigurer,
)


class User(AppBase):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)


@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10

    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        async def setup(engine):
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)

        import asyncio

        asyncio.run(setup(engine))


@repository
class UserRepository:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def find_all(self) -> list[User]:
        session = get_session(self.session_manager)
        stmt = select(User).order_by(User.username)
        result = await session.scalars(stmt)
        return list(result.all())

    async def save(self, user: User) -> User:
        session = get_session(self.session_manager)
        session.add(user)
        return user


@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional(propagation="REQUIRED")
    async def create_user(self, username: str, email: str) -> User:
        user = await self.repo.save(User(username=username, email=email))
        session = get_session(self.repo.session_manager)
        await session.flush()
        await session.refresh(user)
        return user

    @transactional(propagation="REQUIRED")
    async def create_two_and_fail(self):
        await self.repo.save(User(username="good", email="good@example.com"))
        await self.repo.save(User(username="bad", email="bad@example.com"))
        raise RuntimeError("boom")


@component
class NestedService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional(propagation="REQUIRES_NEW")
    async def save_new(self, user: User) -> User:
        user = await self.repo.save(user)
        session = get_session(self.repo.session_manager)
        await session.flush()
        await session.refresh(user)
        return user


@component
class OuterService:
    def __init__(
        self,
        repo: UserRepository,
        nested: NestedService,
        session_manager: SessionManager,
    ):
        self.repo = repo
        self.nested = nested
        self.session_manager = session_manager

    async def outer(self):
        async with self.session_manager.transaction(propagation="REQUIRED"):
            await self.repo.save(User(username="outer", email="o@x.com"))
            await self.nested.save_new(User(username="inner", email="i@x.com"))
            raise RuntimeError("boom")


@pytest.fixture(scope="session")
def container():
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    cfg = configuration(
        DictSource(
            {
                "database": {
                    "url": db_url,
                    "echo": False,
                }
            }
        )
    )

    c = init(
        modules=[
            "pico_sqlalchemy",
            __name__,
        ],
        config=cfg,
    )

    try:
        yield c
    finally:
        c.cleanup_all()


@pytest.fixture
def user_service(container):
    return container.get(UserService)


@pytest.fixture
def nested_service(container):
    return container.get(NestedService)


@pytest.fixture
def outer_service(container):
    return container.get(OuterService)


@pytest.fixture
def session_manager(container):
    return container.get(SessionManager)


@pytest.mark.asyncio
async def test_repository_commit(
    user_service: UserService, session_manager: SessionManager
):
    created = await user_service.create_user("alice", "alice@example.com")
    assert created.id is not None

    async with session_manager.transaction(read_only=True) as session:
        assert isinstance(session, AsyncSession)
        stmt = select(User).order_by(User.username)
        users = list((await session.scalars(stmt)).all())
        usernames = [u.username for u in users]
        assert usernames == ["alice"]


@pytest.mark.asyncio
async def test_repository_rollback(
    user_service: UserService, session_manager: SessionManager
):
    try:
        await user_service.create_two_and_fail()
    except RuntimeError:
        pass

    async with session_manager.transaction(read_only=True) as session:
        stmt = select(User).order_by(User.username)
        users = list((await session.scalars(stmt)).all())
        usernames = [u.username for u in users]
        assert "good" not in usernames
        assert "bad" not in usernames
        assert "alice" in usernames


@pytest.mark.asyncio
async def test_requires_new(outer_service, session_manager):
    try:
        await outer_service.outer()
    except RuntimeError:
        pass

    async with session_manager.transaction(read_only=True) as session:
        stmt = select(User).order_by(User.username)
        users = list((await session.scalars(stmt)).all())
        usernames = [u.username for u in users]
        assert "inner" in usernames
        assert "outer" not in usernames
