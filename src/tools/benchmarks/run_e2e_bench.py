#!/usr/bin/env python3
"""
End-to-End Benchmark Runner for AstraGuard AI

Exercises the full API flow with concurrent requests to measure:
- Response latency (p50, p95, p99)
- Throughput (requests per second)
- Error rates

Usage:
    python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000
    python tools/benchmarks/run_e2e_bench.py --concurrency 10 --duration 30
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class RequestResult:
    """Result of a single HTTP request."""
    endpoint: str
    status_code: int
    latency_ms: float
    error: str | None = None


@dataclass
class BenchmarkStats:
    """Aggregated statistics for a benchmark run."""
    endpoint: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    latencies_ms: List[float] = field(default_factory=list)

    def add_result(self, result: RequestResult) -> None:
        self.total_requests += 1
        if result.error:
            self.failed_requests += 1
        else:
            self.successful_requests += 1
            self.latencies_ms.append(result.latency_ms)

    def summary(self) -> dict:
        if not self.latencies_ms:
            return {
                "endpoint": self.endpoint,
                "total_requests": self.total_requests,
                "successful_requests": 0,
                "failed_requests": self.failed_requests,
                "error_rate": 100.0,
            }

        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)

        return {
            "endpoint": self.endpoint,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": (self.failed_requests / self.total_requests) * 100,
            "latency_p50_ms": sorted_latencies[int(n * 0.50)],
            "latency_p95_ms": sorted_latencies[int(n * 0.95)],
            "latency_p99_ms": sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1],
            "latency_mean_ms": statistics.mean(sorted_latencies),
            "latency_min_ms": min(sorted_latencies),
            "latency_max_ms": max(sorted_latencies),
            "requests_per_sec": self.successful_requests / (max(sorted_latencies) / 1000) if sorted_latencies else 0,
        }


async def make_request(
    session,
    base_url: str,
    endpoint: str,
    method: str = "GET",
    payload: dict | None = None
) -> RequestResult:
    """Make a single HTTP request and measure latency."""
    url = f"{base_url.rstrip('/')}{endpoint}"
    start = time.perf_counter()

    try:
        if method == "GET":
            response = await session.get(url, timeout=10.0)
        else:
            response = await session.post(url, json=payload, timeout=10.0)

        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            endpoint=endpoint,
            status_code=response.status_code,
            latency_ms=latency_ms,
            error=None if response.status_code < 400 else f"HTTP {response.status_code}"
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return RequestResult(
            endpoint=endpoint,
            status_code=0,
            latency_ms=latency_ms,
            error=str(e)
        )


async def run_benchmark(
    base_url: str,
    endpoints: list[dict],
    concurrency: int,
    duration_seconds: int,
) -> dict[str, BenchmarkStats]:
    """Run benchmark with specified concurrency for duration."""

    try:
        import httpx
    except ImportError:
        print("ERROR: httpx not installed. Install with: pip install httpx")
        sys.exit(1)

    stats: dict[str, BenchmarkStats] = {
        ep["path"]: BenchmarkStats(endpoint=ep["path"]) for ep in endpoints
    }

    async with httpx.AsyncClient() as session:
        # Warmup
        print("Warming up...")
        for ep in endpoints:
            try:
                await make_request(session, base_url, ep["path"], ep.get("method", "GET"), ep.get("payload"))
            except Exception:
                pass

        print(f"Running benchmark for {duration_seconds}s with {concurrency} concurrent requests...")
        print("-" * 60)

        start_time = time.perf_counter()
        request_count = 0

        async def worker():
            nonlocal request_count
            while time.perf_counter() - start_time < duration_seconds:
                for ep in endpoints:
                    if time.perf_counter() - start_time >= duration_seconds:
                        break
                    result = await make_request(
                        session, base_url, ep["path"], ep.get("method", "GET"), ep.get("payload")
                    )
                    stats[ep["path"]].add_result(result)
                    request_count += 1

        # Run concurrent workers
        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await asyncio.gather(*workers)

        elapsed = time.perf_counter() - start_time
        print(f"\nCompleted {request_count} requests in {elapsed:.1f}s")
        print(f"Overall throughput: {request_count / elapsed:.1f} req/s")

    return stats


def print_results(stats: dict[str, BenchmarkStats]) -> None:
    """Print benchmark results in a formatted table."""
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    for endpoint, stat in stats.items():
        summary = stat.summary()
        print(f"\n📊 {endpoint}")
        print("-" * 40)
        print(f"  Total Requests:    {summary['total_requests']}")
        print(f"  Successful:        {summary['successful_requests']}")
        print(f"  Failed:            {summary['failed_requests']}")
        print(f"  Error Rate:        {summary['error_rate']:.2f}%")

        if summary['successful_requests'] > 0:
            print(f"  Latency P50:       {summary['latency_p50_ms']:.2f}ms")
            print(f"  Latency P95:       {summary['latency_p95_ms']:.2f}ms")
            print(f"  Latency P99:       {summary['latency_p99_ms']:.2f}ms")
            print(f"  Latency Mean:      {summary['latency_mean_ms']:.2f}ms")
            print(f"  Latency Min/Max:   {summary['latency_min_ms']:.2f}ms / {summary['latency_max_ms']:.2f}ms")

    print("\n" + "=" * 80)


def save_results(stats: dict[str, BenchmarkStats], output_file: Path) -> None:
    """Save benchmark results to JSON file."""
    results = {
        "generated_at": datetime.now().isoformat(),
        "endpoints": {name: stat.summary() for name, stat in stats.items()}
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")


def load_config() -> dict:
    """Load benchmark configuration from bench_config.yaml."""
    config_path = Path(__file__).parent / "bench_config.yaml"
    
    if not config_path.exists():
        return {
            "endpoints": [
                {"path": "/health", "method": "GET"},
                {"path": "/api/status", "method": "GET"},
            ],
            "e2e": {
                "concurrency": 5,
                "duration_seconds": 10
            }
        }

    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        print("WARNING: PyYAML not installed, using default configuration")
        return {
            "endpoints": [
                {"path": "/health", "method": "GET"},
            ],
            "e2e": {
                "concurrency": 5,
                "duration_seconds": 10
            }
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run end-to-end performance benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run against local dev server
    python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000

    # High concurrency test
    python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000 -c 50 -d 60

    # Quick smoke test
    python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000 -c 2 -d 5
        """
    )

    parser.add_argument(
        "--url", "-u",
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=None,
        help="Number of concurrent requests (default: from config or 5)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=None,
        help="Benchmark duration in seconds (default: from config or 10)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON file (default: benchmarks/results/e2e_TIMESTAMP.json)"
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config()
    e2e_config = config.get("e2e", {})

    concurrency = args.concurrency or e2e_config.get("concurrency", 5)
    duration = args.duration or e2e_config.get("duration_seconds", 10)
    endpoints = config.get("endpoints", [{"path": "/health", "method": "GET"}])

    # Setup output path
    if args.output:
        output_file = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = PROJECT_ROOT / "benchmarks" / "results" / f"e2e_{timestamp}.json"

    print(f"Target URL: {args.url}")
    print(f"Concurrency: {concurrency}")
    print(f"Duration: {duration}s")
    print(f"Endpoints: {[ep['path'] for ep in endpoints]}")

    # Run benchmark
    stats = asyncio.run(run_benchmark(args.url, endpoints, concurrency, duration))

    # Print and save results
    print_results(stats)
    save_results(stats, output_file)


if __name__ == "__main__":
    main()
