from datetime import datetime

from sqlalchemy import DateTime, Float, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TransactionRecord(Base):
    """Durable, one-row-per-transaction mirror of the in-memory simulator's
    Transaction dataclass — keyed by id and upserted as a transaction moves
    through its lifecycle, so this table always holds each transaction's
    latest state (like a real payments ledger), not one row per snapshot."""

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    rail: Mapped[str] = mapped_column(String, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, index=True)
    txn_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    auth_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    settle_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    return_code: Mapped[str | None] = mapped_column(String, nullable=True)
    technical_failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
