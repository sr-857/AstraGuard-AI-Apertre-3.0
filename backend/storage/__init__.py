"""
Storage abstraction layer for AstraGuard-AI.

Provides a clean interface for storage operations with multiple implementations:
 - RedisAdapter: Production Redis-backed storage
 - MemoryStorage: In-memory storage for tests and local development
"""

from .base import Storage
from .memory import MemoryStorage

# Redis adapter is optional; import if available to keep compatibility
try:
	from .redis_adapter import RedisAdapter  # type: ignore
except Exception:
	RedisAdapter = None

__all__ = ["Storage", "MemoryStorage"]
if RedisAdapter is not None:
	__all__.insert(1, "RedisAdapter")
