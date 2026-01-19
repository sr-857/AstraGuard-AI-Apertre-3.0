"""
Orchestrator Base Interface

Defines the protocol/interface that all orchestrators must implement.
Orchestrators handle recovery decision logic and action execution.
"""

from typing import Protocol, Dict, Any, Optional, runtime_checkable
from abc import ABC, abstractmethod


@runtime_checkable
class Orchestrator(Protocol):
    """
    Protocol defining the interface for recovery orchestrators.
    
    Orchestrators monitor system state and execute recovery actions
    when thresholds are exceeded. They must accept dependencies via
    constructor injection and keep decision logic pure.
    """
    
    async def run(self) -> None:
        """
        Start the orchestrator's main loop.
        
        Should run continuously until stop() is called, evaluating
        health metrics and executing recovery actions.
        """
        ...
    
    def stop(self) -> None:
        """
        Stop the orchestrator gracefully.
        
        Should signal the main loop to terminate and clean up resources.
        """
        ...
    
    async def handle_event(self, event: Dict[str, Any]) -> None:
        """
        Handle an external event that may trigger recovery.
        
        Args:
            event: Event data containing state information
        """
        ...
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the orchestrator.
        
        Returns:
            Dict containing:
                - running: Whether orchestrator is active
                - metrics: Current metrics
                - last_action: Last recovery action taken
        """
        ...
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get recovery metrics.
        
        Returns:
            Dict with metrics like total_actions, success_rate, etc.
        """
        ...


class OrchestratorBase(ABC):
    """
    Abstract base class for orchestrators with common functionality.
    
    Provides default implementations and utility methods that
    concrete orchestrators can inherit and customize.
    """
    
    def __init__(
        self,
        health_monitor=None,
        fallback_manager=None,
        metrics_collector=None,
        storage=None,
    ):
        """
        Initialize orchestrator with injected dependencies.
        
        Args:
            health_monitor: Health monitoring component
            fallback_manager: Fallback mode manager
            metrics_collector: Metrics collection component
            storage: Persistent storage component
        """
        self.health_monitor = health_monitor
        self.fallback_manager = fallback_manager
        self.metrics_collector = metrics_collector
        self.storage = storage
        self._running = False
    
    @abstractmethod
    async def run(self) -> None:
        """Start the orchestrator's main loop."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        pass
    
    @abstractmethod
    async def handle_event(self, event: Dict[str, Any]) -> None:
        """Handle an external event."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Get recovery metrics."""
        pass
    
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running
