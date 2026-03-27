"""pico-sqlalchemy -- SQLAlchemy async integration for pico-ioc.

Provides Spring-style declarative transactions, a repository pattern with
automatic query execution, and pagination support.  All components are
auto-discovered when ``"pico_sqlalchemy"`` is listed in the ``modules``
argument of ``pico_ioc.init()`` (or via the ``pico_boot.modules`` entry
point).

Typical usage::

    from pico_ioc import init, configuration, DictSource
    from pico_sqlalchemy import (
        repository, query, transactional,
        SessionManager, get_session, AppBase,
        Page, PageRequest, Sort,
    )

    config = configuration(DictSource({
        "database": {"url": "sqlite+aiosqlite:///:memory:"}
    }))
    # pico-boot auto-discovers pico-sqlalchemy — just list your app module
    container = init(modules=["my_app"], config=config)
"""

from .base import AppBase, Mapped, mapped_column
from .config import DatabaseConfigurer, DatabaseSettings
from .decorators import query, repository, transactional
from .factory import SqlAlchemyFactory
from .interceptor import TransactionalInterceptor
from .paging import Page, PageRequest, Sort
from .repository_interceptor import RepositoryQueryInterceptor
from .session import SessionManager, get_session

__all__ = [
    "DatabaseSettings",
    "DatabaseConfigurer",
    "transactional",
    "repository",
    "query",
    "SessionManager",
    "get_session",
    "TransactionalInterceptor",
    "SqlAlchemyFactory",
    "AppBase",
    "Mapped",
    "mapped_column",
    "Page",
    "PageRequest",
    "Sort",
    "RepositoryQueryInterceptor",
]
