from datetime import datetime, timedelta, timezone

from app import config
from app.models import CHANNEL_RAIL
from app.state import AppState

TERMINAL_SUCCESS = {"settled", "posted"}
TERMINAL_FAILURE = {"declined", "failed", "returned"}
TERMINAL = TERMINAL_SUCCESS | TERMINAL_FAILURE


def _percentile(sorted_values: list[float], pct: float) -> float | None:
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _channel_stats(events: list[dict]) -> dict:
    success = sum(1 for e in events if e["status"] in TERMINAL_SUCCESS)
    failure = sum(1 for e in events if e["status"] in TERMINAL_FAILURE)
    total = success + failure
    latencies = sorted(e["auth_latency_ms"] for e in events if e.get("auth_latency_ms") is not None)
    total_amount = sum(e["amount"] for e in events)
    failure_amount = sum(e["amount"] for e in events if e["status"] in TERMINAL_FAILURE)
    # A technical failure ("failed") means the platform never returned a
    # decision at all — distinct from "declined"/"returned", where the
    # platform worked correctly and said no for a business reason. Only
    # technical failures count against availability.
    technical_failures = sum(1 for e in events if e["status"] == "failed")
    availability = ((total - technical_failures) / total) if total else None
    return {
        "total": total,
        "success": success,
        "failure": failure,
        "success_rate": (success / total) if total else None,
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "p99_latency_ms": _percentile(latencies, 0.99),
        "total_amount": round(total_amount, 2),
        "failure_amount": round(failure_amount, 2),
        "technical_failures": technical_failures,
        "availability": availability,
    }


def compute_summary(state: AppState) -> dict:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=config.METRICS_WINDOW_SECONDS)
    budget_start = now - timedelta(seconds=config.ERROR_BUDGET_WINDOW_SECONDS)

    window_events: list[dict] = []
    budget_events: list[dict] = []
    for e in state.transactions:
        if e["status"] not in TERMINAL:
            continue
        ts = datetime.fromisoformat(e["updated_at"])
        if ts >= window_start:
            window_events.append(e)
        if ts >= budget_start:
            budget_events.append(e)

    channels = list(config.CHANNEL_WEIGHTS.keys())
    channel_metrics = {}
    for ch in channels:
        ch_window = [e for e in window_events if e["channel"] == ch]
        ch_budget = [e for e in budget_events if e["channel"] == ch]
        stats = _channel_stats(ch_window)
        budget_stats = _channel_stats(ch_budget)

        rail = CHANNEL_RAIL[ch]
        slo = config.SLO_TARGETS[rail]
        allowed_failure_rate = 1 - slo["success_rate"]
        actual_failure_rate = (1 - budget_stats["success_rate"]) if budget_stats["success_rate"] is not None else 0.0
        burn_pct = (actual_failure_rate / allowed_failure_rate) * 100 if allowed_failure_rate > 0 else 0.0

        # Availability burn — same error-budget methodology, but measured
        # against the five-nines availability target rather than the business
        # approval-rate SLO. A genuinely different axis: a channel can be
        # fully within its approval-rate SLA while still burning availability
        # budget if the platform itself is timing out/erroring.
        allowed_unavailability = 1 - config.AVAILABILITY_SLO_TARGET
        actual_unavailability = (
            (1 - budget_stats["availability"]) if budget_stats["availability"] is not None else 0.0
        )
        availability_burn_pct = (
            (actual_unavailability / allowed_unavailability) * 100 if allowed_unavailability > 0 else 0.0
        )

        incident = state.active_incidents.get(ch)
        health = "healthy"
        if incident:
            health = "degraded"
        if stats["success_rate"] is not None and stats["success_rate"] < slo["success_rate"] * 0.9:
            health = "breached"
        if stats["availability"] is not None and stats["availability"] < config.AVAILABILITY_SLO_TARGET * 0.9:
            health = "breached"

        # Channels whose transactions can be either credit or debit (card and ACH
        # channels) get their own within-channel split, so a single channel card
        # can show "this channel's volume is X% credit / Y% debit" rather than
        # only being visible in the platform-wide type-mix rollup below.
        txn_type_breakdown = None
        if ch in config.TXN_TYPE_MIX:
            txn_type_breakdown = {}
            for txn_type in config.TXN_TYPE_MIX[ch]:
                tt_events = [e for e in ch_window if e["txn_type"] == txn_type]
                tt_stats = _channel_stats(tt_events)
                txn_type_breakdown[txn_type] = {
                    "total": tt_stats["total"],
                    "total_amount": tt_stats["total_amount"],
                }

        channel_metrics[ch] = {
            "channel": ch,
            "rail": rail,
            "health": health,
            "window_seconds": config.METRICS_WINDOW_SECONDS,
            **stats,
            "slo_success_rate": slo["success_rate"],
            "slo_latency_p99_ms": slo["latency_p99_ms"],
            "error_budget_burn_pct": round(burn_pct, 1),
            "availability_slo_target": config.AVAILABILITY_SLO_TARGET,
            "availability_burn_pct": round(availability_burn_pct, 1),
            "active_incident": incident.to_dict() if incident else None,
            "txn_type_breakdown": txn_type_breakdown,
        }

    rail_rollup = {}
    for rail in ("CARD", "WIRE", "ACH_BATCH", "ZELLE"):
        rail_channels = [c for c in channels if CHANNEL_RAIL[c] == rail]
        rail_events = [e for e in window_events if e["channel"] in rail_channels]
        stats = _channel_stats(rail_events)
        rail_rollup[rail] = {
            "rail": rail,
            **stats,
            "slo_success_rate": config.SLO_TARGETS[rail]["success_rate"],
            "availability_slo_target": config.AVAILABILITY_SLO_TARGET,
        }

    # "Credit" and "debit" mean genuinely different things on the card network vs.
    # the ACH network (an ACH credit is a deposit, e.g. payroll; an ACH debit is a
    # pull, e.g. bill pay) — they aren't the same category of money movement just
    # because they share a word. Keying by (rail, txn_type) instead of txn_type
    # alone keeps a card credit and an ACH credit from being silently summed
    # together into one misleading "Credit" bucket.
    TXN_TYPE_BREAKDOWN = [
        ("card_credit", "CARD", "credit"),
        ("card_debit", "CARD", "debit"),
        ("ach_credit", "ACH_BATCH", "credit"),
        ("ach_debit", "ACH_BATCH", "debit"),
        ("wire", "WIRE", "wire"),
        ("zelle", "ZELLE", "zelle"),
    ]
    txn_type_rollup = {}
    for key, rail, txn_type in TXN_TYPE_BREAKDOWN:
        type_events = [
            e for e in window_events if e["rail"] == rail and e["txn_type"] == txn_type
        ]
        stats = _channel_stats(type_events)
        txn_type_rollup[key] = {"txn_type": key, "rail": rail, **stats}

    return {
        "generated_at": now.isoformat(),
        "channels": channel_metrics,
        "rails": rail_rollup,
        "txn_types": txn_type_rollup,
    }
