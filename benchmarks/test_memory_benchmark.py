
import pytest
import asyncio
import shutil
import tempfile
import numpy as np
from datetime import datetime
from memory_engine.memory_store import AdaptiveMemoryStore, MemoryEvent

# Fixture for temporary directory
@pytest.fixture
def temp_memory_dir():
    temp_dir = tempfile.mkdtemp()
    # Patch the base directory in the module
    import memory_engine.memory_store as ms_module
    original_base = ms_module.MEMORY_STORE_BASE_DIR
    ms_module.MEMORY_STORE_BASE_DIR = temp_dir
    yield temp_dir
    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
    ms_module.MEMORY_STORE_BASE_DIR = original_base

@pytest.mark.benchmark(group="memory_write")
def test_memory_write_performance(benchmark, temp_memory_dir):
    """Benchmark the async write operation."""

    # Create a dedicated loop for the benchmark to ensure lock compatibility
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Initialize store within the loop context
    store = AdaptiveMemoryStore(max_capacity=1000)

    embedding = np.random.rand(128).tolist()
    metadata = {"source": "benchmark", "severity": 0.8}

    async def workload():
        await store.write(embedding, metadata)

    def run_benchmark():
        loop.run_until_complete(workload())

    try:
        benchmark(run_benchmark)
    finally:
        loop.close()

@pytest.mark.benchmark(group="memory_retrieve")
def test_memory_retrieve_performance(benchmark, temp_memory_dir):
    """Benchmark the synchronous retrieve operation (CPU bound)."""

    store = AdaptiveMemoryStore(max_capacity=1000)

    # Populate store with diverse data
    for i in range(100):
        embedding = np.random.rand(128).tolist()
        # Ensure some similarity
        if i % 10 == 0:
            embedding = [0.1] * 128

        event = MemoryEvent(embedding, {"id": i}, datetime.now())
        store.memory.append(event)

    query = np.random.rand(128).tolist()

    # Benchmark
    result = benchmark(store.retrieve, query_embedding=query, top_k=5)
    assert len(result) <= 5

@pytest.mark.benchmark(group="memory_prune")
def test_memory_prune_performance(benchmark, temp_memory_dir):
    """Benchmark the prune operation."""

    store = AdaptiveMemoryStore(max_capacity=2000)

    # Populate store with old events
    old_time = datetime.now()
    for i in range(1000):
        embedding = np.random.rand(128).tolist()
        event = MemoryEvent(embedding, {"id": i}, old_time)
        store.memory.append(event)

    # Benchmark
    def setup():
        store.memory = []
        for i in range(1000):
            embedding = np.random.rand(128).tolist()
            event = MemoryEvent(embedding, {"id": i}, old_time)
            store.memory.append(event)
        return (store,), {}

    def run_prune(store):
        store.prune(max_age_hours=0, keep_critical=False)

    benchmark.pedantic(run_prune, setup=setup, rounds=10, iterations=1)
