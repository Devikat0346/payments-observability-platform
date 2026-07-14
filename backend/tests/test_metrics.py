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
    rail="CARD",
    technical_failure_reason=None,
):
    ts = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return {
        "id": "fake-id",
        "rail": rail,
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
        "technical_failure_reason": technical_failure_reason,
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

    def test_technical_failures_are_a_subset_of_business_failures(self):
        # A business decline, a rejected batch file, and a genuine technical
        # failure are all "not a success" (count against success_rate), but
        # availability only cares about the genuinely technical one — keyed on
        # technical_failure_reason, not the "failed" status alone, since a
        # rejected file also uses status "failed" but is a business/
        # operational exception, not an availability miss.
        events = [
            _event(status="settled"),
            _event(status="declined"),  # business — availability shouldn't count this
            _event(status="failed"),  # a rejected batch file — business, not technical
            _event(status="failed", technical_failure_reason="gateway_timeout"),  # genuinely technical
        ]
        stats = _channel_stats(events)
        assert stats["failure"] == 3  # declined + both "failed" events count against success_rate
        assert stats["technical_failures"] == 1  # only the one WITH a technical_failure_reason
        assert stats["availability"] == 3 / 4

    def test_availability_is_none_with_no_terminal_events(self):
        stats = _channel_stats([_event(status="initiated")])
        assert stats["availability"] is None


class TestComputeSummary:
    def test_shape_is_well_formed_even_with_no_data(self):
        state = AppState()
        summary = compute_summary(state)
        assert "channels" in summary
        assert "rails" in summary
        assert "txn_types" in summary
        assert set(summary["rails"].keys()) == {"CARD", "WIRE", "ACH_BATCH", "ZELLE"}
        assert set(summary["txn_types"].keys()) == {
            "card_credit",
            "card_debit",
            "ach_credit",
            "ach_debit",
            "wire",
            "zelle",
        }
        for ch, metric in summary["channels"].items():
            assert metric["health"] in ("healthy", "degraded", "breached")
            assert metric["total"] == 0
            assert metric["success_rate"] is None
            assert metric["availability_slo_target"] == 0.99999

    def test_availability_burn_reflects_only_technical_failures_not_business_declines(self):
        state = AppState()
        # A pile of business declines shouldn't move the availability needle —
        # only genuine technical failures should.
        for _ in range(20):
            state.transactions.append(_event(channel="pos", status="declined", seconds_ago=1))
        summary = compute_summary(state)
        assert summary["channels"]["pos"]["availability_burn_pct"] == 0.0
        # ...but even a single technical failure burns a large chunk of the
        # five-nines budget, since that budget is extremely small by design.
        state.transactions.append(
            _event(channel="pos", status="failed", technical_failure_reason="gateway_timeout", seconds_ago=1)
        )
        summary = compute_summary(state)
        assert summary["channels"]["pos"]["availability_burn_pct"] > 0.0

    def test_rejected_batch_file_does_not_count_against_availability(self):
        # A whole-file rejection uses status "failed" (same as a genuine
        # technical failure) but represents a business/format exception, not
        # an outage — it must not set technical_failure_reason, and therefore
        # must not burn the five-nines availability budget at all.
        state = AppState()
        for _ in range(10):
            state.transactions.append(_event(channel="ach_batch_file", rail="ACH_BATCH", status="failed", seconds_ago=1))
        summary = compute_summary(state)
        assert summary["channels"]["ach_batch_file"]["availability_burn_pct"] == 0.0
        assert summary["channels"]["ach_batch_file"]["availability"] == 1.0

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

    def test_mixed_type_channels_get_a_within_channel_breakdown(self):
        state = AppState()
        state.transactions.append(
            _event(channel="ach_batch_file", rail="ACH_BATCH", txn_type="credit", status="posted", amount=500.0, seconds_ago=1)
        )
        state.transactions.append(
            _event(channel="ach_batch_file", rail="ACH_BATCH", txn_type="debit", status="returned", amount=200.0, seconds_ago=1)
        )
        summary = compute_summary(state)
        breakdown = summary["channels"]["ach_batch_file"]["txn_type_breakdown"]
        assert breakdown is not None
        assert breakdown["credit"]["total"] == 1
        assert breakdown["credit"]["total_amount"] == 500.0
        assert breakdown["debit"]["total"] == 1
        assert breakdown["debit"]["total_amount"] == 200.0

    def test_single_type_channels_have_no_breakdown(self):
        state = AppState()
        summary = compute_summary(state)
        assert summary["channels"]["wire_online"]["txn_type_breakdown"] is None
        assert summary["channels"]["zelle_mobile"]["txn_type_breakdown"] is None

    def test_card_credit_and_ach_credit_are_not_conflated(self):
        # A card credit and an ACH credit are different payment mechanisms that
        # happen to share the word "credit" — they must not be summed together.
        state = AppState()
        state.transactions.append(
            _event(channel="ecommerce", rail="CARD", txn_type="credit", amount=100.0, seconds_ago=1)
        )
        state.transactions.append(
            _event(channel="ach_batch_file", rail="ACH_BATCH", txn_type="credit", amount=9999.0, seconds_ago=1)
        )
        summary = compute_summary(state)
        assert summary["txn_types"]["card_credit"]["total_amount"] == 100.0
        assert summary["txn_types"]["ach_credit"]["total_amount"] == 9999.0
