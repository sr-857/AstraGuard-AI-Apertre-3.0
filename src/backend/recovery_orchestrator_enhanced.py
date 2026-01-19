"""
Compatibility shim for EnhancedRecoveryOrchestrator.

This module provides backward compatibility by re-exporting the refactored
EnhancedRecoveryOrchestrator from backend.orchestration package.

DEPRECATED: This shim is provided for incremental migration. New code should import
directly from backend.orchestration.recovery_orchestrator_enhanced instead.

To migrate:
    OLD: from backend.recovery_orchestrator_enhanced import EnhancedRecoveryOrchestrator
    NEW: from backend.orchestration import EnhancedRecoveryOrchestrator

This shim will be removed in a future version after all imports are updated.
"""

import warnings
from backend.orchestration.recovery_orchestrator_enhanced import (
    EnhancedRecoveryOrchestrator,
    RecoveryAction,
    RecoveryMetrics,
    RecoveryConfig,
    RecoveryResult,
    AnomalyEvent,
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "backend.recovery_orchestrator_enhanced is deprecated. "
    "Import from backend.orchestration.recovery_orchestrator_enhanced instead. "
    "This compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "EnhancedRecoveryOrchestrator",
    "RecoveryAction",
    "RecoveryMetrics",
    "RecoveryConfig",
    "RecoveryResult",
    "AnomalyEvent",
]
