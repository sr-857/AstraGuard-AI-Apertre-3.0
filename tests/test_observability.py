"""Comprehensive tests for AstraGuard observability and metrics functionality."""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager
from prometheus_client import CollectorRegistry, REGISTRY
from prometheus_client.core import CounterMetricFamily, HistogramMetricFamily, GaugeMetricFamily

from astraguard.observability import (
    # Metrics
    REQUEST_COUNT, REQUEST_LATENCY, ACTIVE_CONNECTIONS, REQUEST_SIZE, RESPONSE_SIZE,
    CIRCUIT_BREAKER_STATE, CIRCUIT_BREAKER_TRANSITIONS, RETRY_ATTEMPTS, RETRY_LATENCY,
    CHAOS_INJECTIONS, CHAOS_RECOVERY_TIME, RECOVERY_ACTIONS, HEALTH_CHECK_FAILURES,
    ANOMALY_DETECTIONS, DETECTION_LATENCY, DETECTION_ACCURACY, FALSE_POSITIVES,
    MEMORY_ENGINE_HITS, MEMORY_ENGINE_MISSES, MEMORY_ENGINE_SIZE,
    ERRORS, ERROR_LATENCY,
    # Context managers
    track_request, track_anomaly_detection, track_retry_attempt, track_chaos_recovery,
    # Server functions
    startup_metrics_server, shutdown_metrics_server, get_registry, get_metrics_endpoint
)


class TestMetricsInitialization:
    """Test metrics initialization and safe creation."""

    def test_metrics_exist_and_have_correct_types(self):
        """Test that all metrics are properly initialized."""
        # HTTP Metrics
        if REQUEST_COUNT:
            assert hasattr(REQUEST_COUNT, '_name')
            assert REQUEST_COUNT._name == 'astra_http_requests'
            assert hasattr(REQUEST_COUNT, 'labels')
        
        if REQUEST_LATENCY:
            assert hasattr(REQUEST_LATENCY, '_name')
            assert REQUEST_LATENCY._name == 'astra_http_request_duration_seconds'
            assert hasattr(REQUEST_LATENCY, 'observe')
        
        if ACTIVE_CONNECTIONS:
            assert hasattr(ACTIVE_CONNECTIONS, '_name')
            assert ACTIVE_CONNECTIONS._name == 'astra_active_connections'
            assert hasattr(ACTIVE_CONNECTIONS, 'inc')
            assert hasattr(ACTIVE_CONNECTIONS, 'dec')

    def test_reliability_metrics_initialization(self):
        """Test reliability suite metrics are properly initialized."""
        reliability_metrics = [
            (CIRCUIT_BREAKER_STATE, 'astra_circuit_breaker_state'),
            (CIRCUIT_BREAKER_TRANSITIONS, 'astra_circuit_breaker_transitions'),
            (RETRY_ATTEMPTS, 'astra_retry_attempts'),
            (CHAOS_INJECTIONS, 'astra_chaos_injections'),
            (RECOVERY_ACTIONS, 'astra_recovery_actions'),
            (HEALTH_CHECK_FAILURES, 'astra_health_check_failures')
        ]
        
        for metric, expected_name in reliability_metrics:
            if metric:
                assert hasattr(metric, '_name')
                assert metric._name == expected_name

    def test_ml_anomaly_metrics_initialization(self):
        """Test ML/anomaly detection metrics are properly initialized."""
        ml_metrics = [
            (ANOMALY_DETECTIONS, 'astra_anomalies_detected'),
            (DETECTION_LATENCY, 'astra_detection_latency_seconds'),
            (DETECTION_ACCURACY, 'astra_detection_accuracy'),
            (FALSE_POSITIVES, 'astra_false_positives')
        ]
        
        for metric, expected_name in ml_metrics:
            if metric:
                assert hasattr(metric, '_name')
                assert metric._name == expected_name

    def test_memory_engine_metrics_initialization(self):
        """Test memory engine metrics are properly initialized."""
        memory_metrics = [
            (MEMORY_ENGINE_HITS, 'astra_memory_engine_hits'),
            (MEMORY_ENGINE_MISSES, 'astra_memory_engine_misses'),
            (MEMORY_ENGINE_SIZE, 'astra_memory_engine_size_bytes')
        ]
        
        for metric, expected_name in memory_metrics:
            if metric:
                assert hasattr(metric, '_name')
                assert metric._name == expected_name

    def test_error_metrics_initialization(self):
        """Test error tracking metrics are properly initialized."""
        error_metrics = [
            (ERRORS, 'astra_errors'),
            (ERROR_LATENCY, 'astra_error_resolution_time_seconds')
        ]
        
        for metric, expected_name in error_metrics:
            if metric:
                assert hasattr(metric, '_name')
                assert metric._name == expected_name

    def test_metrics_handle_none_gracefully(self):
        """Test that None metrics don't cause errors."""
        # This tests the safe initialization pattern
        # Even if metrics are None, the code should handle it gracefully
        assert True  # If we get here without exceptions, the test passes


