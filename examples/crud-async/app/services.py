from pico_ioc import component

from .repositories import UserRepository


@component
class UserService:
    """Business logic for user operations."""

    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def create_user(self, name: str, email: str):
        return await self.repo.create(name=name, email=email)

    async def get_user(self, user_id: int):
        return await self.repo.find_by_id(user_id=user_id)

    async def list_users(self):
        return await self.repo.find_all()

    async def update_user_email(self, user_id: int, new_email: str):
        return await self.repo.update_email(user_id=user_id, new_email=new_email)

    async def delete_user(self, user_id: int):
        return await self.repo.delete(user_id=user_id)
