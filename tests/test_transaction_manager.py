from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session, DeclarativeBase
from pico_sqlalchemy import SessionManager


class Base(DeclarativeBase):
    pass


class TxUser(Base):
    __tablename__ = "tx_users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)


def test_commit_and_rollback():
    manager = SessionManager(url="sqlite:///:memory:", echo=False)
    Base.metadata.create_all(manager.engine)

    with manager.transaction() as session:
        assert isinstance(session, Session)
        user = TxUser(username="alice")
        session.add(user)

    with manager.transaction(read_only=True) as session:
        users = session.query(TxUser).all()
        assert len(users) == 1
        assert users[0].username == "alice"

    try:
        with manager.transaction() as session:
            user = TxUser(username="bob")
            session.add(user)
            raise ValueError("boom")
    except ValueError:
        pass

    with manager.transaction(read_only=True) as session:
        users = session.query(TxUser).order_by(TxUser.username).all()
        usernames = [u.username for u in users]
        assert usernames == ["alice"]

