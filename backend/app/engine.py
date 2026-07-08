import asyncio
import random
import uuid
from datetime import datetime, timezone

from app import config, metrics
from app.models import CHANNEL_RAIL, Channel, Incident, Transaction
from app.state import AppState

METRICS_TICK_SECONDS = 2.0


def _pick_channel() -> Channel:
    channels = list(config.CHANNEL_WEIGHTS.keys())
    weights = list(config.CHANNEL_WEIGHTS.values())
    return random.choices(channels, weights=weights, k=1)[0]


def _sample_latency_ms(channel: Channel) -> float:
    mean, stddev = config.BASE_AUTH_LATENCY_MS[channel]
    return max(5.0, random.gauss(mean, stddev))


def _sample_settle_delay_ms(channel: Channel) -> float:
    mean, stddev = config.SETTLE_DELAY_MS[channel]
    return max(5.0, random.gauss(mean, stddev))


def _sample_amount(channel: Channel) -> float:
    lo, hi = config.AMOUNT_RANGE[channel]
    return random.uniform(lo, hi)


class SimulationEngine:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._batch_queue: dict[Channel, list[Transaction]] = {"ach_batch_file": []}
        self._tasks: list[asyncio.Task] = []

    def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._generate_loop()),
            asyncio.create_task(self._batch_loop()),
            asyncio.create_task(self._incident_loop()),
            asyncio.create_task(self._metrics_tick_loop()),
        ]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()

    def _failure_multiplier(self, channel: Channel) -> float:
        incident = self.state.active_incidents.get(channel)
        if incident and incident.kind == "failure_spike":
            return incident.magnitude
        return 1.0

    def _latency_multiplier(self, channel: Channel) -> float:
        incident = self.state.active_incidents.get(channel)
        if incident and incident.kind == "latency_spike":
            return incident.magnitude
        return 1.0

    async def _generate_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0 / config.GENERATION_RATE_PER_SEC)
            channel = _pick_channel()
            txn = Transaction.new(channel, _sample_amount(channel))
            if channel == "ach_batch_file":
                self._batch_queue.setdefault(channel, []).append(txn)
                await self.state.add_transaction(txn)
            else:
                asyncio.create_task(self._process_realtime(txn))

    async def _process_realtime(self, txn: Transaction) -> None:
        channel = txn.channel
        latency = _sample_latency_ms(channel) * self._latency_multiplier(channel)
        await asyncio.sleep(latency / 1000.0)

        base_fail = config.BASE_FAILURE_RATE[channel] * self._failure_multiplier(channel)
        failed = random.random() < min(base_fail, 0.95)

        txn.auth_latency_ms = round(latency, 1)
        txn.updated_at = datetime.now(timezone.utc)
        if failed:
            txn.status = "declined"
            txn.decline_reason = random.choice(config.DECLINE_REASONS)
            await self.state.add_transaction(txn)
            return

        txn.status = "authorized"
        await self.state.add_transaction(txn)

        settle_delay = _sample_settle_delay_ms(channel)
        await asyncio.sleep(settle_delay / 1000.0)
        txn.settle_latency_ms = round(settle_delay, 1)
        txn.status = "settled"
        txn.updated_at = datetime.now(timezone.utc)
        await self.state.add_transaction(txn)

    async def _batch_loop(self) -> None:
        while True:
            await asyncio.sleep(config.BATCH_WINDOW_SECONDS)
            pending = self._batch_queue.get("ach_batch_file", [])
            if not pending:
                continue
            self._batch_queue["ach_batch_file"] = []
            batch_id = f"batch-{uuid.uuid4().hex[:8]}"

            file_rejected = random.random() < config.BATCH_FILE_REJECT_PROB
            fail_mult = self._failure_multiplier("ach_batch_file")

            for txn in pending:
                txn.batch_id = batch_id
                txn.updated_at = datetime.now(timezone.utc)
                if file_rejected:
                    txn.status = "failed"
                    txn.return_code = "FILE_REJECTED"
                else:
                    base_fail = config.BASE_FAILURE_RATE["ach_batch_file"] * fail_mult
                    if random.random() < min(base_fail, 0.95):
                        txn.status = "returned"
                        txn.return_code = random.choice(config.RETURN_CODES)
                    else:
                        txn.status = "posted"
                await self.state.add_transaction(txn)

    async def _incident_loop(self) -> None:
        all_channels = list(config.CHANNEL_WEIGHTS.keys())
        while True:
            await asyncio.sleep(config.INCIDENT_CHECK_INTERVAL_SECONDS)
            for channel in all_channels:
                if channel in self.state.active_incidents:
                    continue
                if random.random() > config.INCIDENT_PROBABILITY / len(all_channels):
                    continue
                kind = random.choice(["latency_spike", "failure_spike"])
                if kind == "latency_spike" and channel == "ach_batch_file":
                    kind = "failure_spike"
                if kind == "latency_spike":
                    magnitude = random.uniform(*config.INCIDENT_LATENCY_MULTIPLIER_RANGE)
                    desc = f"Elevated authorization latency on {channel} (~{magnitude:.1f}x baseline)"
                else:
                    magnitude = random.uniform(*config.INCIDENT_FAILURE_MULTIPLIER_RANGE)
                    desc = f"Elevated decline/return rate on {channel} (~{magnitude:.1f}x baseline)"

                incident = Incident(
                    id=str(uuid.uuid4()),
                    rail=CHANNEL_RAIL[channel],
                    channel=channel,
                    kind=kind,
                    magnitude=magnitude,
                    started_at=datetime.now(timezone.utc),
                    description=desc,
                )
                await self.state.start_incident(incident)
                asyncio.create_task(self._end_incident_later(channel))

    async def _metrics_tick_loop(self) -> None:
        while True:
            await asyncio.sleep(METRICS_TICK_SECONDS)
            summary = metrics.compute_summary(self.state)
            await self.state.publish({"type": "metrics_tick", "data": summary})

    async def _end_incident_later(self, channel: Channel) -> None:
        duration = random.uniform(*config.INCIDENT_DURATION_RANGE_SECONDS)
        await asyncio.sleep(duration)
        await self.state.end_incident(channel)
