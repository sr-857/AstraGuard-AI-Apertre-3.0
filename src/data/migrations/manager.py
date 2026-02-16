"""
Migration Manager for Zero-Downtime Database Migrations.

Coordinates the entire migration process with dual-write pattern,
validation, monitoring, and automatic rollback.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type, Set
import aiosqlite

from .version import VersionManager, SchemaVersion, VersionStatus
from .dual_write import DualWriteManager, SchemaAdapter, ReadRoutingStrategy, WriteStrategy
from .validator import MigrationValidator, ValidationResult, ValidationStatus
from .rollback import RollbackManager, RollbackStrategy, RollbackResult

logger = logging.getLogger(__name__)


class MigrationStrategy(Enum):
    """Strategy for executing migrations."""
    DIRECT = auto()         # Direct migration with downtime
    DUAL_WRITE = auto()     # Zero-downtime with dual-write
    BLUE_GREEN = auto()       # Blue-green deployment
    CANARY = auto()           # Canary release


class MigrationStatus(Enum):
    """Status of migration operation."""
    PENDING = "pending"
    PRE_VALIDATION = "pre_validation"
    SNAPSHOT_CREATED = "snapshot_created"
    IN_PROGRESS = "in_progress"
    DUAL_WRITE_ACTIVE = "dual_write_active"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


@dataclass
class MigrationConfig:
    """Configuration for migration."""
    strategy: MigrationStrategy = MigrationStrategy.DUAL_WRITE
    auto_rollback_on_failure: bool = True
    performance_threshold_percent: float = 5.0
    consistency_check_interval: int = 100
    gradual_shift_increment: float = 10.0
    max_dual_write_duration_minutes: int = 60
    preserve_data_on_rollback: bool = True


@dataclass
class MigrationResult:
    """Result of migration operation."""
    success: bool
    version: str
    status: MigrationStatus
    duration_ms: float
    timestamp: datetime
    dual_write_stats: Optional[Dict[str, Any]] = None
    validation_result: Optional[ValidationResult] = None
    rollback_result: Optional[RollbackResult] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "version": self.version,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "dual_write_stats": self.dual_write_stats,
            "validation_result": self.validation_result.to_dict() if self.validation_result else None,
            "rollback_result": self.rollback_result.to_dict() if self.rollback_result else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


class Migration(ABC):
    """Abstract base class for migrations."""
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Migration version."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Migration name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Migration description."""
        pass
    
    @abstractmethod
    async def apply(self, db: aiosqlite.Connection) -> None:
        """Apply migration."""
        pass
    
    @abstractmethod
    async def revert(self, db: aiosqlite.Connection) -> None:
        """Revert migration."""
        pass
    
    def get_checksum(self) -> str:
        """Get migration checksum."""
        content = f"{self.version}:{self.name}:{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class SQLiteSchemaAdapter(SchemaAdapter):
    """SQLite adapter for schema operations."""
    
    def __init__(self, db_path: str, schema_version: str):
        self.db_path = db_path
        self.schema_version = schema_version
    
    async def read(self, key: str) -> Optional[Any]:
        """Read data by key."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT value FROM migration_data WHERE key = ?",
                    (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return json.loads(row[0])
                    return None
        except Exception:
            return None
    
    async def write(self, key: str, value: Any) -> bool:
        """Write data."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO migration_data (key, value, schema_version, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (key, json.dumps(value), self.schema_version, datetime.now().isoformat())
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"Write failed: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete data."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM migration_data WHERE key = ?",
                    (key,)
                )
                await db.commit()
                return True
        except Exception:
            return False
    
    async def query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    async def health_check(self) -> bool:
        """Check if schema is healthy."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
                return True
        except Exception:
            return False


class MigrationManager:
    """
    Manages database migrations with zero-downtime support.
    
    Coordinates version management, dual-write operations, validation,
    monitoring, and rollback capabilities.
    """
    
    def __init__(
        self,
        db_path: str,
        config: Optional[MigrationConfig] = None,
    ):
        """
        Initialize migration manager.
        
        Args:
            db_path: Path to SQLite database
            config: Migration configuration
        """
        self.db_path = db_path
        self.config = config or MigrationConfig()
        self.version_manager = VersionManager(db_path)
        self.rollback_manager = RollbackManager(db_path, self.version_manager)
        self.validator: Optional[MigrationValidator] = None
        self.dual_write_manager: Optional[DualWriteManager] = None
        self._current_migration: Optional[Migration] = None
        self._status = MigrationStatus.PENDING
    
    async def initialize(self) -> None:
        """Initialize migration system."""
        await self.version_manager.initialize()
        
        # Create migration data table if not exists
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS migration_data (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    schema_version TEXT,
                    updated_at TEXT
                )
            """)
            await db.commit()
        
        logger.info("Migration system initialized")
    
    async def migrate(self, migration: Migration) -> MigrationResult:
        """
        Execute migration with zero-downtime support.
        
        Args:
            migration: Migration to apply
            
        Returns:
            Migration result
        """
        start_time = time.time()
        timestamp = datetime.now()
        self._current_migration = migration
        self._status = MigrationStatus.PENDING
        
        # Check if already applied
        if await self.version_manager.is_version_applied(migration.version):
            return MigrationResult(
                success=True,
                version=migration.version,
                status=MigrationStatus.COMPLETED,
                duration_ms=0,
                timestamp=timestamp,
                error_message="Migration already applied",
            )
        
        try:
            # Phase 1: Pre-validation
            self._status = MigrationStatus.PRE_VALIDATION
            pre_validation = await self._run_pre_validation(migration)
            if pre_validation.overall_status == ValidationStatus.FAILED:
                return MigrationResult(
                    success=False,
                    version=migration.version,
                    status=MigrationStatus.FAILED,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=timestamp,
                    validation_result=pre_validation,
                    error_message="Pre-validation failed",
                )
            
            # Phase 2: Create snapshot
            self._status = MigrationStatus.SNAPSHOT_CREATED
            rollback_point = await self.rollback_manager.create_snapshot(migration.version)
            
            # Register version
            schema_version = SchemaVersion(
                version=migration.version,
                name=migration.name,
                description=migration.description,
                created_at=timestamp,
                status=VersionStatus.IN_PROGRESS,
                checksum=migration.get_checksum(),
                rollback_version=rollback_point.version,
            )
            await self.version_manager.register_version(schema_version)
            
            # Phase 3: Execute migration based on strategy
            if self.config.strategy == MigrationStrategy.DUAL_WRITE:
                result = await self._execute_dual_write_migration(migration, start_time, timestamp)
            else:
                result = await self._execute_direct_migration(migration, start_time, timestamp)
            
            return result
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            
            # Attempt automatic rollback if enabled
            rollback_result = None
            if self.config.auto_rollback_on_failure:
                self._status = MigrationStatus.ROLLING_BACK
                rollback_result = await self.rollback_manager.rollback(
                    migration.version,
                    RollbackStrategy.GRACEFUL if self.config.strategy == MigrationStrategy.DUAL_WRITE else RollbackStrategy.IMMEDIATE,
                    self.config.preserve_data_on_rollback,
                )
                self._status = MigrationStatus.ROLLED_BACK
            
            await self.version_manager.update_version_status(
                migration.version, VersionStatus.FAILED
            )
            
            return MigrationResult(
                success=False,
                version=migration.version,
                status=self._status,
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=timestamp,
                rollback_result=rollback_result,
                error_message=str(e),
            )
    
    async def _execute_dual_write_migration(
        self,
        migration: Migration,
        start_time: float,
        timestamp: datetime,
    ) -> MigrationResult:
        """Execute migration using dual-write pattern."""
        # Create new database for new schema
        new_db_path = f"{self.db_path}.{migration.version}.new"
        
        # Copy current database to new location
        import shutil
        shutil.copy2(self.db_path, new_db_path)
        
        # Apply migration to new schema
        async with aiosqlite.connect(new_db_path) as db:
            await migration.apply(db)
        
        # Set up dual-write manager
        old_adapter = SQLiteSchemaAdapter(self.db_path, "old")
        new_adapter = SQLiteSchemaAdapter(new_db_path, migration.version)
        
        self.dual_write_manager = DualWriteManager(
            old_adapter=old_adapter,
            new_adapter=new_adapter,
            read_strategy=ReadRoutingStrategy.DUAL_READ,
            write_strategy=WriteStrategy.DUAL_WRITE,
            consistency_check_interval=self.config.consistency_check_interval,
        )
        
        self._status = MigrationStatus.DUAL_WRITE_ACTIVE
        
        # Run dual-write phase for configured duration
        dual_write_duration = min(
            self.config.max_dual_write_duration_minutes * 60,
            300  # Max 5 minutes for safety
        )
        
        logger.info(f"Running dual-write phase for {dual_write_duration} seconds")
        await asyncio.sleep(dual_write_duration)
        
        # Gradually shift traffic
        shift_percentage = 0.0
        while shift_percentage < 100.0:
            shift_percentage = self.dual_write_manager.shift_traffic(
                self.config.gradual_shift_increment
            )
            await asyncio.sleep(10)  # Wait between shifts
            
            # Check health
            health = await self.dual_write_manager.health_check()
            if not health["dual_write_healthy"]:
                raise Exception("Health check failed during traffic shift")
        
        # Phase 4: Post-migration validation
        self._status = MigrationStatus.VALIDATION
        
        # Create validator
        self.validator = MigrationValidator(
            old_db_path=self.db_path,
            new_db_path=new_db_path,
        )
        
        post_validation = await self.validator.validate_post_migration(migration.version)
        
        if post_validation.overall_status == ValidationStatus.FAILED:
            raise Exception("Post-migration validation failed")
        
        # Swap databases
        backup_path = f"{self.db_path}.backup.{migration.version}"
        shutil.move(self.db_path, backup_path)
        shutil.move(new_db_path, self.db_path)
        
        # Update version status
        execution_time = (time.time() - start_time) * 1000
        await self.version_manager.update_version_status(
            migration.version,
            VersionStatus.COMPLETED,
            execution_time_ms=execution_time,
        )
        
        self._status = MigrationStatus.COMPLETED
        
        return MigrationResult(
            success=True,
            version=migration.version,
            status=MigrationStatus.COMPLETED,
            duration_ms=execution_time,
            timestamp=timestamp,
            dual_write_stats=self.dual_write_manager.get_stats(),
            validation_result=post_validation,
        )
    
    async def _execute_direct_migration(
        self,
        migration: Migration,
        start_time: float,
        timestamp: datetime,
    ) -> MigrationResult:
        """Execute direct migration (with brief downtime)."""
        self._status = MigrationStatus.IN_PROGRESS
        
        async with aiosqlite.connect(self.db_path) as db:
            await migration.apply(db)
        
        execution_time = (time.time() - start_time) * 1000
        
        await self.version_manager.update_version_status(
            migration.version,
            VersionStatus.COMPLETED,
            execution_time_ms=execution_time,
        )
        
        self._status = MigrationStatus.COMPLETED
        
        return MigrationResult(
            success=True,
            version=migration.version,
            status=MigrationStatus.COMPLETED,
            duration_ms=execution_time,
            timestamp=timestamp,
        )
    
    async def _run_pre_validation(self, migration: Migration) -> ValidationResult:
        """Run pre-migration validation."""
        # Create temporary validator
        validator = MigrationValidator(
            old_db_path=self.db_path,
            new_db_path=self.db_path,  # Same for pre-validation
        )
        
        return await validator.validate_pre_migration(migration.version)
    
    async def rollback(self, to_version: str, strategy: RollbackStrategy = RollbackStrategy.GRACEFUL) -> RollbackResult:
        """
        Rollback to specified version.
        
        Args:
            to_version: Target version
            strategy: Rollback strategy
            
        Returns:
            Rollback result
        """
        return await self.rollback_manager.rollback(
            to_version,
            strategy,
            self.config.preserve_data_on_rollback,
        )
    
    def get_status(self) -> MigrationStatus:
        """Get current migration status."""
        return self._status
    
    async def get_migration_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get migration history."""
        versions = await self.version_manager.get_version_history(limit)
        return [v.to_dict() for v in versions]
    
    async def cleanup(self, keep_snapshots: int = 5) -> int:
        """Clean up old migration artifacts."""
        return await self.rollback_manager.cleanup_old_snapshots(keep_snapshots)
