# Multi-Rail Payments Observability Platform

A synthetic multi-channel payments processor with a live SRE-style observability layer on top: SLIs, SLOs, and error-budget burn, computed in real time from simulated credit, debit, wire, ACH, and Zelle traffic across eleven distinct origination journeys, spanning both real-time and batch rails.

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
│    (CARD, WIRE, ZELLE)   │
│  • batch processor       │
│    (ACH_BATCH, WIRE      │
│     bulk-file batch)     │
│  • incident injector     │
│  • rolling-window metrics│
└──────────────────────────┘
```

Everything runs as background `asyncio` tasks inside a single FastAPI process. The rolling-window metrics stay in-memory by design (see **Design decisions** below); transactions are additionally persisted to Postgres (Supabase's free tier) so history survives restarts and other modules (reconciliation, business insights) have something durable to query — a no-op if `DATABASE_URL` isn't set, so the app runs exactly as before in any environment without one.

### Origination channels simulated

| Channel | Rail | Path | Origination |
|---|---|---|---|
| POS (card-present) | CARD | Real-time | Retail terminal swipe/tap |
| E-commerce (card-not-present) | CARD | Real-time | Online checkout |
| Mobile wallet | CARD | Real-time | In-app tap-to-pay |
| Wire — digital banking | WIRE | Real-time | Customer-initiated online |
| Wire — branch | WIRE | Real-time | In-person at a branch |
| Wire — commercial loan (LoanIQ) | WIRE | Real-time | Loan funding/drawdown via LoanIQ |
| Wire — bulk batch file | WIRE | Batch window | Corporate customer submits a wire file |
| Wire — phone/IVR | WIRE | Real-time | Customer calls in, initiates via IVR |
| ACH batch file | ACH_BATCH | Batch window | Bulk file (payroll, bill pay) |
| Zelle — mobile app | ZELLE | Real-time | P2P send/request, mobile banking app |
| Zelle — online banking | ZELLE | Real-time | P2P send/request, online banking |

Both batch windows (ACH and bulk wire file) run independently every 25s, compressed from a real nightly/intraday cycle.

Each channel has its own latency distribution, baseline decline/return rate, amount range, and decline-reason pool, tuned to be roughly realistic relative to the others — e.g. wire-branch is slower and less failure-prone than e-commerce (which has a materially higher decline rate due to fraud screening); LoanIQ wires move much larger dollar amounts and fail on compliance/collateral grounds rather than insufficient funds; Zelle fails mostly on recipient-not-enrolled or fraud holds rather than technical latency, since it's a near-instant rail by design. Credit vs. debit is a realistic probabilistic mix within card and ACH channels (a POS swipe can be run as either) rather than a fixed 1:1 mapping.

### Observability layer

- **SLIs** — p50/p95/p99 authorization latency and success rate, computed per channel over a rolling 5-minute window.
- **SLOs** — fixed targets per rail (e.g. CARD: 99% success / 1.5s p99; WIRE: 98.5% success / 5s p99; ZELLE: 99.5% success / 2s p99, reflecting its near-instant design).
- **Error-budget burn** — actual failure rate vs. the rail's allowed failure rate, over a rolling 30-minute window (compressed stand-in for a monthly budget), expressed as a percentage — over 100% means the budget is fully spent.
- **Incident injection** — every 20 seconds, each channel has a small independent chance of entering a degraded state (a latency spike or a failure-rate spike) lasting 20–60 seconds, which shows up live on the dashboard as a channel going from Healthy → Degraded and its error budget burning faster.

## Tech stack

- **Backend:** Python 3.12, FastAPI, asyncio, uvicorn, plain WebSocket (no external broker), SQLAlchemy (async) + asyncpg for the Postgres durability layer
- **Deploy:** Render, single free-tier web service (see below), with a Supabase free-tier Postgres for durable transaction history. The frontend lives in the separate [payments-platform](https://github.com/Devikat0346/payments-platform) repo, deployed on Vercel.

## Design decisions

- **Single-instance, in-memory state for the hot path.** The rolling 5m/30m metrics windows live in one process's memory rather than Redis, since horizontally scaling this as-is would give each replica a different view of "recent" — a deliberate scoping choice, not an oversight. Every transaction is *also* upserted into Postgres in small batches (buffered ~5s or 500 rows, whichever comes first, so the simulation loop never blocks on a database round-trip), which is what makes durability and cross-restart history possible without giving up the fast in-memory path for the numbers the dashboard needs every couple of seconds.
- **Why Supabase, not Render Postgres.** Render's free Postgres tier deletes the database outright 30 days (+ a 14-day grace period) after creation — a bad fit for a portfolio project meant to persist. Supabase's free tier instead pauses a project after 7 days of database inactivity (data is preserved, not deleted, and it resumes automatically on the next request in ~30s) — annoying but non-destructive. A scheduled GitHub Action pings a dedicated `/api/db-ping` endpoint every 3 days to keep it from pausing at all.
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

`DATABASE_URL` is optional — without it, the app behaves exactly as it did before persistence existed (in-memory only). Set it to a Postgres connection string (e.g. a Supabase project's URI) to enable durable transaction history; the `transactions` table is created automatically on startup.

To see it rendered, run the [payments-platform](https://github.com/Devikat0346/payments-platform) frontend locally against this backend (point its `NEXT_PUBLIC_OBSERVABILITY_API_URL`/`_WS_URL` at `http://localhost:8000` / `ws://localhost:8000/ws/live`).

## What's next

This is Project 1 of a five-project portfolio. Project 2 (an AI incident copilot) will consume this platform's telemetry directly to auto-summarize root cause during the incidents this simulator already generates.
