"""
Unit tests for core/secrets.py - Centralized Secrets Management Module
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Import secrets module
from core.secrets import (
    SecretManager,
    secrets_manager,
    get_secret,
    require_secrets,
    mask_secret,
)


class TestGetSecret:
    """Test get_secret() function."""
    
    def test_get_secret_from_env(self):
        """Test getting a secret from environment variable."""
        with patch.dict(os.environ, {"TEST_SECRET": "my_secret_value"}):
            secrets_manager.clear_cache()
            result = get_secret("TEST_SECRET")
            assert result == "my_secret_value"
    
    def test_get_secret_with_default(self):
        """Test getting a secret with default value when not set."""
        secrets_manager.clear_cache()
        # Ensure env var is not set
        os.environ.pop("NONEXISTENT_SECRET", None)
        result = get_secret("NONEXISTENT_SECRET", default="fallback")
        assert result == "fallback"
    
    def test_get_secret_returns_none_when_not_set(self):
        """Test that None is returned when secret is not set and no default."""
        secrets_manager.clear_cache()
        os.environ.pop("MISSING_SECRET", None)
        result = get_secret("MISSING_SECRET")
        assert result is None
    
    def test_get_secret_required_raises_error(self):
        """Test that ValueError is raised when required secret is missing."""
        secrets_manager.clear_cache()
        os.environ.pop("REQUIRED_MISSING", None)
        
        with pytest.raises(ValueError) as exc_info:
            get_secret("REQUIRED_MISSING", required=True)
        
        assert "REQUIRED_MISSING" in str(exc_info.value)
        assert "not set" in str(exc_info.value)
    
    def test_get_secret_required_returns_value(self):
        """Test getting a required secret that exists."""
        with patch.dict(os.environ, {"REQUIRED_PRESENT": "secret123"}):
            secrets_manager.clear_cache()
            result = get_secret("REQUIRED_PRESENT", required=True)
            assert result == "secret123"
    
    def test_get_secret_caches_value(self):
        """Test that secrets are cached after first access."""
        with patch.dict(os.environ, {"CACHED_SECRET": "original"}):
            secrets_manager.clear_cache()
            
            # First access
            result1 = get_secret("CACHED_SECRET")
            assert result1 == "original"
            
            # Modify env (shouldn't affect cached value)
            os.environ["CACHED_SECRET"] = "changed"
            result2 = get_secret("CACHED_SECRET")
            
            # Should still be cached original value
            assert result2 == "original"


class TestRequireSecrets:
    """Test require_secrets() function."""
    
    def test_require_secrets_all_present(self):
        """Test validation when all secrets are present."""
        with patch.dict(os.environ, {
            "SECRET_A": "value_a",
            "SECRET_B": "value_b",
            "SECRET_C": "value_c"
        }):
            secrets_manager.clear_cache()
            result = require_secrets(["SECRET_A", "SECRET_B", "SECRET_C"])
            
            assert result["SECRET_A"] == "value_a"
            assert result["SECRET_B"] == "value_b"
            assert result["SECRET_C"] == "value_c"
    
    def test_require_secrets_missing_raises_error(self):
        """Test that ValueError is raised when secrets are missing."""
        secrets_manager.clear_cache()
        # Clear any existing env vars
        os.environ.pop("MISSING_A", None)
        os.environ.pop("MISSING_B", None)
        
        with patch.dict(os.environ, {"PRESENT_ONE": "value"}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                require_secrets(["PRESENT_ONE", "MISSING_A", "MISSING_B"])
            
            error_msg = str(exc_info.value)
            assert "MISSING_A" in error_msg
            assert "MISSING_B" in error_msg
            assert "PRESENT_ONE" not in error_msg
    
    def test_require_secrets_empty_list(self):
        """Test validation with empty list returns empty dict."""
        result = require_secrets([])
        assert result == {}


class TestMaskSecret:
    """Test mask_secret() function."""
    
    def test_mask_secret_default(self):
        """Test masking with default visible chars (4)."""
        result = mask_secret("my_super_secret_key")
        assert result == "***************_key"
        assert result.endswith("_key")
        assert "*" in result
    
    def test_mask_secret_custom_visible(self):
        """Test masking with custom visible chars."""
        result = mask_secret("password123", visible_chars=3)
        assert result == "********123"
    
    def test_mask_secret_short_value(self):
        """Test masking when value is shorter than visible chars."""
        result = mask_secret("abc", visible_chars=4)
        assert result == "***"  # Fully masked
    
    def test_mask_secret_empty_string(self):
        """Test masking empty string."""
        result = mask_secret("")
        assert result == ""
    
    def test_mask_secret_exact_length(self):
        """Test masking when value length equals visible chars."""
        result = mask_secret("abcd", visible_chars=4)
        assert result == "****"  # Fully masked


class TestSecretManager:
    """Test SecretManager class directly."""
    
    def test_singleton_pattern(self):
        """Test that SecretManager uses singleton pattern."""
        manager1 = SecretManager()
        manager2 = SecretManager()
        assert manager1 is manager2
    
    def test_is_secret_name_matches_patterns(self):
        """Test secret name pattern matching."""
        manager = SecretManager()
        
        # Should match
        assert manager.is_secret_name("API_KEY") is True
        assert manager.is_secret_name("database_password") is True
        assert manager.is_secret_name("JWT_SECRET") is True
        assert manager.is_secret_name("auth_token") is True
        assert manager.is_secret_name("user_credentials") is True
        
        # Should not match
        assert manager.is_secret_name("LOG_LEVEL") is False
        assert manager.is_secret_name("MAX_SIZE") is False
        assert manager.is_secret_name("DEBUG_MODE") is False
    
    def test_get_masked(self):
        """Test get_masked() returns masked value."""
        with patch.dict(os.environ, {"MASK_TEST": "supersecret123"}):
            secrets_manager.clear_cache()
            result = secrets_manager.get_masked("MASK_TEST")
            assert result == "**********t123"
            assert "supersecret" not in result
    
    def test_get_masked_not_set(self):
        """Test get_masked() when secret is not set."""
        secrets_manager.clear_cache()
        os.environ.pop("NOT_SET_MASK", None)
        result = secrets_manager.get_masked("NOT_SET_MASK")
        assert result == "<not set>"
    
    def test_clear_cache(self):
        """Test clearing the secrets cache."""
        with patch.dict(os.environ, {"CACHE_TEST": "value1"}):
            secrets_manager.clear_cache()
            
            # Get value (caches it)
            get_secret("CACHE_TEST")
            
            # Change env
            os.environ["CACHE_TEST"] = "value2"
            
            # Still cached
            assert get_secret("CACHE_TEST") == "value1"
            
            # Clear cache
            secrets_manager.clear_cache()
            
            # Now gets new value
            assert get_secret("CACHE_TEST") == "value2"


class TestIntegration:
    """Integration tests for secrets module."""
    
    def test_typical_startup_validation(self):
        """Test typical startup secret validation pattern."""
        with patch.dict(os.environ, {
            "API_KEY": "key123",
            "JWT_SECRET": "jwtsecret456",
            "DATABASE_URL": "postgres://localhost/db"
        }):
            secrets_manager.clear_cache()
            
            # Validate required secrets
            secrets = require_secrets(["API_KEY", "JWT_SECRET", "DATABASE_URL"])
            
            # Use secrets
            api_key = get_secret("API_KEY")
            jwt_secret = get_secret("JWT_SECRET")
            
            assert api_key == "key123"
            assert jwt_secret == "jwtsecret456"
            
            # Safe logging
            masked = mask_secret(api_key)
            assert "key123" not in masked or masked == "***123"
