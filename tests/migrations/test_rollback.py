"""
Tests for Migration Rollback Capabilities.

Tests automatic and manual rollback including:
- Snapshot creation and restoration
- Graceful rollback with data preservation
- Rollback validation
- Multiple rollback strategies
"""

import os
import pytest
import tempfile
import aiosqlite
from pathlib import Path
from datetime import datetime

from data.migrations import (
    RollbackManager,
    RollbackStrategy,
    RollbackStatus,
    VersionManager,
    SchemaVersion,
    VersionStatus,
)


@pytest.fixture
async def rollback_setup():
    """Create rollback manager with test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Create initial schema
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE telemetry (
                id INTEGER PRIMARY KEY,
                voltage REAL,
                temperature REAL
            )
        """)
        await db.execute("""
            INSERT INTO telemetry (voltage, temperature) VALUES (12.5, 25.0)
        """)
        await db.commit()
    
    version_manager = VersionManager(db_path)
    await version_manager.initialize()
    
    backup_dir = tempfile.mkdtemp()
    rollback_manager = RollbackManager(db_path, version_manager, backup_dir)
    
    yield rollback_manager, db_path, version_manager, backup_dir
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    if os.path.exists(backup_dir):
        import shutil
        shutil.rmtree(backup_dir)


@pytest.mark.asyncio
async def test_snapshot_creation(rollback_setup):
    """Test snapshot creation for rollback."""
    rollback_manager, db_path, _, _ = rollback_setup
    
    version = "1.0.0"
    rollback_point = await rollback_manager.create_snapshot(version)
    
    assert rollback_point.version == version
    assert rollback_point.snapshot_path is not None
    assert os.path.exists(rollback_point.snapshot_path)
    assert rollback_point.checksum is not None


@pytest.mark.asyncio
async def test_rollback_to_snapshot(rollback_setup):
    """Test rollback using snapshot."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    # Create initial version
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    
    # Create snapshot
    await rollback_manager.create_snapshot("1.0.0")
    
    # Modify database (simulate migration)
    async with aiosqlite.connect(db_path) as db:
        await db.execute("ALTER TABLE telemetry ADD COLUMN new_field TEXT")
        await db.commit()
    
    # Rollback
    result = await rollback_manager.rollback(
        "1.0.0",
        RollbackStrategy.SNAPSHOT,
        preserve_new_data=False,
    )
    
    assert result.success is True
    assert result.to_version == "1.0.0"
    assert result.status == RollbackStatus.COMPLETED


@pytest.mark.asyncio
async def test_graceful_rollback(rollback_setup):
    """Test graceful rollback strategy."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    # Create version
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    await rollback_manager.create_snapshot("1.0.0")
    
    # Rollback gracefully
    result = await rollback_manager.rollback(
        "1.0.0",
        RollbackStrategy.GRACEFUL,
        preserve_new_data=True,
    )
    
    assert result.to_version == "1.0.0"
    assert result.data_preserved is True


@pytest.mark.asyncio
async def test_rollback_idempotency(rollback_setup):
    """Test rollback is idempotent."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    await rollback_manager.create_snapshot("1.0.0")
    
    # First rollback
    result1 = await rollback_manager.rollback("1.0.0", RollbackStrategy.SNAPSHOT)
    
    # Second rollback to same version
    result2 = await rollback_manager.rollback("1.0.0", RollbackStrategy.SNAPSHOT)
    
    assert result2.success is True
    assert "already at target" in result2.error_message.lower() or result2.status == RollbackStatus.COMPLETED


@pytest.mark.asyncio
async def test_rollback_without_snapshot(rollback_setup):
    """Test rollback fails gracefully without snapshot."""
    rollback_manager, _, _, _ = rollback_setup
    
    result = await rollback_manager.rollback(
        "2.0.0",  # No snapshot for this version
        RollbackStrategy.SNAPSHOT,
    )
    
    assert result.success is False
    assert result.status == RollbackStatus.FAILED
    assert "no rollback point" in result.error_message.lower() or "snapshot not found" in result.error_message.lower()


@pytest.mark.asyncio
async def test_can_rollback_check(rollback_setup):
    """Test can_rollback method."""
    rollback_manager, _, _, _ = rollback_setup
    
    # Initially cannot rollback
    can_rollback = await rollback_manager.can_rollback("1.0.0")
    assert can_rollback is False
    
    # Create snapshot
    await rollback_manager.create_snapshot("1.0.0")
    
    # Now can rollback
    can_rollback = await rollback_manager.can_rollback("1.0.0")
    assert can_rollback is True


@pytest.mark.asyncio
async def test_rollback_history(rollback_setup):
    """Test rollback history tracking."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    await rollback_manager.create_snapshot("1.0.0")
    
    # Perform rollback
    await rollback_manager.rollback("1.0.0", RollbackStrategy.SNAPSHOT)
    
    # Check history
    history = rollback_manager.get_rollback_history()
    assert len(history) >= 1
    
    latest = history[-1]
    assert latest.to_version == "1.0.0"


@pytest.mark.asyncio
async def test_cleanup_old_snapshots(rollback_setup):
    """Test cleanup of old snapshots."""
    rollback_manager, _, _, _ = rollback_setup
    
    # Create multiple snapshots
    for i in range(5):
        await rollback_manager.create_snapshot(f"1.0.{i}")
    
    # Cleanup, keeping only 2
    removed = await rollback_manager.cleanup_old_snapshots(keep_count=2)
    
    assert removed >= 3  # At least 3 should be removed


@pytest.mark.asyncio
async def test_rollback_preserves_data(rollback_setup):
    """Test rollback with data preservation."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    # Create version and snapshot
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    await rollback_manager.create_snapshot("1.0.0")
    
    # Add more data after snapshot
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO telemetry (voltage, temperature) VALUES (13.0, 26.0)"
        )
        await db.commit()
    
    # Rollback with data preservation
    result = await rollback_manager.rollback(
        "1.0.0",
        RollbackStrategy.GRACEFUL,
        preserve_new_data=True,
    )
    
    assert result.data_preserved is True


@pytest.mark.asyncio
async def test_rollback_performance(rollback_setup):
    """Test rollback performance."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    version = SchemaVersion(
        version="1.0.0",
        name="initial",
        description="Initial schema",
        created_at=datetime.now(),
        status=VersionStatus.COMPLETED,
    )
    await version_manager.register_version(version)
    await rollback_manager.create_snapshot("1.0.0")
    
    # Measure rollback time
    import time
    start = time.time()
    
    result = await rollback_manager.rollback("1.0.0", RollbackStrategy.SNAPSHOT)
    
    duration = time.time() - start
    
    assert result.success is True
    assert duration < 5.0  # Should complete in under 5 seconds
    assert result.duration_ms < 5000


@pytest.mark.asyncio
async def test_multiple_version_rollback(rollback_setup):
    """Test rollback across multiple versions."""
    rollback_manager, db_path, version_manager, _ = rollback_setup
    
    # Create multiple versions
    for v in ["1.0.0", "1.1.0", "1.2.0"]:
        version = SchemaVersion(
            version=v,
            name=f"version_{v}",
            description=f"Version {v}",
            created_at=datetime.now(),
            status=VersionStatus.COMPLETED,
        )
        await version_manager.register_version(version)
        await rollback_manager.create_snapshot(v)
    
    # Rollback to first version
    result = await rollback_manager.rollback("1.0.0", RollbackStrategy.SNAPSHOT)
    
    assert result.success is True
    assert result.from_version != "1.0.0"  # Should be current version
    assert result.to_version == "1.0.0"
