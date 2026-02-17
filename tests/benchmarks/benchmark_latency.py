"""
NON-PRODUCTION BENCHMARK UTILITY

This script is a development/testing tool for performance benchmarking.
It is NOT intended for production use and should not be included in
runtime deployments or CI pipelines.

This benchmark imports production modules directly and assumes local paths.
"""

import time
import tempfile
import os
from src.astraguard.hil.metrics.latency import LatencyCollector


def benchmark_latency():
    """Benchmark LatencyCollector performance before and after optimizations."""
    collector = LatencyCollector()

    # Generate test data
    num_measurements = 10000
    print(f"Generating {num_measurements} test measurements...")

    for i in range(num_measurements):
        sat_id = f"SAT{(i % 10) + 1}"
        scenario_time = float(i * 0.1)
        duration = float((i % 100) + 10)  # Vary durations

        if i % 3 == 0:
            collector.record_fault_detection(sat_id, scenario_time, duration)
        elif i % 3 == 1:
            collector.record_agent_decision(sat_id, scenario_time, duration)
        else:
            collector.record_recovery_action(sat_id, scenario_time, duration)

    print(f"Generated {len(collector)} measurements")

    # Benchmark get_stats()
    print("Benchmarking get_stats()...")
    start_time = time.time()
    stats = collector.get_stats()
    stats_time = time.time() - start_time
    print(".4f")

    # Benchmark get_stats_by_satellite()
    print("Benchmarking get_stats_by_satellite()...")
    start_time = time.time()
    sat_stats = collector.get_stats_by_satellite()
    sat_stats_time = time.time() - start_time
    print(".4f")

    # Benchmark export_csv()
    print("Benchmarking export_csv()...")
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        start_time = time.time()
        collector.export_csv(tmp_path)
        export_time = time.time() - start_time
        print(".4f")

        # Verify file size
        file_size = os.path.getsize(tmp_path)
        print(f"CSV file size: {file_size} bytes")

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Benchmark get_summary()
    print("Benchmarking get_summary()...")
    start_time = time.time()
    summary = collector.get_summary()
    summary_time = time.time() - start_time
    print(".4f")

    print("\nBenchmark complete!")

if __name__ == "__main__":
    benchmark_latency()
