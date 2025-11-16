import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from pico_sqlalchemy import SessionManager


class Base(DeclarativeBase):
    pass


class TxUser(Base):
    __tablename__ = "tx_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


@pytest.mark.asyncio
async def test_commit_and_rollback():
    manager = SessionManager(url="sqlite+aiosqlite:///:memory:", echo=False)
    
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with manager.transaction() as session:
        assert isinstance(session, AsyncSession)
        user = TxUser(username="alice")
        session.add(user)

    async with manager.transaction(read_only=True) as session:
        users = list((await session.scalars(select(TxUser))).all())
        assert len(users) == 1
        assert users[0].username == "alice"

    try:
        async with manager.transaction() as session:
            user = TxUser(username="bob")
            session.add(user)
            raise ValueError("boom")
    except ValueError:
        pass

    async with manager.transaction(read_only=True) as session:
        stmt = select(TxUser).order_by(TxUser.username)
        users = list((await session.scalars(stmt)).all())
        usernames = [u.username for u in users]
        assert usernames == ["alice"]
