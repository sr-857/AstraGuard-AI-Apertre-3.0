import asyncio
import time
import json
import statistics
import sys
import os
import signal
import subprocess
import requests
import statistics
from datetime import datetime

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), "src"))

API_URL = "http://localhost:8002"
TELEMETRY_ENDPOINT = "/api/v1/telemetry"

def get_api_key():
    return "stub-benchmark-key"

def run_benchmark(api_key, num_requests=1000):
    print(f"Starting baseline benchmark with {num_requests} requests...")

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "voltage": 12.5,
        "temperature": 45.2,
        "gyro": 0.01,
        "current": 2.1,
        "wheel_speed": 1500.0,
        "cpu_usage": 30.0,
        "memory_usage": 40.0,
        "timestamp": datetime.now().isoformat()
    }

    # Calculate payload size
    payload_bytes = len(json.dumps(payload).encode('utf-8'))
    print(f"Payload Size: {payload_bytes} bytes")

    latencies = []
    failures = 0
    start_time = time.time()

    session = requests.Session()

    for i in range(num_requests):
        try:
            req_start = time.perf_counter()
            response = session.post(f"{API_URL}{TELEMETRY_ENDPOINT}", json=payload, headers=headers)
            req_end = time.perf_counter()

            if response.status_code == 200:
                latencies.append((req_end - req_start) * 1000) # ms
            else:
                failures += 1
        except Exception as e:
            failures += 1
            print(f"Request exception: {e}")

    total_time = time.time() - start_time

    if not latencies:
        print("No successful requests.")
        return

    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18] # 95th percentile

    print("\n--- Baseline Results (Stub Server) ---")
    print(f"Total Requests: {num_requests}")
    print(f"Successful: {len(latencies)}")
    print(f"Failed: {failures}")
    print(f"Avg Latency: {avg_latency:.2f} ms")
    print(f"P95 Latency: {p95_latency:.2f} ms")
    print(f"Payload Size: {payload_bytes} bytes")
    print(f"Total Time: {total_time:.2f} s")
    print(f"Requests/sec: {num_requests / total_time:.2f}")

    print("\n--- Baseline (No Reuse) Check ---")
    no_reuse_latencies = []
    for _ in range(10):
        req_start = time.perf_counter()
        requests.post(f"{API_URL}{TELEMETRY_ENDPOINT}", json=payload, headers=headers)
        no_reuse_latencies.append((time.perf_counter() - req_start) * 1000)
    print(f"Avg Latency (No Reuse): {statistics.mean(no_reuse_latencies):.2f} ms")

if __name__ == "__main__":
    # Ensure we can import src
    sys.path.append(os.path.join(os.getcwd(), "src"))

    # Start Stub Server
    print("Starting stub server...")
    # Don't capture stdout/stderr to avoid buffer blocking
    server_process = subprocess.Popen(
        ["uvicorn", "src.api.service_stub:app", "--port", "8002", "--host", "127.0.0.1"],
        env={**os.environ, "PYTHONPATH": "src"}
    )

    try:
        # Wait for server to be ready
        print("Waiting for server to be ready...")
        ready = False
        retries = 30
        while not ready and retries > 0:
            try:
                requests.get(f"{API_URL}/health/live", timeout=1)
                ready = True
            except:
                time.sleep(1)
                retries -= 1

        if not ready:
            print("Server failed to start (timed out waiting).")
            sys.exit(1)

        api_key = get_api_key()
        run_benchmark(api_key)

    finally:
        server_process.terminate()
        server_process.wait()
