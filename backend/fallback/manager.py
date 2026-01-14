"""
Fallback Manager

Orchestrates progressive fallback logic for AstraGuard AI.
Refactored to use dependency injection with Storage interface.

When primary systems fail, cascade through degraded modes:
- PRIMARY: Full ML-based anomaly detection
- HEURISTIC: Rule-based fallback detection
- SAFE: Conservative no-operation mode

Features:
- Dependency injection via Storage interface
- Decoupled from direct Redis usage
- Testable with in-memory storage
- Clean separation of concerns
"""

import logging
from enum import Enum
from typing import Dict, Any, Callable, Awaitable, Optional
from datetime import datetime
from threading import Lock
import json

from backend.storage import Storage

logger = logging.getLogger(__name__)


class FallbackMode(str, Enum):
    """System operation modes with fallback levels."""

    PRIMARY = "primary"
    HEURISTIC = "heuristic"
    SAFE = "safe"


class FallbackManager:
    """
    Progressive fallback cascade manager with dependency injection.

    Transitions system through operational modes based on component health:
    1. PRIMARY: Full functionality, ML-based detection
    2. HEURISTIC: Rule-based detection (faster, less accurate)
    3. SAFE: Conservative operation (no actions, monitoring only)

    Uses injected Storage for any persistence needs, enabling:
    - Easy unit testing with in-memory storage
    - Production deployment with Redis/other backends
    - Clean separation from infrastructure concerns
    """

    def __init__(
        self,
        storage: Storage,
        config: Optional[Dict[str, Any]] = None,
        logger_instance: Optional[logging.Logger] = None,
        circuit_breaker=None,
        anomaly_detector=None,
        heuristic_detector=None,
    ):
        """
        Initialize fallback manager with dependency injection.

        Args:
            storage: Storage implementation (e.g., RedisAdapter, MemoryStorage)
            config: Optional configuration dict
            logger_instance: Optional logger instance
            circuit_breaker: CircuitBreaker instance for monitoring
            anomaly_detector: Primary ML-based anomaly detector
            heuristic_detector: Fallback rule-based detector
        """
        self.storage = storage
        self.config = config or {}
        self.logger = logger_instance or logger

        self.current_mode = FallbackMode.PRIMARY
        self.cb = circuit_breaker
        self.anomaly_detector = anomaly_detector
        self.heuristic_detector = heuristic_detector

        self._lock = Lock()
        self._mode_transitions: list = []
        self._callbacks: Dict[FallbackMode, Callable[[], Awaitable[None]]] = {}

        self.logger.info(f"FallbackManager initialized in {self.current_mode.value} mode")

    async def cascade(self, health_state: Dict[str, Any]) -> FallbackMode:
        """
        Evaluate system health and cascade to appropriate mode.

        Decision tree:
        - If 2+ component failures → SAFE mode
        - If circuit open OR high retry failures → HEURISTIC mode
        - Otherwise → PRIMARY mode

        Args:
            health_state: Dict from HealthMonitor.get_comprehensive_state()

        Returns:
            New FallbackMode (may be same as current)
        """
        cb_state = health_state.get("circuit_breaker", {})
        retry_state = health_state.get("retry", {})
        system_state = health_state.get("system", {})

        # Determine target mode
        failed_components = system_state.get("failed_components", 0)
        circuit_open = cb_state.get("state") == "OPEN"
        high_retry_failures = retry_state.get("failures_1h", 0) > 50

        if failed_components >= 2:
            target_mode = FallbackMode.SAFE
        elif circuit_open or high_retry_failures:
            target_mode = FallbackMode.HEURISTIC
        else:
            target_mode = FallbackMode.PRIMARY

        # Transition if needed
        if target_mode != self.current_mode:
            await self._transition_to_mode(target_mode, health_state)

        return self.current_mode

    async def _transition_to_mode(
        self,
        new_mode: FallbackMode,
        health_state: Dict[str, Any],
    ) -> None:
        """
        Transition to new mode with proper state management.

        Persists transition history to storage for observability.

        Args:
            new_mode: Target fallback mode
            health_state: Current health state for context
        """
        with self._lock:
            old_mode = self.current_mode
            self.current_mode = new_mode

            transition = {
                "timestamp": datetime.utcnow().isoformat(),
                "from": old_mode.value,
                "to": new_mode.value,
                "reason": self._get_transition_reason(health_state),
            }
            self._mode_transitions.append(transition)

            self.logger.warning(
                f"Fallback cascade: {old_mode.value} → {new_mode.value} "
                f"(reason: {transition['reason']})"
            )

        # Persist transition to storage
        try:
            transition_key = f"fallback:transition:{datetime.utcnow().timestamp()}"
            await self.storage.set(transition_key, json.dumps(transition), ttl=86400)
        except Exception as e:
            self.logger.error(f"Failed to persist transition: {e}")

        # Call mode-specific callback if registered
        if new_mode in self._callbacks:
            try:
                await self._callbacks[new_mode]()
            except Exception as e:
                self.logger.error(f"Error in fallback mode callback: {e}", exc_info=True)

    def _get_transition_reason(self, health_state: Dict[str, Any]) -> str:
        """Generate human-readable transition reason."""
        reasons = []

        cb_state = health_state.get("circuit_breaker", {})
        retry_state = health_state.get("retry", {})
        system_state = health_state.get("system", {})

        if system_state.get("failed_components", 0) >= 2:
            reasons.append(f"multiple_failures({system_state['failed_components']})")

        if cb_state.get("state") == "OPEN":
            reasons.append(
                f"circuit_open({cb_state.get('open_duration_seconds', 0):.0f}s)"
            )

        if retry_state.get("failures_1h", 0) > 50:
            reasons.append(f"high_retry_failures({retry_state['failures_1h']})")

        return "; ".join(reasons) if reasons else "unknown"

    def register_mode_callback(
        self,
        mode: FallbackMode,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """
        Register callback to be called when entering a mode.

        Useful for cleanup, reinitialization, or notifications.

        Args:
            mode: FallbackMode to trigger callback
            callback: Async function to call on mode entry
        """
        self._callbacks[mode] = callback
        self.logger.debug(f"Registered callback for {mode.value} mode")

    async def detect_anomaly(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Detect anomaly using appropriate detector for current mode.

        Mode behavior:
        - PRIMARY: Use ML model via anomaly_detector
        - HEURISTIC: Use rule-based detection via heuristic_detector
        - SAFE: Return safe default (no anomaly, low confidence)

        Args:
            data: Telemetry/sensor data for anomaly detection

        Returns:
            Anomaly detection result: {"anomaly": bool, "confidence": float, ...}
        """
        try:
            if self.current_mode == FallbackMode.PRIMARY:
                if self.anomaly_detector:
                    return await self.anomaly_detector.detect_anomaly(data)
                else:
                    return {
                        "anomaly": False,
                        "confidence": 0.0,
                        "mode": "primary_unavailable",
                    }

            elif self.current_mode == FallbackMode.HEURISTIC:
                if self.heuristic_detector:
                    return await self.heuristic_detector.detect_anomaly(data)
                else:
                    return {
                        "anomaly": False,
                        "confidence": 0.0,
                        "mode": "heuristic_unavailable",
                    }

            else:  # SAFE mode
                # Safe mode: be conservative, no action
                return {"anomaly": False, "confidence": 0.0, "mode": "safe"}

        except Exception as e:
            self.logger.error(f"Error in fallback detect_anomaly: {e}", exc_info=True)
            # On error, be conservative
            return {
                "anomaly": False,
                "confidence": 0.0,
                "mode": "error",
                "error": str(e),
            }

    def get_transitions_log(self, limit: int = 50) -> list:
        """
        Get recent mode transitions.

        Args:
            limit: Maximum number of transitions to return

        Returns:
            List of transition dicts with timestamps and reasons
        """
        with self._lock:
            return self._mode_transitions[-limit:]

    def get_current_mode(self) -> FallbackMode:
        """Get current operational mode."""
        return self.current_mode

    def get_mode_string(self) -> str:
        """Get current mode as string."""
        return self.current_mode.value

    async def set_mode(self, mode: str) -> bool:
        """
        Directly set fallback mode from mode string.

        Used by distributed coordinator to apply cluster consensus decisions.
        Converts string mode to FallbackMode enum and transitions immediately.

        Args:
            mode: Mode string, case-insensitive ("primary", "heuristic", or "safe")

        Returns:
            True if mode was set, False if invalid mode string
        """
        try:
            # Normalize mode string to lowercase for enum matching
            normalized_mode = mode.lower()
            target_mode = FallbackMode(normalized_mode)
            if target_mode != self.current_mode:
                # Create synthetic health state for transition logging
                synthetic_state = {
                    "circuit_breaker": {},
                    "retry": {},
                    "system": {},
                }
                await self._transition_to_mode(target_mode, synthetic_state)
            self.logger.debug(f"Fallback mode set to {normalized_mode}")
            return True
        except ValueError:
            self.logger.warning(
                f"Invalid fallback mode: {mode} (must be one of: primary, heuristic, safe)"
            )
            return False

    def is_degraded(self) -> bool:
        """Check if system is in degraded mode (not PRIMARY)."""
        return self.current_mode != FallbackMode.PRIMARY

    def is_safe_mode(self) -> bool:
        """Check if system is in SAFE mode."""
        return self.current_mode == FallbackMode.SAFE

    async def register_fallback(
        self,
        name: str,
        condition: str,
        action: Callable[[], Awaitable[None]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a fallback with condition and action.

        Stores fallback definition in storage for evaluation loop.

        Args:
            name: Unique fallback identifier
            condition: Condition expression (e.g., "severity >= 0.8")
            action: Async action to trigger when condition met
            metadata: Optional metadata for observability

        Returns:
            True if registered successfully
        """
        try:
            fallback_def = {
                "name": name,
                "condition": condition,
                "metadata": metadata or {},
                "registered_at": datetime.utcnow().isoformat(),
            }

            # Store definition in storage
            key = f"fallback:definition:{name}"
            await self.storage.set(key, json.dumps(fallback_def))

            # Store action in memory (not serializable)
            self._callbacks[name] = action

            self.logger.info(f"Registered fallback: {name} (condition: {condition})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to register fallback {name}: {e}", exc_info=True)
            return False

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get fallback manager metrics.

        Returns:
            Metrics dict with current mode, transitions, etc.
        """
        return {
            "current_mode": self.current_mode.value,
            "is_degraded": self.is_degraded(),
            "is_safe_mode": self.is_safe_mode(),
            "total_transitions": len(self._mode_transitions),
            "recent_transitions": self.get_transitions_log(limit=10),
        }
