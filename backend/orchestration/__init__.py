"""
Orchestration Package

This package provides orchestration and coordination interfaces for AstraGuard-AI.
It includes:
- Orchestrator interface for recovery orchestration
- Coordinator interface for distributed coordination
- Concrete implementations with dependency injection

Exports:
    - Orchestrator: Base interface/protocol for orchestrators
    - Coordinator: Base interface/protocol for coordinators
    - RecoveryOrchestrator: Basic recovery orchestrator implementation
    - EnhancedRecoveryOrchestrator: Enhanced recovery orchestrator with severity-based triggers
    - DistributedResilienceCoordinator: Redis-based distributed coordinator
    - LocalCoordinator: In-process coordinator for local dev/testing
"""

from .orchestrator_base import Orchestrator
from .coordinator import Coordinator, LocalCoordinator
from .recovery_orchestrator import RecoveryOrchestrator
from .recovery_orchestrator_enhanced import EnhancedRecoveryOrchestrator
from .distributed_coordinator import DistributedResilienceCoordinator

__all__ = [
    "Orchestrator",
    "Coordinator",
    "LocalCoordinator",
    "RecoveryOrchestrator",
    "EnhancedRecoveryOrchestrator",
    "DistributedResilienceCoordinator",
]

__version__ = "1.0.0"
