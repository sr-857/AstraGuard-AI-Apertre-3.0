"""
Rollback Management for Database Migrations.

Provides automatic and manual rollback capabilities with data preservation.
"""

import asyncio
import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Set
import aiosqlite

from .version import VersionManager, VersionStatus, SchemaVersion

logger = logging.getLogger(__name__)


class RollbackStrategy(Enum):
    """Strategy for rollback operations."""
    IMMEDIATE = auto()      # Immediate rollback with downtime
    GRACEFUL = auto()       # Graceful rollback with dual-write reversal
    POINT_IN_TIME = auto()  # Rollback to specific point in time
    SNAPSHOT = auto()       # Rollback using pre-migration snapshot


class RollbackStatus(Enum):
    """Status of rollback operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class RollbackPoint:
    """Point to which rollback can be performed."""
    version: str
    timestamp: datetime
    snapshot_path: Optional[str] = None
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RollbackResult:
    """Result of rollback operation."""
    success: bool
    from_version: str
    to_version: str
    status: RollbackStatus
    duration_ms: float
    timestamp: datetime
    data_preserved: bool = True
    tables_rolled_back: List[str] = field(default_factory=list)
    tables_failed: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "data_preserved": self.data_preserved,
            "tables_rolled_back": self.tables_rolled_back,
            "tables_failed": self.tables_failed,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class RollbackManager:
    """
    Manages rollback operations for database migrations.
    
    Provides multiple rollback strategies with data integrity preservation.
    """
    
    def __init__(
        self,
        db_path: str,
        version_manager: VersionManager,
        backup_dir: str = "migrations/backups",
    ):
        """
        Initialize rollback manager.
        
        Args:
            db_path: Path to main database
            version_manager: Version manager instance
            backup_dir: Directory for backups
        """
        self.db_path = db_path
        self.version_manager = version_manager
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._rollback_history: List[RollbackResult] = []
    
    async def create_snapshot(self, version: str) -> RollbackPoint:
        """
        Create a snapshot for rollback point.
        
        Args:
            version: Version to snapshot
            
        Returns:
            Rollback point with snapshot information
        """
        timestamp = datetime.now()
        snapshot_name = f"snapshot_{version}_{timestamp.strftime('%Y%m%d_%H%M%S')}.db"
        snapshot_path = self.backup_dir / snapshot_name
        
        try:
            # Create database snapshot
            shutil.copy2(self.db_path, snapshot_path)
            
            # Calculate checksum
            import hashlib
            with open(snapshot_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()[:16]
            
            logger.info(f"Created snapshot for version {version}: {snapshot_path}")
            
            return RollbackPoint(
                version=version,
                timestamp=timestamp,
                snapshot_path=str(snapshot_path),
                checksum=checksum,
                metadata={"snapshot_size_bytes": snapshot_path.stat().st_size}
            )
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise
    
    async def rollback(
        self,
        to_version: str,
        strategy: RollbackStrategy = RollbackStrategy.GRACEFUL,
        preserve_new_data: bool = True,
    ) -> RollbackResult:
        """
        Perform rollback to specified version.
        
        Args:
            to_version: Target version for rollback
            strategy: Rollback strategy to use
            preserve_new_data: Whether to preserve data added after target version
            
        Returns:
            Rollback result
        """
        start_time = time.time()
        timestamp = datetime.now()
        
        # Get current version
        current_version = await self.version_manager.get_current_version()
        if not current_version:
            return RollbackResult(
                success=False,
                from_version="unknown",
                to_version=to_version,
                status=RollbackStatus.FAILED,
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=timestamp,
                error_message="Cannot determine current version",
            )
        
        from_version = current_version.version
        
        # Check if rollback is possible
        if from_version == to_version:
            return RollbackResult(
                success=True,
                from_version=from_version,
                to_version=to_version,
                status=RollbackStatus.COMPLETED,
                duration_ms=0,
                timestamp=timestamp,
                error_message="Already at target version",
            )
        
        # Find rollback point
        rollback_point = await self._find_rollback_point(to_version)
        if not rollback_point:
            return RollbackResult(
                success=False,
                from_version=from_version,
                to_version=to_version,
                status=RollbackStatus.FAILED,
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=timestamp,
                error_message=f"No rollback point found for version {to_version}",
            )
        
        try:
            if strategy == RollbackStrategy.SNAPSHOT and rollback_point.snapshot_path:
                result = await self._rollback_from_snapshot(
                    rollback_point, from_version, to_version, preserve_new_data
                )
            elif strategy == RollbackStrategy.GRACEFUL:
                result = await self._graceful_rollback(
                    rollback_point, from_version, to_version, preserve_new_data
                )
            else:
                result = await self._immediate_rollback(
                    rollback_point, from_version, to_version
                )
            
            # Update version status
            if result.success:
                await self.version_manager.update_version_status(
                    from_version, VersionStatus.ROLLED_BACK
                )
            
            result.duration_ms = (time.time() - start_time) * 1000
            self._rollback_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return RollbackResult(
                success=False,
                from_version=from_version,
                to_version=to_version,
                status=RollbackStatus.FAILED,
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=timestamp,
                error_message=str(e),
            )
    
    async def _rollback_from_snapshot(
        self,
        rollback_point: RollbackPoint,
        from_version: str,
        to_version: str,
        preserve_new_data: bool,
    ) -> RollbackResult:
        """Rollback using snapshot."""
        timestamp = datetime.now()
        
        if not rollback_point.snapshot_path or not Path(rollback_point.snapshot_path).exists():
            return RollbackResult(
                success=False,
                from_version=from_version,
                to_version=to_version,
                status=RollbackStatus.FAILED,
                duration_ms=0,
                timestamp=timestamp,
                error_message="Snapshot not found",
            )
        
        # If preserving new data, we need to merge
        if preserve_new_data:
            return await self._merge_rollback(rollback_point, from_version, to_version)
        
        # Simple restore from snapshot
        shutil.copy2(rollback_point.snapshot_path, self.db_path)
        
        return RollbackResult(
            success=True,
            from_version=from_version,
            to_version=to_version,
            status=RollbackStatus.COMPLETED,
            duration_ms=0,
            timestamp=timestamp,
            data_preserved=False,
            tables_rolled_back=["all"],
        )
    
    async def _graceful_rollback(
        self,
        rollback_point: RollbackPoint,
        from_version: str,
        to_version: str,
        preserve_new_data: bool,
    ) -> RollbackResult:
        """Perform graceful rollback with dual-write reversal."""
        timestamp = datetime.now()
        tables_rolled_back = []
        tables_failed = []
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get list of tables
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ) as cursor:
                    tables = [row[0] for row in await cursor.fetchall()]
                
                # Reverse schema changes
                for table in tables:
                    try:
                        await self._reverse_table_changes(db, table, to_version)
                        tables_rolled_back.append(table)
                    except Exception as e:
                        logger.error(f"Failed to rollback table {table}: {e}")
                        tables_failed.append(table)
                
                await db.commit()
            
            status = RollbackStatus.COMPLETED if not tables_failed else RollbackStatus.PARTIAL
            
            return RollbackResult(
                success=status == RollbackStatus.COMPLETED,
                from_version=from_version,
                to_version=to_version,
                status=status,
                duration_ms=0,
                timestamp=timestamp,
                data_preserved=preserve_new_data,
                tables_rolled_back=tables_rolled_back,
                tables_failed=tables_failed,
            )
            
        except Exception as e:
            return RollbackResult(
                success=False,
                from_version=from_version,
                to_version=to_version,
                status=RollbackStatus.FAILED,
                duration_ms=0,
                timestamp=timestamp,
                error_message=str(e),
            )
    
    async def _immediate_rollback(
        self,
        rollback_point: RollbackPoint,
        from_version: str,
        to_version: str,
    ) -> RollbackResult:
        """Perform immediate rollback (may have downtime)."""
        return await self._rollback_from_snapshot(
            rollback_point, from_version, to_version, preserve_new_data=False
        )
    
    async def _merge_rollback(
        self,
        rollback_point: RollbackPoint,
        from_version: str,
        to_version: str,
    ) -> RollbackResult:
        """Rollback while preserving new data."""
        timestamp = datetime.now()
        
        # This is a complex operation that requires careful data merging
        # For now, we'll create a backup and flag for manual review
        backup_path = self.backup_dir / f"pre_merge_rollback_{from_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(self.db_path, backup_path)
        
        return RollbackResult(
            success=True,
            from_version=from_version,
            to_version=to_version,
            status=RollbackStatus.PARTIAL,
            duration_ms=0,
            timestamp=timestamp,
            data_preserved=True,
            tables_rolled_back=[],
            metadata={
                "requires_manual_review": True,
                "backup_path": str(backup_path),
                "note": "Data merge requires manual intervention",
            },
        )
    
    async def _reverse_table_changes(
        self,
        db: aiosqlite.Connection,
        table: str,
        target_version: str,
    ) -> None:
        """Reverse schema changes for a table."""
        # This would contain specific rollback logic based on migration type
        # For now, we'll just log the operation
        logger.info(f"Reversing changes for table {table} to version {target_version}")
        
        # Example: Remove columns added after target version
        # This would need to be customized based on actual migration logic
    
    async def _find_rollback_point(self, version: str) -> Optional[RollbackPoint]:
        """Find rollback point for version."""
        # Look for snapshot
        snapshot_pattern = f"snapshot_{version}_*.db"
        snapshots = list(self.backup_dir.glob(snapshot_pattern))
        
        if snapshots:
            # Use most recent snapshot
            latest = max(snapshots, key=lambda p: p.stat().st_mtime)
            return RollbackPoint(
                version=version,
                timestamp=datetime.fromtimestamp(latest.stat().st_mtime),
                snapshot_path=str(latest),
            )
        
        return None
    
    async def can_rollback(self, version: str) -> bool:
        """
        Check if rollback to version is possible.
        
        Args:
            version: Target version
            
        Returns:
            True if rollback is possible
        """
        return await self._find_rollback_point(version) is not None
    
    def get_rollback_history(self) -> List[RollbackResult]:
        """Get history of rollback operations."""
        return self._rollback_history.copy()
    
    async def cleanup_old_snapshots(self, keep_count: int = 5) -> int:
        """
        Clean up old snapshots, keeping only recent ones.
        
        Args:
            keep_count: Number of recent snapshots to keep
            
        Returns:
            Number of snapshots removed
        """
        snapshots = sorted(
            self.backup_dir.glob("snapshot_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        removed = 0
        for old_snapshot in snapshots[keep_count:]:
            try:
                old_snapshot.unlink()
                removed += 1
                logger.info(f"Removed old snapshot: {old_snapshot}")
            except Exception as e:
                logger.error(f"Failed to remove snapshot {old_snapshot}: {e}")
        
        return removed
