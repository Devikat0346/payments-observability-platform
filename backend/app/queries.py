from sqlalchemy import select

from app.db_models import TransactionRecord
from app.state import AppState


def _row_to_dict(row: TransactionRecord) -> dict:
    return {
        "id": row.id,
        "rail": row.rail,
        "channel": row.channel,
        "txn_type": row.txn_type,
        "amount": float(row.amount),
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "auth_latency_ms": row.auth_latency_ms,
        "settle_latency_ms": row.settle_latency_ms,
        "batch_id": row.batch_id,
        "decline_reason": row.decline_reason,
        "return_code": row.return_code,
        "technical_failure_reason": row.technical_failure_reason,
    }


async def get_channel_history(state: AppState, channel: str, limit: int = 50, offset: int = 0) -> list[dict]:
    """Full transaction history for one channel, straight from Postgres —
    unlike the in-memory rolling deque (capped at 20,000 events across every
    channel combined, a few hours of traffic at most), this reaches back over
    however much history the database has retained. Each row is already a
    single current-state-per-id record (see TransactionStore's upsert), so
    there's no snapshot-dedup step needed here unlike the in-memory feed."""
    if not state.db.enabled:
        return []
    async with state.db.session() as session:
        rows = (
            await session.execute(
                select(TransactionRecord)
                .where(TransactionRecord.channel == channel)
                .order_by(TransactionRecord.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()
    return [_row_to_dict(r) for r in rows]


async def get_transaction_from_db(state: AppState, transaction_id: str) -> dict | None:
    """DB fallback for a transaction no longer in the in-memory rolling
    window — the in-memory feed is fast for the common case (a transaction
    from the last few hours), this is the path for anything older."""
    if not state.db.enabled:
        return None
    async with state.db.session() as session:
        row = (
            await session.execute(select(TransactionRecord).where(TransactionRecord.id == transaction_id))
        ).scalar_one_or_none()
    return _row_to_dict(row) if row else None
