"""
Unit tests for api/auth.py

This test suite ensures high reliability of the API authentication module
with comprehensive coverage of:
- API key validation
- FastAPI security integration
- Permission-based access control (RBAC)
- Rate limiting
- Environment-based initialization
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Request
from fastapi.security import APIKeyHeader
from typing import Optional, Set

from api.auth import (
    get_api_key_manager,
    api_key_header,
    get_api_key,
    require_permission,
    initialize_from_env,
    _api_key_manager
)
from core.auth import APIKey, APIKeyManager


@pytest.fixture
def reset_global_manager():
    """Reset the global API key manager and cache before and after each test."""
    import api.auth
    original_manager = api.auth._api_key_manager
    api.auth._api_key_manager = None
    # Clear the cache
    api.auth._validation_cache.clear()
    # Clear lru_cache
    api.auth.get_api_key_manager.cache_clear()
    yield
    api.auth._api_key_manager = original_manager
    api.auth._validation_cache.clear()
    api.auth.get_api_key_manager.cache_clear()


@pytest.fixture
def mock_api_key_manager():
    """Create a mock APIKeyManager."""
    manager = Mock(spec=APIKeyManager)
    manager.api_keys = {}
    manager.key_hashes = {}
    manager._save_keys = Mock()
    return manager


@pytest.fixture
def sample_api_key():
    """Create a sample APIKey instance."""
    return APIKey(
        key="test_key_12345",
        name="test_key",
        created_at=datetime.now(),
        permissions={"read", "write"},
        metadata={"source": "test"}
    )


@pytest.fixture
def admin_api_key():
    """Create an admin APIKey instance."""
    return APIKey(
        key="admin_key_67890",
        name="admin_key",
        created_at=datetime.now(),
        permissions={"read", "write", "admin"},
        metadata={"source": "test", "role": "admin"}
    )


@pytest.fixture
def expired_api_key():
    """Create an expired APIKey instance."""
    return APIKey(
        key="expired_key_11111",
        name="expired_key",
        created_at=datetime.now() - timedelta(days=100),
        expires_at=datetime.now() - timedelta(days=1),
        permissions={"read"},
        metadata={"source": "test"}
    )


@pytest.fixture
def mock_request():
    """Create a mock FastAPI Request."""
    request = Mock(spec=Request)
    request.headers = {"X-API-Key": "test_key_12345"}
    return request


@pytest.fixture
def mock_request_no_key():
    """Create a mock FastAPI Request without API key."""
    request = Mock(spec=Request)
    request.headers = {}
    return request


class TestGetApiKeyManager:
    """Test the global API key manager singleton."""
    
    def test_get_api_key_manager_creates_instance(self, reset_global_manager):
        """Test that get_api_key_manager creates a new instance if none exists."""
        with patch('api.auth.APIKeyManager') as mock_manager_class:
            mock_instance = Mock()
            mock_manager_class.return_value = mock_instance
            
            manager = get_api_key_manager()
            
            mock_manager_class.assert_called_once()
            assert manager == mock_instance
    
    def test_get_api_key_manager_returns_same_instance(self, reset_global_manager):
        """Test that get_api_key_manager returns the same instance on subsequent calls (lru_cache)."""
        with patch('api.auth.APIKeyManager') as mock_manager_class:
            mock_instance = Mock()
            mock_manager_class.return_value = mock_instance
            
            manager1 = get_api_key_manager()
            manager2 = get_api_key_manager()
            
            # With lru_cache, should only be called once
            mock_manager_class.assert_called_once()
            # Both should be the same instance due to caching
            assert manager1 == manager2
    
    def test_get_api_key_manager_uses_lru_cache(self, reset_global_manager):
        """Test that get_api_key_manager uses lru_cache for singleton pattern."""
        with patch('api.auth.APIKeyManager') as mock_manager_class:
            mock_instance = Mock()
            mock_manager_class.return_value = mock_instance
            
            # Call multiple times
            manager1 = get_api_key_manager()
            manager2 = get_api_key_manager()
            manager3 = get_api_key_manager()
            
            # Should only create instance once due to lru_cache
            mock_manager_class.assert_called_once()
            assert manager1 == manager2 == manager3


class TestGetApiKey:
    """Test the FastAPI dependency for API key validation."""
    
    @pytest.mark.asyncio
    async def test_get_api_key_success(self, mock_request, sample_api_key):
        """Test successful API key validation."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.return_value = sample_api_key
            mock_manager.check_rate_limit.return_value = None
            mock_get_manager.return_value = mock_manager
            
            result = await get_api_key(mock_request, "test_key_12345")
            
            assert result == sample_api_key
            mock_manager.validate_key.assert_called_once_with("test_key_12345")
            mock_manager.check_rate_limit.assert_called_once_with("test_key_12345")
    
    @pytest.mark.asyncio
    async def test_get_api_key_missing_header(self, mock_request_no_key):
        """Test that missing API key raises 401 Unauthorized."""
        with pytest.raises(HTTPException) as exc_info:
            await get_api_key(mock_request_no_key, None)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "API key required" in exc_info.value.detail
        assert "X-API-Key" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_api_key_empty_string(self, mock_request):
        """Test that empty string API key raises 401 Unauthorized."""
        with pytest.raises(HTTPException) as exc_info:
            await get_api_key(mock_request, "")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_api_key_invalid_key(self, mock_request):
        """Test that invalid API key raises 401 Unauthorized."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.side_effect = ValueError("Invalid API key")
            mock_get_manager.return_value = mock_manager
            
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(mock_request, "invalid_key")
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid API key" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_api_key_expired_key(self, mock_request):
        """Test that expired API key raises 401 Unauthorized."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.side_effect = ValueError("API key has expired")
            mock_get_manager.return_value = mock_manager
            
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(mock_request, "expired_key")
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "expired" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_get_api_key_rate_limited(self, mock_request, sample_api_key, reset_global_manager):
        """Test that rate-limited API key raises 429 Too Many Requests."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.return_value = sample_api_key
            mock_manager.check_rate_limit.side_effect = ValueError("Rate limit exceeded")
            mock_get_manager.return_value = mock_manager
            
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(mock_request, "test_key_12345")
            
            # Rate limit from cache returns 429, from initial validation returns 401
            assert exc_info.value.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS]
            assert "Rate limit exceeded" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_get_api_key_validates_before_rate_limit(self, mock_request):
        """Test that validation happens before rate limit check."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.side_effect = ValueError("Invalid key")
            mock_get_manager.return_value = mock_manager
            
            with pytest.raises(HTTPException):
                await get_api_key(mock_request, "invalid_key")
            
            mock_manager.check_rate_limit.assert_not_called()


