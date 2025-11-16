import inspect
from typing import Any, Callable
from pico_ioc import MethodCtx, MethodInterceptor, component
from .decorators import TRANSACTIONAL_META
from .session import SessionManager


@component
class TransactionalInterceptor(MethodInterceptor):
    def __init__(self, session_manager: SessionManager):
        self.sm = session_manager

    async def invoke(self, ctx: MethodCtx, call_next: Callable[[MethodCtx], Any]) -> Any:
        func = getattr(ctx.cls, ctx.name, None)
        meta = getattr(func, TRANSACTIONAL_META, None)

        if not meta:
            result = call_next(ctx)
            if inspect.isawaitable(result):
                return await result
            return result

        propagation = meta["propagation"]
        read_only = meta["read_only"]
        isolation = meta["isolation_level"]
        rollback_for = meta["rollback_for"]
        no_rollback_for = meta["no_rollback_for"]

        async with self.sm.transaction(
            propagation=propagation,
            read_only=read_only,
            isolation_level=isolation,
            rollback_for=rollback_for,
            no_rollback_for=no_rollback_for,
        ):
            result = call_next(ctx)
            if inspect.isawaitable(result):
                result = await result
            return result
