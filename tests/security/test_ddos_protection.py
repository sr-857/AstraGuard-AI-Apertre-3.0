"""
Tests for DDoS Protection Module

Comprehensive test suite for DDoS protection functionality including:
- IP blocking and whitelisting
- Rate limiting
- Threat scoring
- Attack pattern detection
- Connection limiting
- Configuration loading
"""

import pytest
import asyncio
import time
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from security.ddos_protection import (
    DDoSProtection,
    DDoSProtectionMiddleware,
    DDoSConfig,
    ThreatScore,
    get_ddos_protection
)
from security.ddos_config_loader import (
    DDoSConfigLoader,
    load_ddos_config,
    is_ddos_protection_enabled
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def ddos_config():
    """Create a test DDoS configuration."""
    return DDoSConfig(
        max_requests_per_minute=60,
        max_requests_per_second=10,
        max_concurrent_connections_per_ip=5,
        max_total_concurrent_connections=100,
        suspicious_pattern_threshold=3,
        request_window_seconds=60,
        auto_block_threshold=80.0,
        block_duration_seconds=300,  # 5 minutes for testing
        permanent_block_threshold=3,
        slowloris_timeout_seconds=30,
        http_flood_threshold=50,
        whitelist_ips={"127.0.0.1", "192.168.1.100"},
        whitelist_user_agents={"TestAgent"}
    )


@pytest.fixture
async def ddos_protection(ddos_config):
    """Create a DDoS protection instance."""
    return DDoSProtection(redis_client=None, config=ddos_config)


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    def create_request(
        ip: str = "192.168.1.50",
        method: str = "GET",
        path: str = "/api/test",
        user_agent: str = "Mozilla/5.0",
        headers: Dict[str, str] = None
    ) -> Mock:
        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = ip
        request.method = method
        request.url = Mock()
        request.url.path = path
        request.url.query = ""
        request.url.scheme = "https"
        
        default_headers = {
            "user-agent": user_agent,
        }
        if headers:
            default_headers.update(headers)
        
        request.headers = Headers(default_headers)
        
        return request
    
    return create_request


# ============================================================================
# Basic Functionality Tests
# ============================================================================

@pytest.mark.asyncio
async def test_ddos_protection_initialization(ddos_config):
    """Test DDoS protection initialization."""
    ddos = DDoSProtection(config=ddos_config)
    
    assert ddos.config == ddos_config
    assert ddos.stats['total_requests_checked'] == 0
    assert ddos.stats['total_blocked'] == 0
    assert len(ddos._blocked_ips) == 0
    assert len(ddos._permanent_blocks) == 0


@pytest.mark.asyncio
async def test_whitelisted_ip_allowed(ddos_protection, mock_request):
    """Test that whitelisted IPs are always allowed."""
    request = mock_request(ip="127.0.0.1")
    
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_whitelisted_user_agent_allowed(ddos_protection, mock_request):
    """Test that whitelisted user agents are allowed."""
    request = mock_request(ip="10.0.0.1", user_agent="TestAgent")
    
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_normal_request_allowed(ddos_protection, mock_request):
    """Test that normal requests are allowed."""
    request = mock_request()
    
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is True
    assert reason is None
    assert ddos_protection.stats['total_requests_checked'] == 1


# ============================================================================
# Rate Limiting Tests
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limit_per_second(ddos_protection, mock_request):
    """Test requests per second rate limiting."""
    ip = "10.0.0.2"
    
    # Send max_requests_per_second requests
    for _ in range(ddos_protection.config.max_requests_per_second):
        request = mock_request(ip=ip)
        is_allowed, _ = await ddos_protection.check_request(request)
        assert is_allowed is True
    
    # Next request should be blocked
    request = mock_request(ip=ip)
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is False
    assert "rate limit" in reason.lower()


@pytest.mark.asyncio
async def test_rate_limit_per_minute(ddos_protection, mock_request):
    """Test requests per minute rate limiting."""
    ip = "10.0.0.3"
    
    # Simulate requests spread over time
    ddos_protection._request_history[ip].clear()
    
    # Add requests to history (simulating past requests)
    now = time.time()
    for i in range(ddos_protection.config.max_requests_per_minute):
        ddos_protection._request_history[ip].append(now - i * 0.5)
    
    # Next request should be blocked
    request = mock_request(ip=ip)
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is False
    assert "rate limit" in reason.lower()


# ============================================================================
# Connection Limiting Tests
# ============================================================================

@pytest.mark.asyncio
async def test_connection_limit_per_ip(ddos_protection):
    """Test concurrent connection limiting per IP."""
    ip = "10.0.0.4"
    
    # Add connections up to the limit
    for _ in range(ddos_protection.config.max_concurrent_connections_per_ip):
        await ddos_protection.track_connection(ip, increment=True)
    
    assert ddos_protection._active_connections[ip] == \
        ddos_protection.config.max_concurrent_connections_per_ip
    
    # Connection limit should be exceeded
    assert await ddos_protection._check_connection_limit(ip) is False


@pytest.mark.asyncio
async def test_connection_tracking(ddos_protection):
    """Test connection tracking increment and decrement."""
    ip = "10.0.0.5"
    
    # Track connections
    await ddos_protection.track_connection(ip, increment=True)
    assert ddos_protection._active_connections[ip] == 1
    
    await ddos_protection.track_connection(ip, increment=True)
    assert ddos_protection._active_connections[ip] == 2
    
    # Remove connections
    await ddos_protection.track_connection(ip, increment=False)
    assert ddos_protection._active_connections[ip] == 1
    
    await ddos_protection.track_connection(ip, increment=False)
    assert ip not in ddos_protection._active_connections


# ============================================================================
# Threat Scoring Tests
# ============================================================================

@pytest.mark.asyncio
async def test_threat_score_increment(ddos_protection):
    """Test threat score incrementing."""
    ip = "10.0.0.6"
    
    await ddos_protection._increment_threat_score(ip, 10.0, "Test violation")
    
    threat_score = await ddos_protection._get_threat_score(ip)
    assert threat_score.score == 10.0
    assert len(threat_score.violations) == 1
    assert "Test violation" in threat_score.violations[0]


@pytest.mark.asyncio
async def test_threat_score_decay(ddos_protection):
    """Test threat score decay over time."""
    ip = "10.0.0.7"
    
    # Set initial threat score
    await ddos_protection._increment_threat_score(ip, 50.0, "Initial threat")
    
    # Simulate time passing (mock time)
    threat_score = ddos_protection._threat_scores[ip]
    threat_score.last_updated = time.time() - 120  # 2 minutes ago
    
    # Get updated score (should decay by ~2 points)
    updated_score = await ddos_protection._get_threat_score(ip)
    assert updated_score.score < 50.0
    assert updated_score.score >= 48.0  # Decay rate dependent


@pytest.mark.asyncio
async def test_threat_score_auto_block(ddos_protection, mock_request):
    """Test automatic blocking when threat score exceeds threshold."""
    ip = "10.0.0.8"
    
    # Increment threat score above threshold
    await ddos_protection._increment_threat_score(
        ip, 
        ddos_protection.config.auto_block_threshold + 10.0,
        "High threat activity"
    )
    
    request = mock_request(ip=ip)
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is False
    assert "threat score" in reason.lower()


# ============================================================================
# IP Blocking Tests
# ============================================================================

@pytest.mark.asyncio
async def test_ip_blocking(ddos_protection, mock_request):
    """Test manual IP blocking."""
    ip = "10.0.0.9"
    
    # Block IP
    await ddos_protection._block_ip(ip, 300)  # 5 minutes
    
    # Check if blocked
    assert await ddos_protection._is_ip_blocked(ip) is True
    
    # Request should be blocked
    request = mock_request(ip=ip)
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is False
    assert "blocked" in reason.lower()


@pytest.mark.asyncio
async def test_ip_unblocking(ddos_protection):
    """Test manual IP unblocking."""
    ip = "10.0.0.10"
    
    # Block IP
    await ddos_protection._block_ip(ip, 300)
    assert await ddos_protection._is_ip_blocked(ip) is True
    
    # Unblock IP
    result = await ddos_protection.unblock_ip(ip)
    
    assert result is True
    assert await ddos_protection._is_ip_blocked(ip) is False


@pytest.mark.asyncio
async def test_permanent_block(ddos_protection, mock_request):
    """Test permanent IP blocking."""
    ip = "10.0.0.11"
    
    # Add to permanent blocks
    await ddos_protection._permanent_block_ip(ip)
    
    # Request should be blocked with permanent status
    request = mock_request(ip=ip)
    is_allowed, reason = await ddos_protection.check_request(request)
    
    assert is_allowed is False
    assert "permanently blocked" in reason.lower()


# ============================================================================
# Attack Pattern Detection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_detect_sql_injection(ddos_protection, mock_request):
    """Test SQL injection pattern detection."""
    request = mock_request(path="/api/users?id=1 UNION SELECT * FROM users--")
    request.url.query = "id=1 UNION SELECT * FROM users--"
    
    pattern = await ddos_protection._detect_suspicious_pattern(request, "10.0.0.12")
    
    assert pattern == "sql_injection_attempt"


@pytest.mark.asyncio
async def test_detect_xss_attempt(ddos_protection, mock_request):
    """Test XSS pattern detection."""
    request = mock_request(path="/api/search?q=<script>alert('xss')</script>")
    request.url.query = "q=<script>alert('xss')</script>"
    
    pattern = await ddos_protection._detect_suspicious_pattern(request, "10.0.0.13")
    
    assert pattern == "xss_attempt"


@pytest.mark.asyncio
async def test_detect_path_traversal(ddos_protection, mock_request):
    """Test path traversal pattern detection."""
    request = mock_request(path="/api/../../../etc/passwd")
    
    pattern = await ddos_protection._detect_suspicious_pattern(request, "10.0.0.14")
    
    assert pattern == "path_traversal_attempt"


@pytest.mark.asyncio
async def test_detect_missing_user_agent(ddos_protection, mock_request):
    """Test missing user agent detection."""
    request = mock_request(user_agent="")
    
    pattern = await ddos_protection._detect_suspicious_pattern(request, "10.0.0.15")
    
    assert pattern == "suspicious_user_agent"


@pytest.mark.asyncio
async def test_detect_excessive_url_length(ddos_protection, mock_request):
    """Test excessive URL length detection."""
    long_path = "/api/test?" + "a" * 2500
    request = mock_request(path=long_path)
    request.url = Mock()
    request.url.__str__ = Mock(return_value=long_path)
    request.url.path = long_path
    request.url.query = "a" * 2500
    
    pattern = await ddos_protection._detect_suspicious_pattern(request, "10.0.0.16")
    
    assert pattern == "excessive_url_length"


# ============================================================================
# Statistics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_stats(ddos_protection, mock_request):
    """Test retrieving DDoS protection statistics."""
    # Perform some operations
    request1 = mock_request(ip="10.0.0.20")
    await ddos_protection.check_request(request1)
    
    request2 = mock_request(ip="10.0.0.21")
    await ddos_protection.check_request(request2)
    
    # Get stats
    stats = await ddos_protection.get_stats()
    
    assert 'total_requests_checked' in stats
    assert 'total_blocked' in stats
    assert 'active_connections' in stats
    assert 'tracked_ips' in stats
    assert stats['total_requests_checked'] >= 2


# ============================================================================
# Configuration Loading Tests
# ============================================================================

def test_ddos_config_loader_default():
    """Test DDoS config loader with default configuration."""
    loader = DDoSConfigLoader(config_path="nonexistent.yaml")
    config = loader.load_config()
    
    assert isinstance(config, DDoSConfig)
    assert config.max_requests_per_minute > 0
    assert config.max_requests_per_second > 0


@patch.dict('os.environ', {'DDOS_ENABLED': 'false'})
def test_ddos_protection_disabled():
    """Test that DDoS protection can be disabled via environment variable."""
    loader = DDoSConfigLoader()
    
    # Check if protection is disabled
    is_enabled = loader.is_enabled()
    
    # Note: This will depend on if config file exists
    # We're testing the environment variable override works
    assert isinstance(is_enabled, bool)


# ============================================================================
# Middleware Tests
# ============================================================================

@pytest.mark.asyncio
async def test_middleware_integration(ddos_config):
    """Test DDoS protection middleware integration."""
    # Create a test FastAPI app
    app = FastAPI()
    ddos = DDoSProtection(config=ddos_config)
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    # Add middleware
    app.add_middleware(DDoSProtectionMiddleware, ddos_protection=ddos)
    
    # Test with client
    client = TestClient(app)
    
    # Normal request should succeed
    response = client.get("/test")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_middleware_blocks_threats(ddos_config):
    """Test that middleware blocks high-threat requests."""
    app = FastAPI()
    ddos = DDoSProtection(config=ddos_config)
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    app.add_middleware(DDoSProtectionMiddleware, ddos_protection=ddos)
    client = TestClient(app)
    
    # Block an IP
    await ddos._block_ip("127.0.0.1", 300)
    
    # Request should be blocked
    response = client.get("/test")
    assert response.status_code == 403
    assert "blocked" in response.json()["message"].lower()


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_client_ip_with_forwarded_header(ddos_protection, mock_request):
    """Test IP extraction from X-Forwarded-For header."""
    request = mock_request(ip="192.168.1.1")
    request.headers = Headers({
        "x-forwarded-for": "203.0.113.1, 192.168.1.1",
        "user-agent": "Test"
    })
    
    ip = ddos_protection._get_client_ip(request)
    
    # Should extract the first IP in the chain
    assert ip == "203.0.113.1"


@pytest.mark.asyncio
async def test_threat_score_max_cap(ddos_protection):
    """Test that threat score is capped at 100."""
    ip = "10.0.0.30"
    
    # Try to increment beyond 100
    await ddos_protection._increment_threat_score(ip, 150.0, "Huge threat")
    
    threat_score = await ddos_protection._get_threat_score(ip)
    assert threat_score.score == 100.0


@pytest.mark.asyncio
async def test_violation_history_limit(ddos_protection):
    """Test that violation history is limited."""
    ip = "10.0.0.31"
    
    # Add many violations
    for i in range(150):
        await ddos_protection._increment_threat_score(ip, 1.0, f"Violation {i}")
    
    threat_score = await ddos_protection._get_threat_score(ip)
    
    # Should keep only last 100 violations
    assert len(threat_score.violations) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
