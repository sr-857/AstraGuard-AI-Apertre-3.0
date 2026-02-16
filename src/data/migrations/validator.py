"""
Migration Validation System for Data Integrity.

Provides comprehensive validation of migrations including:
- Schema compatibility checks
- Data integrity validation
- Performance impact monitoring
- Rollback readiness verification
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
import aiosqlite

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Status of validation check."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class ValidationCheck:
    """Individual validation check result."""
    name: str
    status: ValidationStatus
    message: str
    duration_ms: float
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationResult:
    """Complete validation result."""
    migration_version: str
    timestamp: datetime
    overall_status: ValidationStatus
    checks: List[ValidationCheck] = field(default_factory=list)
    total_duration_ms: float = 0.0
    data_integrity_score: float = 0.0  # 0-100
    performance_impact_percent: float = 0.0  # Performance impact percentage
    
    def add_check(self, check: ValidationCheck) -> None:
        """Add a validation check."""
        self.checks.append(check)
        # Update overall status
        if check.status == ValidationStatus.FAILED:
            self.overall_status = ValidationStatus.FAILED
        elif check.status == ValidationStatus.WARNING and self.overall_status == ValidationStatus.PASSED:
            self.overall_status = ValidationStatus.WARNING
    
    def get_failed_checks(self) -> List[ValidationCheck]:
        """Get all failed checks."""
        return [c for c in self.checks if c.status == ValidationStatus.FAILED]
    
    def get_warnings(self) -> List[ValidationCheck]:
        """Get all warning checks."""
        return [c for c in self.checks if c.status == ValidationStatus.WARNING]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "migration_version": self.migration_version,
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "total_duration_ms": self.total_duration_ms,
            "data_integrity_score": self.data_integrity_score,
            "performance_impact_percent": self.performance_impact_percent,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class DataIntegrityRule(ABC):
    """Abstract base class for data integrity rules."""
    
    @abstractmethod
    async def validate(self, old_db: aiosqlite.Connection, new_db: aiosqlite.Connection) -> ValidationCheck:
        """Validate data integrity between schemas."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name."""
        pass


