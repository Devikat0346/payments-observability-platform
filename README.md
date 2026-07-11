# Multi-Rail Payments Observability Platform

A synthetic multi-channel payments processor with a live SRE-style observability layer on top: SLIs, SLOs, and error-budget burn, computed in real time from simulated credit, debit, and wire traffic across both real-time and batch origination rails.

**Live demo:** https://payments-platform-theta.vercel.app/observability (part of the unified [Payments Platform](https://github.com/Devikat0346/payments-platform) — this repo is backend-only; its original standalone frontend was retired once the unified one shipped)
**API:** https://payments-observability-api.onrender.com/api/health

## Why this exists

Payments platforms originate transactions from very different rails with very different failure modes and latency profiles: card-present POS swipes settle in milliseconds, wire transfers can take seconds and carry tighter compliance requirements, and ACH activity is batched and reconciled hours later. Operating that mix reliably means tracking SLIs per rail, not one blended number — a wire outage and a POS blip look identical in an aggregate success-rate chart but require completely different responses.

This project simulates that environment end-to-end: transaction generation, rail-specific processing logic, randomly injected incidents, and the observability tooling an SRE would actually use to detect and triage them.

## Architecture

```
┌─────────────────────────┐        WebSocket (live ticks)       ┌──────────────────────┐
│  FastAPI backend         │ ───────────────────────────────────▶│  Next.js dashboard    │
│  (asyncio simulation)    │        REST (recent txns/metrics)   │  (React, recharts)    │
│                           │◀───────────────────────────────────│                       │
│  • transaction generator │                                      └──────────────────────┘
│  • real-time processor   │
│    (CARD, WIRE rails)    │
│  • batch processor       │
│    (ACH_BATCH rail)      │
│  • incident injector     │
│  • rolling-window metrics│
└──────────────────────────┘
```

Everything runs as background `asyncio` tasks inside a single FastAPI process — no external queue or database. State is in-memory by design (see **Design decisions** below).

### Origination channels simulated

| Channel | Rail | Path |
|---|---|---|
| POS (card-present) | CARD | Real-time |
| E-commerce (card-not-present) | CARD | Real-time |
| Mobile wallet | CARD | Real-time |
| Wire — online banking | WIRE | Real-time |
| Wire — branch-initiated | WIRE | Real-time |
| ACH batch file | ACH_BATCH | Batch window (every 25s, compressed from a nightly cycle) |

Each channel has its own latency distribution, baseline decline/return rate, and amount range, tuned to be roughly realistic relative to the others (e.g. wire-branch is slower and less failure-prone than e-commerce, which has a materially higher decline rate due to fraud screening).

### Observability layer

- **SLIs** — p50/p95/p99 authorization latency and success rate, computed per channel over a rolling 5-minute window.
- **SLOs** — fixed targets per rail (e.g. CARD: 99% success / 1.5s p99; WIRE: 98.5% success / 5s p99).
- **Error-budget burn** — actual failure rate vs. the rail's allowed failure rate, over a rolling 30-minute window (compressed stand-in for a monthly budget), expressed as a percentage — over 100% means the budget is fully spent.
- **Incident injection** — every 20 seconds, each channel has a small independent chance of entering a degraded state (a latency spike or a failure-rate spike) lasting 20–60 seconds, which shows up live on the dashboard as a channel going from Healthy → Degraded and its error budget burning faster.

## Tech stack

- **Backend:** Python 3.12, FastAPI, asyncio, uvicorn, plain WebSocket (no external broker)
- **Deploy:** Render, single free-tier web service (see below). The frontend lives in the separate [payments-platform](https://github.com/Devikat0346/payments-platform) repo, deployed on Vercel.

## Design decisions

- **Single-instance, in-memory state.** All transaction and metrics state lives in one process's memory rather than Postgres/Redis. This keeps the demo simple and fast to run, but it's a deliberate scoping choice, not an oversight — the backend runs as exactly one instance because horizontally scaling it as-is would give each replica a different view of "recent" transactions. A production version would move transaction state to a shared store (e.g. Postgres for durability, Redis for the rolling metrics windows) before scaling out.
- **Why Render, not Fly.io.** This was originally deployed on Fly.io; its free trial later expired and started requiring a credit card to keep machines running, which conflicted with a hard no-billing constraint for this project. Migrated to Render's free web-service tier instead — the trade-off is that free Render services sleep after ~15 minutes idle and take 30-60s to wake on the next request.
- **Compressed time windows.** Real SLO error budgets are typically tracked over 30-day windows; this demo uses 30 minutes so the burn-rate behavior is visible in a single sitting instead of a month.
- **Snapshot-per-event, not a mutable object.** Each transaction status transition (initiated → authorized → settled, etc.) is stored as an immutable dict snapshot rather than mutating one shared object in place — otherwise every historical reference to a transaction would silently reflect its *current* state instead of the state at that point in time, which would quietly corrupt the metrics history.

## Running locally

```bash
cd backend
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --port 8000
```

To see it rendered, run the [payments-platform](https://github.com/Devikat0346/payments-platform) frontend locally against this backend (point its `NEXT_PUBLIC_OBSERVABILITY_API_URL`/`_WS_URL` at `http://localhost:8000` / `ws://localhost:8000/ws/live`).

## What's next

This is Project 1 of a five-project portfolio. Project 2 (an AI incident copilot) will consume this platform's telemetry directly to auto-summarize root cause during the incidents this simulator already generates.
