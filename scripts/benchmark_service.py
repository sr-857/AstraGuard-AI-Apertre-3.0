import asyncio
import time
import httpx
from typing import List
import statistics
from api.models import TelemetryInput

async def benchmark_telemetry_batch(base_url: str = "http://localhost:8000", batch_sizes: List[int] = [10, 50, 100], num_batches: int = 10):
    """Benchmark telemetry batch processing performance."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = {}

        for batch_size in batch_sizes:
            print(f"\nBenchmarking batch size: {batch_size}")
            latencies = []

            for batch_num in range(num_batches):
                # Generate test telemetry data
                telemetry_data = []
                for i in range(batch_size):
                    telemetry_data.append({
                        "voltage": 5.0 + (i % 10) * 0.1,
                        "temperature": 25.0 + (i % 5) * 2.0,
                        "gyro": 0.01 + (i % 3) * 0.005,
                        "current": 1.0 + (i % 8) * 0.1,
                        "wheel_speed": 10.0 + (i % 6) * 1.0,
                        "cpu_usage": 50.0 + (i % 20),
                        "memory_usage": 60.0 + (i % 15),
                        "network_latency": 10.0 + (i % 10),
                        "disk_io": 100.0 + (i % 50),
                        "error_rate": 0.01 + (i % 5) * 0.005,
                        "response_time": 100.0 + (i % 30),
                        "active_connections": 100 + (i % 50)
                    })

                payload = {"telemetry": telemetry_data}

                try:
                    start_time = time.time()
                    response = await client.post(
                        f"{base_url}/api/v1/telemetry/batch",
                        json=payload,
                        headers={"Authorization": "Bearer test-key"}  # Assuming test auth
                    )
                    latency = time.time() - start_time

                    if response.status_code == 200:
                        latencies.append(latency)
                        data = response.json()
                        print(".3f")
                    else:
                        print(f"  Batch {batch_num + 1}: Failed with status {response.status_code}")

                except Exception as e:
                    print(f"  Batch {batch_num + 1}: Error - {e}")

            if latencies:
                results[batch_size] = {
                    "mean_latency": statistics.mean(latencies),
                    "median_latency": statistics.median(latencies),
                    "min_latency": min(latencies),
                    "max_latency": max(latencies),
                    "successful_batches": len(latencies),
                    "throughput": sum(1/l for l in latencies) / len(latencies)  # requests per second
                }

                print(f"  Results for batch size {batch_size}:")
                print(".3f")
                print(".3f")
                print(".3f")
                print(".3f")
                print(".1f")
                print(".2f")

        return results

async def main():
    print("Starting AstraGuard API Service Performance Benchmark")
    print("=" * 60)

    # Note: This assumes the service is running on localhost:8000
    # In a real scenario, you'd start the service programmatically or ensure it's running

    try:
        results = await benchmark_telemetry_batch()
        print("\nBenchmark completed successfully!")
        print("Results:", results)
    except Exception as e:
        print(f"Benchmark failed: {e}")
        print("Make sure the AstraGuard API service is running on http://localhost:8000")

if __name__ == "__main__":
    asyncio.run(main())