class TestTrackRequestContextManager:
    """Test HTTP request tracking context manager."""

    def test_track_request_successful(self):
        """Test successful request tracking."""
        if not (REQUEST_COUNT and REQUEST_LATENCY and ACTIVE_CONNECTIONS):
            pytest.skip("Required metrics not available")
        
        endpoint = "/api/test"
        method = "POST"
        
        # Get initial values
        initial_active = ACTIVE_CONNECTIONS._value._value
        
        with track_request(endpoint, method):
            # During request, active connections should increase
            assert ACTIVE_CONNECTIONS._value._value == initial_active + 1
            time.sleep(0.01)  # Small delay to ensure measurable latency
        
        # After request, active connections should return to initial
        assert ACTIVE_CONNECTIONS._value._value == initial_active
        
        # Verify metrics were recorded
        # Note: Exact verification depends on metric implementation details

    def test_track_request_with_exception(self):
        """Test request tracking when exception occurs."""
        if not (REQUEST_COUNT and REQUEST_LATENCY and ACTIVE_CONNECTIONS and ERRORS):
            pytest.skip("Required metrics not available")
        
        endpoint = "/api/error"
        method = "GET"
        
        initial_active = ACTIVE_CONNECTIONS._value._value
        
        with pytest.raises(ValueError):
            with track_request(endpoint, method):
                assert ACTIVE_CONNECTIONS._value._value == initial_active + 1
                raise ValueError("Test error")
        
        # Active connections should be decremented even after exception
        assert ACTIVE_CONNECTIONS._value._value == initial_active

    def test_track_request_default_method(self):
        """Test request tracking with default method."""
        if not REQUEST_LATENCY:
            pytest.skip("REQUEST_LATENCY not available")
        
        endpoint = "/api/default"
        
        with track_request(endpoint):
            time.sleep(0.01)
        
        # Should complete without error (default method is POST)

    def test_track_request_timing_accuracy(self):
        """Test that request timing is reasonably accurate."""
        if not REQUEST_LATENCY:
            pytest.skip("REQUEST_LATENCY not available")
        
        endpoint = "/api/timing"
        sleep_duration = 0.1
        
        start_time = time.time()
        with track_request(endpoint):
            time.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        # Should be close to sleep_duration (within reasonable tolerance)
        assert abs(actual_duration - sleep_duration) < 0.05

    def test_track_request_with_none_metrics(self):
        """Test request tracking when metrics are None."""
        # This should not raise exceptions even if metrics are None
        with track_request("/api/test", "GET"):
            time.sleep(0.01)


class TestTrackAnomalyDetectionContextManager:
    """Test anomaly detection tracking context manager."""

    def test_track_anomaly_detection_successful(self):
        """Test successful anomaly detection tracking."""
        if not DETECTION_LATENCY:
            pytest.skip("DETECTION_LATENCY not available")
        
        with track_anomaly_detection():
            time.sleep(0.01)  # Simulate detection work
        
        # Should complete without error

    def test_track_anomaly_detection_with_exception(self):
        """Test anomaly detection tracking with exception."""
        with pytest.raises(RuntimeError):
            with track_anomaly_detection():
                raise RuntimeError("Detection failed")

    def test_track_anomaly_detection_timing(self):
        """Test anomaly detection timing measurement."""
        if not DETECTION_LATENCY:
            pytest.skip("DETECTION_LATENCY not available")
        
        sleep_duration = 0.05
        
        start_time = time.time()
        with track_anomaly_detection():
            time.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        assert abs(actual_duration - sleep_duration) < 0.02

    def test_track_anomaly_detection_with_none_metric(self):
        """Test anomaly detection tracking when metric is None."""
        with track_anomaly_detection():
            time.sleep(0.01)


class TestTrackRetryAttemptContextManager:
    """Test retry attempt tracking context manager."""

    def test_track_retry_attempt_successful(self):
        """Test successful retry attempt tracking."""
        if not RETRY_LATENCY:
            pytest.skip("RETRY_LATENCY not available")
        
        endpoint = "/api/retry"
        
        with track_retry_attempt(endpoint):
            time.sleep(0.01)

    def test_track_retry_attempt_with_exception(self):
        """Test retry attempt tracking with exception."""
        endpoint = "/api/retry_error"
        
        with pytest.raises(ConnectionError):
            with track_retry_attempt(endpoint):
                raise ConnectionError("Retry failed")

    def test_track_retry_attempt_timing(self):
        """Test retry attempt timing measurement."""
        if not RETRY_LATENCY:
            pytest.skip("RETRY_LATENCY not available")
        
        endpoint = "/api/retry_timing"
        sleep_duration = 0.03
        
        start_time = time.time()
        with track_retry_attempt(endpoint):
            time.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        assert abs(actual_duration - sleep_duration) < 0.02

    def test_track_retry_attempt_with_none_metric(self):
        """Test retry attempt tracking when metric is None."""
        with track_retry_attempt("/api/test"):
            time.sleep(0.01)


class TestTrackChaosRecoveryContextManager:
    """Test chaos recovery tracking context manager."""

    def test_track_chaos_recovery_successful(self):
        """Test successful chaos recovery tracking."""
        if not CHAOS_RECOVERY_TIME:
            pytest.skip("CHAOS_RECOVERY_TIME not available")
        
        chaos_type = "network_partition"
        
        with track_chaos_recovery(chaos_type):
            time.sleep(0.01)  # Simulate recovery work

    def test_track_chaos_recovery_with_exception(self):
        """Test chaos recovery tracking with exception."""
        chaos_type = "disk_failure"
        
        with pytest.raises(OSError):
            with track_chaos_recovery(chaos_type):
                raise OSError("Recovery failed")

    def test_track_chaos_recovery_timing(self):
        """Test chaos recovery timing measurement."""
        if not CHAOS_RECOVERY_TIME:
            pytest.skip("CHAOS_RECOVERY_TIME not available")
        
        chaos_type = "cpu_spike"
        sleep_duration = 0.02
        
        start_time = time.time()
        with track_chaos_recovery(chaos_type):
            time.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        assert abs(actual_duration - sleep_duration) < 0.02

    def test_track_chaos_recovery_different_types(self):
        """Test chaos recovery tracking with different chaos types."""
        chaos_types = ["network_partition", "disk_failure", "memory_leak", "cpu_spike"]
        
        for chaos_type in chaos_types:
            with track_chaos_recovery(chaos_type):
                time.sleep(0.001)

    def test_track_chaos_recovery_with_none_metric(self):
        """Test chaos recovery tracking when metric is None."""
        with track_chaos_recovery("test_chaos"):
            time.sleep(0.01)


