"""
Connection Limit Enforcement for AstraGuard

Extends resource_limits.py to add connection-specific tracking and enforcement.
Monitors active connections and enforces configurable limits.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionType(str, Enum):
    """Types of connections"""
    DATABASE = "database"
    API = "api"
    WEBSOCKET = "websocket"
    EXTERNAL = "external"


@dataclass
class ConnectionInfo:
    """Information about an active connection"""
    connection_id: str
    connection_type: ConnectionType
    created_at: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "connection_type": self.connection_type.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


class ConnectionLimiter:
    """
    Enforce connection limits by type.
    
    Features:
    - Track active connections by type
    - Enforce per-type limits
    - Connection metadata tracking
    - Thread-safe operation
    """
    
    def __init__(
        self,
        max_database_connections: int = 50,
        max_api_connections: int = 100,
        max_websocket_connections: int = 200,
        max_external_connections: int = 50
    ):
        """Initialize connection limiter with per-type limits."""
        self.limits = {
            ConnectionType.DATABASE: max_database_connections,
            ConnectionType.API: max_api_connections,
            ConnectionType.WEBSOCKET: max_websocket_connections,
            ConnectionType.EXTERNAL: max_external_connections
        }
        
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = threading.Lock()
        
        logger.info(f"ConnectionLimiter initialized with limits: {self.limits}")
    
    def acquire_connection(
        self,
        connection_id: str,
        connection_type: ConnectionType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Acquire a connection slot.
        
        Args:
            connection_id: Unique connection identifier
            connection_type: Type of connection
            metadata: Optional connection metadata
            
        Raises:
            ValueError: If connection limit exceeded
        """
        with self._lock:
            # Check current count for this type
            current_count = sum(
                1 for conn in self._connections.values()
                if conn.connection_type == connection_type
            )
            
            if current_count >= self.limits[connection_type]:
                raise ValueError(
                    f"{connection_type.value} connection limit exceeded: "
                    f"{current_count} >= {self.limits[connection_type]}"
                )
            
            # Register connection
            conn_info = ConnectionInfo(
                connection_id=connection_id,
                connection_type=connection_type,
                created_at=datetime.now(),
                metadata=metadata or {}
            )
            self._connections[connection_id] = conn_info
            
            logger.debug(
                f"Connection acquired: {connection_id} ({connection_type.value}), "
                f"count: {current_count + 1}/{self.limits[connection_type]}"
            )
    
    def release_connection(self, connection_id: str) -> None:
        """Release a connection slot."""
        with self._lock:
            if connection_id in self._connections:
                conn_type = self._connections[connection_id].connection_type
                del self._connections[connection_id]
                logger.debug(f"Connection released: {connection_id} ({conn_type.value})")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics by type."""
        with self._lock:
            stats = {}
            for conn_type in ConnectionType:
                count = sum(
                    1 for conn in self._connections.values()
                    if conn.connection_type == conn_type
                )
                stats[conn_type.value] = {
                    "active": count,
                    "limit": self.limits[conn_type],
                    "available": self.limits[conn_type] - count,
                    "usage_percent": round((count / self.limits[conn_type]) * 100, 2)
                }
            
            return {
                "by_type": stats,
                "total_active": len(self._connections),
                "total_limit": sum(self.limits.values())
            }
    
    def get_connections(self, connection_type: Optional[ConnectionType] = None) -> list:
        """Get active connections, optionally filtered by type."""
        with self._lock:
            conns = self._connections.values()
            if connection_type:
                conns = [c for c in conns if c.connection_type == connection_type]
            return [c.to_dict() for c in conns]


# Global singleton
_connection_limiter: Optional[ConnectionLimiter] = None
_limiter_lock = threading.Lock()


def get_connection_limiter() -> ConnectionLimiter:
    """Get global connection limiter singleton."""
    global _connection_limiter
    if _connection_limiter is None:
        with _limiter_lock:
            if _connection_limiter is None:
                _connection_limiter = ConnectionLimiter()
    return _connection_limiter
