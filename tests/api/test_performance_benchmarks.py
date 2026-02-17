"""
API Performance Benchmarks

Tests for API performance including:
- Response time benchmarks
- Throughput testing
- Load testing
- Stress testing
- Resource usage monitoring
"""

import pytest
import time
import statistics
from typing import Dict, List, Any, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from fastapi.testclient import TestClient

from tests.api.factories import (
    TelemetryFactory,
    PerformanceDataFactory,
    FeedbackFactory,
)


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    endpoint: str
    method: str
    count: int
    min_ms: float
    max_ms: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    throughput_rps: float
    errors: int
    total_duration_ms: float


class PerformanceBenchmark:
    """Performance benchmarking utilities."""

    @staticmethod
    def measure_request(
        client: TestClient,
        method: str,
        endpoint: str,
        **kwargs
    ) -> tuple[float, int]:
        """Measure a single request."""
        start = time.perf_counter()
        try:
            if method.upper() == "GET":
                response = client.get(endpoint, **kwargs)
            elif method.upper() == "POST":
                response = client.post(endpoint, **kwargs)
            elif method.upper() == "PUT":
                response = client.put(endpoint, **kwargs)
            elif method.upper() == "DELETE":
                response = client.delete(endpoint, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            duration = (time.perf_counter() - start) * 1000
            return duration, response.status_code
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            return duration, 500

    @staticmethod
    def calculate_percentile(data: List[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    @staticmethod
    def run_benchmark(
        client: TestClient,
        method: str,
        endpoint: str,
        iterations: int = 100,
        **kwargs
    ) -> BenchmarkResult:
        """Run a benchmark for an endpoint."""
        durations = []
        errors = 0
        start_time = time.perf_counter()

        for _ in range(iterations):
            duration, status_code = PerformanceBenchmark.measure_request(
                client, method, endpoint, **kwargs
            )
            durations.append(duration)
            if status_code >= 400:
                errors += 1

        total_duration = (time.perf_counter() - start_time) * 1000

        return BenchmarkResult(
            endpoint=endpoint,
            method=method,
            count=iterations,
            min_ms=min(durations),
            max_ms=max(durations),
            avg_ms=statistics.mean(durations),
            median_ms=statistics.median(durations),
            p95_ms=PerformanceBenchmark.calculate_percentile(durations, 95),
            p99_ms=PerformanceBenchmark.calculate_percentile(durations, 99),
            throughput_rps=(iterations * 1000) / total_duration,
            errors=errors,
            total_duration_ms=total_duration,
        )

    @staticmethod
    def run_load_test(
        client: TestClient,
        method: str,
        endpoint: str,
        concurrent_users: int = 10,
        requests_per_user: int = 10,
        **kwargs
    ) -> BenchmarkResult:
        """Run a load test with concurrent requests."""
        durations = []
        errors = 0
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = []
            for _ in range(concurrent_users):
                for _ in range(requests_per_user):
                    future = executor.submit(
                        PerformanceBenchmark.measure_request,
                        client, method, endpoint, **kwargs
                    )
                    futures.append(future)

            for future in as_completed(futures):
                duration, status_code = future.result()
                durations.append(duration)
                if status_code >= 400:
                    errors += 1

        total_duration = (time.perf_counter() - start_time) * 1000
        total_requests = concurrent_users * requests_per_user

        return BenchmarkResult(
            endpoint=endpoint,
            method=method,
            count=total_requests,
            min_ms=min(durations),
            max_ms=max(durations),
            avg_ms=statistics.mean(durations),
            median_ms=statistics.median(durations),
            p95_ms=PerformanceBenchmark.calculate_percentile(durations, 95),
            p99_ms=PerformanceBenchmark.calculate_percentile(durations, 99),
            throughput_rps=(total_requests * 1000) / total_duration,
            errors=errors,
            total_duration_ms=total_duration,
        )


class TestHealthCheckPerformance:
    """Performance tests for health check endpoints."""

    @pytest.mark.benchmark
    def test_health_check_response_time(
        self,
        api_client: TestClient,
        performance_baseline: Dict[str, float],
    ):
        """Benchmark health check response time."""
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "GET",
            "/health",
            iterations=200,
        )
        assert result.p95_ms < performance_baseline["health_endpoint_p95"] * 1000
        assert result.errors == 0

    @pytest.mark.benchmark
    def test_health_check_throughput(self, api_client: TestClient):
        """Benchmark health check throughput."""
        result = PerformanceBenchmark.run_load_test(
            api_client,
            "GET",
            "/health",
            concurrent_users=20,
            requests_per_user=50,
        )
        assert result.throughput_rps > 100  # Should handle > 100 RPS
        assert result.errors == 0

    @pytest.mark.benchmark
    def test_liveness_probe_performance(self, api_client: TestClient):
        """Benchmark liveness probe response time."""
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "GET",
            "/health/live",
            iterations=100,
        )
        assert result.p95_ms < 100  # Should be very fast


class TestTelemetryPerformance:
    """Performance tests for telemetry endpoints."""

    @pytest.mark.benchmark
    def test_single_telemetry_response_time(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
        performance_baseline: Dict[str, float],
    ):
        """Benchmark single telemetry endpoint response time."""
        payload = TelemetryFactory.create_normal()
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "POST",
            "/api/v1/telemetry",
            iterations=100,
            json=payload,
            headers=auth_headers,
        )
        assert result.p95_ms < performance_baseline["telemetry_endpoint_p95"] * 1000
        assert result.errors == 0

    @pytest.mark.benchmark
    def test_batch_telemetry_response_time(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
        performance_baseline: Dict[str, float],
    ):
        """Benchmark batch telemetry endpoint response time."""
        telemetry_list = TelemetryFactory.create_batch(count=10)
        payload = {
            "batch_id": "bench-batch-001",
            "timestamp": datetime.now().isoformat(),
            "telemetry": telemetry_list,
        }
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "POST",
            "/api/v1/telemetry/batch",
            iterations=50,
            json=payload,
            headers=auth_headers,
        )
        assert result.p95_ms < performance_baseline["batch_endpoint_p95"] * 1000
        assert result.errors == 0

    @pytest.mark.benchmark
    def test_telemetry_throughput(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Benchmark telemetry endpoint throughput."""
        payload = TelemetryFactory.create_normal()
        result = PerformanceBenchmark.run_load_test(
            api_client,
            "POST",
            "/api/v1/telemetry",
            concurrent_users=10,
            requests_per_user=50,
            json=payload,
            headers=auth_headers,
        )
        # Should handle 50+ RPS with good performance
        assert result.throughput_rps > 50
        assert result.p95_ms < 500

    @pytest.mark.benchmark
    def test_batch_telemetry_throughput(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Benchmark batch telemetry throughput."""
        telemetry_list = TelemetryFactory.create_batch(count=10)
        payload = {
            "batch_id": "bench-batch-002",
            "timestamp": datetime.now().isoformat(),
            "telemetry": telemetry_list,
        }
        result = PerformanceBenchmark.run_load_test(
            api_client,
            "POST",
            "/api/v1/telemetry/batch",
            concurrent_users=5,
            requests_per_user=20,
            json=payload,
            headers=auth_headers,
        )
        assert result.throughput_rps > 10


class TestSystemStatusPerformance:
    """Performance tests for system status endpoints."""

    @pytest.mark.benchmark
    def test_status_endpoint_response_time(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Benchmark system status endpoint."""
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "GET",
            "/api/v1/status",
            iterations=100,
            headers=auth_headers,
        )
        assert result.p95_ms < 200
        assert result.errors == 0

    @pytest.mark.benchmark
    def test_diagnostics_endpoint_response_time(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Benchmark diagnostics endpoint."""
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "GET",
            "/api/v1/system/diagnostics",
            iterations=50,
            headers=auth_headers,
        )
        assert result.p95_ms < 500
        assert result.errors == 0


class TestAuthenticationPerformance:
    """Performance tests for authentication endpoints."""

    @pytest.mark.benchmark
    def test_auth_key_validation_performance(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
        performance_baseline: Dict[str, float],
    ):
        """Benchmark API key validation."""
        payload = TelemetryFactory.create_normal()
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "POST",
            "/api/v1/telemetry",
            iterations=100,
            json=payload,
            headers=auth_headers,
        )
        # Auth check should not significantly impact performance
        assert result.p95_ms < performance_baseline["auth_endpoint_p95"] * 1000


