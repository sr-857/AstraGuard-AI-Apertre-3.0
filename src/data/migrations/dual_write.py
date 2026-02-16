"""
Dual-Write Pattern Implementation for Zero-Downtime Migrations.

The dual-write pattern writes data to both old and new schemas simultaneously,
allowing gradual migration without downtime.
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Callable, Set, Tuple
import aiosqlite

logger = logging.getLogger(__name__)


class ReadRoutingStrategy(Enum):
    """Strategy for routing read operations during migration."""
    OLD_ONLY = auto()      # Read only from old schema
    NEW_ONLY = auto()      # Read only from new schema
    DUAL_READ = auto()     # Read from both, compare results
    GRADUAL_SHIFT = auto() # Gradually shift traffic from old to new


class WriteStrategy(Enum):
    """Strategy for write operations during migration."""
    OLD_ONLY = auto()      # Write only to old schema
    NEW_ONLY = auto()      # Write only to new schema
    DUAL_WRITE = auto()    # Write to both schemas
    ASYNC_MIRROR = auto()  # Write to old, async mirror to new


@dataclass
class ConsistencyCheck:
    """Result of a consistency check between old and new schemas."""
    passed: bool
    old_value: Any
    new_value: Any
    mismatch_count: int
    check_time_ms: float
    details: Optional[str] = None


@dataclass
class WriteResult:
    """Result of a dual-write operation."""
    old_success: bool
    new_success: bool
    old_duration_ms: float
    new_duration_ms: float
    consistency_verified: bool
    timestamp: datetime
    error: Optional[str] = None


class SchemaAdapter(ABC):
    """
    Abstract base class for schema adapters.
    
    Implementations provide read/write operations for specific schema versions.
    """
    
    @abstractmethod
    async def read(self, key: str) -> Optional[Any]:
        """Read data by key."""
        pass
    
    @abstractmethod
    async def write(self, key: str, value: Any) -> bool:
        """Write data."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data."""
        pass
    
    @abstractmethod
    async def query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """Execute query."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if schema is healthy."""
        pass


