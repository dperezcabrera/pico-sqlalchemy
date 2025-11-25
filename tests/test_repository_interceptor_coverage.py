import pytest
import pytest_asyncio
import asyncio
from typing import Any
from unittest.mock import MagicMock
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from pico_ioc import init, configuration, DictSource, MethodCtx, component
from pico_sqlalchemy import (
    AppBase,
    SessionManager,
    repository,
    query,
    DatabaseConfigurer,
    PageRequest,
    Page,
    RepositoryQueryInterceptor,
)
from pico_sqlalchemy.decorators import QUERY_META


class CovUser(AppBase):
    __tablename__ = "cov_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


@repository
class RepoNoEntity:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @query(expr="name = :name")
    async def find_fail(self, name: str):
        pass


@repository(entity=CovUser)
class RepoWithEntity:
    def __init__(self, manager: SessionManager):
        self.manager = manager

    @query(sql="SELECT * FROM cov_users ORDER BY id", paged=True)
    async def find_sql_paged(self, page: Any):
        pass

    @query(sql="SELECT * FROM cov_users ORDER BY id")
    async def find_sql_list(self):
        pass

    @query(expr="name = :name", paged=True)
    async def find_expr_paged(self, page: Any):
        pass

    @query(expr="name = :name", unique=True)
    async def find_expr_unique(self, name: str):
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
    db_url = f"sqlite+aiosqlite:///{tmp_path}/coverage.db"
    cfg = configuration(DictSource({"database": {"url": db_url}}))
    
    return init(
        modules=["pico_sqlalchemy", __name__],
        config=cfg
    )


@pytest_asyncio.fixture
async def repo_entity(container):
    repo = await container.aget(RepoWithEntity)
    sm = await container.aget(SessionManager)
    async with sm.transaction() as session:
        session.add_all([
            CovUser(name="A"),
            CovUser(name="B"),
            CovUser(name="C")
        ])
    return repo


@pytest.mark.asyncio
async def test_meta_is_none_pass_through(container):
    sm = await container.aget(SessionManager)
    interceptor = RepositoryQueryInterceptor(sm)

    class Dummy:
        async def method(self):
            return "original_result"
    
    ctx = MagicMock(spec=MethodCtx)
    ctx.cls = Dummy
    ctx.name = "method"
    ctx.args = ()
    ctx.kwargs = {}
    
    async def call_next(c):
        return await c.cls().method()

    result = await interceptor.invoke(ctx, call_next)
    assert result == "original_result"


@pytest.mark.asyncio
async def test_unsupported_query_mode(container):
    sm = await container.aget(SessionManager)
    interceptor = RepositoryQueryInterceptor(sm)
    
    async def dummy_func(self): pass
    setattr(dummy_func, QUERY_META, {"mode": "invalid_mode"})
    
    ctx = MagicMock(spec=MethodCtx)
    ctx.cls = type("C", (), {})
    ctx.name = "dummy_func"
    ctx.args = ()
    ctx.kwargs = {}
    
    setattr(ctx.cls, "dummy_func", dummy_func)
    
    async def call_next(c): pass

    with pytest.raises(RuntimeError, match="Unsupported query mode"):
        async with sm.transaction():
            await interceptor.invoke(ctx, call_next)


@pytest.mark.asyncio
async def test_expr_requires_entity(container):
    repo = await container.aget(RepoNoEntity)
    
    with pytest.raises(RuntimeError, match="requires @repository\(entity=...\)"):
        await repo.find_fail("test")


@pytest.mark.asyncio
async def test_paged_sql_type_error(repo_entity):
    with pytest.raises(TypeError, match="requires a 'page: PageRequest' parameter"):
        await repo_entity.find_sql_paged(page=1)


@pytest.mark.asyncio
async def test_paged_sql_success(repo_entity):
    req = PageRequest(page=0, size=2)
    result = await repo_entity.find_sql_paged(page=req)
    
    assert isinstance(result, Page)
    assert result.total_elements == 3
    assert result.size == 2
    assert result.page == 0
    assert len(result.content) == 2
    assert result.content[0].name == "A"
    assert result.content[1].name == "B"


@pytest.mark.asyncio
async def test_sql_list_return(repo_entity):
    result = await repo_entity.find_sql_list()
    assert isinstance(result, list)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_paged_expr_type_error(repo_entity):
    with pytest.raises(TypeError, match="requires a 'page: PageRequest' parameter"):
        await repo_entity.find_expr_paged(page="invalid")


@pytest.mark.asyncio
async def test_expr_unique_return(repo_entity):
    res1 = await repo_entity.find_expr_unique(name="B")
    assert res1 is not None
    assert res1.name == "B"

    res2 = await repo_entity.find_expr_unique(name="Z")
    assert res2 is None