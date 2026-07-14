# Contributing

This is a personal portfolio project, not under active development for outside contributions — but issues and suggestions are genuinely welcome if something looks wrong or could be better.

## Local setup

See the README's "Running locally" section.

## Before submitting a PR

- Run `pytest tests/ -v` from `backend/` — CI runs the same suite on every push.
- Keep new channels/config additions consistent across `models.py`, `config.py`, and `engine.py` — `tests/test_engine.py::TestChannelWeights::test_every_channel_has_required_config` will catch most omissions.

## Reporting a bug

Open an issue with what you expected vs. what happened. If it's about the live demo specifically, note whether it was the Render free-tier host waking from sleep (30-60s cold start) before assuming it's a real bug.
