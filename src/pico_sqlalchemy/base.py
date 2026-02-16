"""SQLAlchemy declarative base registered as a pico-ioc singleton.

All application ORM models should inherit from ``AppBase`` so that they
share a single ``MetaData`` registry, which is required for
``DatabaseConfigurer`` hooks (e.g. ``metadata.create_all``) and for
Alembic migrations.

``Mapped`` and ``mapped_column`` are re-exported from SQLAlchemy for
convenience.

Example::

    from pico_sqlalchemy import AppBase, Mapped, mapped_column
    from sqlalchemy import String

    class User(AppBase):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String(50))
"""

from pico_ioc import component
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@component(scope="singleton")
class AppBase(DeclarativeBase):
    """Central SQLAlchemy ``DeclarativeBase`` for all application models.

    Registered as a pico-ioc singleton so that the same ``MetaData``
    instance is shared across the entire application.  All ORM model
    classes should inherit from this base.
    """

    pass


__all__ = ["AppBase", "Mapped", "mapped_column"]
