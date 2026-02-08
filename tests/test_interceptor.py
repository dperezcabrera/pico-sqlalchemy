import asyncio

from sqlalchemy import Column, Integer, String, select

from conftest import Base, new_session_manager
from pico_sqlalchemy import SessionManager, TransactionalInterceptor, transactional


class InterceptorUser(Base):
    __tablename__ = "interceptor_users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


def test_interceptor_without_transactional_metadata_non_awaitable_result():
    manager = new_session_manager(Base)
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
    manager = new_session_manager(Base)
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
    manager = new_session_manager(Base)
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

    asyncio.run(runner())


def test_transactional_without_parentheses():
    """@transactional without parens uses REQUIRED defaults."""
    manager = new_session_manager(Base)
    interceptor = TransactionalInterceptor(manager)

    class Dummy:
        @transactional
        def method(self):
            return "unused"

    meta = getattr(Dummy.method, "_pico_sqlalchemy_transactional_meta", None)
    assert meta is not None
    assert meta["propagation"] == "REQUIRED"
    assert meta["read_only"] is False

    ctx = type("Ctx", (), {"cls": Dummy, "name": "method"})()

    async def call_next(c):
        assert manager.get_current_session() is not None
        return "bare-result"

    async def runner():
        result = await interceptor.invoke(ctx, call_next)
        assert result == "bare-result"

    asyncio.run(runner())
