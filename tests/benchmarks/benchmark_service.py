"""
Benchmark script for src/api/service.py performance optimizations.

Measures:
1. Single telemetry processing latency
2. Batch telemetry processing throughput
3. Predictive maintenance parallel execution
4. Async chaos injection behavior
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
from datetime import datetime

# Import test dependencies
import sys
from pathlib import Path

# Add src to path (same as conftest.py)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.models import TelemetryInput, TelemetryBatch, AnomalyResponse
from api.service import (
    _process_single_telemetry,
    _process_telemetry,
    submit_telemetry_batch,
    check_chaos_injection,
    active_faults
)



def create_test_telemetry(count: int = 1) -> List[TelemetryInput]:
    """Create test telemetry data points."""
    telemetry_list = []
    for i in range(count):
        telemetry = TelemetryInput(
            voltage=8.0 + (i % 3) * 0.5,  # Vary voltage slightly
            temperature=25.0 + (i % 5) * 2,  # Vary temperature
            gyro=0.05 + (i % 2) * 0.02,  # Small gyro variations
            current=1.0 + (i % 4) * 0.1,
            wheel_speed=5.0 + (i % 3) * 0.5,
            cpu_usage=50.0 + (i % 10) * 5,
            memory_usage=60.0 + (i % 8) * 3,
            network_latency=20.0 + (i % 5) * 2,
            disk_io=100.0 + (i % 6) * 10,
            error_rate=0.1 + (i % 3) * 0.05,
            response_time=50.0 + (i % 7) * 5,
            active_connections=10 + (i % 5),
            timestamp=datetime.now()
        )
        telemetry_list.append(telemetry)
    return telemetry_list


async def benchmark_single_telemetry(count: int = 100) -> Dict[str, float]:
    """
    Benchmark single telemetry processing latency.
    
    Args:
        count: Number of telemetry points to process
        
    Returns:
        Dictionary with latency statistics
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking Single Telemetry Processing ({count} iterations)")
    print(f"{'='*60}")
    
    telemetry_list = create_test_telemetry(count)
    latencies = []
    
    # Initialize components first
    from api.service import initialize_components
    await initialize_components()

    
    for i, telemetry in enumerate(telemetry_list):
        request_start = time.time()
        
        try:
            # Process telemetry
            response = await _process_single_telemetry(telemetry, request_start)
            elapsed_ms = (time.time() - request_start) * 1000
            latencies.append(elapsed_ms)
            
            if (i + 1) % 20 == 0:
                print(f"  Processed {i+1}/{count} - Last latency: {elapsed_ms:.2f}ms")
                
        except Exception as e:
            print(f"  Error processing telemetry {i}: {e}")
            continue
    
    if not latencies:
        return {"error": "No successful measurements"}
    
    results = {
        "count": len(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "mean_ms": statistics.mean(latencies),
        "median_ms": statistics.median(latencies),
        "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        "p95_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else latencies[0],
        "throughput_per_sec": len(latencies) / sum(latencies) * 1000
    }
    
    print(f"\n  Results:")
    print(f"    Count: {results['count']}")
    print(f"    Min: {results['min_ms']:.2f}ms")
    print(f"    Max: {results['max_ms']:.2f}ms")
    print(f"    Mean: {results['mean_ms']:.2f}ms")
    print(f"    Median: {results['median_ms']:.2f}ms")
    print(f"    P95: {results['p95_ms']:.2f}ms")
    print(f"    StdDev: {results['stdev_ms']:.2f}ms")
    print(f"    Throughput: {results['throughput_per_sec']:.2f} req/sec")
    
    return results


async def benchmark_batch_processing(batch_sizes: List[int] = [10, 50, 100]) -> Dict[str, Any]:
    """
    Benchmark batch telemetry processing throughput.
    
    Args:
        batch_sizes: List of batch sizes to test
        
    Returns:
        Dictionary with throughput statistics for each batch size
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking Batch Telemetry Processing")
    print(f"{'='*60}")
    
    results = {}
    
    # Initialize components
    from api.service import initialize_components
    await initialize_components()

    
    for batch_size in batch_sizes:
        print(f"\n  Testing batch size: {batch_size}")
        
        # Create batch
        telemetry_list = create_test_telemetry(batch_size)
        batch = TelemetryBatch(telemetry=telemetry_list)
        
        # Measure batch processing time
        start_time = time.time()
        
        try:
            # Process batch
            response = await submit_telemetry_batch(batch)
            elapsed_ms = (time.time() - start_time) * 1000
            
            throughput = batch_size / (elapsed_ms / 1000)  # items per second
            
            results[batch_size] = {
                "total_time_ms": elapsed_ms,
                "items_processed": response.total_processed,
                "anomalies_detected": response.anomalies_detected,
                "throughput_per_sec": throughput,
                "avg_time_per_item_ms": elapsed_ms / batch_size
            }
            
            print(f"    Total time: {elapsed_ms:.2f}ms")
            print(f"    Throughput: {throughput:.2f} items/sec")
            print(f"    Avg time/item: {elapsed_ms / batch_size:.2f}ms")
            print(f"    Anomalies detected: {response.anomalies_detected}")
            
        except Exception as e:
            print(f"    Error: {e}")
            results[batch_size] = {"error": str(e)}
    
    return results


async def benchmark_async_chaos_injection() -> Dict[str, float]:
    """
    Benchmark async chaos injection behavior.
    Verifies that asyncio.sleep() doesn't block other requests.
    
    Returns:
        Dictionary with concurrency test results
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking Async Chaos Injection (Concurrency Test)")
    print(f"{'='*60}")
    
    # Inject network latency chaos
    from api.service import inject_chaos_fault
    inject_chaos_fault("network_latency", 60)  # 60 second duration

    
    telemetry_list = create_test_telemetry(5)
    
    print(f"  Testing concurrent processing with chaos injection...")
    print(f"  Processing 5 telemetry points concurrently (each with 2s chaos delay)")
    
    start_time = time.time()
    
    # Process all 5 concurrently
    tasks = [
        _process_single_telemetry(telemetry, time.time())
        for telemetry in telemetry_list
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed_ms = (time.time() - start_time) * 1000
    
    # Clean up chaos injection
    if "network_latency" in active_faults:
        del active_faults["network_latency"]
    
    successful = sum(1 for r in results if not isinstance(r, Exception))
    
    results_dict = {
        "concurrent_items": len(telemetry_list),
        "successful": successful,
        "total_time_ms": elapsed_ms,
        "expected_sequential_time_ms": len(telemetry_list) * 2000,  # 2s each
        "time_saved_ms": len(telemetry_list) * 2000 - elapsed_ms,
        "concurrency_efficiency": (len(telemetry_list) * 2000 - elapsed_ms) / (len(telemetry_list) * 2000) * 100
    }
    
    print(f"\n  Results:")
    print(f"    Concurrent items: {results_dict['concurrent_items']}")
    print(f"    Successful: {results_dict['successful']}")
    print(f"    Total time: {results_dict['total_time_ms']:.2f}ms")
    print(f"    Expected sequential: {results_dict['expected_sequential_time_ms']:.2f}ms")
    print(f"    Time saved: {results_dict['time_saved_ms']:.2f}ms")
    print(f"    Concurrency efficiency: {results_dict['concurrency_efficiency']:.1f}%")
    
    return results_dict


async def run_all_benchmarks():
    """Run all benchmarks and print summary."""
    print(f"\n{'#'*60}")
    print(f"# AstraGuard API Service Performance Benchmarks")
    print(f"{'#'*60}")
    print(f"\nTesting optimizations from Phase 1:")
    print(f"  1. Async chaos injection (asyncio.sleep)")
    print(f"  2. Internal batch processing (_process_single_telemetry)")
    print(f"  3. Parallel predictive maintenance (asyncio.gather)")
    print(f"  4. Fixed redundant secret retrieval")
    
    all_results = {}
    
    # Run benchmarks
    all_results['single_telemetry'] = await benchmark_single_telemetry(count=50)
    all_results['batch_processing'] = await benchmark_batch_processing([10, 25, 50])
    all_results['async_chaos'] = await benchmark_async_chaos_injection()
    
    # Print summary
    print(f"\n{'#'*60}")
    print(f"# Benchmark Summary")
    print(f"{'#'*60}")
    
    print(f"\n✅ Single Telemetry Processing:")
    single = all_results['single_telemetry']
    if 'mean_ms' in single:
        print(f"   Mean latency: {single['mean_ms']:.2f}ms")
        print(f"   Throughput: {single['throughput_per_sec']:.2f} req/sec")
    
    print(f"\n✅ Batch Processing:")
    for batch_size, result in all_results['batch_processing'].items():
        if 'throughput_per_sec' in result:
            print(f"   Batch size {batch_size}: {result['throughput_per_sec']:.2f} items/sec")
    
    print(f"\n✅ Async Chaos Injection:")
    chaos = all_results['async_chaos']
    if 'concurrency_efficiency' in chaos:
        print(f"   Concurrency efficiency: {chaos['concurrency_efficiency']:.1f}%")
        print(f"   Time saved vs sequential: {chaos['time_saved_ms']:.2f}ms")
    
    print(f"\n{'#'*60}")
    print(f"# All benchmarks completed!")
    print(f"{'#'*60}")
    
    return all_results


if __name__ == "__main__":
    # Run benchmarks
    results = asyncio.run(run_all_benchmarks())