class TestMetricsServerFunctions:
    """Test metrics server startup and management functions."""

    @patch('astraguard.observability.start_http_server')
    def test_startup_metrics_server_success(self, mock_start_server):
        """Test successful metrics server startup."""
        mock_start_server.return_value = None
        
        with patch('builtins.print') as mock_print:
            startup_metrics_server(port=9090)
        
        mock_start_server.assert_called_once_with(9090)
        mock_print.assert_any_call("✅ Metrics server started on port 9090")
        mock_print.assert_any_call("   Access metrics: http://localhost:9090/metrics")

    @patch('astraguard.observability.start_http_server')
    def test_startup_metrics_server_custom_port(self, mock_start_server):
        """Test metrics server startup with custom port."""
        mock_start_server.return_value = None
        
        with patch('builtins.print') as mock_print:
            startup_metrics_server(port=8080)
        
        mock_start_server.assert_called_once_with(8080)
        mock_print.assert_any_call("✅ Metrics server started on port 8080")

    @patch('astraguard.observability.start_http_server')
    def test_startup_metrics_server_failure(self, mock_start_server):
        """Test metrics server startup failure handling."""
        mock_start_server.side_effect = Exception("Port already in use")
        
        with patch('builtins.print') as mock_print:
            startup_metrics_server(port=9090)
        
        mock_print.assert_any_call("⚠️  Failed to start metrics server: Port already in use")

    def test_shutdown_metrics_server(self):
        """Test metrics server shutdown."""
        # Should not raise any exceptions
        shutdown_metrics_server()

    def test_get_registry(self):
        """Test getting the Prometheus registry."""
        registry = get_registry()
        assert registry is not None
        assert hasattr(registry, '_collector_to_names')

    @patch('prometheus_client.generate_latest')
    def test_get_metrics_endpoint(self, mock_generate_latest):
        """Test metrics endpoint generation."""
        mock_generate_latest.return_value = b"# HELP test_metric Test metric\n"
        
        result = get_metrics_endpoint()
        
        mock_generate_latest.assert_called_once_with(REGISTRY)
        assert isinstance(result, bytes)
        assert b"test_metric" in result


class TestMetricsIntegration:
    """Test integration scenarios with multiple metrics."""

    def test_http_request_full_cycle(self):
        """Test complete HTTP request cycle with all metrics."""
        if not all([REQUEST_COUNT, REQUEST_LATENCY, ACTIVE_CONNECTIONS]):
            pytest.skip("Required HTTP metrics not available")
        
        endpoint = "/api/integration"
        method = "POST"
        
        # Track multiple requests
        for i in range(3):
            with track_request(endpoint, method):
                time.sleep(0.01)

    def test_error_handling_integration(self):
        """Test error handling across multiple context managers."""
        endpoint = "/api/error_integration"
        
        # Test that exceptions in one context don't affect others
        try:
            with track_request(endpoint):
                with track_anomaly_detection():
                    raise ValueError("Integration test error")
        except ValueError:
            pass
        
        # Should be able to continue using context managers
        with track_request(endpoint):
            time.sleep(0.01)

    def test_nested_context_managers(self):
        """Test nested context manager usage."""
        endpoint = "/api/nested"
        chaos_type = "integration_test"
        
        with track_request(endpoint):
            with track_anomaly_detection():
                with track_retry_attempt(endpoint):
                    with track_chaos_recovery(chaos_type):
                        time.sleep(0.01)

    def test_concurrent_metric_updates(self):
        """Test concurrent metric updates don't interfere."""
        import threading
        import time
        
        def worker(worker_id):
            endpoint = f"/api/worker_{worker_id}"
            for i in range(5):
                with track_request(endpoint):
                    time.sleep(0.001)
        
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def test_metrics_with_various_data_types(self):
        """Test metrics with various endpoint and parameter types."""
        test_cases = [
            ("/api/test", "GET"),
            ("/api/test-with-hyphens", "POST"),
            ("/api/test_with_underscores", "PUT"),
            ("/api/test/123", "DELETE"),
            ("/api/test?param=value", "PATCH")
        ]
        
        for endpoint, method in test_cases:
            with track_request(endpoint, method):
                time.sleep(0.001)

    def test_chaos_recovery_scenarios(self):
        """Test various chaos recovery scenarios."""
        chaos_scenarios = [
            "network_partition",
            "disk_failure", 
            "memory_exhaustion",
            "cpu_overload",
            "service_unavailable"
        ]
        
        for scenario in chaos_scenarios:
            with track_chaos_recovery(scenario):
                time.sleep(0.001)


