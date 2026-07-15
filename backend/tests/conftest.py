import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db_models import Base
from app.state import AppState


@pytest_asyncio.fixture
async def test_state():
    """A fresh AppState with its TransactionStore backed by a real in-memory
    SQLite database (not mocked) — queries.py issues real SELECT/WHERE/ORDER
    BY/LIMIT/OFFSET, so this exercises the actual SQL rather than just
    recording calls against a fake session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    state = AppState()
    state.db.enabled = True
    state.db._engine = engine
    state.db._sessionmaker = sessionmaker

    yield state

    await engine.dispose()
