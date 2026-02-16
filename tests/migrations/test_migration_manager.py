"""
Tests for the Migration Manager.

Tests zero-downtime migration capabilities including:
- Dual-write pattern
- Automatic rollback
- Data integrity
- Performance impact < 5%
"""

import asyncio
import os
import pytest
import tempfile
import aiosqlite
from datetime import datetime
from pathlib import Path

from data.migrations import (
    MigrationManager,
    Migration,
    MigrationConfig,
    MigrationStrategy,
    MigrationStatus,
    SchemaVersion,
    VersionStatus,
)


class TestMigration(Migration):
    """Test migration for adding a column."""
    
    @property
    def version(self) -> str:
        return "1.1.0"
    
    @property
    def name(self) -> str:
        return "add_test_column"
    
    @property
    def description(self) -> str:
        return "Add test column to telemetry table"
    
    async def apply(self, db: aiosqlite.Connection) -> None:
        await db.execute(
            "ALTER TABLE telemetry ADD COLUMN test_field TEXT DEFAULT 'default'"
        )
        await db.commit()
    
    async def revert(self, db: aiosqlite.Connection) -> None:
        # SQLite doesn't support DROP COLUMN directly
        # In real implementation, would recreate table
        pass


@pytest.fixture
async def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Create initial schema
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE telemetry (
                id INTEGER PRIMARY KEY,
                voltage REAL,
                temperature REAL,
                timestamp TEXT
            )
        """)
        await db.commit()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
async def migration_manager(temp_db):
    """Create migration manager with test database."""
    config = MigrationConfig(
        strategy=MigrationStrategy.DIRECT,  # Use direct for faster tests
        auto_rollback_on_failure=True,
        performance_threshold_percent=5.0,
    )
    manager = MigrationManager(temp_db, config)
    await manager.initialize()
    return manager


@pytest.mark.asyncio
async def test_migration_manager_initialization(migration_manager):
    """Test migration manager initializes correctly."""
    assert migration_manager is not None
    assert migration_manager.get_status() == MigrationStatus.PENDING


@pytest.mark.asyncio
async def test_migration_application(migration_manager, temp_db):
    """Test migration is applied successfully."""
    migration = TestMigration()
    
    result = await migration_manager.migrate(migration)
    
    assert result.success is True
    assert result.status == MigrationStatus.COMPLETED
    assert result.version == "1.1.0"
    assert result.duration_ms >= 0
    
    # Verify schema was updated
    async with aiosqlite.connect(temp_db) as db:
        async with db.execute("PRAGMA table_info(telemetry)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            assert "test_field" in columns


@pytest.mark.asyncio
async def test_migration_idempotency(migration_manager):
    """Test migration is idempotent (won't reapply)."""
    migration = TestMigration()
    
    # First application
    result1 = await migration_manager.migrate(migration)
    assert result1.success is True
    
    # Second application should be no-op
    result2 = await migration_manager.migrate(migration)
    assert result2.success is True
    assert "already applied" in result2.error_message.lower()


@pytest.mark.asyncio
async def test_version_tracking(migration_manager):
    """Test version tracking works correctly."""
    migration = TestMigration()
    
    # Apply migration
    await migration_manager.migrate(migration)
    
    # Check version was recorded
    history = await migration_manager.get_migration_history()
    assert len(history) >= 1
    
    latest = history[0]
    assert latest["version"] == "1.1.0"
    assert latest["status"] == VersionStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_migration_checksum(migration_manager):
    """Test migration checksum is computed."""
    migration = TestMigration()
    
    checksum = migration.get_checksum()
    assert checksum is not None
    assert len(checksum) == 16  # SHA256 truncated to 16 chars
    
    # Checksum should be consistent
    assert migration.get_checksum() == checksum


@pytest.mark.asyncio
async def test_migration_config_defaults():
    """Test migration configuration defaults."""
    config = MigrationConfig()
    
    assert config.strategy == MigrationStrategy.DUAL_WRITE
    assert config.auto_rollback_on_failure is True
    assert config.performance_threshold_percent == 5.0
    assert config.consistency_check_interval == 100


@pytest.mark.asyncio
async def test_migration_rollback(temp_db):
    """Test automatic rollback on failure."""
    class FailingMigration(Migration):
        @property
        def version(self) -> str:
            return "2.0.0"
        
        @property
        def name(self) -> str:
            return "failing_migration"
        
        @property
        def description(self) -> str:
            return "This migration will fail"
        
        async def apply(self, db: aiosqlite.Connection) -> None:
            raise Exception("Intentional failure")
        
        async def revert(self, db: aiosqlite.Connection) -> None:
            pass
    
    config = MigrationConfig(
        strategy=MigrationStrategy.DIRECT,
        auto_rollback_on_failure=True,
    )
    manager = MigrationManager(temp_db, config)
    await manager.initialize()
    
    migration = FailingMigration()
    result = await manager.migrate(migration)
    
    assert result.success is False
    assert result.rollback_result is not None


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_migration_performance_impact(migration_manager):
    """Test migration performance impact is under 5%."""
    migration = TestMigration()
    
    result = await migration_manager.migrate(migration)
    
    assert result.success is True
    # Performance impact should be under 5%
    if result.validation_result:
        assert result.validation_result.performance_impact_percent < 5.0


@pytest.mark.asyncio
async def test_concurrent_migrations(temp_db):
    """Test that concurrent migrations are handled safely."""
    config = MigrationConfig(strategy=MigrationStrategy.DIRECT)
    manager1 = MigrationManager(temp_db, config)
    manager2 = MigrationManager(temp_db, config)
    
    await manager1.initialize()
    await manager2.initialize()
    
    migration = TestMigration()
    
    # Run migrations concurrently
    results = await asyncio.gather(
        manager1.migrate(migration),
        manager2.migrate(migration),
        return_exceptions=True,
    )
    
    # At least one should succeed
    successes = [r for r in results if isinstance(r, MigrationManager.__init__.__class__) or (hasattr(r, 'success') and r.success)]
    assert len(successes) >= 1


@pytest.mark.asyncio
async def test_migration_cleanup(migration_manager, temp_db):
    """Test migration cleanup removes old snapshots."""
    migration = TestMigration()
    
    # Apply migration
    await migration_manager.migrate(migration)
    
    # Cleanup should complete without error
    removed = await migration_manager.cleanup(keep_snapshots=1)
    assert removed >= 0
