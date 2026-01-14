"""
Fallback Cascade Manager - COMPATIBILITY SHIM

⚠️  DEPRECATED: This module is a compatibility shim.
    New code should import from backend.fallback instead:
    
    from backend.fallback import FallbackManager, FallbackMode
    
This shim will be removed in a future release once all callers
have been migrated to the new DI-based implementation.

Original implementation has been refactored to:
- backend/fallback/manager.py - FallbackManager with Storage DI
- backend/fallback/condition_parser.py - Pure condition parsing

Migration Guide:
1. Import from backend.fallback instead of backend.fallback_manager
2. Update constructor to accept Storage instance:
   
   from backend.fallback import FallbackManager
   from backend.storage import MemoryStorage  # or RedisAdapter
   
   storage = MemoryStorage()
   manager = FallbackManager(storage=storage, ...)
   
3. All other APIs remain the same
"""

import logging
import warnings
from backend.fallback import FallbackManager as NewFallbackManager, FallbackMode
from backend.storage import MemoryStorage

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
__all__ = ["FallbackManager", "FallbackMode"]


class FallbackManager:
    """
    DEPRECATED: Compatibility wrapper for old FallbackManager interface.
    
    This wrapper creates an in-memory storage instance internally to maintain
    backward compatibility. New code should use the refactored FallbackManager
    with explicit Storage dependency injection.
    
    See: backend/fallback/manager.py for new implementation.
    """

    def __init__(
        self,
        circuit_breaker=None,
        anomaly_detector=None,
        heuristic_detector=None,
    ):
        """
        Initialize fallback manager (compatibility mode).
        
        ⚠️  DEPRECATED: Use backend.fallback.FallbackManager with Storage DI instead.

        Args:
            circuit_breaker: CircuitBreaker instance for monitoring
            anomaly_detector: Primary ML-based anomaly detector
            heuristic_detector: Fallback rule-based detector
        """
        warnings.warn(
            "FallbackManager from backend.fallback_manager is deprecated. "
            "Use backend.fallback.FallbackManager with Storage DI instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Create in-memory storage for backward compatibility
        storage = MemoryStorage()
        
        # Delegate to new implementation
        self._impl = NewFallbackManager(
            storage=storage,
            circuit_breaker=circuit_breaker,
            anomaly_detector=anomaly_detector,
            heuristic_detector=heuristic_detector,
        )

    # Delegate all methods to new implementation
    async def cascade(self, health_state):
        """Delegate to new implementation."""
        return await self._impl.cascade(health_state)

    def register_mode_callback(self, mode, callback):
        """Delegate to new implementation."""
        return self._impl.register_mode_callback(mode, callback)

    async def detect_anomaly(self, data):
        """Delegate to new implementation."""
        return await self._impl.detect_anomaly(data)

    def get_transitions_log(self, limit=50):
        """Delegate to new implementation."""
        return self._impl.get_transitions_log(limit)

    def get_current_mode(self):
        """Delegate to new implementation."""
        return self._impl.get_current_mode()

    def get_mode_string(self):
        """Delegate to new implementation."""
        return self._impl.get_mode_string()

    async def set_mode(self, mode):
        """Delegate to new implementation."""
        return await self._impl.set_mode(mode)

    def is_degraded(self):
        """Delegate to new implementation."""
        return self._impl.is_degraded()

    def is_safe_mode(self):
        """Delegate to new implementation."""
        return self._impl.is_safe_mode()

    @property
    def current_mode(self):
        """Get the current mode from implementation."""
        return self._impl.current_mode

    @current_mode.setter
    def current_mode(self, value):
        """Set the current mode in implementation."""
        self._impl.current_mode = value
    @property
    def anomaly_detector(self):
        """Get anomaly detector from implementation."""
        return self._impl.anomaly_detector

    @anomaly_detector.setter
    def anomaly_detector(self, value):
        """Set anomaly detector in implementation."""
        self._impl.anomaly_detector = value

    @property
    def heuristic_detector(self):
        """Get heuristic detector from implementation."""
        return self._impl.heuristic_detector

    @heuristic_detector.setter
    def heuristic_detector(self, value):
        """Set heuristic detector in implementation."""
        self._impl.heuristic_detector = value

    @property
    def circuit_breaker(self):
        """Get circuit breaker from implementation."""
        return self._impl.circuit_breaker

    @circuit_breaker.setter
    def circuit_breaker(self, value):
        """Set circuit breaker in implementation."""
        self._impl.circuit_breaker = value