from app.models import Channel, Rail

# Relative weights for which channel originates a new transaction.
CHANNEL_WEIGHTS: dict[Channel, float] = {
    "pos": 0.32,
    "ecommerce": 0.24,
    "mobile_wallet": 0.12,
    "wire_online": 0.08,
    "wire_branch": 0.04,
    "ach_batch_file": 0.20,
}

# Base authorization latency (ms) as (mean, stddev) for real-time rails.
BASE_AUTH_LATENCY_MS: dict[Channel, tuple[float, float]] = {
    "pos": (180, 60),
    "ecommerce": (320, 120),
    "mobile_wallet": (220, 80),
    "wire_online": (900, 300),
    "wire_branch": (1400, 400),
}

# Base decline/return probability per channel under normal conditions.
BASE_FAILURE_RATE: dict[Channel, float] = {
    "pos": 0.010,
    "ecommerce": 0.035,
    "mobile_wallet": 0.015,
    "wire_online": 0.006,
    "wire_branch": 0.004,
    "ach_batch_file": 0.020,
}

DECLINE_REASONS = ["insufficient_funds", "fraud_suspected", "invalid_account", "limit_exceeded"]
RETURN_CODES = ["R01_insufficient_funds", "R02_account_closed", "R03_no_account", "R29_unauthorized"]

# Amount ranges (min, max) per channel, in USD.
AMOUNT_RANGE: dict[Channel, tuple[float, float]] = {
    "pos": (5, 250),
    "ecommerce": (10, 600),
    "mobile_wallet": (3, 150),
    "wire_online": (200, 25000),
    "wire_branch": (500, 100000),
    "ach_batch_file": (20, 5000),
}

# How many new transactions to generate per second, on average.
GENERATION_RATE_PER_SEC = 6.0

# Batch rail: how often a batch window "runs" (seconds). Compressed vs. real nightly cycles for demo purposes.
BATCH_WINDOW_SECONDS = 25.0
BATCH_FILE_REJECT_PROB = 0.03  # whole-file rejection probability per batch run

# Settlement delay after authorization, real-time rails (ms).
SETTLE_DELAY_MS: dict[Channel, tuple[float, float]] = {
    "pos": (400, 100),
    "ecommerce": (600, 150),
    "mobile_wallet": (350, 100),
    "wire_online": (2000, 500),
    "wire_branch": (3000, 700),
}

# SLO targets per rail, used for error-budget burn calculations.
SLO_TARGETS: dict[Rail, dict] = {
    "CARD": {"success_rate": 0.99, "latency_p99_ms": 1500},
    "WIRE": {"success_rate": 0.985, "latency_p99_ms": 5000},
    "ACH_BATCH": {"success_rate": 0.97, "latency_p99_ms": None},
}

METRICS_WINDOW_SECONDS = 300  # 5-minute rolling window for SLIs
ERROR_BUDGET_WINDOW_SECONDS = 1800  # 30-minute rolling window for error-budget burn (compressed "month")

# Incident injection tuning.
INCIDENT_CHECK_INTERVAL_SECONDS = 20
INCIDENT_PROBABILITY = 0.35
INCIDENT_DURATION_RANGE_SECONDS = (20, 60)
INCIDENT_LATENCY_MULTIPLIER_RANGE = (3.0, 7.0)
INCIDENT_FAILURE_MULTIPLIER_RANGE = (5.0, 12.0)
