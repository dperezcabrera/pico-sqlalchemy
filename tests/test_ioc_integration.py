import os
import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session

from pico_ioc import init, configuration, DictSource, component

from pico_sqlalchemy import (
    AppBase,
    SessionManager,
    transactional,
    repository,
    get_session,
    DatabaseConfigurer,
)


class User(AppBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=False)


@component
class TableCreationConfigurer(DatabaseConfigurer):
    priority = 10

    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        self.base.metadata.create_all(engine)


@repository
class UserRepository:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def find_all(self) -> list[User]:
        session = get_session(self.session_manager)
        return session.query(User).order_by(User.username).all()

    def save(self, user: User) -> User:
        session = get_session(self.session_manager)
        session.add(user)
        return user


@component
class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional(propagation="REQUIRED")
    def create_user(self, username: str, email: str) -> User:
        user = self.repo.save(User(username=username, email=email))
        session = get_session(self.repo.session_manager)
        session.flush()
        session.refresh(user)
        return user

    @transactional(propagation="REQUIRED")
    def create_two_and_fail(self):
        self.repo.save(User(username="good", email="good@example.com"))
        self.repo.save(User(username="bad", email="bad@example.com"))
        raise RuntimeError("boom")


@component
class NestedService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @transactional(propagation="REQUIRES_NEW")
    def save_new(self, user: User) -> User:
        user = self.repo.save(user)
        session = get_session(self.repo.session_manager)
        session.flush()
        session.refresh(user)
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

    def outer(self):
        with self.session_manager.transaction(propagation="REQUIRED"):
            self.repo.save(User(username="outer", email="o@x.com"))
            self.nested.save_new(User(username="inner", email="i@x.com"))
            raise RuntimeError("boom")


@pytest.fixture(scope="session")
def container():
    db_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")
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


def test_repository_commit(user_service: UserService, session_manager: SessionManager):
    created = user_service.create_user("alice", "alice@example.com")
    assert created.id is not None

    with session_manager.transaction(read_only=True) as session:
        assert isinstance(session, Session)
        users = session.query(User).order_by(User.username).all()
        usernames = [u.username for u in users]
        assert usernames == ["alice"]


def test_repository_rollback(
    user_service: UserService, session_manager: SessionManager
):
    try:
        user_service.create_two_and_fail()
    except RuntimeError:
        pass

    with session_manager.transaction(read_only=True) as session:
        users = session.query(User).order_by(User.username).all()
        usernames = [u.username for u in users]
        assert "good" not in usernames
        assert "bad" not in usernames
        assert "alice" in usernames


def test_requires_new(outer_service, session_manager):
    try:
        outer_service.outer()
    except RuntimeError:
        pass

    with session_manager.transaction(read_only=True) as session:
        users = session.query(User).order_by(User.username).all()
        usernames = [u.username for u in users]
        assert "inner" in usernames
        assert "outer" not in usernames