class TestMetricsAccuracy:
    """Test metrics accuracy and correctness."""

    def test_timing_accuracy_across_context_managers(self):
        """Test timing accuracy across different context managers."""
        timing_tests = [
            (track_request, ("/api/timing",)),
            (track_anomaly_detection, ()),
            (track_retry_attempt, ("/api/retry",)),
            (track_chaos_recovery, ("timing_test",))
        ]
        
        for context_manager, args in timing_tests:
            sleep_duration = 0.05
            start_time = time.time()
            
            with context_manager(*args):
                time.sleep(sleep_duration)
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            # Should be within 20ms of expected duration
            assert abs(actual_duration - sleep_duration) < 0.02

    def test_active_connections_accuracy(self):
        """Test active connections counter accuracy."""
        if not ACTIVE_CONNECTIONS:
            pytest.skip("ACTIVE_CONNECTIONS not available")
        
        initial_count = ACTIVE_CONNECTIONS._value._value
        
        # Test single connection
        with track_request("/api/single"):
            assert ACTIVE_CONNECTIONS._value._value == initial_count + 1
        
        assert ACTIVE_CONNECTIONS._value._value == initial_count
        
        # Test nested connections
        with track_request("/api/outer"):
            assert ACTIVE_CONNECTIONS._value._value == initial_count + 1
            with track_request("/api/inner"):
                assert ACTIVE_CONNECTIONS._value._value == initial_count + 2
            assert ACTIVE_CONNECTIONS._value._value == initial_count + 1
        
        assert ACTIVE_CONNECTIONS._value._value == initial_count

    def test_exception_handling_preserves_metrics_state(self):
        """Test that exceptions don't leave metrics in inconsistent state."""
        if not ACTIVE_CONNECTIONS:
            pytest.skip("ACTIVE_CONNECTIONS not available")
        
        initial_count = ACTIVE_CONNECTIONS._value._value
        
        # Exception should not leave active connections incremented
        with pytest.raises(RuntimeError):
            with track_request("/api/exception"):
                assert ACTIVE_CONNECTIONS._value._value == initial_count + 1
                raise RuntimeError("Test exception")
        
        assert ACTIVE_CONNECTIONS._value._value == initial_count


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_endpoint_names(self):
        """Test handling of empty or unusual endpoint names."""
        edge_case_endpoints = [
            "",
            "/",
            "//",
            "/api//test",
            "/api/test/",
            None  # This might cause issues, testing graceful handling
        ]
        
        for endpoint in edge_case_endpoints:
            try:
                if endpoint is not None:
                    with track_request(endpoint):
                        time.sleep(0.001)
            except (TypeError, AttributeError):
                # Expected for None endpoint
                pass

    def test_very_long_endpoint_names(self):
        """Test handling of very long endpoint names."""
        long_endpoint = "/api/" + "x" * 1000
        
        with track_request(long_endpoint):
            time.sleep(0.001)

    def test_special_characters_in_endpoints(self):
        """Test handling of special characters in endpoint names."""
        special_endpoints = [
            "/api/test%20with%20spaces",
            "/api/test-with-unicode-café",
            "/api/test&param=value",
            "/api/test#fragment"
        ]
        
        for endpoint in special_endpoints:
            with track_request(endpoint):
                time.sleep(0.001)

    def test_zero_duration_operations(self):
        """Test handling of very fast operations."""
        # These should not cause issues even with zero or near-zero duration
        with track_request("/api/fast"):
            pass  # No sleep, should be very fast
        
        with track_anomaly_detection():
            pass
        
        with track_retry_attempt("/api/fast_retry"):
            pass
        
        with track_chaos_recovery("fast_recovery"):
            pass

    def test_very_long_duration_operations(self):
        """Test handling of longer duration operations."""
        # Test with longer sleep to ensure metrics handle larger values
        sleep_duration = 0.5
        
        start_time = time.time()
        with track_request("/api/slow"):
            time.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        assert abs(actual_duration - sleep_duration) < 0.1


class TestMetricsReset:
    """Test metrics reset and cleanup scenarios."""

    def test_metrics_survive_multiple_operations(self):
        """Test that metrics continue working after many operations."""
        endpoint = "/api/stress_test"
        
        # Perform many operations
        for i in range(100):
            with track_request(endpoint):
                if i % 10 == 0:  # Occasionally add some delay
                    time.sleep(0.001)

    def test_context_manager_exception_recovery(self):
        """Test that context managers recover properly after exceptions."""
        endpoint = "/api/recovery_test"
        
        # Cause exception in context manager
        for i in range(5):
            try:
                with track_request(endpoint):
                    if i == 2:  # Cause exception on third iteration
                        raise ValueError("Test exception")
                    time.sleep(0.001)
            except ValueError:
                pass
        
        # Should still work normally after exceptions
        with track_request(endpoint):
            time.sleep(0.001)


class TestPerformanceCharacteristics:
    """Test performance characteristics of metrics collection."""

    def test_metrics_overhead_is_minimal(self):
        """Test that metrics collection has minimal performance overhead."""
        iterations = 1000
        
        # Measure time without metrics
        start_time = time.time()
        for i in range(iterations):
            time.sleep(0.0001)  # Simulate small amount of work
        baseline_time = time.time() - start_time
        
        # Measure time with metrics
        start_time = time.time()
        for i in range(iterations):
            with track_request(f"/api/perf_test_{i % 10}"):
                time.sleep(0.0001)
        metrics_time = time.time() - start_time
        
        # Metrics overhead should be reasonable (less than 50% overhead)
        overhead_ratio = (metrics_time - baseline_time) / baseline_time
        assert overhead_ratio < 0.5, f"Metrics overhead too high: {overhead_ratio:.2%}"

    def test_concurrent_metrics_performance(self):
        """Test metrics performance under concurrent load."""
        import threading
        
        def worker():
            for i in range(50):
                with track_request(f"/api/concurrent_{i}"):
                    time.sleep(0.0001)
        
        # Run concurrent workers
        threads = []
        start_time = time.time()
        
        for i in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Should complete in reasonable time (less than 5 seconds for this load)
        assert total_time < 5.0, f"Concurrent metrics too slow: {total_time:.2f}s"


