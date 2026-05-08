"""
Test setup.

Uses a dedicated `finance_ai_test` PostgreSQL database.
- DB is created/dropped once per session using a synchronous psycopg2 connection
  (avoids event-loop scope issues with asyncpg at session scope).
- Tables are dropped and recreated fresh for every test (function scope).
- No truncation needed: create_all / drop_all guarantees a clean slate.

Run from inside Docker:
    docker compose exec backend pytest

Run locally (set TEST_DATABASE_URL env var to use localhost):
    TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/finance_ai_test \
    TEST_ADMIN_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres \
    pytest
"""
import os

import psycopg2
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa — registers all models on Base.metadata
from app.database import Base, get_db
from app.main import app

TEST_DB_NAME = "finance_ai_test"
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://postgres:postgres@postgres:5432/{TEST_DB_NAME}",
)

# Synchronous DSN for psycopg2 (used only for CREATE/DROP DATABASE)
_SYNC_ADMIN_DSN = os.getenv(
    "TEST_ADMIN_SYNC_DSN",
    "host=postgres port=5432 dbname=postgres user=postgres password=postgres",
)


# ── session-scoped: create the test DB once (sync, no event loop) ─────────────

@pytest.fixture(scope="session")
def _ensure_test_db():
    conn = psycopg2.connect(_SYNC_ADMIN_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = %s AND pid <> pg_backend_pid()",
        (TEST_DB_NAME,),
    )
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    cur.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    cur.close()
    conn.close()

    yield

    conn = psycopg2.connect(_SYNC_ADMIN_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = %s AND pid <> pg_backend_pid()",
        (TEST_DB_NAME,),
    )
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
    cur.close()
    conn.close()


# ── function-scoped async engine: fresh per test, same loop as db/client ──────

@pytest_asyncio.fixture
async def test_engine(_ensure_test_db):
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine) -> AsyncSession:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