class DualWriteManager:
    """
    Manages dual-write operations during schema migration.
    
    Provides zero-downtime migration by writing to both old and new schemas
    while gradually shifting read traffic.
    """
    
    def __init__(
        self,
        old_adapter: SchemaAdapter,
        new_adapter: SchemaAdapter,
        read_strategy: ReadRoutingStrategy = ReadRoutingStrategy.DUAL_READ,
        write_strategy: WriteStrategy = WriteStrategy.DUAL_WRITE,
        consistency_check_interval: int = 100,
        gradual_shift_percentage: float = 0.0,
    ):
        """
        Initialize dual-write manager.
        
        Args:
            old_adapter: Adapter for old schema
            new_adapter: Adapter for new schema
            read_strategy: Strategy for read routing
            write_strategy: Strategy for write operations
            consistency_check_interval: Check consistency every N writes
            gradual_shift_percentage: Percentage of reads to route to new (0-100)
        """
        self.old_adapter = old_adapter
        self.new_adapter = new_adapter
        self.read_strategy = read_strategy
        self.write_strategy = write_strategy
        self.consistency_check_interval = consistency_check_interval
        self.gradual_shift_percentage = max(0.0, min(100.0, gradual_shift_percentage))
        
        self._write_count = 0
        self._consistency_failures = 0
        self._write_results: List[WriteResult] = []
        self._max_results_history = 1000
        self._lock = asyncio.Lock()
        
    async def read(self, key: str) -> Optional[Any]:
        """
        Read data with routing strategy.
        
        Args:
            key: Data key to read
            
        Returns:
            Data value or None
        """
        if self.read_strategy == ReadRoutingStrategy.OLD_ONLY:
            return await self.old_adapter.read(key)
        
        elif self.read_strategy == ReadRoutingStrategy.NEW_ONLY:
            return await self.new_adapter.read(key)
        
        elif self.read_strategy == ReadRoutingStrategy.DUAL_READ:
            # Read from both and compare
            old_value, new_value = await asyncio.gather(
                self.old_adapter.read(key),
                self.new_adapter.read(key),
                return_exceptions=True
            )
            
            # Log inconsistencies
            if old_value != new_value:
                logger.warning(
                    f"Data inconsistency detected for key {key}: "
                    f"old={old_value}, new={new_value}"
                )
            
            # Return old value as source of truth during migration
            return old_value if not isinstance(old_value, Exception) else new_value
        
        elif self.read_strategy == ReadRoutingStrategy.GRADUAL_SHIFT:
            # Route based on percentage
            import random
            if random.random() * 100 < self.gradual_shift_percentage:
                return await self.new_adapter.read(key)
            else:
                return await self.old_adapter.read(key)
        
        else:
            raise ValueError(f"Unknown read strategy: {self.read_strategy}")
    
    async def write(self, key: str, value: Any) -> WriteResult:
        """
        Write data with dual-write strategy.
        
        Args:
            key: Data key
            value: Data value
            
        Returns:
            WriteResult with operation details
        """
        start_time = time.time()
        result = WriteResult(
            old_success=False,
            new_success=False,
            old_duration_ms=0.0,
            new_duration_ms=0.0,
            consistency_verified=False,
            timestamp=datetime.now(),
            error=None
        )
        
        async with self._lock:
            self._write_count += 1
            
            try:
                if self.write_strategy == WriteStrategy.OLD_ONLY:
                    old_start = time.time()
                    result.old_success = await self.old_adapter.write(key, value)
                    result.old_duration_ms = (time.time() - old_start) * 1000
                
                elif self.write_strategy == WriteStrategy.NEW_ONLY:
                    new_start = time.time()
                    result.new_success = await self.new_adapter.write(key, value)
                    result.new_duration_ms = (time.time() - new_start) * 1000
                
                elif self.write_strategy == WriteStrategy.DUAL_WRITE:
                    # Write to both schemas
                    old_start = time.time()
                    old_task = self.old_adapter.write(key, value)
                    new_task = self.new_adapter.write(key, value)
                    
                    old_result, new_result = await asyncio.gather(
                        old_task, new_task, return_exceptions=True
                    )
                    
                    result.old_success = old_result is True
                    result.new_success = new_result is True
                    result.old_duration_ms = (time.time() - old_start) * 1000
                    
                    # Measure new schema write time separately if needed
                    if result.new_success:
                        result.new_duration_ms = result.old_duration_ms  # Approximate
                    
                    # Check consistency periodically
                    if self._write_count % self.consistency_check_interval == 0:
                        result.consistency_verified = await self._verify_consistency(key, value)
                
                elif self.write_strategy == WriteStrategy.ASYNC_MIRROR:
                    # Write to old, mirror async to new
                    old_start = time.time()
                    result.old_success = await self.old_adapter.write(key, value)
                    result.old_duration_ms = (time.time() - old_start) * 1000
                    
                    # Async mirror to new schema
                    asyncio.create_task(self._async_mirror_write(key, value))
                    result.new_success = True  # Optimistic
                
                else:
                    raise ValueError(f"Unknown write strategy: {self.write_strategy}")
                
            except Exception as e:
                result.error = str(e)
                logger.error(f"Dual-write failed for key {key}: {e}")
            
            # Store result for monitoring
            self._write_results.append(result)
            if len(self._write_results) > self._max_results_history:
                self._write_results.pop(0)
        
        total_duration = (time.time() - start_time) * 1000
        logger.debug(f"Dual-write completed in {total_duration:.2f}ms: {result}")
        
        return result
    
    async def _async_mirror_write(self, key: str, value: Any) -> None:
        """Asynchronously mirror write to new schema."""
        try:
            await self.new_adapter.write(key, value)
        except Exception as e:
            logger.warning(f"Async mirror write failed for key {key}: {e}")
    
    async def _verify_consistency(self, key: str, expected_value: Any) -> bool:
        """Verify consistency between old and new schemas."""
        try:
            old_value = await self.old_adapter.read(key)
            new_value = await self.new_adapter.read(key)
            
            # Compare values (handle different serialization)
            old_hash = self._compute_hash(old_value)
            new_hash = self._compute_hash(new_value)
            
            consistent = old_hash == new_hash
            if not consistent:
                self._consistency_failures += 1
                logger.error(
                    f"Consistency check failed for key {key}: "
                    f"old_hash={old_hash}, new_hash={new_hash}"
                )
            
            return consistent
            
        except Exception as e:
            logger.error(f"Consistency verification failed: {e}")
            return False
    
    def _compute_hash(self, value: Any) -> str:
        """Compute hash for value comparison."""
        if value is None:
            return "null"
        
        try:
            value_str = json.dumps(value, sort_keys=True, default=str)
            return hashlib.sha256(value_str.encode()).hexdigest()[:16]
        except (TypeError, ValueError):
            return hashlib.sha256(str(value).encode()).hexdigest()[:16]
    
    async def delete(self, key: str) -> bool:
        """
        Delete data from both schemas.
        
        Args:
            key: Data key to delete
            
        Returns:
            True if deletion was successful in at least one schema
        """
        old_result, new_result = await asyncio.gather(
            self.old_adapter.delete(key),
            self.new_adapter.delete(key),
            return_exceptions=True
        )
        
        old_success = old_result is True
        new_success = new_result is True
        
        if not old_success and not new_success:
            logger.warning(f"Failed to delete key {key} from both schemas")
            return False
        
        return True
    
    async def query(self, query: str, params: Tuple = ()) -> List[Dict]:
        """
        Execute query with routing strategy.
        
        During migration, queries are routed to old schema for consistency.
        """
        # Default to old schema for complex queries during migration
        return await self.old_adapter.query(query, params)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get dual-write statistics.
        
        Returns:
            Dictionary with operation statistics
        """
        if not self._write_results:
            return {
                "total_writes": 0,
                "old_success_rate": 0.0,
                "new_success_rate": 0.0,
                "consistency_failures": self._consistency_failures,
                "avg_old_duration_ms": 0.0,
                "avg_new_duration_ms": 0.0,
            }
        
        total = len(self._write_results)
        old_successes = sum(1 for r in self._write_results if r.old_success)
        new_successes = sum(1 for r in self._write_results if r.new_success)
        
        avg_old_duration = sum(r.old_duration_ms for r in self._write_results) / total
        avg_new_duration = sum(r.new_duration_ms for r in self._write_results) / total
        
        return {
            "total_writes": self._write_count,
            "old_success_rate": old_successes / total * 100,
            "new_success_rate": new_successes / total * 100,
            "consistency_failures": self._consistency_failures,
            "avg_old_duration_ms": avg_old_duration,
            "avg_new_duration_ms": avg_new_duration,
            "read_strategy": self.read_strategy.name,
            "write_strategy": self.write_strategy.name,
            "gradual_shift_percentage": self.gradual_shift_percentage,
        }
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of both schemas.
        
        Returns:
            Dictionary with health status
        """
        old_health = await self.old_adapter.health_check()
        new_health = await self.new_adapter.health_check()
        
        return {
            "old_schema_healthy": old_health,
            "new_schema_healthy": new_health,
            "dual_write_healthy": old_health and new_health,
        }
    
    def set_gradual_shift_percentage(self, percentage: float) -> None:
        """
        Update gradual shift percentage.
        
        Args:
            percentage: New percentage (0-100)
        """
        self.gradual_shift_percentage = max(0.0, min(100.0, percentage))
        logger.info(f"Updated gradual shift percentage to {self.gradual_shift_percentage}%")
    
    def shift_traffic(self, percentage_increase: float = 10.0) -> float:
        """
        Gradually shift traffic to new schema.
        
        Args:
            percentage_increase: Percentage to increase
            
        Returns:
            New shift percentage
        """
        self.gradual_shift_percentage = min(
            100.0, 
            self.gradual_shift_percentage + percentage_increase
        )
        logger.info(
            f"Traffic shifted to new schema: {self.gradual_shift_percentage}%"
        )
        return self.gradual_shift_percentage
