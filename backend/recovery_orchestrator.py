"""
Compatibility shim for RecoveryOrchestrator.

This module provides backward compatibility by re-exporting the refactored
RecoveryOrchestrator from backend.orchestration package.

DEPRECATED: This shim is provided for incremental migration. New code should import
directly from backend.orchestration.recovery_orchestrator instead.

To migrate:
    OLD: from backend.recovery_orchestrator import RecoveryOrchestrator
    NEW: from backend.orchestration import RecoveryOrchestrator

This shim will be removed in a future version after all imports are updated.
"""

import warnings
from backend.orchestration.recovery_orchestrator import (
    RecoveryOrchestrator,
    RecoveryAction,
    RecoveryMetrics,
    RecoveryConfig,
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "backend.recovery_orchestrator is deprecated. "
    "Import from backend.orchestration.recovery_orchestrator instead. "
    "This compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "RecoveryOrchestrator",
    "RecoveryAction",
    "RecoveryMetrics",
    "RecoveryConfig",
]
