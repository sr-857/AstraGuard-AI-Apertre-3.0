import asyncio
import time
import tempfile
from pathlib import Path
from astraguard.hil.results.storage import ResultStorage

async def benchmark_storage():
    """Benchmark storage operations before and after optimizations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = ResultStorage(temp_dir)

        # Create test data
        test_results = [
            {"status": "passed", "duration": 1.5, "details": {"test": f"scenario_{i}"}}
            for i in range(100)
        ]

        print("Benchmarking save_scenario_result...")
        start_time = time.time()
        tasks = []
        for i, result in enumerate(test_results):
            task = asyncio.create_task(storage.save_scenario_result(f"scenario_{i}", result))
            tasks.append(task)
        await asyncio.gather(*tasks)
        save_time = time.time() - start_time
        print(f"Save time: {save_time:.4f} seconds")

        print("Benchmarking get_scenario_results...")
        start_time = time.time()
        tasks = []
        for i in range(10):
            task = asyncio.create_task(storage.get_scenario_results(f"scenario_{i}", limit=10))
            tasks.append(task)
        await asyncio.gather(*tasks)
        get_time = time.time() - start_time
        print(f"Get time: {get_time:.4f} seconds")

        print("Benchmarking get_result_statistics...")
        start_time = time.time()
        stats = await storage.get_result_statistics()
        stats_time = time.time() - start_time
        print(f"Stats time: {stats_time:.4f} seconds")

        print("Benchmarking clear_results...")
        start_time = time.time()
        deleted = await storage.clear_results(older_than_days=0)  # Clear all for test
        clear_time = time.time() - start_time
        print(f"Clear time: {clear_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(benchmark_storage())
