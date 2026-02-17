from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from pico_sqlalchemy import AppBase


class User(AppBase):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
