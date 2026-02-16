"""
Benchmark script for src/api/models.py performance analysis.
Testing validators and model creation performance.
"""

import time
import statistics
from datetime import datetime
from typing import List, Callable

from src.api.models import (
    TelemetryInput,
    TelemetryBatch,
    APIKeyCreateRequest,
    UserCreateRequest,
    PhaseUpdateRequest,
    AnomalyHistoryQuery,
    MissionPhaseEnum
)


def benchmark_function(func: Callable, iterations: int = 1000) -> dict:
    """Benchmark a function with multiple iterations."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to milliseconds
    
    return {
        "mean_ms": statistics.mean(times),
        "median_ms": statistics.median(times),
        "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
        "min_ms": min(times),
        "max_ms": max(times),
        "total_ms": sum(times),
        "iterations": iterations
    }


def benchmark_telemetry_creation():
    """Benchmark single telemetry creation."""
    TelemetryInput(
        voltage=12.5,
        temperature=25.0,
        gyro=0.5
    )


def benchmark_telemetry_batch():
    """Benchmark telemetry batch creation."""
    telemetry_data = [
        TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.5)
        for _ in range(100)
    ]
    TelemetryBatch(telemetry=telemetry_data)


def benchmark_api_key_validation():
    """Benchmark API key validation with permissions."""
    APIKeyCreateRequest(
        name="test_key",
        permissions=["read", "write"]
    )


def benchmark_api_key_invalid_permissions():
    """Benchmark API key validation with invalid permissions."""
    try:
        APIKeyCreateRequest(
            name="test_key",
            permissions=["read", "write", "invalid"]
        )
    except Exception:
        pass


def benchmark_user_creation():
    """Benchmark user creation validation."""
    UserCreateRequest(
        username="testuser123",
        email="test@example.com",
        role="analyst",
        password="secureP@ssw0rd"
    )


def benchmark_phase_update_valid():
    """Benchmark phase update with valid phase."""
    PhaseUpdateRequest(phase=MissionPhaseEnum.NOMINAL_OPS)


def benchmark_phase_update_invalid():
    """Benchmark phase update with invalid phase."""
    try:
        PhaseUpdateRequest(phase="INVALID_PHASE")
    except Exception:
        pass


def benchmark_anomaly_history_query():
    """Benchmark anomaly history query validation."""
    AnomalyHistoryQuery(
        start_time=datetime(2025, 1, 1),
        end_time=datetime(2025, 12, 31),
        limit=100,
        severity_min=0.5
    )


def run_all_benchmarks():
    """Run all benchmarks and print results."""
    benchmarks = [
        ("TelemetryInput Creation", benchmark_telemetry_creation),
        ("TelemetryBatch (100 items)", benchmark_telemetry_batch),
        ("APIKey Validation (valid)", benchmark_api_key_validation),
        ("APIKey Validation (invalid perms)", benchmark_api_key_invalid_permissions),
        ("User Creation", benchmark_user_creation),
        ("Phase Update (valid)", benchmark_phase_update_valid),
        ("Phase Update (invalid)", benchmark_phase_update_invalid),
        ("Anomaly History Query", benchmark_anomaly_history_query),
    ]
    
    print("=" * 80)
    print("PERFORMANCE BENCHMARK RESULTS - src/api/models.py")
    print("=" * 80)
    print()
    
    results = {}
    for name, func in benchmarks:
        print(f"Benchmarking: {name}...")
        result = benchmark_function(func, iterations=1000)
        results[name] = result
        
        print(f"  Mean:   {result['mean_ms']:.4f} ms")
        print(f"  Median: {result['median_ms']:.4f} ms")
        print(f"  StdDev: {result['stdev_ms']:.4f} ms")
        print(f"  Min:    {result['min_ms']:.4f} ms")
        print(f"  Max:    {result['max_ms']:.4f} ms")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY - Operations per second (based on mean)")
    print("=" * 80)
    for name, result in results.items():
        ops_per_sec = 1000 / result['mean_ms'] if result['mean_ms'] > 0 else 0
        print(f"{name:40s}: {ops_per_sec:>8,.0f} ops/sec")
    
    print()
    print("=" * 80)
    print("HOTSPOTS - Slowest operations")
    print("=" * 80)
    sorted_results = sorted(results.items(), key=lambda x: x[1]['mean_ms'], reverse=True)
    for name, result in sorted_results[:5]:
        print(f"{name:40s}: {result['mean_ms']:.4f} ms")
    
    return results


if __name__ == "__main__":
    run_all_benchmarks()
