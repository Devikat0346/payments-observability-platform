from datetime import datetime, timedelta, timezone

import pytest

from app import queries
from app.db_models import TransactionRecord

NOW = datetime.now(timezone.utc)


def _row(id_, channel="pos", rail="CARD", amount=50.0, status="settled", updated_ago=0) -> TransactionRecord:
    return TransactionRecord(
        id=id_,
        rail=rail,
        channel=channel,
        txn_type="debit",
        amount=amount,
        status=status,
        created_at=NOW - timedelta(seconds=updated_ago + 5),
        updated_at=NOW - timedelta(seconds=updated_ago),
    )


@pytest.mark.asyncio
class TestGetChannelHistory:
    async def test_returns_most_recent_first_for_the_given_channel(self, test_state):
        async with test_state.db.session() as session:
            session.add_all(
                [
                    _row("a", channel="pos", updated_ago=60),
                    _row("b", channel="pos", updated_ago=0),
                    _row("c", channel="ecommerce", updated_ago=0),
                ]
            )
            await session.commit()

        result = await queries.get_channel_history(test_state, "pos", limit=10)

        assert [r["id"] for r in result] == ["b", "a"]

    async def test_respects_limit_and_offset(self, test_state):
        async with test_state.db.session() as session:
            session.add_all([_row(f"t{i}", channel="pos", updated_ago=i) for i in range(5)])
            await session.commit()

        page = await queries.get_channel_history(test_state, "pos", limit=2, offset=1)

        assert [r["id"] for r in page] == ["t1", "t2"]

    async def test_returns_empty_list_when_db_not_enabled(self, test_state):
        test_state.db.enabled = False

        result = await queries.get_channel_history(test_state, "pos")

        assert result == []


@pytest.mark.asyncio
class TestGetTransactionFromDb:
    async def test_returns_none_for_unknown_id(self, test_state):
        assert await queries.get_transaction_from_db(test_state, "nonexistent") is None

    async def test_returns_the_matching_transaction(self, test_state):
        async with test_state.db.session() as session:
            session.add(_row("known-id", amount=123.45))
            await session.commit()

        result = await queries.get_transaction_from_db(test_state, "known-id")

        assert result["id"] == "known-id"
        assert result["amount"] == 123.45

    async def test_returns_none_when_db_not_enabled(self, test_state):
        test_state.db.enabled = False

        assert await queries.get_transaction_from_db(test_state, "any-id") is None
