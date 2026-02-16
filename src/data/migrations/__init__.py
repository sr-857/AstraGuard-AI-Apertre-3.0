"""
Zero-Downtime Database Migration System for AstraGuard AI.

This package provides a comprehensive migration framework with:
- Dual-write pattern for zero-downtime migrations
- Backward-compatible schema changes
- Automatic rollback on failure
- Migration validation and monitoring
- Performance impact tracking

Example:
    from data.migrations import MigrationManager, DualWriteManager
    
    # Initialize migration manager
    manager = MigrationManager(db_path="astraguard.db")
    
    # Run migration with dual-write
    await manager.migrate(
        migration=AddTelemetryColumns(),
        strategy=MigrationStrategy.DUAL_WRITE
    )
"""

from .manager import MigrationManager, MigrationStrategy, MigrationStatus, Migration, MigrationConfig
from .version import SchemaVersion, VersionManager, VersionStatus
from .validator import MigrationValidator, ValidationResult, ValidationStatus, DataIntegrityRule, RowCountMatchRule
from .rollback import RollbackManager, RollbackStrategy, RollbackResult, RollbackStatus

from .dual_write import DualWriteManager, ReadRoutingStrategy, WriteStrategy, SchemaAdapter
from .monitoring import MigrationMonitor, MigrationMetrics, MigrationDashboard, MetricType

__all__ = [
    # Manager
    "MigrationManager",
    "MigrationStrategy", 
    "MigrationStatus",
    "Migration",
    "MigrationConfig",
    # Versioning
    "SchemaVersion",
    "VersionManager",
    "VersionStatus",
    # Validation
    "MigrationValidator",
    "ValidationResult",
    "ValidationStatus",
    "DataIntegrityRule",
    "RowCountMatchRule",
    # Rollback
    "RollbackManager",
    "RollbackStrategy",
    "RollbackResult",
    "RollbackStatus",

    # Dual-write
    "DualWriteManager",
    "ReadRoutingStrategy",
    "WriteStrategy",
    "SchemaAdapter",
    # Monitoring
    "MigrationMonitor",
    "MigrationMetrics",
    "MigrationDashboard",
    "MetricType",
]
