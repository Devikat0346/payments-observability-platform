from fastapi.testclient import TestClient

from app.main import app
from app.state import state


def test_health():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_metrics_summary_shape():
    with TestClient(app) as client:
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "channels" in body
        assert "rails" in body
        assert "txn_types" in body
        assert "pos" in body["channels"]
        assert "zelle_mobile" in body["channels"]
        assert "wire_loaniq" in body["channels"]


def test_recent_transactions_channel_filter():
    with TestClient(app) as client:
        # seed deterministic data directly into shared state rather than waiting
        # on the live simulation loop, so this test doesn't depend on timing.
        state.transactions.append(
            {
                "id": "seed-1",
                "rail": "CARD",
                "channel": "pos",
                "txn_type": "debit",
                "amount": 12.5,
                "status": "settled",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "auth_latency_ms": 100.0,
                "settle_latency_ms": 200.0,
                "batch_id": None,
                "decline_reason": None,
                "return_code": None,
            }
        )
        resp = client.get("/api/transactions/recent", params={"channel": "pos", "limit": 5})
        assert resp.status_code == 200
        results = resp.json()
        assert any(t["id"] == "seed-1" for t in results)
        assert all(t["channel"] == "pos" for t in results)


def test_incidents_endpoint_returns_list():
    with TestClient(app) as client:
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_transaction_by_id_returns_latest_snapshot():
    with TestClient(app) as client:
        state.transactions.append(
            {
                "id": "seed-lifecycle",
                "rail": "WIRE",
                "channel": "wire_online",
                "txn_type": "wire",
                "amount": 500.0,
                "status": "authorized",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "auth_latency_ms": 900.0,
                "settle_latency_ms": None,
                "batch_id": None,
                "decline_reason": None,
                "return_code": None,
            }
        )
        state.transactions.append(
            {
                "id": "seed-lifecycle",
                "rail": "WIRE",
                "channel": "wire_online",
                "txn_type": "wire",
                "amount": 500.0,
                "status": "settled",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:05+00:00",
                "auth_latency_ms": 900.0,
                "settle_latency_ms": 1200.0,
                "batch_id": None,
                "decline_reason": None,
                "return_code": None,
            }
        )
        resp = client.get("/api/transactions/seed-lifecycle")
        assert resp.status_code == 200
        assert resp.json()["status"] == "settled"


def test_transaction_by_id_404_when_missing():
    with TestClient(app) as client:
        resp = client.get("/api/transactions/does-not-exist")
        assert resp.status_code == 404