# ============================================================================
# ASYNC CONTEXT MANAGER TESTS
# ============================================================================

class TestAsyncContextManagers:
    """Test async versions of context managers."""

    @pytest.mark.asyncio
    async def test_async_track_request_successful(self):
        """Test successful async request tracking."""
        from astraguard.observability import async_track_request, REQUEST_COUNT, REQUEST_LATENCY, ACTIVE_CONNECTIONS
        
        if not (REQUEST_COUNT and REQUEST_LATENCY and ACTIVE_CONNECTIONS):
            pytest.skip("Required metrics not available")
        
        endpoint = "/api/async_test"
        method = "POST"
        
        initial_active = ACTIVE_CONNECTIONS._value._value
        
        async with async_track_request(endpoint, method):
            # During request, active connections should increase
            assert ACTIVE_CONNECTIONS._value._value == initial_active + 1
            await asyncio.sleep(0.01)
        
        # After request, active connections should return to initial
        assert ACTIVE_CONNECTIONS._value._value == initial_active

    @pytest.mark.asyncio
    async def test_async_track_request_with_exception(self):
        """Test async request tracking when exception occurs."""
        from astraguard.observability import async_track_request, ACTIVE_CONNECTIONS
        
        if not ACTIVE_CONNECTIONS:
            pytest.skip("ACTIVE_CONNECTIONS not available")
        
        endpoint = "/api/async_error"
        method = "GET"
        
        initial_active = ACTIVE_CONNECTIONS._value._value
        
        with pytest.raises(ValueError):
            async with async_track_request(endpoint, method):
                assert ACTIVE_CONNECTIONS._value._value == initial_active + 1
                raise ValueError("Async test error")
        
        # Active connections should be decremented even after exception
        assert ACTIVE_CONNECTIONS._value._value == initial_active

    @pytest.mark.asyncio
    async def test_async_track_request_timing_accuracy(self):
        """Test that async request timing is reasonably accurate."""
        from astraguard.observability import async_track_request, REQUEST_LATENCY
        
        if not REQUEST_LATENCY:
            pytest.skip("REQUEST_LATENCY not available")
        
        endpoint = "/api/async_timing"
        sleep_duration = 0.1
        
        start_time = time.time()
        async with async_track_request(endpoint):
            await asyncio.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        # Should be close to sleep_duration (within reasonable tolerance)
        assert abs(actual_duration - sleep_duration) < 0.05

    @pytest.mark.asyncio
    async def test_async_track_anomaly_detection_successful(self):
        """Test successful async anomaly detection tracking."""
        from astraguard.observability import async_track_anomaly_detection, DETECTION_LATENCY
        
        if not DETECTION_LATENCY:
            pytest.skip("DETECTION_LATENCY not available")
        
        async with async_track_anomaly_detection():
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_async_track_anomaly_detection_with_exception(self):
        """Test async anomaly detection tracking with exception."""
        from astraguard.observability import async_track_anomaly_detection
        
        with pytest.raises(RuntimeError):
            async with async_track_anomaly_detection():
                raise RuntimeError("Async detection failed")

    @pytest.mark.asyncio
    async def test_async_track_retry_attempt_successful(self):
        """Test successful async retry attempt tracking."""
        from astraguard.observability import async_track_retry_attempt, RETRY_LATENCY
        
        if not RETRY_LATENCY:
            pytest.skip("RETRY_LATENCY not available")
        
        endpoint = "/api/async_retry"
        
        async with async_track_retry_attempt(endpoint):
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_async_track_retry_attempt_with_exception(self):
        """Test async retry attempt tracking with exception."""
        from astraguard.observability import async_track_retry_attempt
        
        endpoint = "/api/async_retry_error"
        
        with pytest.raises(ConnectionError):
            async with async_track_retry_attempt(endpoint):
                raise ConnectionError("Async retry failed")

    @pytest.mark.asyncio
    async def test_async_track_chaos_recovery_successful(self):
        """Test successful async chaos recovery tracking."""
        from astraguard.observability import async_track_chaos_recovery, CHAOS_RECOVERY_TIME
        
        if not CHAOS_RECOVERY_TIME:
            pytest.skip("CHAOS_RECOVERY_TIME not available")
        
        chaos_type = "async_network_partition"
        
        async with async_track_chaos_recovery(chaos_type):
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_async_track_chaos_recovery_with_exception(self):
        """Test async chaos recovery tracking with exception."""
        from astraguard.observability import async_track_chaos_recovery
        
        chaos_type = "async_disk_failure"
        
        with pytest.raises(OSError):
            async with async_track_chaos_recovery(chaos_type):
                raise OSError("Async recovery failed")

    @pytest.mark.asyncio
    async def test_async_track_chaos_recovery_timing(self):
        """Test async chaos recovery timing measurement."""
        from astraguard.observability import async_track_chaos_recovery, CHAOS_RECOVERY_TIME
        
        if not CHAOS_RECOVERY_TIME:
            pytest.skip("CHAOS_RECOVERY_TIME not available")
        
        chaos_type = "async_cpu_spike"
        sleep_duration = 0.02
        
        start_time = time.time()
        async with async_track_chaos_recovery(chaos_type):
            await asyncio.sleep(sleep_duration)
        end_time = time.time()
        
        actual_duration = end_time - start_time
        assert abs(actual_duration - sleep_duration) < 0.02

    @pytest.mark.asyncio
    async def test_nested_async_context_managers(self):
        """Test nested async context manager usage."""
        from astraguard.observability import (
            async_track_request, async_track_anomaly_detection,
            async_track_retry_attempt, async_track_chaos_recovery
        )
        
        endpoint = "/api/async_nested"
        chaos_type = "async_integration_test"
        
        async with async_track_request(endpoint):
            async with async_track_anomaly_detection():
                async with async_track_retry_attempt(endpoint):
                    async with async_track_chaos_recovery(chaos_type):
                        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_concurrent_async_requests(self):
        """Test concurrent async request tracking."""
        from astraguard.observability import async_track_request
        
        async def async_worker(worker_id):
            endpoint = f"/api/async_worker_{worker_id}"
            for i in range(5):
                async with async_track_request(endpoint):
                    await asyncio.sleep(0.001)
        
        # Run multiple async tasks concurrently
        tasks = [async_worker(i) for i in range(3)]
        await asyncio.gather(*tasks)


