
import pytest
import asyncio
import tempfile
import os
import aiosqlite
from db.database import init_pool, close_pool, get_connection
from db.pool_config import PoolConfig

@pytest.fixture
async def temp_db_path():
    # Create a temp file
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Initialize DB schema (minimal)
    async with aiosqlite.connect(path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, value TEXT)")
        await db.commit()

    yield path

    # Cleanup
    if os.path.exists(path):
        os.unlink(path)

@pytest.fixture
async def db_pool(temp_db_path):
    # Initialize pool
    config = PoolConfig(
        db_path=temp_db_path,
        min_size=1,
        max_size=5,
        connection_timeout=5.0,
        enable_pool=True
    )
    await init_pool(config)
    # Yield the current loop so tests can use it
    yield asyncio.get_running_loop()
    await close_pool()

@pytest.mark.benchmark(group="db_connection")
def test_db_connection_acquisition(benchmark, db_pool):
    """Benchmark acquiring a connection from the pool."""

    loop = db_pool

    async def workload():
        async with get_connection() as conn:
            pass

    def run_benchmark():
        loop.run_until_complete(workload())

    benchmark(run_benchmark)

@pytest.mark.benchmark(group="db_query")
def test_db_simple_query(benchmark, db_pool):
    """Benchmark a simple SELECT query."""

    loop = db_pool

    async def workload():
        async with get_connection() as conn:
            async with conn.execute("SELECT 1") as cursor:
                await cursor.fetchone()

    def run_benchmark():
        loop.run_until_complete(workload())

    benchmark(run_benchmark)

@pytest.mark.benchmark(group="db_insert")
def test_db_insert_query(benchmark, db_pool):
    """Benchmark an INSERT query."""

    loop = db_pool

    async def workload():
        async with get_connection() as conn:
            await conn.execute("INSERT INTO test (value) VALUES (?)", ("benchmark",))
            await conn.commit()

    def run_benchmark():
        loop.run_until_complete(workload())

    benchmark(run_benchmark)
