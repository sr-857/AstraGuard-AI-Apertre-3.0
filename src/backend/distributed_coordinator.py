"""
Compatibility shim for DistributedResilienceCoordinator.

This module provides backward compatibility by re-exporting the refactored
DistributedResilienceCoordinator from backend.orchestration package.

DEPRECATED: This shim is provided for incremental migration. New code should import
directly from backend.orchestration.distributed_coordinator instead.

To migrate:
    OLD: from backend.distributed_coordinator import DistributedResilienceCoordinator
    NEW: from backend.orchestration import DistributedResilienceCoordinator

This shim will be removed in a future version after all imports are updated.
"""

import warnings
from backend.orchestration.distributed_coordinator import (
    DistributedResilienceCoordinator,
)
from backend.orchestration.coordinator import (
    ConsensusDecision,
    NodeInfo,
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "backend.distributed_coordinator is deprecated. "
    "Import from backend.orchestration.distributed_coordinator instead. "
    "This compatibility shim will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "DistributedResilienceCoordinator",
    "ConsensusDecision",
    "NodeInfo",
]