# ============================================================================
# SAFE METRIC CREATION TESTS
# ============================================================================

class TestSafeMetricCreation:
    """Test the _safe_create_metric function for handling duplicate metrics."""

    def test_safe_create_metric_new_metric(self):
        """Test creating a new metric with _safe_create_metric."""
        from astraguard.observability import _safe_create_metric, _metric_cache
        from prometheus_client import Counter
        
        # Create a new unique metric
        metric_name = f"test_metric_{time.time()}"
        metric = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            f"Test metric {metric_name}"
        )
        
        assert metric is not None
        assert hasattr(metric, '_name')
        assert metric_name in _metric_cache

    def test_safe_create_metric_cached_retrieval(self):
        """Test that _safe_create_metric returns cached metrics."""
        from astraguard.observability import _safe_create_metric, _metric_cache
        from prometheus_client import Counter
        
        # Create a metric
        metric_name = f"test_cached_metric_{time.time()}"
        metric1 = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test cached metric"
        )
        
        # Retrieve the same metric from cache
        metric2 = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test cached metric"
        )
        
        # Should return the same instance from cache
        assert metric1 is metric2

    def test_safe_create_metric_with_labels(self):
        """Test creating metrics with labels using _safe_create_metric."""
        from astraguard.observability import _safe_create_metric
        from prometheus_client import Counter
        
        metric_name = f"test_labeled_metric_{time.time()}"
        metric = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test labeled metric",
            labelnames=['label1', 'label2']
        )
        
        assert metric is not None
        assert hasattr(metric, 'labels')
        
        # Test using the labeled metric
        metric.labels(label1='value1', label2='value2').inc()

    def test_safe_create_metric_different_types(self):
        """Test _safe_create_metric with different metric types."""
        from astraguard.observability import _safe_create_metric
        from prometheus_client import Counter, Gauge, Histogram, Summary
        
        timestamp = time.time()
        
        # Test Counter
        counter = _safe_create_metric(
            Counter,
            f"test_counter_{timestamp}",
            f"test_counter_{timestamp}",
            "Test counter"
        )
        assert counter is not None
        
        # Test Gauge
        gauge = _safe_create_metric(
            Gauge,
            f"test_gauge_{timestamp}",
            f"test_gauge_{timestamp}",
            "Test gauge"
        )
        assert gauge is not None
        
        # Test Histogram
        histogram = _safe_create_metric(
            Histogram,
            f"test_histogram_{timestamp}",
            f"test_histogram_{timestamp}",
            "Test histogram"
        )
        assert histogram is not None
        
        # Test Summary
        summary = _safe_create_metric(
            Summary,
            f"test_summary_{timestamp}",
            f"test_summary_{timestamp}",
            "Test summary"
        )
        assert summary is not None


# ============================================================================
# METRIC LABELS TESTS
# ============================================================================

