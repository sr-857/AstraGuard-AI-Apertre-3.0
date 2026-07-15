import asyncio
import time
import tempfile
from pathlib import Path
from src.astraguard.hil.metrics.storage import MetricsStorage
from src.astraguard.hil.metrics.latency import LatencyCollector

async def benchmark_metrics_storage():
    """Benchmark MetricsStorage operations before and after optimizations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple runs for testing
        runs = []
        for i in range(5):
            run_id = f"run_{i}"
            storage = MetricsStorage(run_id, temp_dir)
            runs.append(storage)

            # Simulate latency collector with some data
            collector = LatencyCollector()
            # Add some fake measurements
            for j in range(100):
                collector.add_measurement("test_metric", j * 0.01, satellite_id=f"sat_{j%10}")

            print(f"Benchmarking save_latency_stats for {run_id}...")
            start_time = time.time()
            paths = storage.save_latency_stats(collector)
            save_time = time.time() - start_time
            print(f"Save time for {run_id}: {save_time:.4f} seconds")

        # Benchmark get_run_metrics
        print("Benchmarking get_run_metrics...")
        start_time = time.time()
        for storage in runs:
            metrics = storage.get_run_metrics()
        get_time = time.time() - start_time
        print(f"Get time: {get_time:.4f} seconds")

        # Benchmark compare_runs
        print("Benchmarking compare_runs...")
        start_time = time.time()
        comparison = runs[0].compare_runs(runs[1].run_id)
        compare_time = time.time() - start_time
        print(f"Compare time: {compare_time:.4f} seconds")

        # Benchmark get_recent_runs
        print("Benchmarking get_recent_runs...")
        start_time = time.time()
        recent = MetricsStorage.get_recent_runs(temp_dir, limit=10)
        recent_time = time.time() - start_time
        print(f"Recent runs time: {recent_time:.4f} seconds")

async def benchmark_observability():
    """Benchmark observability metrics creation and access."""
    import time
    from src.astraguard.observability import _safe_create_metric, Counter

    print("Benchmarking metric creation...")
    start = time.time()
    for i in range(1000):
        metric = _safe_create_metric(Counter, f'test_metric_{i}', f'Test {i}', ['label'])
    end = time.time()
    print(f"Time to create 1000 metrics: {end - start:.4f} seconds")

    # Benchmark registry access
    print("Benchmarking registry access...")
    start = time.time()
    from src.astraguard.observability import get_registry
    registry = get_registry()
    for _ in range(1000):
        metrics = registry._collector_to_names
    end = time.time()
    print(f"Time for 1000 registry accesses: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(benchmark_metrics_storage())
    asyncio.run(benchmark_observability())
