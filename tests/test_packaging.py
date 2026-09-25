"""Packaging claims that the code cannot express."""

import pathlib
import tomllib

PYPROJECT = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_sqlalchemy_dependency_pulls_the_asyncio_extra_for_greenlet():
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    assert "sqlalchemy[asyncio] >= 2.0" in deps
