import pytest
import asyncio
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from pico_sqlalchemy import SessionManager


class Base(DeclarativeBase):
    pass


class TxUser(Base):
    __tablename__ = "tx_users_propagation"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)


@pytest.fixture
def manager():
    m = SessionManager(url="sqlite+aiosqlite:///:memory:", echo=False)

    async def create_tables(engine: AsyncEngine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_tables(m.engine))
    return m


async def _count_users(manager: SessionManager) -> int:
    async with manager.transaction(read_only=True) as session:
        assert isinstance(session, AsyncSession)
        stmt = select(TxUser)
        result = await session.scalars(stmt)
        return len(result.all())


@pytest.mark.asyncio
async def test_propagation_mandatory_requires_active(manager: SessionManager):
    with pytest.raises(RuntimeError):
        async with manager.transaction(propagation="MANDATORY"):
            pass


@pytest.mark.asyncio
async def test_propagation_mandatory_joins_active(manager: SessionManager):
    async with manager.transaction() as outer:
        async with manager.transaction(propagation="MANDATORY") as inner:
            assert inner is outer
            session = manager.get_current_session()
            assert session is outer


@pytest.mark.asyncio
async def test_propagation_never_without_active(manager: SessionManager):
    async with manager.transaction(propagation="NEVER") as session:
        assert isinstance(session, AsyncSession)
        assert manager.get_current_session() is None


@pytest.mark.asyncio
async def test_propagation_never_with_active_fails(manager: SessionManager):
    async with manager.transaction() as outer:
        assert manager.get_current_session() is outer
        with pytest.raises(RuntimeError):
            async with manager.transaction(propagation="NEVER"):
                pass


@pytest.mark.asyncio
async def test_propagation_not_supported_with_active(manager: SessionManager):
    async with manager.transaction() as outer:
        assert manager.get_current_session() is outer
        async with manager.transaction(propagation="NOT_SUPPORTED") as inner:
            assert isinstance(inner, AsyncSession)
            assert manager.get_current_session() is None
        assert manager.get_current_session() is outer


@pytest.mark.asyncio
async def test_propagation_not_supported_without_active(manager: SessionManager):
    async with manager.transaction(propagation="NOT_SUPPORTED") as session:
        assert isinstance(session, AsyncSession)
        assert manager.get_current_session() is None


@pytest.mark.asyncio
async def test_propagation_supports_with_active(manager: SessionManager):
    async with manager.transaction() as outer:
        async with manager.transaction(propagation="SUPPORTS") as inner:
            assert inner is outer
            assert manager.get_current_session() is outer


@pytest.mark.asyncio
async def test_propagation_supports_without_active(manager: SessionManager):
    async with manager.transaction(propagation="SUPPORTS") as session:
        assert isinstance(session, AsyncSession)
        assert manager.get_current_session() is None


@pytest.mark.asyncio
async def test_propagation_requires_new_with_active(manager: SessionManager):
    async with manager.transaction() as outer:
        assert manager.get_current_session() is outer
        async with manager.transaction(propagation="REQUIRES_NEW") as inner:
            assert isinstance(inner, AsyncSession)
            assert inner is not outer
            assert manager.get_current_session() is inner
        assert manager.get_current_session() is outer


@pytest.mark.asyncio
async def test_propagation_requires_new_without_active(manager: SessionManager):
    async with manager.transaction(propagation="REQUIRES_NEW") as session:
        assert isinstance(session, AsyncSession)
        assert manager.get_current_session() is session
    assert manager.get_current_session() is None


@pytest.mark.asyncio
async def test_isolation_level_branch(manager: SessionManager):
    async with manager.transaction(isolation_level="SERIALIZABLE") as session:
        assert isinstance(session, AsyncSession)
        assert manager.get_current_session() is session


@pytest.mark.asyncio
async def test_rollback_for_default_rolls_back(manager: SessionManager):
    async with manager.transaction() as session:
        user = TxUser(username="rollback_default")
        session.add(user)
    assert await _count_users(manager) == 1
    try:
        async with manager.transaction() as session:
            user = TxUser(username="should_be_rolled_back")
            session.add(user)
            raise ValueError("boom")
    except ValueError:
        pass
    
    async with manager.transaction(read_only=True) as session:
        stmt = select(TxUser).order_by(TxUser.username)
        users = list((await session.scalars(stmt)).all())
        usernames = [u.username for u in users]
        assert "rollback_default" in usernames
        assert "should_be_rolled_back" not in usernames


@pytest.mark.asyncio
async def test_no_rollback_for_skips_rollback_branch(manager: SessionManager):
    initial_count = await _count_users(manager)
    try:
        async with manager.transaction(rollback_for=(Exception,), no_rollback_for=(ValueError,)) as session:
            user = TxUser(username="no_rollback_branch")
            session.add(user)
            raise ValueError("do_not_rollback")
    except ValueError:
        pass
    assert await _count_users(manager) == initial_count


@pytest.mark.asyncio
async def test_unknown_propagation_raises_value_error(manager: SessionManager):
    with pytest.raises(ValueError):
        async with manager.transaction(propagation="UNKNOWN"):
            pass
