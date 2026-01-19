"""
Health Monitor API & Observability

Provides comprehensive health status of AstraGuard AI system:
- Real-time circuit breaker state
- Retry failure tracking (1h window)
- Fallback mode detection
- Component health aggregation
- Prometheus metrics endpoint
- Pluggable MetricsSink for metric emission
- Registrable HealthCheck instances

Integrates with Issue #14 (CircuitBreaker) and #15 (Retry).
Refactored for Issue #445 with HealthCheck and MetricsSink abstractions.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import time
from threading import Lock

from fastapi import APIRouter, Response, HTTPException
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge

# Import from core modules
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.component_health import SystemHealthMonitor, HealthStatus
from core.metrics import REGISTRY
from core.resource_monitor import get_resource_monitor

from backend.health.checks import HealthCheck, HealthCheckResult, HealthCheckStatus
from backend.health.sinks import MetricsSink, NoOpMetricsSink

logger = logging.getLogger(__name__)


class FallbackMode(str, Enum):
    """Fallback cascade modes"""

    PRIMARY = "primary"
    HEURISTIC = "heuristic"
    SAFE = "safe"


# ============================================================================
# METRICS
# ============================================================================

FALLBACK_MODE_GAUGE = Gauge(
    "astraguard_fallback_mode",
    "Current fallback mode (0=primary, 1=heuristic, 2=safe)",
    registry=REGISTRY,
)

HEALTH_CHECK_DURATION = Gauge(
    "astraguard_health_check_duration_seconds",
    "Time to complete health check",
    registry=REGISTRY,
)

# ============================================================================
# HEALTH MONITOR CLASS
# ============================================================================


class HealthMonitor:
    """
    Centralized health monitoring and observability engine.

    Tracks:
    - Circuit breaker state and open duration
    - Retry failures over time window
    - Fallback mode cascade status
    - Component health aggregation
    - System uptime
    - Registered health checks

    Thread-safe with background health polling.
    Supports pluggable MetricsSink for metric emission.
    """

    def __init__(
        self,
        circuit_breaker=None,
        retry_tracker=None,
        failure_window_seconds: int = 3600,
        metrics_sink: Optional[MetricsSink] = None,
    ):
        """
        Initialize health monitor.

        Args:
            circuit_breaker: Optional CircuitBreaker instance from issue #14
            retry_tracker: Optional retry failure tracker from issue #15
            failure_window_seconds: Time window for retry failure tracking (default: 1 hour)
            metrics_sink: Optional MetricsSink for metric emission (default: NoOpMetricsSink)
        """
        self.cb = circuit_breaker
        self.retry_tracker = retry_tracker
        self.failure_window_seconds = failure_window_seconds
        self.metrics_sink = metrics_sink or NoOpMetricsSink()

        self.fallback_mode = FallbackMode.PRIMARY
        self.component_health = SystemHealthMonitor()
        self.resource_monitor = get_resource_monitor()
        self.start_time = datetime.utcnow()

        self._lock = Lock()
        self._fallback_lock = Lock()
        self._retry_failures: List[datetime] = []
        self._fallback_cascade_log: List[Dict[str, Any]] = []
        self._cascade_log_max_size: int = 100  # Limit cascade log size

        # Registered health checks
        self._health_checks: Dict[str, HealthCheck] = {}

        logger.info("HealthMonitor initialized with MetricsSink injection")

    def register_check(self, check: HealthCheck) -> None:
        """
        Register a health check.

        Args:
            check: HealthCheck instance to register
        """
        with self._lock:
            self._health_checks[check.name] = check
            logger.info(f"Registered health check: {check.name}")

    def unregister_check(self, name: str) -> None:
        """
        Unregister a health check by name.

        Args:
            name: Name of the check to remove
        """
        with self._lock:
            if name in self._health_checks:
                del self._health_checks[name]
                logger.info(f"Unregistered health check: {name}")

    async def run_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks.

        Returns:
            Dict mapping check names to their results
        """
        results = {}
        with self._lock:
            checks = dict(self._health_checks)

        for name, check in checks.items():
            try:
                result = await check.check()
                results[name] = result
                # Emit metrics via sink
                self.metrics_sink.emit_health_check(
                    name, result.status.value, result.latency_ms
                )
            except Exception as e:
                logger.error(f"Error running health check {name}: {e}")
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthCheckStatus.UNKNOWN,
                    message=f"Check failed: {e}",
                )

        return results

    async def get_comprehensive_state(self) -> Dict[str, Any]:
        """
        Get comprehensive health snapshot for dashboard.

        Returns:
            Dict with system state, metrics, and component health
        """
        start = time.time()

        try:
            # Run registered health checks
            check_results = await self.run_checks()

            state = {
                "timestamp": datetime.utcnow().isoformat(),
                "system": self._get_system_health(),
                "circuit_breaker": self._get_circuit_breaker_state(),
                "retry": self._get_retry_metrics(),
                "resources": self._get_resource_health(),
                "fallback": {
                    "mode": self._get_fallback_mode_safe(),
                    "cascade_log": self._get_cascade_log_safe(),  # Last 10 entries
                },
                "components": self._get_components_health(),
                "health_checks": {name: r.to_dict() for name, r in check_results.items()},
                "uptime_seconds": self._get_uptime_seconds(),
            }

            duration = time.time() - start
            HEALTH_CHECK_DURATION.set(duration)
            self.metrics_sink.emit("health_check_duration_seconds", duration)

            return state
        except Exception as e:
            logger.error(f"Error in get_comprehensive_state: {e}", exc_info=True)
            raise

    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        statuses = [c.status for c in self.component_health._components.values()]

        if not statuses:
            overall = HealthStatus.UNKNOWN.value
        elif HealthStatus.FAILED in statuses:
            overall = HealthStatus.FAILED.value
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED.value
        else:
            overall = HealthStatus.HEALTHY.value

        return {
            "status": overall,
            "healthy_components": sum(1 for s in statuses if s == HealthStatus.HEALTHY),
            "degraded_components": sum(
                1 for s in statuses if s == HealthStatus.DEGRADED
            ),
            "failed_components": sum(1 for s in statuses if s == HealthStatus.FAILED),
            "total_components": len(statuses),
        }

    def _get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Get circuit breaker state and metrics with None safety."""
        if not self.cb:
            return {
                "available": False,
                "state": "UNKNOWN",
                "open_duration_seconds": 0,
                "failures_total": 0,
                "successes_total": 0,
                "trips_total": 0,
                "consecutive_failures": 0,
            }

        try:
            cb_state = getattr(self.cb, "state", "UNKNOWN")
            metrics = getattr(self.cb, "metrics", None)

            open_duration = 0
            if cb_state == "OPEN" and metrics is not None and hasattr(metrics, "state_change_time"):
                state_change = metrics.state_change_time
                if state_change is not None:
                    open_duration = (datetime.now() - state_change).total_seconds()

            return {
                "available": True,
                "state": str(cb_state),
                "open_duration_seconds": max(0, open_duration),
                "failures_total": metrics.failures_total if metrics is not None else 0,
                "successes_total": metrics.successes_total if metrics is not None else 0,
                "trips_total": metrics.trips_total if metrics is not None else 0,
                "consecutive_failures": metrics.consecutive_failures if metrics is not None else 0,
            }
        except Exception as e:
            logger.error(f"Error retrieving circuit breaker state: {e}", exc_info=False)
            return {
                "available": False,
                "state": "ERROR",
                "open_duration_seconds": 0,
                "failures_total": 0,
                "successes_total": 0,
                "trips_total": 0,
                "consecutive_failures": 0,
            }

    def _get_retry_metrics(self) -> Dict[str, Any]:
        """Get retry failure metrics within time window."""
        with self._lock:
            # Clean old entries outside time window
            cutoff_time = datetime.utcnow() - timedelta(
                seconds=self.failure_window_seconds
            )
            self._retry_failures = [t for t in self._retry_failures if t > cutoff_time]

            failure_count = len(self._retry_failures)
            
            # Determine retry state based on failure count
            if failure_count < 5:
                state = "STABLE"
            elif failure_count < 20:
                state = "ELEVATED"
            else:
                state = "CRITICAL"

            return {
                "state": state,
                "failures_1h": failure_count,
                "failure_rate": failure_count / 3600.0,  # Per second
                "total_attempts": (
                    self.retry_tracker.total_attempts if self.retry_tracker else 0
                ),
            }

    def _get_components_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all registered components."""
        result = {}
        for name, health in self.component_health._components.items():
            result[name] = health.to_dict()
        return result

    def _get_uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        return (datetime.utcnow() - self.start_time).total_seconds()

    def _get_resource_health(self) -> Dict[str, Any]:
        """Get resource monitoring status."""
        try:
            resource_status = self.resource_monitor.check_resource_health()
            current_metrics = self.resource_monitor.get_current_metrics()

            return {
                "status": resource_status,
                "current_metrics": current_metrics.to_dict(),
                "available": True
            }
        except Exception as e:
            logger.error(f"Error getting resource health: {e}", exc_info=False)
            return {
                "status": {
                    "cpu": "unknown",
                    "memory": "unknown",
                    "disk": "unknown",
                    "overall": "unknown"
                },
                "current_metrics": {},
                "available": False
            }

    def record_retry_failure(self):
        """Record a retry failure for tracking."""
        with self._lock:
            self._retry_failures.append(datetime.utcnow())
        self.metrics_sink.emit_counter("retry_failures_total")

    def _get_fallback_mode_safe(self) -> str:
        """Thread-safe access to fallback mode."""
        with self._fallback_lock:
            return self.fallback_mode.value

    def _get_cascade_log_safe(self) -> List[Dict[str, Any]]:
        """Thread-safe access to cascade log."""
        with self._lock:
            return self._fallback_cascade_log[-10:]  # Last 10 entries

    async def cascade_fallback(
        self, state: Optional[Dict[str, Any]] = None
    ) -> FallbackMode:
        """
        Determine fallback mode based on system health.

        Progressive cascade:
        1. PRIMARY: All systems healthy
        2. HEURISTIC: Circuit breaker open OR high retry failure rate
        3. SAFE: Multiple component failures OR resource exhaustion

        Args:
            state: Optional pre-computed health state (for efficiency)

        Returns:
            New fallback mode
        """
        if state is None:
            state = await self.get_comprehensive_state()

        cb_state = state.get("circuit_breaker", {})
        retry_state = state.get("retry", {})
        system_state = state.get("system", {})
        resource_state = state.get("resources", {})

        old_mode = self.fallback_mode

        # Determine new mode
        if (system_state.get("failed_components", 0) >= 2 or
            resource_state.get("status", {}).get("overall") == "critical"):
            new_mode = FallbackMode.SAFE
        elif cb_state.get("state") == "OPEN" or retry_state.get("failures_1h", 0) > 50:
            new_mode = FallbackMode.HEURISTIC
        else:
            new_mode = FallbackMode.PRIMARY

        # Record transition
        if new_mode != old_mode:
            self.fallback_mode = new_mode
            with self._lock:
                self._fallback_cascade_log.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "from": old_mode.value,
                        "to": new_mode.value,
                        "reason": self._get_cascade_reason(
                            cb_state, retry_state, system_state, resource_state
                        ),
                    }
                )
                # Trim cascade log to prevent memory leaks
                if len(self._fallback_cascade_log) > self._cascade_log_max_size:
                    self._fallback_cascade_log = self._fallback_cascade_log[-self._cascade_log_max_size:]
            logger.warning(f"Fallback cascade: {old_mode.value} → {new_mode.value}")
            self.metrics_sink.emit_counter("fallback_transitions_total", tags={"to": new_mode.value})

        # Update metrics
        mode_to_value = {
            FallbackMode.PRIMARY: 0,
            FallbackMode.HEURISTIC: 1,
            FallbackMode.SAFE: 2,
        }
        with self._fallback_lock:
            FALLBACK_MODE_GAUGE.set(mode_to_value.get(self.fallback_mode, 0))
            self.metrics_sink.emit("fallback_mode", mode_to_value.get(self.fallback_mode, 0))

        return self.fallback_mode

    def _get_cascade_reason(
        self,
        cb_state: Dict[str, Any],
        retry_state: Dict[str, Any],
        system_state: Dict[str, Any],
        resource_state: Dict[str, Any],
    ) -> str:
        """Generate detailed context reason for fallback cascade with full error details."""
        reasons = []
        error_context: Dict[str, Any] = {}

        # Circuit breaker context
        if cb_state.get("state") == "OPEN":
            reasons.append("circuit_open")
            error_context["circuit_breaker"] = {
                "state": cb_state.get("state"),
                "open_duration_seconds": cb_state.get("open_duration_seconds", 0),
                "failures_total": cb_state.get("failures_total", 0),
                "consecutive_failures": cb_state.get("consecutive_failures", 0),
            }

        # Retry failure context
        if retry_state.get("failures_1h", 0) > 50:
            failures = retry_state["failures_1h"]
            reasons.append(f"high_retry_failures({failures})")
            error_context["retry_failures"] = {
                "failures_1h": failures,
                "failure_rate_per_second": retry_state.get("failure_rate", 0),
                "state": retry_state.get("state", "UNKNOWN"),
                "total_attempts": retry_state.get("total_attempts", 0),
            }

        # Component failure context
        if system_state.get("failed_components", 0) > 0:
            failed_count = system_state["failed_components"]
            reasons.append(f"component_failures({failed_count})")
            error_context["component_health"] = {
                "failed_components": failed_count,
                "degraded_components": system_state.get("degraded_components", 0),
                "healthy_components": system_state.get("healthy_components", 0),
                "total_components": system_state.get("total_components", 0),
            }

        # Resource exhaustion context
        if resource_state.get("status", {}).get("overall") == "critical":
            reasons.append("resource_exhaustion")
            error_context["resource_health"] = {
                "overall_status": resource_state.get("status", {}).get("overall"),
                "cpu_status": resource_state.get("status", {}).get("cpu"),
                "memory_status": resource_state.get("status", {}).get("memory"),
                "disk_status": resource_state.get("status", {}).get("disk"),
                "available": resource_state.get("available", False),
            }

        reason_str = "; ".join(reasons) if reasons else "unknown"

        # Log cascade with full context
        if error_context:
            logger.warning(f"Fallback cascade triggered: {reason_str} | Context: {error_context}")

        return reason_str