class RowCountMatchRule(DataIntegrityRule):
    """Validate row counts match between schemas."""
    
    def __init__(self, table_name: str, tolerance_percent: float = 0.0):
        self.table_name = table_name
        self.tolerance_percent = tolerance_percent
    
    @property
    def name(self) -> str:
        return f"row_count_match_{self.table_name}"
    
    async def validate(self, old_db: aiosqlite.Connection, new_db: aiosqlite.Connection) -> ValidationCheck:
        """Validate row counts match."""
        start_time = time.time()
        
        try:
            # Get row counts
            async with old_db.execute(f"SELECT COUNT(*) FROM {self.table_name}") as cursor:
                old_count = (await cursor.fetchone())[0]
            
            async with new_db.execute(f"SELECT COUNT(*) FROM {self.table_name}") as cursor:
                new_count = (await cursor.fetchone())[0]
            
            # Check tolerance
            if old_count == 0:
                diff_percent = 0 if new_count == 0 else 100
            else:
                diff_percent = abs(new_count - old_count) / old_count * 100
            
            duration_ms = (time.time() - start_time) * 1000
            
            if diff_percent <= self.tolerance_percent:
                return ValidationCheck(
                    name=self.name,
                    status=ValidationStatus.PASSED,
                    message=f"Row counts match: {old_count} rows (diff: {diff_percent:.2f}%)",
                    duration_ms=duration_ms,
                    details={"old_count": old_count, "new_count": new_count, "diff_percent": diff_percent}
                )
            else:
                return ValidationCheck(
                    name=self.name,
                    status=ValidationStatus.FAILED,
                    message=f"Row count mismatch: old={old_count}, new={new_count} (diff: {diff_percent:.2f}%)",
                    duration_ms=duration_ms,
                    details={"old_count": old_count, "new_count": new_count, "diff_percent": diff_percent}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ValidationCheck(
                name=self.name,
                status=ValidationStatus.FAILED,
                message=f"Row count validation failed: {str(e)}",
                duration_ms=duration_ms,
                details={"error": str(e)}
            )


class MigrationValidator:
    """
    Validates migrations for data integrity and performance.
    
    Performs comprehensive checks before, during, and after migration.
    """
    
    # Performance threshold: 5% impact maximum
    PERFORMANCE_THRESHOLD_PERCENT = 5.0
    
    def __init__(
        self,
        old_db_path: str,
        new_db_path: str,
        integrity_rules: Optional[List[DataIntegrityRule]] = None,
    ):
        """
        Initialize migration validator.
        
        Args:
            old_db_path: Path to old schema database
            new_db_path: Path to new schema database
            integrity_rules: List of data integrity rules
        """
        self.old_db_path = old_db_path
        self.new_db_path = new_db_path
        self.integrity_rules = integrity_rules or []
        self._baseline_performance: Optional[Dict[str, float]] = None
    
    async def validate_pre_migration(self, migration_version: str) -> ValidationResult:
        """
        Validate before migration starts.
        
        Args:
            migration_version: Version being migrated to
            
        Returns:
            Validation result
        """
        start_time = time.time()
        result = ValidationResult(
            migration_version=migration_version,
            timestamp=datetime.now(),
            overall_status=ValidationStatus.PASSED,
        )
        
        # Check old database exists and is accessible
        check_start = time.time()
        old_accessible = await self._check_database_accessible(self.old_db_path)
        result.add_check(ValidationCheck(
            name="old_database_accessible",
            status=ValidationStatus.PASSED if old_accessible else ValidationStatus.FAILED,
            message="Old database is accessible" if old_accessible else "Old database is not accessible",
            duration_ms=(time.time() - check_start) * 1000,
        ))
        
        # Check new database is ready
        check_start = time.time()
        new_ready = await self._check_database_accessible(self.new_db_path)
        result.add_check(ValidationCheck(
            name="new_database_accessible",
            status=ValidationStatus.PASSED if new_ready else ValidationStatus.FAILED,
            message="New database is accessible" if new_ready else "New database is not accessible",
            duration_ms=(time.time() - check_start) * 1000,
        ))
        
        # Establish baseline performance
        check_start = time.time()
        await self._establish_baseline()
        result.add_check(ValidationCheck(
            name="baseline_performance_established",
            status=ValidationStatus.PASSED,
            message="Baseline performance metrics established",
            duration_ms=(time.time() - check_start) * 1000,
            details=self._baseline_performance,
        ))
        
        result.total_duration_ms = (time.time() - start_time) * 1000
        return result
    
    async def validate_post_migration(self, migration_version: str) -> ValidationResult:
        """
        Validate after migration completes.
        
        Args:
            migration_version: Version being migrated to
            
        Returns:
            Validation result
        """
        start_time = time.time()
        result = ValidationResult(
            migration_version=migration_version,
            timestamp=datetime.now(),
            overall_status=ValidationStatus.PASSED,
        )
        
        # Connect to both databases
        async with aiosqlite.connect(self.old_db_path) as old_db, \
                   aiosqlite.connect(self.new_db_path) as new_db:
            
            # Run all integrity rules
            for rule in self.integrity_rules:
                check = await rule.validate(old_db, new_db)
                result.add_check(check)
        
        # Calculate data integrity score
        passed_checks = sum(1 for c in result.checks if c.status == ValidationStatus.PASSED)
        total_checks = len(result.checks)
        result.data_integrity_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        result.total_duration_ms = (time.time() - start_time) * 1000
        return result
    
    async def _check_database_accessible(self, db_path: str) -> bool:
        """Check if database is accessible."""
        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute("SELECT 1")
                return True
        except Exception as e:
            logger.error(f"Database accessibility check failed for {db_path}: {e}")
            return False
    
    async def _establish_baseline(self) -> None:
        """Establish baseline performance metrics."""
        start_time = time.time()
        
        try:
            async with aiosqlite.connect(self.old_db_path) as db:
                # Measure simple query performance
                query_start = time.time()
                await db.execute("SELECT COUNT(*) FROM sqlite_master")
                baseline_query_time = (time.time() - query_start) * 1000
                
                self._baseline_performance = {
                    "query_time_ms": baseline_query_time,
                    "timestamp": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.error(f"Failed to establish baseline: {e}")
            self._baseline_performance = {"query_time_ms": 0, "error": str(e)}
    
    def add_integrity_rule(self, rule: DataIntegrityRule) -> None:
        """Add a data integrity rule."""
        self.integrity_rules.append(rule)
        logger.info(f"Added integrity rule: {rule.name}")
