import pytest
import pytest_asyncio
from pico_ioc import DictSource, component, configuration, init
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from conftest import SetupDBBase
from pico_sqlalchemy import (
    AppBase,
    Page,
    PageRequest,
    SessionManager,
    get_session,
    query,
    repository,
    transactional,
)


class User(AppBase):
    __tablename__ = "repo_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)


@component
class SetupDB(SetupDBBase):
    pass


@repository(entity=User)
class UserRepository:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    @query(expr="username = :username", unique=True)
    async def find_by_username(self, username: str):
        raise AssertionError("Body should not be executed")

    @query.sql(
        "SELECT * FROM repo_users WHERE email = :email",
        unique=True,
    )
    async def find_by_email(self, email: str):
        raise AssertionError("Body should not be executed")

    @query(expr="1 = 1", paged=True)
    async def find_all_paged(self, page: PageRequest):
        raise AssertionError("Body should not be executed")

    @transactional()
    async def create(self, username: str, email: str) -> User:
        session = get_session(self.session_manager)
        user = User(username=username, email=email)
        session.add(user)
        return user


@pytest.fixture
def container(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test_repo_query.db"
    src = DictSource({"database": {"url": db_url, "echo": False}})
    return init(modules=["pico_sqlalchemy", __name__], config=configuration(src))


@pytest_asyncio.fixture
async def session_manager(container) -> SessionManager:
    return container.get(SessionManager)


@pytest_asyncio.fixture
async def repo(container) -> UserRepository:
    return container.get(UserRepository)


@pytest.mark.asyncio
async def test_query_expr_unique(repo: UserRepository, session_manager: SessionManager):
    async with session_manager.transaction() as session:
        u1 = User(username="alice", email="alice@example.com")
        u2 = User(username="bob", email="bob@example.com")
        session.add_all([u1, u2])
    row = await repo.find_by_username("alice")
    assert row is not None
    assert row["username"] == "alice"
    assert row["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_query_sql_unique(repo: UserRepository, session_manager: SessionManager):
    async with session_manager.transaction() as session:
        u = User(username="carol", email="carol@example.com")
        session.add(u)
    row = await repo.find_by_email("carol@example.com")
    assert row is not None
    assert row["email"] == "carol@example.com"


@pytest.mark.asyncio
async def test_query_paged(repo: UserRepository, session_manager: SessionManager):
    async with session_manager.transaction() as session:
        for i in range(10):
            u = User(username=f"user{i}", email=f"user{i}@example.com")
            session.add(u)
    page_request = PageRequest(page=1, size=3)
    page = await repo.find_all_paged(page_request)
    assert isinstance(page, Page)
    assert page.page == 1
    assert page.size == 3
    assert page.total_elements == 10
    assert len(page.content) == 3