# ============================================================================
# FASTAPI ROUTER
# ============================================================================

router = APIRouter(
    prefix="/health", tags=["health"], responses={500: {"description": "Server error"}}
)

# Global health monitor instance (will be initialized in main.py)
_health_monitor: Optional[HealthMonitor] = None


def set_health_monitor(monitor: HealthMonitor):
    """Initialize health monitor instance (called from main.py)."""
    global _health_monitor
    _health_monitor = monitor
    logger.info("Health monitor endpoint initialized")


def get_health_monitor() -> HealthMonitor:
    """Get health monitor instance."""
    if _health_monitor is None:
        raise HTTPException(status_code=503, detail="Health monitor not initialized")
    return _health_monitor


@router.get("/metrics")
async def prometheus_metrics():
    """
    Prometheus /metrics endpoint.

    Returns metrics in Prometheus text format.
    Used by Prometheus scraper for monitoring.
    """
    try:
        metrics_output = generate_latest(REGISTRY)
        return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
    except Exception as e:
        logger.error(
            f"Error generating metrics: {e}",
            extra={
                "component": "health_monitor",
                "endpoint": "/metrics",
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to generate metrics")


@router.get("/state")
async def health_state():
    """
    Comprehensive health snapshot for dashboard.

    Returns JSON with:
    - System health status
    - Circuit breaker state
    - Retry metrics (1h window)
    - Fallback mode
    - Component health details
    - System uptime

    Used by Streamlit dashboard for live updates.
    """
    try:
        monitor = get_health_monitor()
        state = await monitor.get_comprehensive_state()
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting health state: {e}",
            extra={
                "component": "health_monitor",
                "endpoint": "/state",
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to get health state")


@router.get("/cascade")
async def trigger_cascade():
    """
    Trigger fallback cascade evaluation.

    Determines current fallback mode based on system health.
    Can be called by external orchestrators.
    """
    try:
        monitor = get_health_monitor()
        new_mode = await monitor.cascade_fallback()
        return {
            "fallback_mode": new_mode.value,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(
            f"Error during cascade: {e}",
            extra={
                "component": "health_monitor",
                "endpoint": "/cascade",
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to evaluate cascade")


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes-style readiness check.

    Returns 200 if system is ready to accept traffic.
    Returns 503 if in safe mode or components are unavailable.
    """
    try:
        monitor = get_health_monitor()
        state = await monitor.get_comprehensive_state()

        system_health = state.get("system", {})
        fallback = state.get("fallback", {})

        # Ready if primary mode and no failed components
        is_ready = (
            fallback.get("mode") == FallbackMode.PRIMARY.value
            and system_health.get("failed_components", 0) == 0
        )

        if is_ready:
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Service not ready: {fallback.get('mode')} mode",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in readiness check: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Readiness check failed")


@router.get("/live")
async def liveness_check():
    """
    Kubernetes-style liveness check.

    Returns 200 if service is alive and responsive.
    """
    try:
        return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error in liveness check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Liveness check failed")


@router.get("/checks")
async def get_registered_checks():
    """
    List all registered health checks and their current status.
    """
    try:
        monitor = get_health_monitor()
        results = await monitor.run_checks()
        return {
            "checks": {name: result.to_dict() for name, result in results.items()},
            "timestamp": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running health checks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to run health checks")
