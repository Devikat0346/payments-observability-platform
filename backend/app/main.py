import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import metrics, queries
from app.engine import SimulationEngine
from app.state import state

engine = SimulationEngine(state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state.db.start()
    engine.start()
    yield
    await engine.stop()
    await state.db.stop()


app = FastAPI(title="Payments Observability Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/db-ping")
async def db_ping():
    # Deliberately separate from /api/health: this one touches the database
    # (also serves as the target for an external keep-alive cron, since
    # Supabase's free tier pauses a project after 7 days with no database
    # activity) rather than being on the hot path of a routine liveness check.
    if not state.db.enabled:
        return {"database": "not configured"}
    return {"database": "ok" if await state.db.ping() else "unreachable"}


@app.get("/api/metrics/summary")
async def metrics_summary():
    return metrics.compute_summary(state)


@app.get("/api/incidents")
async def incidents(active_only: bool = False):
    items = state.incidents
    if active_only:
        items = [i for i in items if i.ended_at is None]
    return [i.to_dict() for i in sorted(items, key=lambda i: i.started_at, reverse=True)]


@app.get("/api/transactions/recent")
async def recent_transactions(limit: int = 50, channel: str | None = None, status: str | None = None):
    latest_by_id: dict[str, dict] = {}
    for event in state.transactions:
        if channel is not None and event["channel"] != channel:
            continue
        if status is not None and event["status"] != status:
            continue
        latest_by_id[event["id"]] = event
    ordered = sorted(
        latest_by_id.values(),
        key=lambda e: datetime.fromisoformat(e["updated_at"]),
        reverse=True,
    )
    return ordered[:limit]


@app.get("/api/transactions/{transaction_id}")
async def transaction_by_id(transaction_id: str):
    # A transaction can have multiple snapshots over its lifecycle (e.g.
    # authorized, then settled) — return the latest one, same dedup logic
    # as recent_transactions.
    matches = [e for e in state.transactions if e["id"] == transaction_id]
    if matches:
        return max(matches, key=lambda e: datetime.fromisoformat(e["updated_at"]))

    # Not in the in-memory rolling window (a few hours at most) — fall back
    # to Postgres for anything older, if persistence is configured.
    from_db = await queries.get_transaction_from_db(state, transaction_id)
    if from_db is not None:
        return from_db
    raise HTTPException(status_code=404, detail="transaction not found")


@app.get("/api/channels/{channel}/history")
async def channel_history(channel: str, limit: int = 50, offset: int = 0):
    return await queries.get_channel_history(state, channel, limit=limit, offset=offset)


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket):
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    state.subscribers.add(queue)
    try:
        await websocket.send_json({"type": "metrics_tick", "data": metrics.compute_summary(state)})
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        state.subscribers.discard(queue)
