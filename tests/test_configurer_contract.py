"""DatabaseConfigurer contract: structural matching without subclassing or a
priority attribute, and hooks that stay safe under a running event loop
(the ASGI case: uvicorn runs the @configure phase inside the loop)."""

import asyncio

from pico_ioc import DictSource, component, configuration, init

calls: list[str] = []


@component
class PlainConfigurer:
    """No subclass, no priority: the one method is the whole contract."""

    def configure_database(self, engine) -> None:
        calls.append("plain")


@component
class BlockingConfigurer:
    """Uses asyncio.run(), as the documented DDL pattern does."""

    priority = 1

    def configure_database(self, engine) -> None:
        async def _probe():
            calls.append("blocking")

        asyncio.run(_probe())


CONFIG = {"database": {"url": "sqlite+aiosqlite:///:memory:"}}


def _boot():
    import sys

    from pico_sqlalchemy import SessionManager

    container = init(modules=["pico_sqlalchemy", sys.modules[__name__]], config=configuration(DictSource(CONFIG)))
    container.get(SessionManager)
    container.shutdown()


def test_plain_component_is_collected_without_subclass_or_priority():
    calls.clear()
    _boot()
    assert "plain" in calls, "configurer estructural (solo configure_database) no recogido"
    assert calls == ["plain", "blocking"]  # priority 0 antes que 1


def test_hooks_run_safely_inside_a_running_event_loop():
    """uvicorn boots the container from inside the loop; asyncio.run() in a
    hook must keep working (fails on 0.5.0 with 'cannot be called from a
    running event loop')."""
    calls.clear()

    async def boot_like_asgi():
        _boot()

    asyncio.run(boot_like_asgi())
    assert calls == ["plain", "blocking"]
