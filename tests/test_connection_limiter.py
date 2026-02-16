"""Tests for Connection Limit Enforcement (#678)"""

import pytest
from src.core.connection_limiter import (
    ConnectionLimiter,
    ConnectionType,
    get_connection_limiter
)


class TestConnectionLimiter:
    @pytest.fixture
    def limiter(self):
        return ConnectionLimiter(
            max_database_connections=2,
            max_api_connections=3
        )
    
    def test_acquire_connection(self, limiter):
        limiter.acquire_connection("conn1", ConnectionType.DATABASE)
        assert len(limiter._connections) == 1
    
    def test_connection_limit_exceeded(self, limiter):
        limiter.acquire_connection("conn1", ConnectionType.DATABASE)
        limiter.acquire_connection("conn2", ConnectionType.DATABASE)
        
        with pytest.raises(ValueError, match="connection limit exceeded"):
            limiter.acquire_connection("conn3", ConnectionType.DATABASE)
    
    def test_release_connection(self, limiter):
        limiter.acquire_connection("conn1", ConnectionType.DATABASE)
        limiter.release_connection("conn1")
        assert len(limiter._connections) == 0
    
    def test_get_connection_stats(self, limiter):
        limiter.acquire_connection("conn1", ConnectionType.DATABASE)
        stats = limiter.get_connection_stats()
        assert stats["by_type"]["database"]["active"] == 1
        assert stats["total_active"] == 1
    
    def test_singleton(self):
        limiter1 = get_connection_limiter()
        limiter2 = get_connection_limiter()
        assert limiter1 is limiter2
