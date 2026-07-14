from collections import Counter

from app import config
from app.engine import _pick_channel, _sample_txn_type
from app.models import CHANNEL_RAIL


class TestChannelWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(config.CHANNEL_WEIGHTS.values()) - 1.0) < 1e-9

    def test_every_channel_has_required_config(self):
        for channel in config.CHANNEL_WEIGHTS:
            assert channel in config.AMOUNT_RANGE
            assert channel in config.BASE_FAILURE_RATE
            if channel in config.BATCH_CHANNELS:
                assert channel in config.CHANNEL_RETURN_CODES
            else:
                assert channel in config.BASE_AUTH_LATENCY_MS
                assert channel in config.SETTLE_DELAY_MS
                assert channel in config.CHANNEL_DECLINE_REASONS
                # Real-time channels need a system-failure rate to simulate
                # genuine availability misses; batch channels get theirs from
                # BATCH_FILE_REJECT_PROB instead, so they're deliberately
                # excluded from this config dict.
                assert channel in config.SYSTEM_FAILURE_RATE

    def test_system_failure_rate_is_far_rarer_than_business_failure_rate(self):
        # Five nines only allows ~5 minutes/year of no-decision-reached — if
        # this were ever close to the business decline rate, the "genuinely
        # different thing" distinction the availability metric relies on
        # would collapse.
        for channel, rate in config.SYSTEM_FAILURE_RATE.items():
            assert rate < config.BASE_FAILURE_RATE[channel] / 50

    def test_pick_channel_only_returns_known_channels(self):
        for _ in range(200):
            channel = _pick_channel()
            assert channel in config.CHANNEL_WEIGHTS


class TestTxnTypeSampling:
    def test_wire_channels_are_always_wire(self):
        for _ in range(50):
            assert _sample_txn_type("wire_online") == "wire"
            assert _sample_txn_type("wire_loaniq") == "wire"

    def test_zelle_channels_are_always_zelle(self):
        for _ in range(50):
            assert _sample_txn_type("zelle_mobile") == "zelle"

    def test_card_channel_mix_is_probabilistic_not_fixed(self):
        # A large sample of a mixed channel should produce both types —
        # this guards against regressing to the old hardcoded 1:1 mapping.
        results = Counter(_sample_txn_type("pos") for _ in range(500))
        assert results["debit"] > 0
        assert results["credit"] > 0

    def test_txn_type_mix_matches_configured_ratio_roughly(self):
        mix = config.TXN_TYPE_MIX["ecommerce"]
        results = Counter(_sample_txn_type("ecommerce") for _ in range(2000))
        observed_credit_ratio = results["credit"] / sum(results.values())
        assert abs(observed_credit_ratio - mix["credit"]) < 0.08


class TestRailMapping:
    def test_every_channel_maps_to_a_valid_rail(self):
        valid_rails = {"CARD", "WIRE", "ACH_BATCH", "ZELLE"}
        for channel, rail in CHANNEL_RAIL.items():
            assert rail in valid_rails

    def test_batch_channels_are_ach_or_wire_batch_only(self):
        assert config.BATCH_CHANNELS == {"ach_batch_file", "wire_batch"}
