"""
In-Memory Storage Implementation

Provides testing-friendly storage without external dependencies.
Supports TTL expiration and all Storage interface operations.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .base import Storage


class MemoryStorage(Storage):
    """
    In-memory storage implementation for testing.
    
    Features:
    - TTL support with automatic expiration
    - Atomic operations
    - Pattern-based key matching
    - Thread-safe operations
    """

    def __init__(self):
        """Initialize empty in-memory storage."""
        self._data: Dict[str, Any] = {}
        self._ttls: Dict[str, float] = {}  # key -> expiry timestamp
        self._counters: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self.connected = False

    async def connect(self) -> bool:
        """Connect to storage (no-op for in-memory)."""
        self.connected = True
        return True

    async def close(self) -> bool:
        """Close storage connection (no-op for in-memory)."""
        self.connected = False
        return True

    async def health_check(self) -> bool:
        """Check storage health (always healthy for in-memory)."""
        return self.connected

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value, returning None if expired."""
        async with self._lock:
            # Check expiration
            if key in self._ttls:
                if time.time() > self._ttls[key]:
                    # Expired
                    del self._data[key]
                    del self._ttls[key]
                    return None

            return self._data.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None, expire: Optional[int] = None) -> bool:
        """Store value with optional TTL (supports both ttl and expire params)."""
        # Support both 'ttl' and 'expire' parameter names
        expiry_time = expire if expire is not None else ttl
        
        async with self._lock:
            self._data[key] = value

            if expiry_time is not None:
                self._ttls[key] = time.time() + expiry_time
            elif key in self._ttls:
                # Clear TTL if explicitly set to None
                del self._ttls[key]

            return True

    async def delete(self, key: str) -> bool:
        """Delete key if it exists."""
        async with self._lock:
            if key in self._data:
                del self._data[key]
                if key in self._ttls:
                    del self._ttls[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        value = await self.get(key)  # Handles expiration check
        return value is not None or key in self._data

    async def keys(self, pattern: str = "*") -> List[str]:
        """
        List keys matching pattern.
        
        Supports simple wildcards:
        - "*" matches everything
        - "prefix:*" matches keys starting with "prefix:"
        - "*:suffix" matches keys ending with ":suffix"
        """
        async with self._lock:
            # Remove expired keys first
            await self._cleanup_expired()

            all_keys = list(self._data.keys())

            if pattern == "*":
                return all_keys

            # Simple pattern matching
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in all_keys if k.startswith(prefix)]
            elif pattern.startswith("*"):
                suffix = pattern[1:]
                return [k for k in all_keys if k.endswith(suffix)]
            else:
                # Exact match
                return [k for k in all_keys if k == pattern]

    async def scan_keys(self, pattern: str = "*", cursor: int = 0, count: int = 10) -> List[str]:
        """
        Scan keys matching pattern.
        
        Returns list of keys (not tuple for test compatibility).
        """
        all_keys = await self.keys(pattern)
        # Simple pagination
        start = cursor
        end = min(cursor + count, len(all_keys))
        
        return all_keys[start:end]

    async def expire(self, key: str, ttl: int) -> bool:
        """Set or update expiry on existing key."""
        async with self._lock:
            if key in self._data:
                self._ttls[key] = time.time() + ttl
                return True
            return False

    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomically increment counter."""
        async with self._lock:
            self._counters[key] += amount
            return self._counters[key]

    async def _cleanup_expired(self):
        """Remove expired keys (internal helper)."""
        now = time.time()
        expired = [k for k, exp_time in self._ttls.items() if now > exp_time]
        for key in expired:
            if key in self._data:
                del self._data[key]
            del self._ttls[key]

    def clear(self):
        """Clear all data (testing utility)."""
        self._data.clear()
        self._ttls.clear()
        self._counters.clear()
    
    async def clear_all(self) -> bool:
        """Async clear all data."""
        async with self._lock:
            self._data.clear()
            self._ttls.clear()
            self._counters.clear()
            return True
