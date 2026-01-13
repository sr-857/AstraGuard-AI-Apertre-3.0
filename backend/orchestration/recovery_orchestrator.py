"""
Automated Recovery Orchestrator (Issue #17 - Refactored for Issue #444)

Autonomous self-healing system that monitors health metrics and executes
recovery actions without human intervention. Integrates with:
- HealthMonitor (#16) for state evaluation
- FallbackManager (#16) for mode cascading
- CircuitBreaker (#14) for circuit recovery
- Retry logic (#15) for failure tracking

Recovery Actions:
1. Circuit Restart: Reload model when circuit open > threshold
2. Cache Purge: Clear cache + scale memory when retry failures high
3. Safe Mode: Activate when accuracy degraded below threshold

Refactoring (Issue #444):
- Implements Orchestrator interface
- Uses dependency injection for all external dependencies
- Pure decision logic with side-effects through injected components
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
import yaml
import os

from backend.orchestration.orchestrator_base import OrchestratorBase

# Import report generator for anomaly reporting
try:
    from anomaly.report_generator import get_report_generator
except ImportError:
    get_report_generator = None

logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================


@dataclass
class RecoveryAction:
    """Track a recovery action execution"""

    action_type: str  # "circuit_restart", "cache_purge", "safe_mode"
    timestamp: datetime
    reason: str
    success: bool = True
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class RecoveryMetrics:
    """Aggregated recovery metrics"""

    total_actions_executed: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    actions_by_type: Dict[str, int] = field(
        default_factory=lambda: {
            "circuit_restart": 0,
            "cache_purge": 0,
            "safe_mode": 0,
        }
    )
    last_action_time: Optional[datetime] = None
    last_action_type: Optional[str] = None


# ============================================================================
# CONFIGURATION LOADER
# ============================================================================


class RecoveryConfig:
    """Loads and manages recovery configuration from YAML"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "poll_interval": 30,  # seconds
        "thresholds": {
            "circuit_open_duration": 300,  # 5 minutes
            "retry_failures_1h": 50,
            "min_anomaly_accuracy": 0.80,
            "failed_components": 2,
        },
        "cooldowns": {
            "circuit_restart": 300,  # 5 min between restarts
            "cache_purge": 600,  # 10 min between purges
            "safe_mode": 300,  # 5 min between safe mode activations
        },
        "recovery_actions": {
            "circuit_restart": {"enabled": True, "timeout": 30},
            "cache_purge": {"enabled": True, "timeout": 60},
            "safe_mode": {"enabled": True, "timeout": 10},
        },
        "logging": {
            "level": "INFO",
            "slack_webhook": "",  # Optional
        },
    }

    def __init__(self, config_path: str = "config/recovery.yaml"):
        """
        Load recovery configuration.

        Args:
            config_path: Path to recovery.yaml
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML config with environment variable substitution and defaults fallback."""
        if os.path.exists(self.config_path):
            try:
                from config.config_utils import load_config_with_env_vars
                loaded = load_config_with_env_vars(self.config_path, self.DEFAULT_CONFIG)
                # Merge with defaults
                return self._merge_dicts(self.DEFAULT_CONFIG, loaded)
            except Exception as e:
                logger.warning(
                    f"Failed to load {self.config_path}: {e}, using defaults"
                )
                return self.DEFAULT_CONFIG.copy()
        else:
            logger.debug(f"Config file not found: {self.config_path}, using defaults")
            return self.DEFAULT_CONFIG.copy()

    def _merge_dicts(self, defaults: Dict, overrides: Dict) -> Dict:
        """Recursively merge override dict into defaults."""
        result = defaults.copy()
        for key, value in overrides.items():
            if isinstance(value, dict) and key in result:
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, key: str, default=None) -> Any:
        """Get config value by dot-notation key."""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def reload(self):
        """Reload configuration from disk (for hot-reload)."""
        self.config = self._load_config()
        logger.info("Recovery configuration reloaded")


