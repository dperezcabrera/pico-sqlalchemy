import asyncio

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncEngine

from pico_sqlalchemy import SessionManager, TransactionalInterceptor, transactional


class Base(DeclarativeBase):
    pass


class InterceptorUser(Base):
    __tablename__ = "interceptor_users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


def _new_manager() -> SessionManager:
    manager = SessionManager(url="sqlite+aiosqlite:///:memory:", echo=False)

    async def create_tables(engine: AsyncEngine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables(manager.engine))
    return manager


def test_interceptor_without_transactional_metadata_non_awaitable_result():
    manager = _new_manager()
    interceptor = TransactionalInterceptor(manager)

    class Dummy:
        def method(self):
            return "ok"

    ctx = type("Ctx", (), {"cls": Dummy, "name": "method"})()

    def call_next(c):
        assert c is ctx
        return "plain-result"

    async def runner():
        result = await interceptor.invoke(ctx, call_next)
        assert result == "plain-result"

    asyncio.run(runner())


def test_interceptor_with_transactional_metadata_and_awaitable_result():
    manager = _new_manager()
    interceptor = TransactionalInterceptor(manager)

    class Dummy:
        @transactional(propagation="REQUIRES_NEW", read_only=False)
        def method(self):
            return "unused"

    ctx = type("Ctx", (), {"cls": Dummy, "name": "method"})()

    async def call_next(c):
        assert c is ctx
        return "awaited-result"

    async def runner():
        result = await interceptor.invoke(ctx, call_next)
        assert result == "awaited-result"

    asyncio.run(runner())


def test_interceptor_transaction_block_allows_db_work():
    manager = _new_manager()
    interceptor = TransactionalInterceptor(manager)

    class Dummy:
        @transactional(propagation="REQUIRED")
        def create_user(self, name: str):
            return name

    ctx = type("Ctx", (), {"cls": Dummy, "name": "create_user"})()

    async def call_next(c):
        session = manager.get_current_session()
        assert session is not None
        user = InterceptorUser(name="bob")
        session.add(user)
        return "done"

    async def runner():
        result = await interceptor.invoke(ctx, call_next)
        assert result == "done"

        async def check_user():
            async with manager.transaction(read_only=True) as session:
                stmt = select(InterceptorUser)
                result = await session.scalars(stmt)
                users = list(result.all())
                names = [u.name for u in users]
                assert "bob" in names

        await check_user()

    from sqlalchemy import select
    import asyncio # Re-import asyncio just in case, though it's at the top.
    
    asyncio.run(runner())
