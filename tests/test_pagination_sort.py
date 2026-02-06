import pytest
import pytest_asyncio
import asyncio
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from pico_ioc import init, configuration, DictSource, component
from pico_sqlalchemy import (
    AppBase,
    SessionManager,
    repository,
    query,
    DatabaseConfigurer,
    PageRequest,
    Page,
)
from pico_sqlalchemy.paging import Sort


class SortUser(AppBase):
    __tablename__ = "sort_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(Integer)


@repository(entity=SortUser)
class SortUserRepository:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @query(expr="1=1", paged=True)
    async def find_all(self, page: PageRequest):
        pass


@component
class SetupDB(DatabaseConfigurer):
    def __init__(self, base: AppBase):
        self.base = base

    def configure(self, engine):
        async def run():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)
        asyncio.run(run())


@pytest.fixture
def container(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/sort_test.db"
    cfg = configuration(DictSource({"database": {"url": db_url}}))
    return init(
        modules=["pico_sqlalchemy", __name__],
        config=cfg
    )


@pytest_asyncio.fixture
async def repo(container):
    repo = await container.aget(SortUserRepository)
    sm = await container.aget(SessionManager)
    async with sm.transaction() as session:
        session.add_all([
            SortUser(name="Charlie", age=30),
            SortUser(name="Alice", age=25),
            SortUser(name="Bob", age=40)
        ])
    return repo


@pytest.mark.asyncio
async def test_sort_asc(repo):
    req = PageRequest(page=0, size=10, sorts=[Sort(field="name", direction="ASC")])
    page = await repo.find_all(req)
    
    assert len(page.content) == 3
    names = [u.name for u in page.content]
    assert names == ["Alice", "Bob", "Charlie"]


@pytest.mark.asyncio
async def test_sort_desc(repo):
    req = PageRequest(page=0, size=10, sorts=[Sort(field="age", direction="DESC")])
    page = await repo.find_all(req)
    
    ages = [u.age for u in page.content]
    assert ages == [40, 30, 25]


@pytest.mark.asyncio
async def test_sort_multiple(repo):
    sm = repo.manager
    async with sm.transaction() as session:
        session.add(SortUser(name="Alice", age=20))

    req = PageRequest(
        page=0, 
        size=10, 
        sorts=[
            Sort(field="name", direction="ASC"),
            Sort(field="age", direction="DESC")
        ]
    )
    page = await repo.find_all(req)
    
    assert len(page.content) == 4
    users = [(u.name, u.age) for u in page.content]
    
    assert users[0] == ("Alice", 25)
    assert users[1] == ("Alice", 20)
    assert users[2] == ("Bob", 40)
    assert users[3] == ("Charlie", 30)


@pytest.mark.asyncio
async def test_security_invalid_column_raises_error(repo):
    req = PageRequest(page=0, size=10, sorts=[Sort(field="hacked_column", direction="ASC")])

    with pytest.raises(ValueError, match="Invalid sort field"):
        await repo.find_all(req)


class TestPageRequest:

    def test_offset_first_page(self):
        req = PageRequest(page=0, size=10)
        assert req.offset == 0

    def test_offset_second_page(self):
        req = PageRequest(page=1, size=10)
        assert req.offset == 10

    def test_offset_large_page(self):
        req = PageRequest(page=5, size=20)
        assert req.offset == 100

    def test_default_sorts_empty(self):
        req = PageRequest(page=0, size=10)
        assert req.sorts == []


class TestPage:

    def test_total_pages_exact_division(self):
        page = Page(content=[], total_elements=30, page=0, size=10)
        assert page.total_pages == 3

    def test_total_pages_with_remainder(self):
        page = Page(content=[], total_elements=31, page=0, size=10)
        assert page.total_pages == 4

    def test_total_pages_single_page(self):
        page = Page(content=[], total_elements=5, page=0, size=10)
        assert page.total_pages == 1

    def test_total_pages_zero_elements(self):
        page = Page(content=[], total_elements=0, page=0, size=10)
        assert page.total_pages == 0

    def test_total_pages_zero_size(self):
        page = Page(content=[], total_elements=10, page=0, size=0)
        assert page.total_pages == 0

    def test_is_first_true(self):
        page = Page(content=[], total_elements=30, page=0, size=10)
        assert page.is_first is True

    def test_is_first_false(self):
        page = Page(content=[], total_elements=30, page=1, size=10)
        assert page.is_first is False

    def test_is_last_true(self):
        page = Page(content=[], total_elements=30, page=2, size=10)
        assert page.is_last is True

    def test_is_last_false(self):
        page = Page(content=[], total_elements=30, page=0, size=10)
        assert page.is_last is False

    def test_is_last_single_page(self):
        page = Page(content=[], total_elements=5, page=0, size=10)
        assert page.is_last is True


class TestSort:

    def test_valid_asc(self):
        s = Sort(field="name", direction="ASC")
        assert s.direction == "ASC"

    def test_valid_desc(self):
        s = Sort(field="name", direction="DESC")
        assert s.direction == "DESC"

    def test_default_direction(self):
        s = Sort(field="name")
        assert s.direction == "ASC"

    def test_invalid_direction_raises(self):
        with pytest.raises(ValueError, match="Invalid sort direction"):
            Sort(field="name", direction="INVALID")

    def test_sort_exported_from_package(self):
        from pico_sqlalchemy import Sort as ExportedSort
        assert ExportedSort is Sort