"""
MetricsSink Interface and Implementations

Provides a pluggable abstraction for metric emission:
- MetricsSink: Abstract interface for sinks
- NoOpMetricsSink: For tests (does nothing)
- LoggingMetricsSink: Logs metrics to standard logger
- PrometheusMetricsSink: Wraps Prometheus client
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsSink(ABC):
    """Abstract interface for metric emission.

    Implementations should handle the actual metric storage/transmission.
    """

    @abstractmethod
    def emit(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Emit a gauge-style metric.

        Args:
            name: Metric name (e.g., "astraguard_circuit_breaker_state")
            value: Metric value
            tags: Optional key-value pairs for labeling
            timestamp: Optional timestamp (defaults to now)
        """
        ...

    @abstractmethod
    def emit_counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Emit a counter metric (increment).

        Args:
            name: Metric name
            value: Increment amount (default 1)
            tags: Optional key-value pairs for labeling
        """
        ...

    @abstractmethod
    def emit_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Emit a histogram observation.

        Args:
            name: Metric name
            value: Observed value
            tags: Optional key-value pairs for labeling
        """
        ...

    def emit_health_check(
        self,
        check_name: str,
        status: str,
        latency_ms: float
    ) -> None:
        """Convenience method for emitting health check metrics.

        Args:
            check_name: Name of the health check
            status: Status string (healthy, degraded, unhealthy)
            latency_ms: Check latency in milliseconds
        """
        status_value = {"healthy": 1, "degraded": 0.5, "unhealthy": 0}.get(status, -1)
        self.emit(f"health_check_{check_name}_status", status_value)
        self.emit_histogram(f"health_check_{check_name}_latency_ms", latency_ms)


class NoOpMetricsSink(MetricsSink):
    """No-op sink for tests - swallows all metrics."""

    def emit(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Swallow metric."""
        pass

    def emit_counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Swallow counter."""
        pass

    def emit_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Swallow histogram."""
        pass


class LoggingMetricsSink(MetricsSink):
    """Sink that logs metrics to standard logger."""

    def __init__(self, log_level: int = logging.DEBUG):
        self.log_level = log_level

    def _format_tags(self, tags: Optional[Dict[str, str]]) -> str:
        """Format tags for logging."""
        if not tags:
            return ""
        return " " + " ".join(f"{k}={v}" for k, v in tags.items())

    def emit(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Log gauge metric."""
        ts = timestamp or datetime.utcnow()
        logger.log(
            self.log_level,
            f"METRIC gauge {name}={value}{self._format_tags(tags)} ts={ts.isoformat()}"
        )

    def emit_counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Log counter metric."""
        logger.log(
            self.log_level,
            f"METRIC counter {name}+={value}{self._format_tags(tags)}"
        )

    def emit_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Log histogram observation."""
        logger.log(
            self.log_level,
            f"METRIC histogram {name}={value}{self._format_tags(tags)}"
        )


class PrometheusMetricsSink(MetricsSink):
    """Sink that uses Prometheus client library.

    This wraps the existing Prometheus metrics from core.metrics.
    """

    def __init__(self, registry: Optional[Any] = None):
        """Initialize with optional custom registry.

        Args:
            registry: Prometheus registry (defaults to core.metrics.REGISTRY)
        """
        self._gauges: Dict[str, Any] = {}
        self._counters: Dict[str, Any] = {}
        self._histograms: Dict[str, Any] = {}

        if registry is None:
            try:
                from core.metrics import REGISTRY
                self.registry = REGISTRY
            except ImportError:
                from prometheus_client import REGISTRY as DEFAULT_REGISTRY
                self.registry = DEFAULT_REGISTRY
        else:
            self.registry = registry

    def _get_or_create_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Any:
        """Get or create a Prometheus Gauge."""
        from prometheus_client import Gauge

        label_names = tuple(sorted(tags.keys())) if tags else ()
        key = (name, label_names)

        if key not in self._gauges:
            self._gauges[key] = Gauge(
                name,
                f"Gauge metric: {name}",
                labelnames=label_names,
                registry=self.registry
            )
        return self._gauges[key]

    def _get_or_create_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> Any:
        """Get or create a Prometheus Counter."""
        from prometheus_client import Counter

        label_names = tuple(sorted(tags.keys())) if tags else ()
        key = (name, label_names)

        if key not in self._counters:
            self._counters[key] = Counter(
                name,
                f"Counter metric: {name}",
                labelnames=label_names,
                registry=self.registry
            )
        return self._counters[key]

    def _get_or_create_histogram(self, name: str, tags: Optional[Dict[str, str]] = None) -> Any:
        """Get or create a Prometheus Histogram."""
        from prometheus_client import Histogram

        label_names = tuple(sorted(tags.keys())) if tags else ()
        key = (name, label_names)

        if key not in self._histograms:
            self._histograms[key] = Histogram(
                name,
                f"Histogram metric: {name}",
                labelnames=label_names,
                registry=self.registry
            )
        return self._histograms[key]

    def emit(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Emit gauge metric to Prometheus."""
        try:
            gauge = self._get_or_create_gauge(name, tags)
            if tags:
                gauge.labels(**tags).set(value)
            else:
                gauge.set(value)
        except Exception as e:
            logger.warning(f"Failed to emit Prometheus gauge {name}: {e}")

    def emit_counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Emit counter metric to Prometheus."""
        try:
            counter = self._get_or_create_counter(name, tags)
            if tags:
                counter.labels(**tags).inc(value)
            else:
                counter.inc(value)
        except Exception as e:
            logger.warning(f"Failed to emit Prometheus counter {name}: {e}")

    def emit_histogram(
        self,
        name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Emit histogram observation to Prometheus."""
        try:
            histogram = self._get_or_create_histogram(name, tags)
            if tags:
                histogram.labels(**tags).observe(value)
            else:
                histogram.observe(value)
        except Exception as e:
            logger.warning(f"Failed to emit Prometheus histogram {name}: {e}")
