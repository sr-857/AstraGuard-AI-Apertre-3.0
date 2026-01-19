"""
Storage interface protocol for AstraGuard-AI.

Defines a minimal, well-typed Storage interface that abstracts away
the underlying storage implementation (Redis, in-memory, etc.).
"""

from typing import Protocol, Optional, Any, List
from abc import abstractmethod


class Storage(Protocol):
    """
    Storage interface for key-value operations.
    
    This protocol defines the contract that all storage implementations
    must fulfill. It supports basic operations like get, set, delete,
    and key scanning with optional expiration.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value by key.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The stored value (deserialized from JSON) or None if not found
        """
        ...

    @abstractmethod
    async def set(
        self, 
        key: str, 
        value: Any, 
        *, 
        expire: Optional[int] = None
    ) -> bool:
        """
        Store a value with optional expiration.
        
        Args:
            key: The key to store under
            value: The value to store (will be serialized to JSON)
            expire: Optional TTL in seconds
            
        Returns:
            True if successful, False otherwise
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a key.
        
        Args:
            key: The key to delete
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        ...

    @abstractmethod
    async def scan_keys(self, pattern: str) -> List[str]:
        """
        Scan for keys matching a pattern.
        
        Args:
            pattern: Glob-style pattern (e.g., "prefix:*")
            
        Returns:
            List of matching keys
        """
        ...

    @abstractmethod
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration on an existing key.
        
        Args:
            key: The key to set expiration on
            seconds: TTL in seconds
            
        Returns:
            True if expiration was set, False if key doesn't exist
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: The key to check
            
        Returns:
            True if key exists, False otherwise
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the storage backend is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        ...
