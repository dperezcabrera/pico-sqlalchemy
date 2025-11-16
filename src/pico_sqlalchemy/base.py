from sqlalchemy.orm import DeclarativeBase
from pico_ioc import component


@component(scope="singleton")
class AppBase(DeclarativeBase):

    pass