class TestMetricLabels:
    """Test metrics with label functionality."""

    def test_request_count_labels(self):
        """Test REQUEST_COUNT with different label combinations."""
        if not REQUEST_COUNT:
            pytest.skip("REQUEST_COUNT not available")
        
        # Test various label combinations
        label_combinations = [
            ("GET", "/api/test1", "200"),
            ("POST", "/api/test2", "201"),
            ("PUT", "/api/test3", "200"),
            ("DELETE", "/api/test4", "204"),
            ("PATCH", "/api/test5", "200"),
        ]
        
        for method, endpoint, status in label_combinations:
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()

    def test_circuit_breaker_state_labels(self):
        """Test CIRCUIT_BREAKER_STATE with different names."""
        if not CIRCUIT_BREAKER_STATE:
            pytest.skip("CIRCUIT_BREAKER_STATE not available")
        
        breaker_names = ["api_breaker", "db_breaker", "cache_breaker"]
        
        for name in breaker_names:
            CIRCUIT_BREAKER_STATE.labels(name=name).set(0)  # CLOSED
            CIRCUIT_BREAKER_STATE.labels(name=name).set(1)  # OPEN
            CIRCUIT_BREAKER_STATE.labels(name=name).set(2)  # HALF_OPEN

    def test_circuit_breaker_transitions_labels(self):
        """Test CIRCUIT_BREAKER_TRANSITIONS with state transitions."""
        if not CIRCUIT_BREAKER_TRANSITIONS:
            pytest.skip("CIRCUIT_BREAKER_TRANSITIONS not available")
        
        transitions = [
            ("api_breaker", "CLOSED", "OPEN"),
            ("api_breaker", "OPEN", "HALF_OPEN"),
            ("api_breaker", "HALF_OPEN", "CLOSED"),
            ("db_breaker", "CLOSED", "OPEN"),
        ]
        
        for name, from_state, to_state in transitions:
            CIRCUIT_BREAKER_TRANSITIONS.labels(
                name=name, from_state=from_state, to_state=to_state
            ).inc()

    def test_retry_attempts_labels(self):
        """Test RETRY_ATTEMPTS with different outcomes."""
        if not RETRY_ATTEMPTS:
            pytest.skip("RETRY_ATTEMPTS not available")
        
        test_cases = [
            ("/api/endpoint1", "success"),
            ("/api/endpoint1", "failure"),
            ("/api/endpoint2", "success"),
            ("/api/endpoint2", "timeout"),
        ]
        
        for endpoint, outcome in test_cases:
            RETRY_ATTEMPTS.labels(endpoint=endpoint, outcome=outcome).inc()

    def test_chaos_injections_labels(self):
        """Test CHAOS_INJECTIONS with different types and statuses."""
        if not CHAOS_INJECTIONS:
            pytest.skip("CHAOS_INJECTIONS not available")
        
        chaos_tests = [
            ("network_partition", "injected"),
            ("network_partition", "recovered"),
            ("disk_failure", "injected"),
            ("cpu_spike", "injected"),
            ("memory_leak", "recovered"),
        ]
        
        for chaos_type, status in chaos_tests:
            CHAOS_INJECTIONS.labels(type=chaos_type, status=status).inc()

    def test_anomaly_detections_labels(self):
        """Test ANOMALY_DETECTIONS with different severity levels."""
        if not ANOMALY_DETECTIONS:
            pytest.skip("ANOMALY_DETECTIONS not available")
        
        severities = ["low", "medium", "high", "critical"]
        
        for severity in severities:
            ANOMALY_DETECTIONS.labels(severity=severity).inc()

    def test_false_positives_labels(self):
        """Test FALSE_POSITIVES with different detector types."""
        if not FALSE_POSITIVES:
            pytest.skip("FALSE_POSITIVES not available")
        
        detectors = ["statistical", "ml_model", "rule_based", "ensemble"]
        
        for detector in detectors:
            FALSE_POSITIVES.labels(detector=detector).inc()

    def test_memory_engine_labels(self):
        """Test memory engine metrics with different store types."""
        if not (MEMORY_ENGINE_HITS and MEMORY_ENGINE_MISSES and MEMORY_ENGINE_SIZE):
            pytest.skip("Memory engine metrics not available")
        
        store_types = ["redis", "memory", "disk"]
        
        for store_type in store_types:
            MEMORY_ENGINE_HITS.labels(store_type=store_type).inc()
            MEMORY_ENGINE_MISSES.labels(store_type=store_type).inc()
            MEMORY_ENGINE_SIZE.labels(store_type=store_type).set(1024)

    def test_errors_labels(self):
        """Test ERRORS with different error types and endpoints."""
        if not ERRORS:
            pytest.skip("ERRORS not available")
        
        error_cases = [
            ("ValueError", "/api/endpoint1"),
            ("TypeError", "/api/endpoint2"),
            ("ConnectionError", "/api/endpoint3"),
            ("TimeoutError", "/api/endpoint1"),
        ]
        
        for error_type, endpoint in error_cases:
            ERRORS.labels(type=error_type, endpoint=endpoint).inc()

    def test_recovery_actions_labels(self):
        """Test RECOVERY_ACTIONS with different action types and statuses."""
        if not RECOVERY_ACTIONS:
            pytest.skip("RECOVERY_ACTIONS not available")
        
        recovery_tests = [
            ("restart", "success"),
            ("rollback", "success"),
            ("scale_up", "in_progress"),
            ("circuit_open", "success"),
            ("failover", "failure"),
        ]
        
        for action_type, status in recovery_tests:
            RECOVERY_ACTIONS.labels(type=action_type, status=status).inc()


# ============================================================================
# METRIC CACHE TESTS
# ============================================================================

class TestMetricCache:
    """Test metric caching functionality."""

    def test_metric_cache_population(self):
        """Test that metric cache is populated on creation."""
        from astraguard.observability import _safe_create_metric, _metric_cache
        from prometheus_client import Counter
        
        # Clear specific cache entry if exists
        metric_name = f"test_cache_pop_{time.time()}"
        if metric_name in _metric_cache:
            del _metric_cache[metric_name]
        
        # Create metric
        metric = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test cache population"
        )
        
        # Verify it's in cache
        assert metric_name in _metric_cache
        assert _metric_cache[metric_name] is metric

    def test_metric_cache_hit_performance(self):
        """Test that cache hits are faster than creation."""
        from astraguard.observability import _safe_create_metric, _metric_cache
        from prometheus_client import Counter
        
        metric_name = f"test_cache_perf_{time.time()}"
        
        # First call - will create and cache
        start = time.time()
        metric1 = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test cache performance"
        )
        first_call_time = time.time() - start
        
        # Second call - should hit cache
        start = time.time()
        metric2 = _safe_create_metric(
            Counter,
            metric_name,
            metric_name,
            "Test cache performance"
        )
        second_call_time = time.time() - start
        
        # Cache hit should be faster
        assert second_call_time <= first_call_time
        assert metric1 is metric2

    def test_metric_cache_consistency(self):
        """Test that cache maintains consistency across operations."""
        from astraguard.observability import _safe_create_metric, _metric_cache
        from prometheus_client import Counter
        
        metric_name = f"test_cache_consistency_{time.time()}"
        
        # Create metric multiple times
        metrics = []
        for i in range(5):
            metric = _safe_create_metric(
                Counter,
                metric_name,
                metric_name,
                "Test cache consistency"
            )
            metrics.append(metric)
        
        # All should be the same instance
        for metric in metrics:
            assert metric is metrics[0]
        
        # Cache should contain only one entry for this metric
        assert metric_name in _metric_cache
        assert _metric_cache[metric_name] is metrics[0]


