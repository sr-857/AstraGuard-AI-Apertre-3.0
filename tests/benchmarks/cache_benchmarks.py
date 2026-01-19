#!/usr/bin/env python3
"""
Cache Performance Benchmarks

Microbenchmarks comparing cold vs hot reads and measuring cache performance.
Run with: python benchmarks/cache_benchmarks.py

Output is formatted for inclusion in pull requests.
"""

import asyncio
import time
import statistics
from typing import List, Tuple

# Add project root to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.cache.in_memory import InMemoryLRUCache


def format_duration(ms: float) -> str:
    """Format duration in appropriate units."""
    if ms < 0.001:
        return f"{ms * 1000:.2f}μs"
    elif ms < 1:
        return f"{ms * 1000:.2f}μs"
    else:
        return f"{ms:.3f}ms"


async def benchmark_in_memory_cache() -> dict:
    """Benchmark InMemoryLRUCache operations."""
    cache = InMemoryLRUCache(maxsize=10000, default_ttl=60)
    results = {}
    
    # Warm up
    for i in range(100):
        await cache.set(f"warmup_{i}", f"value_{i}")
        await cache.get(f"warmup_{i}")
    await cache.clear()
    
    # Benchmark SET operations
    set_times = []
    for i in range(1000):
        start = time.perf_counter()
        await cache.set(f"key_{i}", {"data": f"value_{i}", "index": i})
        elapsed = (time.perf_counter() - start) * 1000
        set_times.append(elapsed)
    
    results["set"] = {
        "mean": statistics.mean(set_times),
        "median": statistics.median(set_times),
        "p95": statistics.quantiles(set_times, n=20)[18],
        "p99": statistics.quantiles(set_times, n=100)[98],
    }
    
    # Benchmark GET (cache hit)
    get_hit_times = []
    for i in range(1000):
        start = time.perf_counter()
        await cache.get(f"key_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        get_hit_times.append(elapsed)
    
    results["get_hit"] = {
        "mean": statistics.mean(get_hit_times),
        "median": statistics.median(get_hit_times),
        "p95": statistics.quantiles(get_hit_times, n=20)[18],
        "p99": statistics.quantiles(get_hit_times, n=100)[98],
    }
    
    # Benchmark GET (cache miss)
    get_miss_times = []
    for i in range(1000):
        start = time.perf_counter()
        await cache.get(f"missing_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        get_miss_times.append(elapsed)
    
    results["get_miss"] = {
        "mean": statistics.mean(get_miss_times),
        "median": statistics.median(get_miss_times),
        "p95": statistics.quantiles(get_miss_times, n=20)[18],
        "p99": statistics.quantiles(get_miss_times, n=100)[98],
    }
    
    # Benchmark invalidate
    invalidate_times = []
    for i in range(500):
        start = time.perf_counter()
        await cache.invalidate(f"key_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        invalidate_times.append(elapsed)
    
    results["invalidate"] = {
        "mean": statistics.mean(invalidate_times),
        "median": statistics.median(invalidate_times),
        "p95": statistics.quantiles(invalidate_times, n=20)[18],
        "p99": statistics.quantiles(invalidate_times, n=100)[98],
    }
    
    return results


async def benchmark_cold_vs_hot() -> Tuple[float, float]:
    """Compare cold read (compute + cache) vs hot read (cache hit)."""
    cache = InMemoryLRUCache(maxsize=1000)
    
    async def expensive_computation(user_id: str) -> dict:
        """Simulated expensive database/API call."""
        await asyncio.sleep(0.001)  # 1ms simulated latency
        return {"user_id": user_id, "name": f"User {user_id}"}
    
    # Cold read (compute + cache)
    cold_times = []
    for i in range(100):
        start = time.perf_counter()
        result = await cache.get(f"user:{i}")
        if result is None:
            result = await expensive_computation(str(i))
            await cache.set(f"user:{i}", result)
        elapsed = (time.perf_counter() - start) * 1000
        cold_times.append(elapsed)
    
    # Hot read (cache hit)
    hot_times = []
    for i in range(100):
        start = time.perf_counter()
        result = await cache.get(f"user:{i}")
        elapsed = (time.perf_counter() - start) * 1000
        hot_times.append(elapsed)
    
    return statistics.mean(cold_times), statistics.mean(hot_times)


async def benchmark_throughput() -> dict:
    """Measure operations per second."""
    cache = InMemoryLRUCache(maxsize=10000)
    
    # Pre-populate cache
    for i in range(1000):
        await cache.set(f"key_{i}", f"value_{i}")
    
    # Measure GET throughput
    start = time.perf_counter()
    ops = 0
    while time.perf_counter() - start < 1.0:  # Run for 1 second
        await cache.get(f"key_{ops % 1000}")
        ops += 1
    get_ops_per_sec = ops
    
    # Measure SET throughput
    start = time.perf_counter()
    ops = 0
    while time.perf_counter() - start < 1.0:
        await cache.set(f"key_{ops % 1000}", f"newvalue_{ops}")
        ops += 1
    set_ops_per_sec = ops
    
    return {
        "get_ops_per_sec": get_ops_per_sec,
        "set_ops_per_sec": set_ops_per_sec,
    }


async def benchmark_eviction_pressure() -> dict:
    """Benchmark cache under eviction pressure."""
    cache = InMemoryLRUCache(maxsize=100)  # Small cache to force evictions
    
    # Fill cache and continue adding (causes evictions)
    eviction_times = []
    for i in range(1000):
        start = time.perf_counter()
        await cache.set(f"key_{i}", f"value_{i}")
        elapsed = (time.perf_counter() - start) * 1000
        if i >= 100:  # After cache is full
            eviction_times.append(elapsed)
    
    stats = cache.stats()
    
    return {
        "evictions": stats.evictions,
        "set_with_eviction_mean_ms": statistics.mean(eviction_times),
        "set_with_eviction_p99_ms": statistics.quantiles(eviction_times, n=100)[98],
    }


def print_results():
    """Run all benchmarks and print results."""
    print("=" * 60)
    print("ASTRAGUARD CACHE PERFORMANCE BENCHMARKS")
    print("=" * 60)
    print()
    
    # In-memory cache benchmarks
    print("## InMemoryLRUCache Operations\n")
    results = asyncio.run(benchmark_in_memory_cache())
    
    print("| Operation   | Mean      | Median    | P95       | P99       |")
    print("|-------------|-----------|-----------|-----------|-----------|")
    for op, metrics in results.items():
        print(
            f"| {op:11} | "
            f"{format_duration(metrics['mean']):9} | "
            f"{format_duration(metrics['median']):9} | "
            f"{format_duration(metrics['p95']):9} | "
            f"{format_duration(metrics['p99']):9} |"
        )
    print()
    
    # Cold vs Hot comparison
    print("## Cold vs Hot Read Comparison\n")
    cold_ms, hot_ms = asyncio.run(benchmark_cold_vs_hot())
    speedup = cold_ms / hot_ms if hot_ms > 0 else 0
    
    print(f"| Scenario    | Latency   | Speedup   |")
    print(f"|-------------|-----------|-----------|")
    print(f"| Cold Read   | {format_duration(cold_ms):9} | 1.0x      |")
    print(f"| Hot Read    | {format_duration(hot_ms):9} | {speedup:.1f}x      |")
    print()
    
    # Throughput
    print("## Throughput (operations/second)\n")
    throughput = asyncio.run(benchmark_throughput())
    
    print(f"| Operation   | Ops/sec   |")
    print(f"|-------------|-----------|")
    print(f"| GET (hit)   | {throughput['get_ops_per_sec']:,}    |")
    print(f"| SET         | {throughput['set_ops_per_sec']:,}    |")
    print()
    
    # Eviction pressure
    print("## Eviction Pressure (maxsize=100, 1000 writes)\n")
    eviction = asyncio.run(benchmark_eviction_pressure())
    
    print(f"- Evictions: {eviction['evictions']}")
    print(f"- Mean SET (with eviction): {format_duration(eviction['set_with_eviction_mean_ms'])}")
    print(f"- P99 SET (with eviction): {format_duration(eviction['set_with_eviction_p99_ms'])}")
    print()
    
    print("=" * 60)
    print("BENCHMARK COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    print_results()
