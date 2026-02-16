"""
Benchmark tests for encryption performance

Validates the <5ms encryption overhead requirement.
"""

import pytest
import time
import statistics
import tempfile
import shutil
import os

from security import (
    init_encryption_system,
    encrypt_data,
    decrypt_data,
    get_encryption_engine,
)


@pytest.fixture
def temp_storage():
    """Create temporary storage for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
async def benchmark_system(temp_storage):
    """Initialize encryption system for benchmarking."""
    os.environ["MASTER_KEY_SEED"] = "benchmark-master-key-seed"
    
    await init_encryption_system(
        master_key="benchmark-master-key-32-bytes!",
        storage_path=temp_storage,
        enable_hsm=False,
        fips_enabled=False,
        auto_rotation=False,
    )
    
    yield
    
    if "MASTER_KEY_SEED" in os.environ:
        del os.environ["MASTER_KEY_SEED"]


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_encryption_latency_requirement(benchmark_system):
    """
    Test that encryption meets <5ms latency requirement.
    
    This is a critical acceptance criterion.
    """
    engine = get_encryption_engine()
    
    test_data = "Sensitive satellite telemetry data"
    iterations = 1000
    
    # Warmup
    for _ in range(100):
        enc, dek = encrypt_data(test_data)
        decrypt_data(enc, dek)
    
    # Benchmark encryption
    encrypt_times = []
    for _ in range(iterations):
        start = time.perf_counter()
        enc, dek = encrypt_data(test_data)
        elapsed_ms = (time.perf_counter() - start) * 1000
        encrypt_times.append(elapsed_ms)
    
    # Benchmark decryption
    decrypt_times = []
    for _ in range(iterations):
        enc, dek = encrypt_data(test_data)
        start = time.perf_counter()
        decrypt_data(enc, dek)
        elapsed_ms = (time.perf_counter() - start) * 1000
        decrypt_times.append(elapsed_ms)
    
    # Calculate statistics
    encrypt_stats = {
        "min": min(encrypt_times),
        "max": max(encrypt_times),
        "avg": statistics.mean(encrypt_times),
        "median": statistics.median(encrypt_times),
        "p95": sorted(encrypt_times)[int(iterations * 0.95)],
        "p99": sorted(encrypt_times)[int(iterations * 0.99)],
        "stdev": statistics.stdev(encrypt_times) if len(encrypt_times) > 1 else 0,
    }
    
    decrypt_stats = {
        "min": min(decrypt_times),
        "max": max(decrypt_times),
        "avg": statistics.mean(decrypt_times),
        "median": statistics.median(decrypt_times),
        "p95": sorted(decrypt_times)[int(iterations * 0.95)],
        "p99": sorted(decrypt_times)[int(iterations * 0.99)],
        "stdev": statistics.stdev(decrypt_times) if len(decrypt_times) > 1 else 0,
    }
    
    # Print results
    print("\n=== Encryption Performance Benchmark ===")
    print(f"Iterations: {iterations}")
    print(f"Data size: {len(test_data)} bytes")
    print("\nEncryption:")
    print(f"  Min:    {encrypt_stats['min']:.3f}ms")
    print(f"  Max:    {encrypt_stats['max']:.3f}ms")
    print(f"  Avg:    {encrypt_stats['avg']:.3f}ms")
    print(f"  Median: {encrypt_stats['median']:.3f}ms")
    print(f"  P95:    {encrypt_stats['p95']:.3f}ms")
    print(f"  P99:    {encrypt_stats['p99']:.3f}ms")
    print(f"  Stdev:  {encrypt_stats['stdev']:.3f}ms")
    
    print("\nDecryption:")
    print(f"  Min:    {decrypt_stats['min']:.3f}ms")
    print(f"  Max:    {decrypt_stats['max']:.3f}ms")
    print(f"  Avg:    {decrypt_stats['avg']:.3f}ms")
    print(f"  Median: {decrypt_stats['median']:.3f}ms")
    print(f"  P95:    {decrypt_stats['p95']:.3f}ms")
    print(f"  P99:    {decrypt_stats['p99']:.3f}ms")
    print(f"  Stdev:  {decrypt_stats['stdev']:.3f}ms")
    
    # Validate requirements
    assert encrypt_stats['avg'] < 5.0, f"Encryption avg {encrypt_stats['avg']:.3f}ms >= 5ms"
    assert encrypt_stats['p95'] < 5.0, f"Encryption p95 {encrypt_stats['p95']:.3f}ms >= 5ms"
    assert encrypt_stats['p99'] < 5.0, f"Encryption p99 {encrypt_stats['p99']:.3f}ms >= 5ms"
    
    assert decrypt_stats['avg'] < 5.0, f"Decryption avg {decrypt_stats['avg']:.3f}ms >= 5ms"
    assert decrypt_stats['p95'] < 5.0, f"Decryption p95 {decrypt_stats['p95']:.3f}ms >= 5ms"
    assert decrypt_stats['p99'] < 5.0, f"Decryption p99 {decrypt_stats['p99']:.3f}ms >= 5ms"
    
    print("\n✅ All performance requirements met (<5ms)")


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_encryption_throughput(benchmark_system):
    """Test encryption throughput."""
    engine = get_encryption_engine()
    
    test_data = "X" * 1024  # 1KB
    duration_seconds = 5
    
    start_time = time.time()
    count = 0
    
    while time.time() - start_time < duration_seconds:
        enc, dek = encrypt_data(test_data)
        count += 1
    
    elapsed = time.time() - start_time
    throughput = count / elapsed
    
    print(f"\n=== Throughput Benchmark ===")
    print(f"Duration: {elapsed:.2f}s")
    print(f"Operations: {count}")
    print(f"Throughput: {throughput:.2f} ops/sec")
    print(f"Data size: {len(test_data)} bytes")
    
    # Should handle at least 1000 ops/sec for 1KB data
    assert throughput > 1000, f"Throughput {throughput:.2f} ops/sec too low"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_encryption_different_sizes(benchmark_system):
    """Test encryption performance with different data sizes."""
    sizes = [16, 64, 256, 1024, 4096, 16384, 65536, 262144]
    
    print("\n=== Size-Based Performance ===")
    print(f"{'Size (bytes)':<15} {'Avg (ms)':<12} {'P95 (ms)':<12} {'P99 (ms)':<12}")
    print("-" * 51)
    
    for size in sizes:
        data = "X" * size
        
        times = []
        for _ in range(100):
            start = time.perf_counter()
            enc, dek = encrypt_data(data)
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
        
        avg = statistics.mean(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        p99 = sorted(times)[int(len(times) * 0.99)]
        
        print(f"{size:<15} {avg:<12.3f} {p95:<12.3f} {p99:<12.3f}")
        
        # All sizes should be under 5ms
        assert p99 < 5.0, f"Size {size}: p99 {p99:.3f}ms >= 5ms"


@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_hardware_acceleration_detection(benchmark_system):
    """Test that hardware acceleration is detected and used."""
    engine = get_encryption_engine()
    
    print(f"\n=== Hardware Acceleration ===")
    print(f"AES-NI Available: {engine.use_hardware_acceleration}")
    
    # Performance should be good regardless
    test_data = "Test data"
    times = []
    
    for _ in range(1000):
        start = time.perf_counter()
        enc, dek = encrypt_data(test_data)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    
    avg = statistics.mean(times)
    print(f"Average encryption time: {avg:.3f}ms")
    
    assert avg < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])
