"""
Tests for the Dual-Write Pattern.

Tests zero-downtime capabilities including:
- Simultaneous writes to old and new schemas
- Read routing strategies
- Data consistency validation
- Gradual traffic shifting
"""

import os
import pytest
import tempfile
import aiosqlite
import asyncio
from pathlib import Path

from data.migrations import (
    DualWriteManager,
    ReadRoutingStrategy,
    WriteStrategy,
    SchemaAdapter,
)


class TestSchemaAdapter(SchemaAdapter):
    """Test implementation of schema adapter using SQLite."""
    
    def __init__(self, db_path: str, table_name: str = "test_data"):
        self.db_path = db_path
        self.table_name = table_name
        self._initialized = False
    
    async def _ensure_initialized(self):
        if not self._initialized:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                await db.commit()
            self._initialized = True
    
    async def read(self, key: str):
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                f"SELECT value FROM {self.table_name} WHERE key = ?",
                (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def write(self, key: str, value):
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"INSERT OR REPLACE INTO {self.table_name} (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            await db.commit()
            return True
    
    async def delete(self, key: str):
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"DELETE FROM {self.table_name} WHERE key = ?",
                (key,)
            )
            await db.commit()
            return True
    
    async def query(self, query: str, params: tuple = ()):
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                return await cursor.fetchall()
    
    async def health_check(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
                return True
        except Exception:
            return False


@pytest.fixture
async def dual_write_setup():
    """Create dual-write manager with test adapters."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        old_db = f.name
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        new_db = f.name
    
    old_adapter = TestSchemaAdapter(old_db, "old_data")
    new_adapter = TestSchemaAdapter(new_db, "new_data")
    
    yield old_adapter, new_adapter, old_db, new_db
    
    # Cleanup
    for db in [old_db, new_db]:
        if os.path.exists(db):
            os.unlink(db)


@pytest.mark.asyncio
async def test_dual_write_basic(dual_write_setup):
    """Test basic dual-write functionality."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.DUAL_READ,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Write data
    result = await manager.write("key1", "value1")
    
    assert result.old_success is True
    assert result.new_success is True
    assert result.error is None
    
    # Read data
    value = await manager.read("key1")
    assert value == "value1"


@pytest.mark.asyncio
async def test_read_routing_old_only(dual_write_setup):
    """Test OLD_ONLY read routing strategy."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.OLD_ONLY,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Write to both
    await manager.write("key1", "value1")
    
    # Should read from old
    value = await manager.read("key1")
    assert value == "value1"


@pytest.mark.asyncio
async def test_read_routing_new_only(dual_write_setup):
    """Test NEW_ONLY read routing strategy."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.NEW_ONLY,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Write to both
    await manager.write("key1", "value1")
    
    # Should read from new
    value = await manager.read("key1")
    assert value == "value1"


@pytest.mark.asyncio
async def test_write_strategy_old_only(dual_write_setup):
    """Test OLD_ONLY write strategy."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.OLD_ONLY,
        write_strategy=WriteStrategy.OLD_ONLY,
    )
    
    # Write only to old
    result = await manager.write("key1", "value1")
    
    assert result.old_success is True
    assert result.new_success is False  # Not written to new
    
    # Verify old has data
    old_value = await old_adapter.read("key1")
    assert old_value == "value1"
    
    # Verify new doesn't have data
    new_value = await new_adapter.read("key1")
    assert new_value is None


@pytest.mark.asyncio
async def test_consistency_check(dual_write_setup):
    """Test data consistency checking."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.DUAL_READ,
        write_strategy=WriteStrategy.DUAL_WRITE,
        consistency_check_interval=1,  # Check every write
    )
    
    # Write data
    await manager.write("key1", "value1")
    
    # Stats should show consistency
    stats = manager.get_stats()
    assert stats["total_writes"] >= 1


@pytest.mark.asyncio
async def test_gradual_traffic_shift(dual_write_setup):
    """Test gradual traffic shifting."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        read_strategy=ReadRoutingStrategy.GRADUAL_SHIFT,
        write_strategy=WriteStrategy.DUAL_WRITE,
        gradual_shift_percentage=0.0,
    )
    
    # Shift traffic gradually
    percentage = manager.shift_traffic(25.0)
    assert percentage == 25.0
    
    percentage = manager.shift_traffic(25.0)
    assert percentage == 50.0
    
    percentage = manager.shift_traffic(60.0)  # Should cap at 100
    assert percentage == 100.0


@pytest.mark.asyncio
async def test_health_check(dual_write_setup):
    """Test health checking."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
    )
    
    health = await manager.health_check()
    
    assert "old_schema_healthy" in health
    assert "new_schema_healthy" in health
    assert "dual_write_healthy" in health


@pytest.mark.asyncio
async def test_delete_operation(dual_write_setup):
    """Test delete operation on both schemas."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Write then delete
    await manager.write("key1", "value1")
    result = await manager.delete("key1")
    
    assert result is True
    
    # Verify deleted from both
    old_value = await old_adapter.read("key1")
    new_value = await new_adapter.read("key1")
    assert old_value is None
    assert new_value is None


@pytest.mark.asyncio
async def test_async_mirror_write(dual_write_setup):
    """Test ASYNC_MIRROR write strategy."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        write_strategy=WriteStrategy.ASYNC_MIRROR,
    )
    
    # Write (should be async to new)
    result = await manager.write("key1", "value1")
    
    assert result.old_success is True
    assert result.new_success is True  # Optimistic
    
    # Wait for async operation
    await asyncio.sleep(0.1)
    
    # Verify both have data
    old_value = await old_adapter.read("key1")
    assert old_value == "value1"


@pytest.mark.asyncio
async def test_dual_write_stats(dual_write_setup):
    """Test dual-write statistics collection."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Perform some writes
    for i in range(5):
        await manager.write(f"key{i}", f"value{i}")
    
    stats = manager.get_stats()
    
    assert stats["total_writes"] == 5
    assert "old_success_rate" in stats
    assert "new_success_rate" in stats
    assert "avg_old_duration_ms" in stats
    assert "avg_new_duration_ms" in stats


@pytest.mark.asyncio
async def test_query_routing(dual_write_setup):
    """Test query routing to old schema."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
    )
    
    # Insert data
    await old_adapter.write("key1", "value1")
    
    # Query should route to old
    results = await manager.query("SELECT * FROM old_data")
    assert len(results) >= 1


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_dual_write_performance(dual_write_setup):
    """Test dual-write performance impact."""
    old_adapter, new_adapter, _, _ = dual_write_setup
    
    manager = DualWriteManager(
        old_adapter=old_adapter,
        new_adapter=new_adapter,
        write_strategy=WriteStrategy.DUAL_WRITE,
    )
    
    # Perform writes and measure
    start = asyncio.get_event_loop().time()
    
    for i in range(100):
        await manager.write(f"key{i}", f"value{i}")
    
    duration = asyncio.get_event_loop().time() - start
    
    # Should complete in reasonable time
    assert duration < 5.0  # 100 writes in under 5 seconds
    
    stats = manager.get_stats()
    # Both schemas should have high success rates
    assert stats["old_success_rate"] > 95.0
    assert stats["new_success_rate"] > 95.0
