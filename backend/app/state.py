import asyncio
from collections import deque
from typing import Deque

from app import config
from app.models import Incident, Transaction
from app.persistence import TransactionStore

RECENT_TXN_MAXLEN = 20_000


class AppState:
    def __init__(self) -> None:
        # Each entry is an immutable snapshot (dict) of a transaction at one status
        # transition, not a live object reference — a transaction produces multiple
        # snapshots over its lifecycle (e.g. authorized, then settled).
        self.transactions: Deque[dict] = deque(maxlen=RECENT_TXN_MAXLEN)
        self.incidents: list[Incident] = []
        self.active_incidents: dict[str, Incident] = {}  # channel -> Incident
        self.subscribers: set[asyncio.Queue] = set()
        self.lock = asyncio.Lock()
        # In-memory deque above is a bounded, fast rolling window for the live
        # dashboard's SLI/burn calculations. This is the durable side: every
        # transaction also gets upserted into Postgres (a no-op if
        # DATABASE_URL isn't set), so history survives restarts/redeploys and
        # Reconciliation/Business Insights have something to query.
        self.db = TransactionStore(config.DATABASE_URL)

    async def add_transaction(self, txn: Transaction) -> None:
        snapshot = txn.to_dict()
        async with self.lock:
            self.transactions.append(snapshot)
        await self.db.enqueue(txn)
        await self.publish({"type": "transaction", "data": snapshot})

    async def start_incident(self, incident: Incident) -> None:
        async with self.lock:
            self.incidents.append(incident)
            self.active_incidents[incident.channel] = incident
        await self.publish({"type": "incident_start", "data": incident.to_dict()})

    async def end_incident(self, channel: str) -> None:
        async with self.lock:
            incident = self.active_incidents.pop(channel, None)
        if incident:
            from app.models import now

            incident.ended_at = now()
            await self.publish({"type": "incident_end", "data": incident.to_dict()})

    async def publish(self, message: dict) -> None:
        dead = []
        for q in self.subscribers:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.subscribers.discard(q)


state = AppState()