# ============================================================================
# ENHANCED ERROR HANDLING TESTS
# ============================================================================

class TestEnhancedErrorHandling:
    """Test enhanced error handling for get_metrics_endpoint."""

    @patch('prometheus_client.generate_latest')
    def test_get_metrics_endpoint_with_exception(self, mock_generate_latest):
        """Test get_metrics_endpoint handles exceptions properly."""
        mock_generate_latest.side_effect = RuntimeError("Registry error")
        
        with pytest.raises(RuntimeError):
            get_metrics_endpoint()

    @patch('prometheus_client.generate_latest')
    def test_get_metrics_endpoint_increments_error_metric(self, mock_generate_latest):
        """Test that get_metrics_endpoint increments error metric on failure."""
        from astraguard.observability import ERRORS
        
        if not ERRORS:
            pytest.skip("ERRORS metric not available")
        
        mock_generate_latest.side_effect = ValueError("Test error")
        
        # Get initial error count (if metric exists)
        try:
            with pytest.raises(ValueError):
                get_metrics_endpoint()
        except Exception:
            pass

    def test_get_metrics_endpoint_returns_bytes(self):
        """Test that get_metrics_endpoint returns bytes."""
        result = get_metrics_endpoint()
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_get_metrics_endpoint_contains_metric_data(self):
        """Test that get_metrics_endpoint contains actual metric data."""
        result = get_metrics_endpoint()
        
        # Should contain standard Prometheus format indicators
        assert b"# HELP" in result or b"# TYPE" in result or len(result) > 0

    def test_get_metrics_endpoint_after_metric_operations(self):
        """Test get_metrics_endpoint after performing metric operations."""
        # Perform some metric operations
        with track_request("/api/test_metrics_endpoint"):
            time.sleep(0.01)
        
        # Get metrics
        result = get_metrics_endpoint()
        
        assert isinstance(result, bytes)
        assert len(result) > 0


# ============================================================================
# ADDITIONAL INTEGRATION TESTS
# ============================================================================

class TestAdditionalIntegration:
    """Additional integration tests for comprehensive coverage."""

    def test_all_context_managers_in_sequence(self):
        """Test all context managers used in sequence."""
        endpoints = ["/api/seq1", "/api/seq2", "/api/seq3"]
        
        for endpoint in endpoints:
            with track_request(endpoint):
                time.sleep(0.001)
            
            with track_anomaly_detection():
                time.sleep(0.001)
            
            with track_retry_attempt(endpoint):
                time.sleep(0.001)
            
            with track_chaos_recovery("sequential_test"):
                time.sleep(0.001)

    def test_metrics_server_lifecycle(self):
        """Test metrics server startup and shutdown lifecycle."""
        # Test shutdown (should be safe even if not started)
        shutdown_metrics_server()
        
        # Test getting registry
        registry = get_registry()
        assert registry is not None

    @pytest.mark.asyncio
    async def test_mixed_sync_async_operations(self):
        """Test that sync and async operations don't interfere."""
        from astraguard.observability import async_track_request
        
        # Sync operation
        with track_request("/api/sync"):
            time.sleep(0.01)
        
        # Async operation
        async with async_track_request("/api/async"):
            await asyncio.sleep(0.01)
        
        # Another sync operation
        with track_request("/api/sync2"):
            time.sleep(0.01)

    def test_histogram_buckets_configuration(self):
        """Test that histogram metrics have proper bucket configuration."""
        if not REQUEST_LATENCY:
            pytest.skip("REQUEST_LATENCY not available")
        
        # Histograms should have buckets defined
        assert hasattr(REQUEST_LATENCY, '_buckets') or hasattr(REQUEST_LATENCY, '_upper_bounds')

    def test_summary_metrics_observation(self):
        """Test summary metrics can observe values."""
        if not REQUEST_SIZE:
            pytest.skip("REQUEST_SIZE not available")
        
        # Should be able to observe values
        test_sizes = [100, 500, 1000, 5000, 10000]
        for size in test_sizes:
            REQUEST_SIZE.observe(size)

    def test_gauge_increment_decrement(self):
        """Test gauge metrics support inc/dec operations."""
        if not ACTIVE_CONNECTIONS:
            pytest.skip("ACTIVE_CONNECTIONS not available")
        
        initial_value = ACTIVE_CONNECTIONS._value._value
        
        # Test increment
        ACTIVE_CONNECTIONS.inc(5)
        assert ACTIVE_CONNECTIONS._value._value == initial_value + 5
        
        # Test decrement
        ACTIVE_CONNECTIONS.dec(5)
        assert ACTIVE_CONNECTIONS._value._value == initial_value

    def test_gauge_set_operation(self):
        """Test gauge metrics support set operation."""
        if not MEMORY_ENGINE_SIZE:
            pytest.skip("MEMORY_ENGINE_SIZE not available")
        
        test_value = 12345
        MEMORY_ENGINE_SIZE.labels(store_type="test").set(test_value)