import asyncio
import time
import json
import statistics
import sys
import os
import subprocess
import requests
from datetime import datetime

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from network.batcher import RequestBatcher
from network.client import get_network_client, close_client
from network.serialization import serialize_payload
from network.compression import compress_payload

API_URL = "http://localhost:8002"
BATCH_ENDPOINT = f"{API_URL}/api/v1/telemetry/batch"

async def run_benchmark(num_items=1000):
    print(f"Starting OPTIMIZED benchmark with {num_items} items...")

    # 1. Payload Size Check
    sample_payload = {
        "voltage": 12.5,
        "temperature": 45.2,
        "gyro": 0.01,
        "current": 2.1,
        "wheel_speed": 1500.0,
        "cpu_usage": 30.0,
        "memory_usage": 40.0,
        "timestamp": datetime.now().isoformat()
    }

    # Baseline Size (JSON)
    json_bytes = len(json.dumps(sample_payload).encode('utf-8'))

    # Optimized Size (MsgPack + Zstd)
    # We batch 20 items usually.
    batch_payload = {"telemetry": [sample_payload] * 20}

    # JSON Batch Size
    json_batch_bytes = len(json.dumps(batch_payload).encode('utf-8'))

    # Optimized Batch Size
    msgpack_bytes = serialize_payload(batch_payload)
    zstd_bytes = compress_payload(msgpack_bytes)

    print(f"Single Item JSON Size: {json_bytes} bytes")
    print(f"Batch (20) JSON Size: {json_batch_bytes} bytes")
    print(f"Batch (20) Optimized Size: {len(zstd_bytes)} bytes")
    print(f"Reduction: {100 * (1 - len(zstd_bytes)/json_batch_bytes):.2f}%")

    # 2. Latency & Throughput
    batcher = RequestBatcher(endpoint=BATCH_ENDPOINT, batch_size=20, max_wait_ms=100)
    await batcher.start()

    start_time = time.time()

    # Add items
    for i in range(num_items):
        await batcher.add(sample_payload)
        # No sleep to stress test throughput

    # Stop flushes remaining items
    await batcher.stop()

    total_time = time.time() - start_time

    print("\n--- Optimized Results ---")
    print(f"Total Items: {num_items}")
    print(f"Total Time: {total_time:.2f} s")
    print(f"Throughput (Items/sec): {num_items / total_time:.2f}")

    await close_client()

if __name__ == "__main__":
    # Start Stub Server
    print("Starting stub server...")
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
            print("Server failed to start.")
            sys.exit(1)

        asyncio.run(run_benchmark(num_items=5000))

    finally:
        server_process.terminate()
        server_process.wait()
