from pico_ioc import component
from pico_sqlalchemy import transactional, repository

from .models import User


@component
@repository
class UserRepository:
    """Repository for User CRUD operations."""

    @transactional
    async def create(self, session, name: str, email: str) -> User:
        user = User(name=name, email=email)
        session.add(user)
        await session.flush()
        return user

    @transactional(read_only=True)
    async def find_by_id(self, session, user_id: int) -> User | None:
        return await session.get(User, user_id)

    @transactional(read_only=True)
    async def find_all(self, session) -> list[User]:
        from sqlalchemy import select
        result = await session.execute(select(User))
        return list(result.scalars().all())

    @transactional
    async def update_email(self, session, user_id: int, new_email: str) -> User | None:
        user = await session.get(User, user_id)
        if user:
            user.email = new_email
        return user

    @transactional
    async def delete(self, session, user_id: int) -> bool:
        user = await session.get(User, user_id)
        if user:
            await session.delete(user)
            return True
        return False
