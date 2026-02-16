"""
Resource Chaos Actions for Chaos Testing

Provides resource exhaustion simulation:
- Memory consumption
- CPU load generation
- Disk space consumption
- File descriptor exhaustion
"""

import asyncio
import logging
import os
import tempfile
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)

# Global state for resource chaos
_resource_chaos_active = False
_allocated_memory: List[bytearray] = []
_cpu_tasks: List[asyncio.Task] = []
_temp_files: List[str] = []


async def consume_memory(
    duration_seconds: int = 30,
    memory_mb: int = 512,
) -> bool:
    """
    Consume memory for chaos testing.
    
    Args:
        duration_seconds: How long to keep memory consumed
        memory_mb: Amount of memory to consume in MB
        
    Returns:
        True if memory consumption started
    """
    global _resource_chaos_active, _allocated_memory
    
    logger.info(f"Consuming memory: {memory_mb}MB for {duration_seconds}s")
    
    try:
        # Allocate memory in chunks
        chunk_size = 10 * 1024 * 1024  # 10 MB chunks
        chunks_needed = (memory_mb * 1024 * 1024) // chunk_size
        
        for _ in range(chunks_needed):
            chunk = bytearray(chunk_size)
            # Write to ensure memory is actually allocated
            for i in range(0, chunk_size, 4096):
                chunk[i] = 1
            _allocated_memory.append(chunk)
        
        _resource_chaos_active = True
        
        # Schedule release
        asyncio.create_task(_auto_release_resources(duration_seconds))
        
        logger.info(f"Allocated {len(_allocated_memory) * 10}MB of memory")
        return True
        
    except MemoryError:
        logger.error("Failed to allocate memory - system may already be under pressure")
        return False


async def consume_cpu(
    duration_seconds: int = 30,
    cpu_percent: int = 80,
) -> bool:
    """
    Generate CPU load for chaos testing.
    
    Args:
        duration_seconds: How long to generate CPU load
        cpu_percent: Target CPU utilization (0-100)
        
    Returns:
        True if CPU load generation started
    """
    global _resource_chaos_active, _cpu_tasks
    
    logger.info(f"Generating CPU load: {cpu_percent}% for {duration_seconds}s")
    
    _resource_chaos_active = True
    
    # Create CPU-intensive tasks
    num_tasks = max(1, cpu_percent // 20)  # 1 task per 20% CPU
    
    for _ in range(num_tasks):
        task = asyncio.create_task(_cpu_intensive_task(duration_seconds))
        _cpu_tasks.append(task)
    
    return True


async def consume_disk_space(
    duration_seconds: int = 30,
    size_mb: int = 100,
) -> bool:
    """
    Consume disk space for chaos testing.
    
    Args:
        duration_seconds: How long to keep disk space consumed
        size_mb: Amount of disk space to consume in MB
        
    Returns:
        True if disk space consumption started
    """
    global _resource_chaos_active, _temp_files
    
    logger.info(f"Consuming disk space: {size_mb}MB for {duration_seconds}s")
    
    try:
        # Create temporary files
        chunk_size = 10 * 1024 * 1024  # 10 MB
        num_files = (size_mb * 1024 * 1024) // chunk_size
        
        for i in range(num_files):
            fd, path = tempfile.mkstemp(prefix="chaos_disk_")
            try:
                # Write data to file
                os.write(fd, b'0' * chunk_size)
                _temp_files.append(path)
            finally:
                os.close(fd)
        
        _resource_chaos_active = True
        
        # Schedule cleanup
        asyncio.create_task(_auto_release_resources(duration_seconds))
        
        logger.info(f"Created {len(_temp_files)} temp files")
        return True
        
    except OSError as e:
        logger.error(f"Failed to consume disk space: {e}")
        return False


async def release_resources() -> bool:
    """
    Release all consumed resources.
    
    Returns:
        True if resources released successfully
    """
    global _resource_chaos_active, _allocated_memory, _cpu_tasks, _temp_files
    
    logger.info("Releasing all consumed resources")
    
    # Release memory
    _allocated_memory.clear()
    
    # Cancel CPU tasks
    for task in _cpu_tasks:
        task.cancel()
    _cpu_tasks.clear()
    
    # Clean up temp files
    for path in _temp_files:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            logger.warning(f"Failed to remove temp file {path}: {e}")
    _temp_files.clear()
    
    _resource_chaos_active = False
    
    logger.info("All resources released")
    return True


async def _cpu_intensive_task(duration_seconds: int):
    """
    Background task that generates CPU load.
    """
    end_time = datetime.utcnow().timestamp() + duration_seconds
    
    while datetime.utcnow().timestamp() < end_time:
        # CPU-intensive calculation
        _ = sum(i * i for i in range(100000))
        
        # Small yield to prevent complete blocking
        await asyncio.sleep(0.001)


async def _auto_release_resources(delay_seconds: int):
    """Automatically release resources after delay."""
    await asyncio.sleep(delay_seconds)
    if _resource_chaos_active:
        logger.info(f"Auto-releasing resources after {delay_seconds}s")
        await release_resources()


def get_resource_chaos_status() -> dict:
    """
    Get current resource chaos status.
    
    Returns:
        Dictionary with resource chaos status
    """
    memory_consumed = len(_allocated_memory) * 10  # 10MB per chunk
    disk_consumed = len(_temp_files) * 10  # 10MB per file
    cpu_active = len(_cpu_tasks) > 0
    
    return {
        "active": _resource_chaos_active,
        "memory_consumed_mb": memory_consumed,
        "disk_consumed_mb": disk_consumed,
        "cpu_load_active": cpu_active,
        "temp_files_count": len(_temp_files),
    }
