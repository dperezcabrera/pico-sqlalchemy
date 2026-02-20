"""Shared test fixtures for pico-sqlalchemy tests."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase

from pico_sqlalchemy import AppBase, DatabaseConfigurer, SessionManager

# ── Shared declarative base for standalone SessionManager tests ──


class Base(DeclarativeBase):
    pass


# ── Shared DatabaseConfigurer base for IOC-based tests ──


class SetupDBBase(DatabaseConfigurer):
    """Table creation configurer — subclass with @component in each test module."""

    def __init__(self, base: AppBase):
        self.base = base

    def configure_database(self, engine):
        async def run():
            async with engine.begin() as conn:
                await conn.run_sync(self.base.metadata.create_all)

        asyncio.run(run())


# ── SessionManager helper for standalone tests ──


def new_session_manager(base: type) -> SessionManager:
    """Create an in-memory SessionManager and create all tables for the given base."""
    manager = SessionManager(url="sqlite+aiosqlite:///:memory:", echo=False)

    async def create_tables(engine: AsyncEngine):
        async with engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    asyncio.run(create_tables(manager.engine))
    return manager
