#!/usr/bin/env python3
"""
Benchmark script for telemetry submission latency.

This script measures the performance of submitting telemetry data to the API,
focusing on latency and throughput before and after optimizations.
"""

import asyncio
import time
import statistics
import aiohttp
from typing import List, Dict, Any
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8002"
NUM_REQUESTS = 100
CONCURRENT_REQUESTS = 10
TELEMETRY_ENDPOINT = "/api/v1/telemetry"

# Sample telemetry data
SAMPLE_TELEMETRY = {
    "voltage": 12.5,
    "temperature": 25.0,
    "gyro": 0.1,
    "current": 1.2,
    "wheel_speed": 50.0,
    "cpu_usage": 45.0,
    "memory_usage": 60.0,
    "network_latency": 10.0,
    "disk_io": 100.0,
    "error_rate": 0.01,
    "response_time": 150.0,
    "active_connections": 25
}

# API Key for authentication (replace with actual key)
API_KEY = "test-api-key"

async def submit_telemetry(session: aiohttp.ClientSession, telemetry_data: Dict[str, Any]) -> float:
    """Submit a single telemetry request and return latency."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    start_time = time.time()
    try:
        async with session.post(
            f"{API_BASE_URL}{TELEMETRY_ENDPOINT}",
            json=telemetry_data,
            headers=headers
        ) as response:
            await response.text()  # Consume response
            latency = time.time() - start_time
            return latency
    except Exception as e:
        print(f"Request failed: {e}")
        return time.time() - start_time  # Return latency even on failure

async def benchmark_telemetry_submission() -> Dict[str, Any]:
    """Run telemetry submission benchmark."""
    print(f"Starting telemetry submission benchmark with {NUM_REQUESTS} requests...")

    latencies: List[float] = []

    async with aiohttp.ClientSession() as session:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)

        async def submit_with_semaphore(telemetry: Dict[str, Any]) -> float:
            async with semaphore:
                return await submit_telemetry(session, telemetry)

        # Generate telemetry data with slight variations
        telemetry_requests = []
        for i in range(NUM_REQUESTS):
            telemetry = SAMPLE_TELEMETRY.copy()
            telemetry["voltage"] += (i % 10) * 0.1  # Add some variation
            telemetry["temperature"] += (i % 5) * 0.5
            telemetry_requests.append(telemetry)

        # Run requests concurrently
        start_time = time.time()
        tasks = [submit_with_semaphore(req) for req in telemetry_requests]
        latencies = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

    # Calculate statistics
    if latencies:
        avg_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        throughput = NUM_REQUESTS / total_time
    else:
        avg_latency = median_latency = min_latency = max_latency = p95_latency = throughput = 0

    results = {
        "timestamp": datetime.now().isoformat(),
        "num_requests": NUM_REQUESTS,
        "concurrent_requests": CONCURRENT_REQUESTS,
        "total_time_seconds": round(total_time, 2),
        "throughput_requests_per_second": round(throughput, 2),
        "latency_ms": {
            "average": round(avg_latency * 1000, 2),
            "median": round(median_latency * 1000, 2),
            "min": round(min_latency * 1000, 2),
            "max": round(max_latency * 1000, 2),
            "p95": round(p95_latency * 1000, 2)
        }
    }

    print("Benchmark Results:")
    print(json.dumps(results, indent=2))

    return results

if __name__ == "__main__":
    # Run the benchmark
    results = asyncio.run(benchmark_telemetry_submission())

    # Save results to file
    with open("benchmark_results_telemetry_before.json", "w") as f:
        json.dump(results, f, indent=2)

    print("Results saved to benchmark_results_telemetry_before.json")
