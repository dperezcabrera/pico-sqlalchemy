"""The public API is exactly what ``__all__`` declares (stability contract)."""

import pico_sqlalchemy


def test_public_api_is_declared_and_importable():
    assert set(pico_sqlalchemy.__all__) == {
        "AlembicMigrator",
        "AppBase",
        "DatabaseConfigurer",
        "DatabaseSettings",
        "Mapped",
        "Page",
        "PageRequest",
        "RepositoryQueryInterceptor",
        "SessionManager",
        "Sort",
        "SqlAlchemyFactory",
        "TransactionalInterceptor",
        "get_session",
        "mapped_column",
        "query",
        "repository",
        "transactional",
    }
    for name in pico_sqlalchemy.__all__:
        assert getattr(pico_sqlalchemy, name) is not None
