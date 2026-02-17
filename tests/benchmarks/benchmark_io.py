import asyncio
import time
import os
import sys
import shutil
import tempfile
import numpy as np
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../src"))

# Suppress logging during benchmark imports and setup
logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)

from memory_engine.memory_store import AdaptiveMemoryStore
from core.audit_logger import AuditLogger, AuditEventType
from astraguard.logging_config import setup_json_logging

# Configure structlog to be silent or redirect to null
import structlog
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(file=open(os.devnull, "w")),
)

async def benchmark_memory_store(iterations=1000):
    print(f"\n--- Benchmarking AdaptiveMemoryStore ({iterations} writes) ---")

    # Use a temporary directory for safe testing
    temp_dir = tempfile.mkdtemp()
    store_path = os.path.join(temp_dir, "memory_store.pkl")

    try:
        store = AdaptiveMemoryStore()
        store.storage_path = store_path # Override path for safety

        # Benchmark Write (In-memory append + potential internal operations)
        start_time = time.perf_counter()
        for i in range(iterations):
            embedding = np.random.rand(128).tolist()
            metadata = {"id": i, "data": "test_data_" * 10}
            await store.write(embedding, metadata)
        write_duration = time.perf_counter() - start_time
        print(f"Write Time (In-Memory): {write_duration:.4f} s ({iterations/write_duration:.2f} ops/s)")
        print(f"Avg Write Latency: {(write_duration/iterations)*1000:.4f} ms")

        # Benchmark Save (Disk I/O - Pickle)
        start_time = time.perf_counter()
        await store.save()
        save_duration = time.perf_counter() - start_time
        print(f"Save Time (Disk I/O): {save_duration:.4f} s")

        # Benchmark Load
        start_time = time.perf_counter()
        store.load()
        load_duration = time.perf_counter() - start_time
        print(f"Load Time (Disk I/O): {load_duration:.4f} s")

        return write_duration, save_duration

    finally:
        shutil.rmtree(temp_dir)

def benchmark_audit_logger(iterations=1000):
    print(f"\n--- Benchmarking AuditLogger ({iterations} logs) ---")

    temp_dir = tempfile.mkdtemp()
    log_dir = os.path.join(temp_dir, "logs")

    try:
        # Reconfigure logger to point to our temp dir and NOT stdout
        # But AuditLogger internally sets up handlers.
        # We need to make sure we measure the AuditLogger overhead.

        logger = AuditLogger(log_dir=log_dir)
        # We want to measure the cost of `log_event`.

        start_time = time.perf_counter()
        for i in range(iterations):
            logger.log_event(
                AuditEventType.DATA_ACCESS,
                user_id=f"user_{i}",
                resource="benchmark_resource",
                action="read",
                details={"iteration": i, "payload": "x" * 100}
            )
        duration = time.perf_counter() - start_time
        print(f"Logging Time (Sync I/O): {duration:.4f} s ({iterations/duration:.2f} ops/s)")
        print(f"Avg Latency per Log: {(duration/iterations)*1000:.4f} ms")

        return duration

    finally:
        shutil.rmtree(temp_dir)

async def main():
    print("Starting I/O Benchmark...")
    await benchmark_memory_store(1000)
    benchmark_audit_logger(1000)
    print("\nBenchmark Complete.")

if __name__ == "__main__":
    asyncio.run(main())