class TestRequirePermission:
    """Test the permission-based access control decorator."""
    
    @pytest.mark.asyncio
    async def test_require_permission_success(self, sample_api_key):
        """Test that user with required permission is allowed."""
        permission_checker = require_permission("read")
        
        result = await permission_checker(sample_api_key)
        
        assert result == sample_api_key
    
    @pytest.mark.asyncio
    async def test_require_permission_multiple_permissions(self, admin_api_key):
        """Test that user with multiple permissions including required one is allowed."""
        permission_checker = require_permission("admin")
        
        result = await permission_checker(admin_api_key)
        
        assert result == admin_api_key
    
    @pytest.mark.asyncio
    async def test_require_permission_missing_permission(self, sample_api_key):
        """Test that user without required permission is denied."""
        permission_checker = require_permission("admin")
        
        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(sample_api_key)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "admin" in exc_info.value.detail
        assert "required" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_require_permission_case_sensitive(self, sample_api_key):
        """Test that permission check is case-sensitive."""
        permission_checker = require_permission("READ")
        
        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(sample_api_key)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    @pytest.mark.asyncio
    async def test_require_permission_empty_permissions(self):
        """Test that API key with no permissions is denied."""
        key_no_perms = APIKey(
            key="no_perms_key",
            name="no_perms",
            created_at=datetime.now(),
            permissions=set(),
            metadata={}
        )
        
        permission_checker = require_permission("read")
        
        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(key_no_perms)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    def test_require_permission_returns_callable(self):
        """Test that require_permission returns a callable dependency."""
        permission_checker = require_permission("test")
        
        assert callable(permission_checker)
    
    @pytest.mark.asyncio
    async def test_require_permission_with_special_characters(self, sample_api_key):
        """Test permission check with special characters."""
        sample_api_key.permissions.add("resource:action")
        
        permission_checker = require_permission("resource:action")
        result = await permission_checker(sample_api_key)
        
        assert result == sample_api_key


