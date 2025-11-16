from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pico_ioc import component


@component(scope="singleton")
class AppBase(DeclarativeBase):
    pass


__all__ = ["AppBase", "Mapped", "mapped_column"]
