from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

Rail = Literal["CARD", "WIRE", "ACH_BATCH"]
Channel = Literal[
    "pos",
    "ecommerce",
    "mobile_wallet",
    "wire_online",
    "wire_branch",
    "ach_batch_file",
]
TxnType = Literal["credit", "debit", "wire"]
Status = Literal[
    "initiated",
    "authorized",
    "declined",
    "settled",
    "posted",
    "failed",
    "returned",
]


def now() -> datetime:
    return datetime.now(timezone.utc)


CHANNEL_RAIL: dict[Channel, Rail] = {
    "pos": "CARD",
    "ecommerce": "CARD",
    "mobile_wallet": "CARD",
    "wire_online": "WIRE",
    "wire_branch": "WIRE",
    "ach_batch_file": "ACH_BATCH",
}

CHANNEL_TXN_TYPE: dict[Channel, TxnType] = {
    "pos": "debit",
    "ecommerce": "credit",
    "mobile_wallet": "credit",
    "wire_online": "wire",
    "wire_branch": "wire",
    "ach_batch_file": "debit",
}


@dataclass
class Transaction:
    id: str
    rail: Rail
    channel: Channel
    txn_type: TxnType
    amount: float
    status: Status
    created_at: datetime
    updated_at: datetime
    auth_latency_ms: Optional[float] = None
    settle_latency_ms: Optional[float] = None
    batch_id: Optional[str] = None
    decline_reason: Optional[str] = None
    return_code: Optional[str] = None

    @staticmethod
    def new(channel: Channel, amount: float) -> "Transaction":
        ts = now()
        return Transaction(
            id=str(uuid.uuid4()),
            rail=CHANNEL_RAIL[channel],
            channel=channel,
            txn_type=CHANNEL_TXN_TYPE[channel],
            amount=amount,
            status="initiated",
            created_at=ts,
            updated_at=ts,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rail": self.rail,
            "channel": self.channel,
            "txn_type": self.txn_type,
            "amount": round(self.amount, 2),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "auth_latency_ms": self.auth_latency_ms,
            "settle_latency_ms": self.settle_latency_ms,
            "batch_id": self.batch_id,
            "decline_reason": self.decline_reason,
            "return_code": self.return_code,
        }


@dataclass
class Incident:
    id: str
    rail: Rail
    channel: Channel
    kind: Literal["latency_spike", "failure_spike"]
    magnitude: float
    started_at: datetime
    ended_at: Optional[datetime] = None
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rail": self.rail,
            "channel": self.channel,
            "kind": self.kind,
            "magnitude": self.magnitude,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "description": self.description,
            "active": self.ended_at is None,
        }
