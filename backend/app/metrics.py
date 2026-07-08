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
    return {
        "total": total,
        "success": success,
        "failure": failure,
        "success_rate": (success / total) if total else None,
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "p99_latency_ms": _percentile(latencies, 0.99),
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

        incident = state.active_incidents.get(ch)
        health = "healthy"
        if incident:
            health = "degraded"
        if stats["success_rate"] is not None and stats["success_rate"] < slo["success_rate"] * 0.9:
            health = "breached"

        channel_metrics[ch] = {
            "channel": ch,
            "rail": rail,
            "health": health,
            "window_seconds": config.METRICS_WINDOW_SECONDS,
            **stats,
            "slo_success_rate": slo["success_rate"],
            "slo_latency_p99_ms": slo["latency_p99_ms"],
            "error_budget_burn_pct": round(burn_pct, 1),
            "active_incident": incident.to_dict() if incident else None,
        }

    rail_rollup = {}
    for rail in ("CARD", "WIRE", "ACH_BATCH"):
        rail_channels = [c for c in channels if CHANNEL_RAIL[c] == rail]
        rail_events = [e for e in window_events if e["channel"] in rail_channels]
        stats = _channel_stats(rail_events)
        rail_rollup[rail] = {
            "rail": rail,
            **stats,
            "slo_success_rate": config.SLO_TARGETS[rail]["success_rate"],
        }

    return {
        "generated_at": now.isoformat(),
        "channels": channel_metrics,
        "rails": rail_rollup,
    }
