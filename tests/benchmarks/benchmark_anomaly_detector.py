import asyncio
import time
import random
from src.anomaly.anomaly_detector import detect_anomaly, load_model

async def benchmark_anomaly_detector():
    """Benchmark anomaly detection latency before and after optimizations."""
    print("Benchmarking anomaly detector latency...")

    # Ensure model is loaded
    await load_model()

    # Generate synthetic telemetry data
    num_calls = 1000
    test_data = []
    for _ in range(num_calls):
        data = {
            "voltage": random.uniform(7.0, 9.0),
            "temperature": random.uniform(20.0, 50.0),
            "gyro": random.uniform(-0.2, 0.2),
            "current": random.uniform(0.5, 2.0),
            "wheel_speed": random.uniform(0.0, 10.0),
        }
        test_data.append(data)

    print(f"Generated {num_calls} synthetic telemetry data points.")

    # Benchmark detect_anomaly calls
    latencies = []
    for data in test_data:
        start_time = time.time()
        await detect_anomaly(data)
        latency = time.time() - start_time
        latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0

    print(f"  Avg latency: {avg_latency:.6f}s")
    print(f"  Min latency: {min_latency:.6f}s")
    print(f"  Max latency: {max_latency:.6f}s")
    print(f"  P95 latency: {p95:.6f}s")
    print(f"  Total time:  {sum(latencies):.4f}s for {num_calls} calls")

    return avg_latency, min_latency, max_latency

if __name__ == "__main__":
    asyncio.run(benchmark_anomaly_detector())
