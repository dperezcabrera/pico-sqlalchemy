"""Alembic migrations on startup.

Set ``database.migrations_path`` to your Alembic script directory (the
one containing ``env.py``) and the container runs ``upgrade head``
before any other ``DatabaseConfigurer`` (priority -100). Alembic is an
optional dependency: ``pip install pico-sqlalchemy[migrations]``.

The configured ``database.url`` is handed to Alembic verbatim as
``sqlalchemy.url`` — write ``env.py`` for the async URL (Alembic's
async template) or derive a sync engine from it there.
"""

import logging

from pico_ioc import component

from .config import DatabaseSettings

logger = logging.getLogger(__name__)


@component
class AlembicMigrator:
    priority = -100

    def __init__(self, settings: DatabaseSettings):
        self._settings = settings

    def configure_database(self, engine) -> None:
        path = self._settings.migrations_path
        if not path:
            return
        try:
            from alembic import command
            from alembic.config import Config
        except ImportError as exc:
            raise RuntimeError(
                "database.migrations_path is set but Alembic is not installed: pip install pico-sqlalchemy[migrations]"
            ) from exc

        config = Config()
        config.set_main_option("script_location", path)
        config.set_main_option("sqlalchemy.url", self._settings.url)
        target = self._settings.migrations_target
        logger.info("running alembic upgrade %s from %s", target, path)
        command.upgrade(config, target)
