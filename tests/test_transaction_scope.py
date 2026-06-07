"""The pico-ioc ``"transaction"`` DI scope, bound to the SQLAlchemy
transaction boundary by ``TransactionalInterceptor``.

Whenever a *new* transaction is born (``REQUIRED`` with no enclosing
transaction, and ``REQUIRES_NEW``) the interceptor activates a fresh
``"transaction"`` DI scope for exactly the lifetime of that transaction.
These tests assert the resulting semantics end-to-end through ``init()``:

* a ``scope="transaction"`` component is one instance per transaction,
* the same instance is shared when a transaction is joined,
* ``REQUIRES_NEW`` gets its own instance and restores the outer one,
* resolving it outside any transaction fails fast (``ScopeError``),
* its ``@cleanup`` hook runs when the transaction ends.

Note: ``REQUIRES_NEW`` is exercised by calling a *separate* injected
component, not via ``self`` -- AOP method interception (like Spring's)
does not apply to self-invocation, so a nested ``self.method()`` would
silently bypass the proxy and never open a new transaction.
"""

import pytest
from pico_ioc import (
    DictSource,
    PicoContainer,
    ScopeError,
    cleanup,
    component,
    configuration,
    init,
)

from pico_sqlalchemy import SessionManager, transactional


@component(scope="transaction")
class TxScoped:
    """Transaction-scoped probe: a unique id per instance and a cleanup tally."""

    created = 0
    cleaned = 0

    def __init__(self) -> None:
        TxScoped.created += 1
        self.id = TxScoped.created

    @cleanup
    def _done(self) -> None:
        TxScoped.cleaned += 1


@component
class NestedProbe:
    def __init__(self, container: PicoContainer):
        self.container = container

    @transactional(propagation="REQUIRES_NEW")
    async def scoped_id_in_new_tx(self) -> int:
        return self.container.get(TxScoped).id


@component
class Probe:
    def __init__(self, container: PicoContainer, nested: NestedProbe):
        self.container = container
        self.nested = nested

    @transactional(propagation="REQUIRED")
    async def one(self) -> int:
        return self.container.get(TxScoped).id

    @transactional(propagation="REQUIRED")
    async def twice(self) -> tuple[int, int]:
        return self.container.get(TxScoped).id, self.container.get(TxScoped).id

    @transactional(propagation="REQUIRED")
    async def outer_with_nested_new(self) -> tuple[int, int, int]:
        outer = self.container.get(TxScoped).id
        inner = await self.nested.scoped_id_in_new_tx()  # separate component -> proxied
        again = self.container.get(TxScoped).id  # back in the outer tx
        return outer, inner, again


@pytest.fixture(scope="module")
def container():
    cfg = configuration(
        DictSource({"database": {"url": "sqlite+aiosqlite:///:memory:", "echo": False}})
    )
    c = init(modules=["pico_sqlalchemy", __name__], config=cfg)
    try:
        yield c
    finally:
        c.cleanup_all()


@pytest.fixture
def probe(container) -> Probe:
    return container.get(Probe)


@pytest.fixture(autouse=True)
def _reset_counters():
    TxScoped.created = 0
    TxScoped.cleaned = 0


@pytest.mark.asyncio
async def test_one_instance_per_transaction(probe: Probe):
    first = await probe.one()
    second = await probe.one()
    assert first != second, "each top-level transaction must get a fresh instance"


@pytest.mark.asyncio
async def test_shared_within_a_transaction(probe: Probe):
    a, b = await probe.twice()
    assert a == b, "resolutions within one transaction must share the instance"


@pytest.mark.asyncio
async def test_requires_new_pushes_and_restores_scope(probe: Probe):
    outer, inner, again = await probe.outer_with_nested_new()
    assert inner != outer, "REQUIRES_NEW must get its own transaction-scoped instance"
    assert again == outer, "the outer transaction scope must be restored afterwards"


@pytest.mark.asyncio
async def test_resolution_outside_transaction_fails_fast(container):
    with pytest.raises(ScopeError):
        container.get(TxScoped)


@pytest.mark.asyncio
async def test_cleanup_runs_when_transaction_ends(probe: Probe):
    await probe.one()
    assert TxScoped.cleaned == 1, "the @cleanup hook must run once the transaction ends"
