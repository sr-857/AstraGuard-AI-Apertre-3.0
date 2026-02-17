
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from network.batcher import RequestBatcher

@pytest.fixture
def mock_client():
    client = AsyncMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    client.post.return_value = response
    return client

@pytest.fixture
def batcher(mock_client):
    with patch("network.batcher.get_network_client", return_value=mock_client):
        # Create batcher with a large batch size so flush is manual
        batcher = RequestBatcher(endpoint="http://test/api", batch_size=1000, max_wait_ms=10000)
        yield batcher

@pytest.mark.benchmark(group="swarm_add")
def test_swarm_add_performance(benchmark, batcher):
    """Benchmark adding items to the batcher (memory operation)."""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    item = {"telemetry": "test", "value": 123}

    async def workload():
        await batcher.add(item)

    def run_benchmark():
        loop.run_until_complete(workload())

    try:
        benchmark(run_benchmark)
    finally:
        loop.close()

@pytest.mark.benchmark(group="swarm_flush")
def test_swarm_flush_performance(benchmark, batcher):
    """Benchmark flushing the batch (serialization + compression + mock network)."""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # We use pedantic to setup (fill) before each run
    def setup():
        batcher.batch = []
        for i in range(100):
            batcher.batch.append({"telemetry": f"data_{i}", "value": i})
        return (batcher,), {}

    def run_flush(batcher):
        loop.run_until_complete(batcher.flush())

    try:
        benchmark.pedantic(run_flush, setup=setup, rounds=50, iterations=1)
    finally:
        loop.close()
