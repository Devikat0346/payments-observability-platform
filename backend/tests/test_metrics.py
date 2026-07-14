from datetime import datetime, timedelta, timezone

from app.metrics import _channel_stats, _percentile, compute_summary
from app.state import AppState


def _event(
    channel="pos",
    status="settled",
    auth_latency_ms=200.0,
    txn_type="debit",
    amount=50.0,
    seconds_ago=0,
):
    ts = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return {
        "id": "fake-id",
        "rail": "CARD",
        "channel": channel,
        "txn_type": txn_type,
        "amount": amount,
        "status": status,
        "created_at": ts.isoformat(),
        "updated_at": ts.isoformat(),
        "auth_latency_ms": auth_latency_ms,
        "settle_latency_ms": None,
        "batch_id": None,
        "decline_reason": None,
        "return_code": None,
    }


class TestPercentile:
    def test_empty_list_returns_none(self):
        assert _percentile([], 0.5) is None

    def test_single_value(self):
        assert _percentile([42.0], 0.5) == 42.0
        assert _percentile([42.0], 0.99) == 42.0

    def test_known_distribution(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        assert _percentile(values, 0.5) == 30.0
        assert _percentile(values, 0.0) == 10.0
        assert _percentile(values, 1.0) == 50.0


class TestChannelStats:
    def test_empty_events(self):
        stats = _channel_stats([])
        assert stats["total"] == 0
        assert stats["success_rate"] is None
        assert stats["p50_latency_ms"] is None

    def test_success_and_failure_counted_correctly(self):
        events = [
            _event(status="settled"),
            _event(status="posted"),
            _event(status="declined"),
            _event(status="initiated"),  # non-terminal, must be excluded
        ]
        stats = _channel_stats(events)
        assert stats["total"] == 3  # initiated excluded
        assert stats["success"] == 2
        assert stats["failure"] == 1
        assert stats["success_rate"] == 2 / 3

    def test_dollar_amounts_aggregate_correctly(self):
        events = [
            _event(status="settled", amount=100.0),
            _event(status="declined", amount=250.0),
            _event(status="posted", amount=50.0),
        ]
        stats = _channel_stats(events)
        assert stats["total_amount"] == 400.0
        assert stats["failure_amount"] == 250.0

    def test_latency_percentiles_ignore_null_latency(self):
        events = [
            _event(status="settled", auth_latency_ms=100.0),
            _event(status="settled", auth_latency_ms=200.0),
            _event(status="posted", auth_latency_ms=None),  # batch-style, no latency
        ]
        stats = _channel_stats(events)
        assert stats["p50_latency_ms"] in (100.0, 200.0, 150.0)
        assert stats["total"] == 3


class TestComputeSummary:
    def test_shape_is_well_formed_even_with_no_data(self):
        state = AppState()
        summary = compute_summary(state)
        assert "channels" in summary
        assert "rails" in summary
        assert "txn_types" in summary
        assert set(summary["rails"].keys()) == {"CARD", "WIRE", "ACH_BATCH", "ZELLE"}
        assert set(summary["txn_types"].keys()) == {"credit", "debit", "wire", "zelle"}
        for ch, metric in summary["channels"].items():
            assert metric["health"] in ("healthy", "degraded", "breached")
            assert metric["total"] == 0
            assert metric["success_rate"] is None

    def test_events_outside_window_are_excluded(self):
        state = AppState()
        state.transactions.append(_event(seconds_ago=10_000))  # ancient, outside every window
        summary = compute_summary(state)
        assert summary["channels"]["pos"]["total"] == 0

    def test_events_inside_window_are_counted(self):
        state = AppState()
        state.transactions.append(_event(channel="pos", status="settled", seconds_ago=5))
        state.transactions.append(_event(channel="pos", status="declined", seconds_ago=5))
        summary = compute_summary(state)
        assert summary["channels"]["pos"]["total"] == 2
        assert summary["channels"]["pos"]["success"] == 1

    def test_health_is_breached_when_success_rate_far_below_slo(self):
        state = AppState()
        for _ in range(20):
            state.transactions.append(_event(channel="pos", status="declined", seconds_ago=1))
        summary = compute_summary(state)
        assert summary["channels"]["pos"]["health"] == "breached"
