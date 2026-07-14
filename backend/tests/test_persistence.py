import pytest

from app.models import Transaction
from app.persistence import MAX_BUFFER_SIZE, TransactionStore


def _txn(channel="pos", status="settled") -> Transaction:
    txn = Transaction.new(channel=channel, txn_type="debit", amount=42.0)
    txn.status = status
    return txn


class FakeSession:
    def __init__(self, recorder: list, should_fail: bool) -> None:
        self._recorder = recorder
        self._should_fail = should_fail

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def execute(self, stmt) -> None:
        if self._should_fail:
            raise RuntimeError("simulated database failure")
        self._recorder.append(stmt)

    async def commit(self) -> None:
        pass


class FakeSessionmaker:
    """Stands in for SQLAlchemy's async_sessionmaker — records each executed
    statement without touching a real database."""

    def __init__(self, should_fail: bool = False) -> None:
        self.recorder: list = []
        self.should_fail = should_fail

    def __call__(self) -> FakeSession:
        return FakeSession(self.recorder, self.should_fail)


def _store_with_fake_backend(should_fail: bool = False) -> tuple[TransactionStore, FakeSessionmaker]:
    # A real (but never-connected-to) URL: constructing an async engine is
    # lazy in SQLAlchemy, so this doesn't touch a network. The sessionmaker
    # is then swapped for a fake so _flush() never needs a real database.
    store = TransactionStore("postgresql+asyncpg://user:pass@localhost/test")
    fake_sessionmaker = FakeSessionmaker(should_fail=should_fail)
    store._sessionmaker = fake_sessionmaker
    return store, fake_sessionmaker


class TestTransactionStoreDisabled:
    @pytest.mark.asyncio
    async def test_disabled_when_no_database_url(self):
        store = TransactionStore("")
        assert store.enabled is False

    @pytest.mark.asyncio
    async def test_enqueue_is_a_no_op_when_disabled(self):
        store = TransactionStore("")
        await store.enqueue(_txn())
        assert store._buffer == []

    @pytest.mark.asyncio
    async def test_start_and_stop_are_no_ops_when_disabled(self):
        store = TransactionStore("")
        await store.start()
        await store.stop()

    @pytest.mark.asyncio
    async def test_ping_returns_false_when_disabled(self):
        store = TransactionStore("")
        assert await store.ping() is False


class TestTransactionStoreBuffering:
    @pytest.mark.asyncio
    async def test_enqueue_buffers_without_flushing_immediately(self):
        store, backend = _store_with_fake_backend()

        await store.enqueue(_txn())

        assert len(store._buffer) == 1
        assert backend.recorder == []

    @pytest.mark.asyncio
    async def test_flush_clears_buffer_and_executes_one_batched_statement(self):
        store, backend = _store_with_fake_backend()

        await store.enqueue(_txn(channel="pos"))
        await store.enqueue(_txn(channel="wire_online"))
        await store._flush()

        assert store._buffer == []
        assert len(backend.recorder) == 1

    @pytest.mark.asyncio
    async def test_reaching_max_buffer_size_triggers_an_immediate_flush(self):
        store, backend = _store_with_fake_backend()

        for _ in range(MAX_BUFFER_SIZE):
            await store.enqueue(_txn())

        assert store._buffer == []
        assert len(backend.recorder) == 1

    @pytest.mark.asyncio
    async def test_failed_flush_requeues_the_batch_for_the_next_retry(self):
        store, backend = _store_with_fake_backend(should_fail=True)

        await store.enqueue(_txn())
        await store._flush()

        assert len(store._buffer) == 1
        assert backend.recorder == []
