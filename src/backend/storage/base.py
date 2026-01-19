"""
Storage Interface for AstraGuard Backend

Provides abstract base class for persistent storage implementations.
Supports dependency injection and testing with in-memory implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Storage(ABC):
    """
    Abstract storage interface for backend components.
    
    Implementations include:
    - RedisAdapter: Production Redis-based storage
    - MemoryStorage: In-memory testing implementation
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value by key.
        
        Args:
            key: Storage key
            
        Returns:
            Stored value or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Store value with optional TTL.
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time to live in seconds (None = no expiry)
            
        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete key from storage.
        
        Args:
            key: Storage key
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Storage key
            
        Returns:
            True if key exists, False otherwise
        """
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        List keys matching pattern.
        
        Args:
            pattern: Key pattern (supports wildcards like "prefix:*")
            
        Returns:
            List of matching keys
        """
        pass

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Atomically increment counter.
        
        Args:
            key: Counter key
            amount: Amount to increment (can be negative)
            
        Returns:
            New counter value
        """
        pass