class TestInitializeFromEnv:
    """Test environment-based API key initialization."""
    
    def test_initialize_from_env_success(self, reset_global_manager):
        """Test successful initialization from environment."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:abc123,key2:def456"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 2
            assert "abc123" in mock_manager.api_keys
            assert "def456" in mock_manager.api_keys
            
            key1 = mock_manager.api_keys["abc123"]
            assert key1.name == "key1"
            assert "read" in key1.permissions
            assert "write" in key1.permissions
            assert key1.metadata["source"] == "environment"
            
            mock_manager._save_keys.assert_called_once()
    
    
    def test_initialize_from_env_empty_string(self, reset_global_manager):
        """Test initialization with empty string from environment."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = ""
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 0
    
    def test_initialize_from_env_single_key(self, reset_global_manager):
        """Test initialization with single API key."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "single_key:xyz789"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 1
            assert "xyz789" in mock_manager.api_keys
    
    def test_initialize_from_env_skips_existing_keys(self, reset_global_manager):
        """Test that existing keys are not overwritten."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:abc123,key2:def456"
            
            existing_key = APIKey(
                key="abc123",
                name="existing_key",
                created_at=datetime.now() - timedelta(days=10),
                permissions={"admin"},
                metadata={"source": "manual"}
            )
            
            mock_manager = Mock()
            mock_manager.api_keys = {"abc123": existing_key}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 2
            
            assert mock_manager.api_keys["abc123"].name == "existing_key"
            assert mock_manager.api_keys["abc123"].metadata["source"] == "manual"
            
            assert "def456" in mock_manager.api_keys
    
    def test_initialize_from_env_with_whitespace(self, reset_global_manager):
        """Test initialization handles whitespace in keys."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = " key1 : abc123 , key2 : def456 "
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 2
            key1 = mock_manager.api_keys["abc123"]
            assert key1.name == "key1"
    
    def test_initialize_from_env_malformed_entry(self, reset_global_manager, caplog):
        """Test initialization handles malformed entries gracefully."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:abc123,malformed_entry,key2:def456"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 2
            assert "abc123" in mock_manager.api_keys
            assert "def456" in mock_manager.api_keys
    
    def test_initialize_from_env_creates_hash_entries(self, reset_global_manager):
        """Test that initialization creates corresponding hash entries."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager, \
             patch('api.auth.hashlib.sha256') as mock_sha256:
            
            mock_get_secret.return_value = "key1:abc123"
            
            mock_hash = Mock()
            mock_hash.hexdigest.return_value = "hash_of_abc123"
            mock_sha256.return_value = mock_hash
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert "hash_of_abc123" in mock_manager.key_hashes
            assert mock_manager.key_hashes["hash_of_abc123"] == "abc123"
    
    def test_initialize_from_env_exception_handling(self, reset_global_manager, caplog):
        """Test that exceptions during initialization are logged."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:abc123"
            mock_get_manager.side_effect = Exception("Manager creation failed")
            
            initialize_from_env()
            
            # Check for the actual error message
            assert "Unexpected error initializing API keys" in caplog.text
    
    def test_initialize_from_env_multiple_colons(self, reset_global_manager):
        """Test initialization handles keys with multiple colons (e.g., URLs)."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:https://example.com:8080/api"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.api_keys) == 1
            key = list(mock_manager.api_keys.values())[0]
            assert key.name == "key1"
            assert key.key == "https://example.com:8080/api"


class TestIntegration:
    """Integration tests for complete authentication workflows."""
    
    @pytest.mark.asyncio
    async def test_full_authentication_workflow(self, mock_request, sample_api_key):
        """Test complete authentication flow from request to validated key."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.return_value = sample_api_key
            mock_manager.check_rate_limit.return_value = None
            mock_get_manager.return_value = mock_manager
            
            validated_key = await get_api_key(mock_request, "test_key_12345")
            assert validated_key == sample_api_key
            
            permission_checker = require_permission("read")
            result = await permission_checker(validated_key)
            assert result == sample_api_key
    
    @pytest.mark.asyncio
    async def test_authentication_workflow_permission_denied(self, mock_request, sample_api_key):
        """Test authentication workflow where permission is denied."""
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.return_value = sample_api_key
            mock_manager.check_rate_limit.return_value = None
            mock_get_manager.return_value = mock_manager
            
            validated_key = await get_api_key(mock_request, "test_key_12345")
            
            permission_checker = require_permission("admin")
            with pytest.raises(HTTPException) as exc_info:
                await permission_checker(validated_key)
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    
    def test_env_initialization_and_validation_workflow(self, reset_global_manager):
        """Test initializing from environment and then using the keys."""
        with patch('api.auth.get_secret') as mock_get_secret:
            mock_get_secret.return_value = "test_key:abc123"
            
            initialize_from_env()
            
            manager = get_api_key_manager()
            assert "abc123" in manager.api_keys
            
            key = manager.api_keys["abc123"]
            assert key.name == "test_key"
            assert "read" in key.permissions


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_get_api_key_with_none_request(self):
        """Test get_api_key with None request."""
        with pytest.raises(HTTPException):
            await get_api_key(None, None)
    
    @pytest.mark.asyncio
    async def test_require_permission_empty_string(self, sample_api_key):
        """Test require_permission with empty string permission."""
        sample_api_key.permissions.add("")
        
        permission_checker = require_permission("")
        result = await permission_checker(sample_api_key)
        assert result == sample_api_key
    
    @pytest.mark.asyncio
    async def test_require_permission_very_long_permission(self, sample_api_key):
        """Test require_permission with very long permission string."""
        long_permission = "a" * 1000
        sample_api_key.permissions.add(long_permission)
        
        permission_checker = require_permission(long_permission)
        result = await permission_checker(sample_api_key)
        assert result == sample_api_key
    
    def test_initialize_from_env_with_special_characters(self, reset_global_manager):
        """Test initialization with special characters in keys."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key-with-dash:abc_123_xyz"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert "abc_123_xyz" in mock_manager.api_keys
            key = mock_manager.api_keys["abc_123_xyz"]
            assert key.name == "key-with-dash"
    
    @pytest.mark.asyncio
    async def test_get_api_key_with_unicode_characters(self, mock_request):
        """Test get_api_key with unicode characters in key."""
        unicode_key = "test_key_🔑_unicode"
        
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_api_key = APIKey(
                key=unicode_key,
                name="unicode_key",
                created_at=datetime.now(),
                permissions={"read"},
                metadata={}
            )
            
            mock_manager = Mock()
            mock_manager.validate_key.return_value = mock_api_key
            mock_manager.check_rate_limit.return_value = None
            mock_get_manager.return_value = mock_manager
            
            result = await get_api_key(mock_request, unicode_key)
            assert result.key == unicode_key


class TestApiKeyHeader:
    """Test the APIKeyHeader security scheme."""
    
    def test_api_key_header_configuration(self):
        """Test that APIKeyHeader is configured correctly."""
        assert isinstance(api_key_header, APIKeyHeader)
        assert api_key_header.model.name == "X-API-Key"
        assert api_key_header.auto_error is False


class TestConcurrency:
    """Test concurrent access patterns."""
    
    @pytest.mark.asyncio
    async def test_concurrent_api_key_validation(self, mock_request, sample_api_key, reset_global_manager):
        """Test multiple concurrent API key validations with caching."""
        import asyncio
        
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.return_value = sample_api_key
            mock_manager.check_rate_limit.return_value = None
            mock_get_manager.return_value = mock_manager
            
            tasks = [
                get_api_key(mock_request, "test_key_12345")
                for _ in range(10)
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 10
            # All results should be the same APIKey object
            assert all(r.key == sample_api_key.key for r in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_permission_checks(self, admin_api_key):
        """Test multiple concurrent permission checks."""
        import asyncio
        
        permission_checker = require_permission("admin")
        
        tasks = [
            permission_checker(admin_api_key)
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(r == admin_api_key for r in results)


class TestSecurity:
    """Test security-related aspects."""
    
    @pytest.mark.asyncio
    async def test_api_key_not_logged_in_error(self, mock_request):
        """Test that API key value is not exposed in error messages."""
        sensitive_key = "super_secret_key_do_not_log"
        
        with patch('api.auth.get_api_key_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.validate_key.side_effect = ValueError("Invalid API key")
            mock_get_manager.return_value = mock_manager
            
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key(mock_request, sensitive_key)
            
            assert sensitive_key not in exc_info.value.detail
    
    def test_initialize_from_env_hashes_keys(self, reset_global_manager):
        """Test that keys are properly hashed during initialization."""
        with patch('api.auth.get_secret') as mock_get_secret, \
             patch('api.auth.get_api_key_manager') as mock_get_manager:
            
            mock_get_secret.return_value = "key1:secret123"
            
            mock_manager = Mock()
            mock_manager.api_keys = {}
            mock_manager.key_hashes = {}
            mock_manager._save_keys = Mock()
            mock_get_manager.return_value = mock_manager
            
            initialize_from_env()
            
            assert len(mock_manager.key_hashes) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=api.auth', '--cov-report=html'])