"""AOP interceptor that manages transaction boundaries.

``TransactionalInterceptor`` is the first link in the interceptor chain
for every ``@transactional``, ``@repository``, and ``@query`` method.
It inspects decorator metadata to determine the correct propagation mode
and opens (or joins) a transaction via ``SessionManager.transaction()``
before delegating to the next interceptor or the original method body.

Priority resolution order (highest wins):

1. ``@transactional`` metadata (explicit, user-defined).
2. ``@query`` metadata (implicit ``read_only=True``).
3. ``@repository`` metadata (implicit ``read_only=False``).
"""

import inspect
from contextlib import nullcontext
from typing import Any, Callable
from uuid import uuid4

from pico_ioc import MethodCtx, MethodInterceptor, PicoContainer, component

from .decorators import QUERY_META, REPOSITORY_META, TRANSACTIONAL_META
from .session import SessionManager


@component
class TransactionalInterceptor(MethodInterceptor):
    """Opens or joins a transaction for intercepted methods.

    Registered as a ``@component`` and injected with a ``SessionManager``.
    Applied to methods via ``@intercepted_by(TransactionalInterceptor)``
    (which is done automatically by the ``@transactional``,
    ``@repository``, and ``@query`` decorators).

    The interceptor determines the transaction configuration from
    decorator metadata in the following priority order:

    1. ``@transactional`` (highest) -- user-defined propagation/read_only.
    2. ``@query`` -- ``REQUIRED`` propagation, ``read_only=True``.
    3. ``@repository`` -- ``REQUIRED`` propagation, ``read_only=False``.

    If none of these markers are present, the method is invoked directly
    without opening a transaction.

    In addition to the SQLAlchemy transaction, this interceptor binds
    pico-ioc's ``"transaction"`` DI scope to the same boundary: whenever a
    *new* transaction is started (``REQUIRES_NEW``, or ``REQUIRED`` with no
    enclosing transaction) it activates a fresh ``"transaction"`` scope for
    the duration of the call, so ``scope="transaction"`` components live
    exactly one transaction and are released (running their ``@cleanup``
    hooks) when it ends. Joins reuse the enclosing scope.

    Args:
        session_manager: The ``SessionManager`` singleton used to open
            or join transactions.
        container: The pico-ioc container, used to activate the
            ``"transaction"`` DI scope around new transactions. Optional:
            when ``None`` (e.g. a directly-constructed interceptor in a
            unit test) the transaction still runs but no DI scope is bound.
    """

    def __init__(self, session_manager: SessionManager, container: PicoContainer | None = None):
        self.sm = session_manager
        self.container = container

    async def invoke(self, ctx: MethodCtx, call_next: Callable[[MethodCtx], Any]) -> Any:
        """Intercept the method call and wrap it in a transaction if needed.

        Args:
            ctx: The AOP method context containing target class, method
                name, and arguments.
            call_next: Callback to invoke the next interceptor or the
                original method.

        Returns:
            The return value of the intercepted method.
        """
        func = getattr(ctx.cls, ctx.name, None)
        meta = getattr(func, TRANSACTIONAL_META, None)

        if not meta:
            is_query = getattr(func, QUERY_META, None) is not None
            repo_meta = getattr(ctx.cls, REPOSITORY_META, None)
            is_repository = repo_meta is not None

            if is_query:
                meta = {
                    "propagation": "REQUIRED",
                    "read_only": True,
                    "isolation_level": None,
                    "rollback_for": (Exception,),
                    "no_rollback_for": (),
                }
            elif is_repository:
                meta = {
                    "propagation": "REQUIRED",
                    "read_only": False,
                    "isolation_level": None,
                    "rollback_for": (Exception,),
                    "no_rollback_for": (),
                }

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

        # A *new* transaction is born when REQUIRES_NEW is requested, or
        # when REQUIRED finds no enclosing transaction. Those are exactly
        # the cases that should push a fresh DI "transaction" scope; every
        # other mode (joins, MANDATORY, SUPPORTS-with-tx) reuses the
        # enclosing scope, and the non-transactional modes open none. We
        # bind the scope here, at the interceptor, rather than inside
        # SessionManager: a ContextVar set deep in the transaction
        # async-generator does not reliably reach the method body across
        # nesting, whereas this frame wraps ``call_next`` directly.
        opens_new_tx = propagation == "REQUIRES_NEW" or (
            propagation == "REQUIRED" and self.sm.get_current_session() is None
        )
        scope_cm = (
            self.container.scope("transaction", uuid4().hex, cleanup=True)
            if opens_new_tx and self.container is not None
            else nullcontext()
        )

        async with self.sm.transaction(
            propagation=propagation,
            read_only=read_only,
            isolation_level=isolation,
            rollback_for=rollback_for,
            no_rollback_for=no_rollback_for,
        ):
            with scope_cm:
                result = call_next(ctx)
                if inspect.isawaitable(result):
                    result = await result
                return result
