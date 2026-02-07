from pico_ioc import component
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@component(scope="singleton")
class AppBase(DeclarativeBase):
    pass


__all__ = ["AppBase", "Mapped", "mapped_column"]
