"""Tests for AlembicMigrator: startup migrations from database.migrations_path."""

import sqlite3
import sys
import textwrap

import pytest
from pico_ioc import DictSource, configuration, init

from pico_sqlalchemy import AlembicMigrator, DatabaseSettings

ENV_PY = textwrap.dedent(
    """
    from alembic import context
    from sqlalchemy import create_engine

    url = context.config.get_main_option("sqlalchemy.url").replace("+aiosqlite", "")
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    """
)

REVISION_1 = textwrap.dedent(
    """
    import sqlalchemy as sa
    from alembic import op

    revision = "0001"
    down_revision = None

    def upgrade():
        op.create_table("migrated_things", sa.Column("id", sa.Integer, primary_key=True))

    def downgrade():
        op.drop_table("migrated_things")
    """
)

REVISION_2 = textwrap.dedent(
    """
    import sqlalchemy as sa
    from alembic import op

    revision = "0002"
    down_revision = "0001"

    def upgrade():
        op.add_column("migrated_things", sa.Column("name", sa.String(50)))

    def downgrade():
        op.drop_column("migrated_things", "name")
    """
)


@pytest.fixture
def migrations_dir(tmp_path):
    scripts = tmp_path / "migrations"
    (scripts / "versions").mkdir(parents=True)
    (scripts / "env.py").write_text(ENV_PY, encoding="utf-8")
    (scripts / "versions" / "0001_initial.py").write_text(REVISION_1, encoding="utf-8")
    (scripts / "versions" / "0002_add_name.py").write_text(REVISION_2, encoding="utf-8")
    return scripts


def _tables(db_path) -> set:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _columns(db_path, table) -> set:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def test_container_startup_runs_migrations(tmp_path, migrations_dir):
    db_path = tmp_path / "app.db"
    config = configuration(
        DictSource(
            {
                "database": {
                    "url": f"sqlite+aiosqlite:///{db_path}",
                    "migrations_path": str(migrations_dir),
                }
            }
        )
    )
    container = init(modules=["pico_sqlalchemy"], config=config)
    try:
        assert "migrated_things" in _tables(db_path)
        assert "name" in _columns(db_path, "migrated_things")
        assert "alembic_version" in _tables(db_path)
    finally:
        container.shutdown()


def test_migrations_target_stops_at_revision(tmp_path, migrations_dir):
    db_path = tmp_path / "app.db"
    settings = DatabaseSettings(
        url=f"sqlite+aiosqlite:///{db_path}",
        migrations_path=str(migrations_dir),
        migrations_target="0001",
    )
    AlembicMigrator(settings).configure_database(engine=None)
    assert "migrated_things" in _tables(db_path)
    assert "name" not in _columns(db_path, "migrated_things")


def test_no_path_is_a_noop(tmp_path):
    settings = DatabaseSettings(url=f"sqlite+aiosqlite:///{tmp_path}/app.db")
    AlembicMigrator(settings).configure_database(engine=None)
    assert not (tmp_path / "app.db").exists()


def test_missing_alembic_raises_actionable_error(tmp_path, migrations_dir, monkeypatch):
    monkeypatch.setitem(sys.modules, "alembic", None)
    monkeypatch.setitem(sys.modules, "alembic.config", None)
    settings = DatabaseSettings(
        url=f"sqlite+aiosqlite:///{tmp_path}/app.db",
        migrations_path=str(migrations_dir),
    )
    with pytest.raises(RuntimeError, match="pico-sqlalchemy\\[migrations\\]"):
        AlembicMigrator(settings).configure_database(engine=None)


def test_rerun_is_idempotent(tmp_path, migrations_dir):
    db_path = tmp_path / "app.db"
    settings = DatabaseSettings(
        url=f"sqlite+aiosqlite:///{db_path}",
        migrations_path=str(migrations_dir),
    )
    migrator = AlembicMigrator(settings)
    migrator.configure_database(engine=None)
    migrator.configure_database(engine=None)
    assert "migrated_things" in _tables(db_path)