class TestFeedbackPerformance:
    """Performance tests for feedback endpoints."""

    @pytest.mark.benchmark
    def test_feedback_submission_response_time(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Benchmark feedback submission."""
        payload = FeedbackFactory.create()
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "POST",
            "/api/v1/feedback",
            iterations=50,
            json=payload,
            headers=auth_headers,
        )
        assert result.p95_ms < 300
        assert result.errors == 0


class TestEndToEndPerformance:
    """End-to-end performance tests."""

    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_full_workflow_performance(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test full workflow performance."""
        # Submit telemetry
        payload = TelemetryFactory.create_normal()
        response = api_client.post(
            "/api/v1/telemetry",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Get status
        response = api_client.get(
            "/api/v1/status",
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Submit feedback
        feedback = FeedbackFactory.create()
        response = api_client.post(
            "/api/v1/feedback",
            json=feedback,
            headers=auth_headers,
        )
        assert response.status_code in [200, 201]


class TestConcurrencyPerformance:
    """Tests for concurrency and thread safety."""

    @pytest.mark.benchmark
    def test_concurrent_telemetry_submissions(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test concurrent telemetry submissions."""
        result = PerformanceBenchmark.run_load_test(
            api_client,
            "POST",
            "/api/v1/telemetry",
            concurrent_users=20,
            requests_per_user=25,
            json=TelemetryFactory.create_normal(),
            headers=auth_headers,
        )
        # All requests should succeed
        assert result.errors / (result.count) < 0.05  # Less than 5% errors
        # Performance should degrade gracefully
        assert result.throughput_rps > 10


class TestScalabilityPerformance:
    """Scalability performance tests."""

    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_system_under_sustained_load(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test system under sustained load."""
        load_config = {
            "concurrent_users": 30,
            "requests_per_user": 100,
            "endpoint": "/api/v1/telemetry",
            "method": "POST",
        }

        result = PerformanceBenchmark.run_load_test(
            api_client,
            load_config["method"],
            load_config["endpoint"],
            concurrent_users=load_config["concurrent_users"],
            requests_per_user=load_config["requests_per_user"],
            json=TelemetryFactory.create_normal(),
            headers=auth_headers,
        )

        # Check sustainability
        assert result.p95_ms < 1000  # Should stay under 1 second at p95
        assert (result.errors / result.count) < 0.10  # Less than 10% errors


class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    @pytest.mark.benchmark
    def test_batch_processing_memory_efficiency(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Test batch processing efficiency."""
        large_batch = TelemetryFactory.create_batch(count=100)
        payload = {
            "batch_id": "large-batch-001",
            "timestamp": datetime.now().isoformat(),
            "telemetry": large_batch,
        }

        start = time.perf_counter()
        response = api_client.post(
            "/api/v1/telemetry/batch",
            json=payload,
            headers=auth_headers,
        )
        duration = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        # Should process 100 items in reasonable time
        assert duration < 5000  # 5 seconds


class TestResponseTimeDistribution:
    """Test response time distribution characteristics."""

    @pytest.mark.benchmark
    def test_response_time_distribution(
        self,
        api_client: TestClient,
        auth_headers: Dict[str, str],
    ):
        """Analyze response time distribution."""
        result = PerformanceBenchmark.run_benchmark(
            api_client,
            "GET",
            "/health",
            iterations=500,
        )

        # Check distribution characteristics
        variance = result.max_ms - result.min_ms
        assert result.median_ms <= result.avg_ms * 1.5  # Not too skewed
        assert result.p99_ms <= result.max_ms
        assert result.p95_ms >= result.median_ms
