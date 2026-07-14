from app.models import Channel, Rail, TxnType

# Relative weights for which channel originates a new transaction.
CHANNEL_WEIGHTS: dict[Channel, float] = {
    "pos": 0.22,
    "ecommerce": 0.16,
    "mobile_wallet": 0.08,
    "wire_online": 0.05,
    "wire_branch": 0.02,
    "wire_loaniq": 0.015,
    "wire_batch": 0.025,
    "wire_ivr": 0.01,
    "ach_batch_file": 0.14,
    "zelle_mobile": 0.18,
    "zelle_online": 0.10,
}

# Batch-processed channels: transactions accumulate and are processed together in
# a window, rather than authorized/settled individually in real time.
BATCH_CHANNELS: set[Channel] = {"ach_batch_file", "wire_batch"}

# Base authorization latency (ms) as (mean, stddev) for real-time (non-batch) channels.
BASE_AUTH_LATENCY_MS: dict[Channel, tuple[float, float]] = {
    "pos": (180, 60),
    "ecommerce": (320, 120),
    "mobile_wallet": (220, 80),
    "wire_online": (900, 300),
    "wire_branch": (1400, 400),
    "wire_loaniq": (2200, 500),
    "wire_ivr": (1800, 600),
    "zelle_mobile": (250, 70),
    "zelle_online": (300, 80),
}

# Base decline/return probability per channel under normal conditions.
BASE_FAILURE_RATE: dict[Channel, float] = {
    "pos": 0.010,
    "ecommerce": 0.035,
    "mobile_wallet": 0.015,
    "wire_online": 0.006,
    "wire_branch": 0.004,
    "wire_loaniq": 0.008,
    "wire_batch": 0.015,
    "wire_ivr": 0.012,
    "ach_batch_file": 0.020,
    "zelle_mobile": 0.020,
    "zelle_online": 0.016,
}

# Probability mix of transaction type within a channel that isn't a single fixed
# type (a card swipe can be run as either credit or debit; an ACH batch entry can
# be a debit pull or a credit deposit). Channels not listed here have exactly one
# possible type (all wire_* channels are "wire", all zelle_* channels are "zelle").
TXN_TYPE_MIX: dict[Channel, dict[TxnType, float]] = {
    "pos": {"debit": 0.65, "credit": 0.35},
    "ecommerce": {"credit": 0.70, "debit": 0.30},
    "mobile_wallet": {"credit": 0.50, "debit": 0.50},
    "ach_batch_file": {"debit": 0.60, "credit": 0.40},
}

# Decline reason pools for real-time (non-batch) channels — distinct per origination
# path, since a POS decline and an IVR-initiated wire decline fail for different reasons.
CARD_DECLINE_REASONS = ["insufficient_funds", "fraud_suspected", "invalid_account", "limit_exceeded"]
WIRE_DECLINE_REASONS = ["invalid_beneficiary_bank", "ofac_hold", "insufficient_funds", "invalid_account"]
LOANIQ_DECLINE_REASONS = [
    "collateral_verification_failed",
    "compliance_hold",
    "invalid_loan_reference",
    "funding_conditions_not_met",
]
IVR_DECLINE_REASONS = ["voice_auth_failed", "otp_mismatch", "customer_hung_up", "invalid_account"]
ZELLE_DECLINE_REASONS = ["recipient_not_enrolled", "daily_limit_exceeded", "fraud_hold", "duplicate_request"]

CHANNEL_DECLINE_REASONS: dict[Channel, list[str]] = {
    "pos": CARD_DECLINE_REASONS,
    "ecommerce": CARD_DECLINE_REASONS,
    "mobile_wallet": CARD_DECLINE_REASONS,
    "wire_online": WIRE_DECLINE_REASONS,
    "wire_branch": WIRE_DECLINE_REASONS,
    "wire_loaniq": LOANIQ_DECLINE_REASONS,
    "wire_ivr": IVR_DECLINE_REASONS,
    "zelle_mobile": ZELLE_DECLINE_REASONS,
    "zelle_online": ZELLE_DECLINE_REASONS,
}

# Return-code pools for batch channels (whole batch runs, not individual auth calls).
ACH_RETURN_CODES = ["R01_insufficient_funds", "R02_account_closed", "R03_no_account", "R29_unauthorized"]
WIRE_BATCH_RETURN_CODES = [
    "invalid_beneficiary_bank",
    "duplicate_wire_reference",
    "insufficient_funds_at_settlement",
    "ofac_hold",
]