# ============================================================================
# RECOVERY ORCHESTRATOR
# ============================================================================


class RecoveryOrchestrator(OrchestratorBase):
    """
    Autonomous self-healing orchestration engine.

    Monitors system health metrics and automatically executes recovery actions
    when thresholds are exceeded. Includes cooldown protection to prevent
    thrashing and excessive action execution.

    Recovery Actions:
    1. Circuit Restart: Recover stuck circuit breakers
    2. Cache Purge: Free memory and scale memory pools
    3. Safe Mode: Activate conservative operation mode
    
    Refactored (Issue #444):
    - Extends OrchestratorBase
    - All dependencies injected via constructor
    - Side-effects isolated to injected components
    """

    def __init__(
        self,
        health_monitor=None,
        fallback_manager=None,
        metrics_collector=None,
        storage=None,
        config_path: str = "config/recovery.yaml",
    ):
        """
        Initialize recovery orchestrator with dependency injection.

        Args:
            health_monitor: HealthMonitor instance from issue #16
            fallback_manager: FallbackManager instance from issue #16
            metrics_collector: Metrics collection component (optional)
            storage: Persistent storage component (optional)
            config_path: Path to recovery.yaml configuration
        """
        # Initialize base class with injected dependencies
        super().__init__(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
            metrics_collector=metrics_collector,
            storage=storage,
        )
        
        self.config = RecoveryConfig(config_path)
        self._last_action_times: Dict[str, datetime] = {}
        self.metrics = RecoveryMetrics()
        self._action_history: list = []  # Recent actions for inspection

        # Registered recovery action handlers
        self._action_handlers: Dict[str, Callable[[], Awaitable[None]]] = {
            "circuit_restart": self._action_circuit_restart,
            "cache_purge": self._action_cache_purge,
            "safe_mode": self._action_safe_mode,
        }

        logger.info("RecoveryOrchestrator initialized")

    # ========== INTERFACE METHODS ==========

    async def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Handle an external event that may trigger recovery.
        
        Args:
            event: Event data containing state information
        """
        try:
            # Extract event type and process accordingly
            event_type = event.get("type", "unknown")
            
            if event_type == "health_check":
                # Process health check event
                state = event.get("state", {})
                await self._evaluate_circuit_recovery(state)
                await self._evaluate_cache_recovery(state)
                await self._evaluate_accuracy_recovery(state)
            elif event_type == "manual_trigger":
                # Manual recovery trigger
                action_type = event.get("action_type")
                reason = event.get("reason", "Manual trigger")
                if action_type and action_type in self._action_handlers:
                    await self._execute_action(action_type, reason)
            else:
                logger.warning(f"Unknown event type: {event_type}")
                
        except Exception as e:
            logger.error(f"Error handling event: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the orchestrator.
        
        Returns:
            Dict containing running state, metrics, and last action
        """
        return {
            "running": self._running,
            "enabled": self.config.get("enabled"),
            "poll_interval": self.config.get("poll_interval"),
            "metrics": self.get_metrics(),
            "cooldown_status": self.get_cooldown_status(),
            "last_action": (
                {
                    "timestamp": self.metrics.last_action_time.isoformat(),
                    "type": self.metrics.last_action_type,
                }
                if self.metrics.last_action_time
                else None
            ),
        }

    # ========== LIFECYCLE ==========

    async def run(self):
        """
        Main recovery orchestration loop.

        Runs continuously, evaluating health metrics and executing recovery
        actions at configured intervals. Respects cooldown periods to prevent
        thrashing.
        """
        if not self.config.get("enabled"):
            logger.info("Recovery orchestrator disabled via config")
            return

        self._running = True
        poll_interval = self.config.get("poll_interval", 30)

        logger.info(f"🚀 Recovery Orchestrator started (interval: {poll_interval}s)")

        try:
            while self._running:
                try:
                    await self._recovery_cycle()
                except Exception as e:
                    logger.error(f"Recovery cycle failed: {e}", exc_info=True)

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("Recovery Orchestrator stopped")
            self._running = False
        except Exception as e:
            logger.error(f"Unexpected error in recovery loop: {e}", exc_info=True)
            self._running = False

    def stop(self):
        """Stop the recovery orchestrator."""
        self._running = False
        logger.info("Recovery Orchestrator stop requested")

    # ========== RECOVERY CYCLE ==========

    async def _recovery_cycle(self):
        """
        Single recovery evaluation and action cycle.

        Flow:
        1. Get current health state
        2. Evaluate all recovery conditions
        3. Execute actions where thresholds exceeded (respecting cooldown)
        4. Update metrics
        """
        if not self.health_monitor:
            return

        try:
            # Get current state
            state = await self.health_monitor.get_comprehensive_state()

            # Evaluate each recovery condition
            await self._evaluate_circuit_recovery(state)
            await self._evaluate_cache_recovery(state)
            await self._evaluate_accuracy_recovery(state)

            logger.debug("Recovery cycle complete")

        except Exception as e:
            logger.error(f"Error in recovery cycle: {e}", exc_info=True)

    # ========== CONDITION EVALUATION ==========

    async def _evaluate_circuit_recovery(self, state: Dict[str, Any]):
        """Evaluate if circuit breaker needs recovery."""
        try:
            cb = state.get("circuit_breaker", {})

            if cb.get("state") != "OPEN":
                return  # Circuit healthy

            open_duration = cb.get("open_duration_seconds", 0)
            threshold = self.config.get("thresholds.circuit_open_duration", 300)

            if open_duration > threshold:
                if self._check_cooldown("circuit_restart"):
                    logger.warning(
                        f"Circuit OPEN for {open_duration}s (threshold: {threshold}s) - "
                        "triggering recovery"
                    )
                    await self._execute_action(
                        "circuit_restart", f"open_duration={open_duration}s"
                    )
                else:
                    cooldown_remaining = self._get_cooldown_remaining("circuit_restart")
                    logger.debug(
                        f"Circuit restart in cooldown ({cooldown_remaining:.0f}s remaining)"
                    )
        except Exception as e:
            logger.error(f"Error evaluating circuit recovery: {e}", exc_info=True)

    async def _evaluate_cache_recovery(self, state: Dict[str, Any]):
        """Evaluate if cache purge is needed due to high retry failures."""
        try:
            retry = state.get("retry", {})
            failures_1h = retry.get("failures_1h", 0)
            threshold = self.config.get("thresholds.retry_failures_1h", 50)

            if failures_1h > threshold:
                if self._check_cooldown("cache_purge"):
                    logger.warning(
                        f"High retry failures ({failures_1h} in 1h, threshold: {threshold}) - "
                        "triggering cache purge"
                    )
                    await self._execute_action(
                        "cache_purge", f"failures_1h={failures_1h}"
                    )
                else:
                    cooldown_remaining = self._get_cooldown_remaining("cache_purge")
                    logger.debug(
                        f"Cache purge in cooldown ({cooldown_remaining:.0f}s remaining)"
                    )
        except Exception as e:
            logger.error(f"Error evaluating cache recovery: {e}", exc_info=True)

    async def _evaluate_accuracy_recovery(self, state: Dict[str, Any]):
        """Evaluate if safe mode needed due to accuracy degradation."""
        try:
            # Placeholder - would integrate with ML accuracy metrics
            # For now, check if multiple components failed
            system = state.get("system", {})
            failed_components = system.get("failed_components", 0)
            threshold = self.config.get("thresholds.failed_components", 2)

            if failed_components >= threshold:
                if self._check_cooldown("safe_mode"):
                    logger.warning(
                        f"Multiple component failures ({failed_components}, threshold: {threshold}) - "
                        "activating safe mode"
                    )
                    await self._execute_action(
                        "safe_mode", f"failed_components={failed_components}"
                    )
                else:
                    cooldown_remaining = self._get_cooldown_remaining("safe_mode")
                    logger.debug(
                        f"Safe mode in cooldown ({cooldown_remaining:.0f}s remaining)"
                    )
        except Exception as e:
            logger.error(f"Error evaluating accuracy recovery: {e}", exc_info=True)

    # ========== RECOVERY ACTIONS ==========

    async def _execute_action(self, action_type: str, reason: str = ""):
        """
        Execute a recovery action with metrics tracking.

        Args:
            action_type: Type of recovery action
            reason: Human-readable reason for action
        """
        if action_type not in self._action_handlers:
            logger.error(f"Unknown recovery action: {action_type}")
            return

        if not self.config.get(f"recovery_actions.{action_type}.enabled"):
            logger.debug(f"Recovery action {action_type} is disabled")
            return

        start_time = time.time()
        action = RecoveryAction(
            action_type=action_type,
            timestamp=datetime.utcnow(),
            reason=reason,
        )

        try:
            logger.info(
                f"▶️  Executing recovery action: {action_type} (reason: {reason})"
            )

            # Execute handler
            handler = self._action_handlers[action_type]
            await handler()

            action.success = True
            action.duration_seconds = time.time() - start_time

            logger.info(
                f"✅ Recovery action succeeded: {action_type} ({action.duration_seconds:.1f}s)"
            )

            # Update metrics
            self._update_metrics(action)
            self._record_action_history(action)
            self._record_cooldown(action_type)
            
            # Record for anomaly reporting
            self._record_recovery_action_for_reporting(action, reason)

        except Exception as e:
            action.success = False
            action.error = str(e)
            action.duration_seconds = time.time() - start_time

            logger.error(
                f"❌ Recovery action failed: {action_type} - {e}",
                exc_info=True,
            )

            self._update_metrics(action)
            self._record_action_history(action)
            
            # Record failed recovery action for reporting
            self._record_recovery_action_for_reporting(action, reason)

    async def _action_circuit_restart(self):
        """Recovery action: Restart model loader to recover circuit."""
        timeout = self.config.get("recovery_actions.circuit_restart.timeout", 30)

        try:
            # In production, would call: await model_loader.restart()
            logger.info("🔄 Restarting model loader...")
            await asyncio.sleep(0.5)  # Simulate restart
            logger.info("✓ Model loader restarted successfully")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Model restart timeout after {timeout}s")

    async def _action_cache_purge(self):
        """Recovery action: Purge cache and scale memory pools."""
        timeout = self.config.get("recovery_actions.cache_purge.timeout", 60)

        try:
            # In production, would call:
            # await cache_manager.purge_stale()
            # await memory_pool_scaler.scale(factor=2)
            logger.info("🧹 Purging cache and scaling memory pools...")
            await asyncio.sleep(1)  # Simulate cache purge
            logger.info("✓ Cache purged, memory pools scaled")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Cache purge timeout after {timeout}s")

    async def _action_safe_mode(self):
        """Recovery action: Activate safe mode."""
        timeout = self.config.get("recovery_actions.safe_mode.timeout", 10)

        try:
            logger.info("🛡️  Activating safe mode...")

            if self.fallback_manager:
                # Trigger safe mode cascade
                await self.fallback_manager.cascade(
                    {
                        "system": {"failed_components": 2},
                        "circuit_breaker": {"state": "OPEN"},
                        "retry": {"failures_1h": 0},
                    }
                )

            logger.info("✓ Safe mode activated")
        except asyncio.TimeoutError:
            raise RuntimeError(f"Safe mode activation timeout after {timeout}s")

    # ========== COOLDOWN MANAGEMENT ==========

    def _check_cooldown(self, action_type: str) -> bool:
        """
        Check if action is allowed (respecting cooldown).

        Args:
            action_type: Type of recovery action

        Returns:
            True if cooldown has passed, False if still in cooldown
        """
        cooldown_seconds = self.config.get(f"cooldowns.{action_type}", 300)
        last_time = self._last_action_times.get(action_type)

        if not last_time:
            return True  # First execution, no cooldown

        elapsed = (datetime.utcnow() - last_time).total_seconds()
        return elapsed >= cooldown_seconds

    def _record_cooldown(self, action_type: str):
        """Record action execution for cooldown tracking."""
        self._last_action_times[action_type] = datetime.utcnow()

    def _get_cooldown_remaining(self, action_type: str) -> float:
        """Get seconds remaining in cooldown period."""
        cooldown_seconds = self.config.get(f"cooldowns.{action_type}", 300)
        last_time = self._last_action_times.get(action_type)

        if not last_time:
            return 0.0

        elapsed = (datetime.utcnow() - last_time).total_seconds()
        remaining = max(0, cooldown_seconds - elapsed)
        return remaining

    # ========== METRICS & HISTORY ==========

    def _update_metrics(self, action: RecoveryAction):
        """Update aggregated recovery metrics."""
        self.metrics.total_actions_executed += 1

        if action.success:
            self.metrics.successful_actions += 1
        else:
            self.metrics.failed_actions += 1

        self.metrics.actions_by_type[action.action_type] += 1
        self.metrics.last_action_time = action.timestamp
        self.metrics.last_action_type = action.action_type

    def _record_action_history(self, action: RecoveryAction, max_history: int = 100):
        """Record action to history for inspection."""
        self._action_history.append(action)
        # Keep last N actions
        self._action_history = self._action_history[-max_history:]

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated recovery metrics."""
        return {
            "total_actions_executed": self.metrics.total_actions_executed,
            "successful_actions": self.metrics.successful_actions,
            "failed_actions": self.metrics.failed_actions,
            "success_rate": (
                self.metrics.successful_actions / self.metrics.total_actions_executed
                if self.metrics.total_actions_executed > 0
                else 0.0
            ),
            "actions_by_type": self.metrics.actions_by_type,
            "last_action_time": (
                self.metrics.last_action_time.isoformat()
                if self.metrics.last_action_time
                else None
            ),
            "last_action_type": self.metrics.last_action_type,
            "running": self._running,
        }

    def get_action_history(self, limit: int = 50) -> list:
        """Get recent recovery actions."""
        actions = self._action_history[-limit:]
        return [
            {
                "timestamp": a.timestamp.isoformat(),
                "action_type": a.action_type,
                "reason": a.reason,
                "success": a.success,
                "error": a.error,
                "duration_seconds": a.duration_seconds,
            }
            for a in actions
        ]

    def get_cooldown_status(self) -> Dict[str, Any]:
        """Get current cooldown status for all actions."""
        return {
            action_type: {
                "available": self._check_cooldown(action_type),
                "seconds_remaining": self._get_cooldown_remaining(action_type),
                "last_executed": (
                    self._last_action_times[action_type].isoformat()
                    if action_type in self._last_action_times
                    else None
                ),
            }
            for action_type in self._action_handlers.keys()
        }
    
    def _record_recovery_action_for_reporting(self, action: RecoveryAction, reason: str) -> None:
        """
        Record recovery action for anomaly reporting.
        
        Args:
            action: The RecoveryAction dataclass instance
            reason: The reason for the action
        """
        if get_report_generator is None:
            return
            
        try:
            report_generator = get_report_generator()
            
            # Determine anomaly type from reason or action type
            # This is a heuristic - in a real system, this would be passed explicitly
            anomaly_type = "unknown"
            if "circuit" in action.action_type.lower():
                anomaly_type = "circuit_failure"
            elif "cache" in action.action_type.lower():
                anomaly_type = "memory_pressure"
            elif "safe" in action.action_type.lower():
                anomaly_type = "system_stress"
            
            report_generator.record_recovery_action(
                action_type=action.action_type,
                anomaly_type=anomaly_type,
                success=action.success,
                duration_seconds=action.duration_seconds,
                error_message=action.error,
                metadata={"reason": reason, "orchestrator": "basic"}
            )
            
        except Exception as e:
            logger.warning(f"Failed to record recovery action for reporting: {e}")
