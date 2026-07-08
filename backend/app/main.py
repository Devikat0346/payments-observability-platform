import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import metrics
from app.engine import SimulationEngine
from app.state import state

engine = SimulationEngine(state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.start()
    yield
    await engine.stop()


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
async def recent_transactions(limit: int = 50):
    latest_by_id: dict[str, dict] = {}
    for event in state.transactions:
        latest_by_id[event["id"]] = event
    ordered = sorted(
        latest_by_id.values(),
        key=lambda e: datetime.fromisoformat(e["updated_at"]),
        reverse=True,
    )
    return ordered[:limit]


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