CHANNEL_RETURN_CODES: dict[Channel, list[str]] = {
    "ach_batch_file": ACH_RETURN_CODES,
    "wire_batch": WIRE_BATCH_RETURN_CODES,
}

# Amount ranges (min, max) per channel, in USD.
AMOUNT_RANGE: dict[Channel, tuple[float, float]] = {
    "pos": (5, 250),
    "ecommerce": (10, 600),
    "mobile_wallet": (3, 150),
    "wire_online": (200, 25000),
    "wire_branch": (500, 100000),
    "wire_loaniq": (50000, 5000000),
    "wire_batch": (1000, 250000),
    "wire_ivr": (500, 50000),
    "ach_batch_file": (20, 5000),
    "zelle_mobile": (10, 2500),
    "zelle_online": (10, 2500),
}

# How many new transactions to generate per second, on average.
GENERATION_RATE_PER_SEC = 8.0

# Batch rail: how often a batch window "runs" (seconds). Compressed vs. real nightly cycles for demo purposes.
BATCH_WINDOW_SECONDS = 25.0
BATCH_FILE_REJECT_PROB = 0.03  # whole-file rejection probability per batch run

# Settlement delay after authorization, real-time channels (ms).
SETTLE_DELAY_MS: dict[Channel, tuple[float, float]] = {
    "pos": (400, 100),
    "ecommerce": (600, 150),
    "mobile_wallet": (350, 100),
    "wire_online": (2000, 500),
    "wire_branch": (3000, 700),
    "wire_loaniq": (3500, 800),
    "wire_ivr": (2800, 700),
    "zelle_mobile": (150, 50),
    "zelle_online": (180, 50),
}

# SLO targets per rail, used for error-budget burn calculations. This is the
# business APPROVAL RATE target (of transactions the platform actually
# processed, how many were approved) — legitimate declines (fraud, NSF,
# compliance holds) count against it, since those are expected, designed-for
# outcomes, not reliability problems.
SLO_TARGETS: dict[Rail, dict] = {
    "CARD": {"success_rate": 0.99, "latency_p99_ms": 1500},
    "WIRE": {"success_rate": 0.985, "latency_p99_ms": 5000},
    "ACH_BATCH": {"success_rate": 0.97, "latency_p99_ms": None},
    "ZELLE": {"success_rate": 0.995, "latency_p99_ms": 2000},
}

# Platform AVAILABILITY target — "five nines" — a genuinely different thing
# from the approval-rate SLOs above. This measures whether the platform
# returned a decision at all (approved or declined), vs. a true system/
# technical failure (timeout, internal error). A card declined for
# insufficient funds is the system working correctly; a card transaction that
# never got a response because the gateway timed out is an availability miss.
# Uniform across every rail, since infrastructure availability is typically a
# platform-wide commitment, not a per-rail one.
AVAILABILITY_SLO_TARGET = 0.99999

# Baseline probability a real-time transaction hits a genuine system/technical
# failure rather than reaching a normal business decision. Deliberately much
# rarer than BASE_FAILURE_RATE — availability failures should be rare, since
# five nines only allows about 5 minutes of "no decision reached" per year.
# Batch channels don't need an entry here: their technical-failure signal is
# already BATCH_FILE_REJECT_PROB (a whole-file rejection), which is a system
# failure, not a business one.
SYSTEM_FAILURE_RATE: dict[Channel, float] = {
    "pos": 0.00003,
    "ecommerce": 0.00005,
    "mobile_wallet": 0.00003,
    "wire_online": 0.00002,
    "wire_branch": 0.00002,
    "wire_loaniq": 0.00002,
    "wire_ivr": 0.00004,
    "zelle_mobile": 0.00003,
    "zelle_online": 0.00003,
}
SYSTEM_FAILURE_REASONS = ["gateway_timeout", "internal_error", "downstream_unavailable"]

METRICS_WINDOW_SECONDS = 300  # 5-minute rolling window for SLIs
ERROR_BUDGET_WINDOW_SECONDS = 1800  # 30-minute rolling window for error-budget burn (compressed "month")

# Incident injection tuning.
INCIDENT_CHECK_INTERVAL_SECONDS = 20
INCIDENT_PROBABILITY = 0.35
INCIDENT_DURATION_RANGE_SECONDS = (20, 60)
INCIDENT_LATENCY_MULTIPLIER_RANGE = (3.0, 7.0)
INCIDENT_FAILURE_MULTIPLIER_RANGE = (5.0, 12.0)
