import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.db_models import Base, TransactionRecord
from app.models import Transaction

logger = logging.getLogger("persistence")

FLUSH_INTERVAL_SECONDS = 5.0
MAX_BUFFER_SIZE = 500

_UPDATE_COLUMNS = (
    "status",
    "updated_at",
    "auth_latency_ms",
    "settle_latency_ms",
    "batch_id",
    "decline_reason",
    "return_code",
    "technical_failure_reason",
)


def _row_from_transaction(txn: Transaction) -> dict:
    return {
        "id": txn.id,
        "rail": txn.rail,
        "channel": txn.channel,
        "txn_type": txn.txn_type,
        "amount": round(txn.amount, 2),
        "status": txn.status,
        "created_at": txn.created_at,
        "updated_at": txn.updated_at,
        "auth_latency_ms": txn.auth_latency_ms,
        "settle_latency_ms": txn.settle_latency_ms,
        "batch_id": txn.batch_id,
        "decline_reason": txn.decline_reason,
        "return_code": txn.return_code,
        "technical_failure_reason": txn.technical_failure_reason,
    }


class TransactionStore:
    """Durable, upsert-by-id persistence for transactions, buffered and
    flushed in batches so the live simulation loop never blocks on a database
    round-trip. A complete no-op when database_url is empty, so the app runs
    exactly as it did before this existed in any environment without one."""

    def __init__(self, database_url: str) -> None:
        self.enabled = bool(database_url)
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None
        self._buffer: list[Transaction] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        if self.enabled:
            self._engine = create_async_engine(database_url, pool_size=3, max_overflow=2)
            self._sessionmaker = async_sessionmaker(self._engine, expire_on_commit=False)

    async def start(self) -> None:
        if not self.enabled:
            return
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        if self._flush_task:
            self._flush_task.cancel()
        if self.enabled:
            await self._flush()
            await self._engine.dispose()

    async def enqueue(self, txn: Transaction) -> None:
        if not self.enabled:
            return
        async with self._lock:
            self._buffer.append(txn)
            should_flush_now = len(self._buffer) >= MAX_BUFFER_SIZE
        if should_flush_now:
            await self._flush()

    async def ping(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with self._sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("database ping failed")
            return False

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
            await self._flush()

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []

        rows = [_row_from_transaction(txn) for txn in batch]
        try:
            async with self._sessionmaker() as session:
                stmt = pg_insert(TransactionRecord).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={col: getattr(stmt.excluded, col) for col in _UPDATE_COLUMNS},
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            logger.exception("failed to flush %d transaction(s) to the database", len(rows))
            # Put them back so the next flush cycle retries, rather than
            # silently losing data on a transient hiccup (e.g. Supabase
            # waking up from an inactivity pause).
            async with self._lock:
                self._buffer = batch + self._buffer
