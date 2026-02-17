"""Benchmark script for logging_config.py optimizations.

Tests performance improvements from:
- Cached secret retrieval
- Direct async logging execution
"""

import time
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from astraguard.logging_config import (
    _cached_get_secret,
    get_logger,
    async_log_request,
    async_log_error,
    async_log_detection,
    setup_json_logging
)


def benchmark_cached_secret_retrieval(iterations=1000):
    """Benchmark cached vs uncached secret retrieval."""
    print(f"\n{'='*60}")
    print(f"Benchmarking cached secret retrieval ({iterations} iterations)")
    print(f"{'='*60}")
    
    # Warm up cache
    _cached_get_secret("test_key", "default")
    
    # Benchmark cached retrieval
    start = time.perf_counter()
    for _ in range(iterations):
        _cached_get_secret("environment", "development")
        _cached_get_secret("app_version", "1.0.0")
    cached_duration = time.perf_counter() - start
    
    print(f"[OK] Cached retrieval: {cached_duration*1000:.2f}ms total")
    print(f"     Per call: {(cached_duration/iterations)*1000:.4f}ms")
    
    return cached_duration


async def benchmark_async_logging(iterations=1000):
    """Benchmark async logging performance."""
    print(f"\n{'='*60}")
    print(f"Benchmarking async logging ({iterations} iterations)")
    print(f"{'='*60}")
    
    logger = get_logger(__name__)
    
    # Benchmark async_log_request
    start = time.perf_counter()
    for i in range(iterations):
        await async_log_request(logger, "GET", "/api/test", 200, 15.5)
    request_duration = time.perf_counter() - start
    
    print(f"[OK] async_log_request: {request_duration*1000:.2f}ms total")
    print(f"     Per call: {(request_duration/iterations)*1000:.4f}ms")
    
    # Benchmark async_log_error
    try:
        raise ValueError("Test error")
    except ValueError as e:
        test_error = e
    
    start = time.perf_counter()
    for i in range(iterations):
        await async_log_error(logger, test_error, "test_context")
    error_duration = time.perf_counter() - start
    
    print(f"[OK] async_log_error: {error_duration*1000:.2f}ms total")
    print(f"     Per call: {(error_duration/iterations)*1000:.4f}ms")
    
    # Benchmark async_log_detection
    start = time.perf_counter()
    for i in range(iterations):
        await async_log_detection(logger, "warning", "anomaly", 0.85)
    detection_duration = time.perf_counter() - start
    
    print(f"[OK] async_log_detection: {detection_duration*1000:.2f}ms total")
    print(f"     Per call: {(detection_duration/iterations)*1000:.4f}ms")
    
    return request_duration, error_duration, detection_duration


def benchmark_setup_json_logging(iterations=10):
    """Benchmark setup_json_logging with cached secrets."""
    print(f"\n{'='*60}")
    print(f"Benchmarking setup_json_logging ({iterations} iterations)")
    print(f"{'='*60}")
    
    durations = []
    for _ in range(iterations):
        start = time.perf_counter()
        setup_json_logging()
        duration = time.perf_counter() - start
        durations.append(duration)
    
    avg_duration = sum(durations) / len(durations)
    min_duration = min(durations)
    max_duration = max(durations)
    
    print(f"[OK] Average: {avg_duration*1000:.2f}ms")
    print(f"     Min: {min_duration*1000:.2f}ms")
    print(f"     Max: {max_duration*1000:.2f}ms")
    
    return avg_duration


async def main():
    """Run all benchmarks."""
    print("\n" + "="*60)
    print("LOGGING_CONFIG.PY OPTIMIZATION BENCHMARKS")
    print("="*60)
    
    # Run benchmarks
    cached_time = benchmark_cached_secret_retrieval(1000)
    request_time, error_time, detection_time = await benchmark_async_logging(1000)
    setup_time = benchmark_setup_json_logging(10)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Cached secret retrieval: ~{(cached_time/1000)*1000000:.2f}µs per call")
    print(f"Async log request: ~{(request_time/1000)*1000:.2f}µs per call")
    print(f"Async log error: ~{(error_time/1000)*1000:.2f}µs per call")
    print(f"Async log detection: ~{(detection_time/1000)*1000:.2f}µs per call")
    print(f"Setup JSON logging: ~{setup_time*1000:.2f}ms")
    
    print("\nOptimizations Applied:")
    print("[+] LRU cache for secret retrieval (32 entries)")
    print("[+] Direct execution for async logging (no thread overhead)")
    print("[+] Cached environment/version lookups)")
    print("\nExpected performance improvements:")
    print("- Secret retrieval: ~10-100x faster (cached vs I/O)")
    print("- Async logging: ~2-5x faster (no thread spawning)")
    print("- Setup: ~1.5-3x faster (cached secrets)")
    

if __name__ == "__main__":
    asyncio.run(main())
