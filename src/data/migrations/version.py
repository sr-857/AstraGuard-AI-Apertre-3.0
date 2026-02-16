"""
Schema Version Management for Database Migrations.

Provides version tracking, comparison, and migration history.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
import aiosqlite

logger = logging.getLogger(__name__)


class VersionStatus(Enum):
    """Status of a schema version."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class SchemaVersion:
    """Represents a schema version with metadata."""
    version: str
    name: str
    description: str
    created_at: datetime
    applied_at: Optional[datetime] = None
    status: VersionStatus = VersionStatus.PENDING
    checksum: Optional[str] = None
    execution_time_ms: Optional[float] = None
    rollback_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "status": self.status.value,
            "checksum": self.checksum,
            "execution_time_ms": self.execution_time_ms,
            "rollback_version": self.rollback_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchemaVersion":
        """Create from dictionary."""
        return cls(
            version=data["version"],
            name=data["name"],
            description=data["description"],
            created_at=datetime.fromisoformat(data["created_at"]),
            applied_at=datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None,
            status=VersionStatus(data.get("status", "pending")),
            checksum=data.get("checksum"),
            execution_time_ms=data.get("execution_time_ms"),
            rollback_version=data.get("rollback_version"),
        )


class VersionManager:
    """
    Manages schema versions and migration history.
    
    Tracks all schema changes with full audit trail for rollback capability.
    """
    
    VERSION_TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS schema_versions (
        version TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        applied_at TEXT,
        status TEXT NOT NULL,
        checksum TEXT,
        execution_time_ms REAL,
        rollback_version TEXT,
        metadata TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_schema_versions_status ON schema_versions(status);
    CREATE INDEX IF NOT EXISTS idx_schema_versions_applied_at ON schema_versions(applied_at);
    """
    
    def __init__(self, db_path: str):
        """
        Initialize version manager.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._lock = asyncio.Lock() if 'asyncio' in globals() else None
    
    async def initialize(self) -> None:
        """Initialize version tracking table."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(self.VERSION_TABLE_SCHEMA)
            await db.commit()
            logger.info("Schema version table initialized")
    
    async def register_version(self, version: SchemaVersion) -> None:
        """
        Register a new schema version.
        
        Args:
            version: Schema version to register
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO schema_versions 
                (version, name, description, created_at, applied_at, status, checksum, 
                 execution_time_ms, rollback_version, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version.version,
                    version.name,
                    version.description,
                    version.created_at.isoformat(),
                    version.applied_at.isoformat() if version.applied_at else None,
                    version.status.value,
                    version.checksum,
                    version.execution_time_ms,
                    version.rollback_version,
                    json.dumps(version.to_dict()),
                )
            )
            await db.commit()
            logger.info(f"Registered schema version: {version.version} ({version.name})")
    
    async def update_version_status(
        self, 
        version: str, 
        status: VersionStatus,
        execution_time_ms: Optional[float] = None
    ) -> None:
        """
        Update version status.
        
        Args:
            version: Version identifier
            status: New status
            execution_time_ms: Optional execution time
        """
        async with aiosqlite.connect(self.db_path) as db:
            if execution_time_ms is not None:
                await db.execute(
                    """
                    UPDATE schema_versions 
                    SET status = ?, execution_time_ms = ?, applied_at = ?
                    WHERE version = ?
                    """,
                    (status.value, execution_time_ms, datetime.now().isoformat(), version)
                )
            else:
                await db.execute(
                    "UPDATE schema_versions SET status = ? WHERE version = ?",
                    (status.value, version)
                )
            await db.commit()
            logger.info(f"Updated version {version} status to {status.value}")
    
    async def get_version(self, version: str) -> Optional[SchemaVersion]:
        """
        Get specific version details.
        
        Args:
            version: Version identifier
            
        Returns:
            SchemaVersion if found, None otherwise
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM schema_versions WHERE version = ?",
                (version,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_version(row)
                return None
    
    async def get_all_versions(self) -> List[SchemaVersion]:
        """
        Get all registered versions ordered by creation time.
        
        Returns:
            List of schema versions
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT * FROM schema_versions ORDER BY created_at ASC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_version(row) for row in rows]
    
    async def get_current_version(self) -> Optional[SchemaVersion]:
        """
        Get the most recently applied version.
        
        Returns:
            Current schema version or None
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM schema_versions 
                WHERE status = ? 
                ORDER BY applied_at DESC 
                LIMIT 1
                """,
                (VersionStatus.COMPLETED.value,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_version(row)
                return None
    
    async def get_pending_versions(self) -> List[SchemaVersion]:
        """
        Get all pending versions.
        
        Returns:
            List of pending schema versions
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM schema_versions 
                WHERE status = ? 
                ORDER BY created_at ASC
                """,
                (VersionStatus.PENDING.value,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_version(row) for row in rows]
    
    async def get_failed_versions(self) -> List[SchemaVersion]:
        """
        Get all failed versions.
        
        Returns:
            List of failed schema versions
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM schema_versions 
                WHERE status = ? 
                ORDER BY applied_at DESC
                """,
                (VersionStatus.FAILED.value,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_version(row) for row in rows]
    
    async def is_version_applied(self, version: str) -> bool:
        """
        Check if a version has been successfully applied.
        
        Args:
            version: Version identifier
            
        Returns:
            True if version is completed
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT 1 FROM schema_versions 
                WHERE version = ? AND status = ?
                """,
                (version, VersionStatus.COMPLETED.value)
            ) as cursor:
                return await cursor.fetchone() is not None
    
    async def get_version_history(self, limit: int = 100) -> List[SchemaVersion]:
        """
        Get version history with pagination.
        
        Args:
            limit: Maximum number of versions to return
            
        Returns:
            List of schema versions
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """
                SELECT * FROM schema_versions 
                ORDER BY created_at DESC 
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_version(row) for row in rows]
    
    def _row_to_version(self, row: sqlite3.Row) -> SchemaVersion:
        """Convert database row to SchemaVersion."""
        return SchemaVersion(
            version=row[0],
            name=row[1],
            description=row[2],
            created_at=datetime.fromisoformat(row[3]),
            applied_at=datetime.fromisoformat(row[4]) if row[4] else None,
            status=VersionStatus(row[5]),
            checksum=row[6],
            execution_time_ms=row[7],
            rollback_version=row[8],
        )
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Supports semantic versioning (e.g., "1.2.3").
        
        Args:
            v1: First version
            v2: Second version
            
        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """
        def parse_version(v: str) -> List[int]:
            # Remove 'v' prefix if present
            v = v.lstrip('v')
            parts = v.split('.')
            return [int(p) for p in parts if p.isdigit()]
        
        parts1 = parse_version(v1)
        parts2 = parse_version(v2)
        
        # Pad shorter version with zeros
        max_len = max(len(parts1), len(parts2))
        parts1.extend([0] * (max_len - len(parts1)))
        parts2.extend([0] * (max_len - len(parts2)))
        
        for p1, p2 in zip(parts1, parts2):
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
        return 0


# Import asyncio for type hints
import asyncio
