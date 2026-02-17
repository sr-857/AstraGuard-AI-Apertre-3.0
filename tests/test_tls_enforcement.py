"""
Test suite for TLS/SSL enforcement module.

Tests TLS configuration, secure HTTP client, and TLS enforcement
to ensure all internal service communication uses encrypted channels.
"""

import pytest
import ssl
import os
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse

# Import TLS modules
from core.tls_config import (
    TLSConfig,
    TLSConfigManager,
    get_tls_config,
    get_tls_config_manager,
    is_tls_required,
    create_ssl_context,
)
from core.secure_http_client import (
    SecureHTTPClient,
    HTTPSTransportError,
    enforce_https,
    create_secure_client,
)
from core.tls_enforcement import (
    TLSValidator,
    TLSEnforcementError,
    require_tls,
    require_https_urls,
    require_secure_redis,
    ensure_https,
    ensure_rediss,
    _is_http_url,
    _is_redis_url,
    TLSMiddleware,
)


class TestTLSConfig:
    """Test TLS configuration management."""

    def test_tls_config_defaults(self):
        """Test TLSConfig with default values."""
        config = TLSConfig()
        assert config.enabled is True
        assert config.enforce_tls is True
        assert config.verify_mode == ssl.CERT_REQUIRED
        assert config.min_tls_version == ssl.TLSVersion.TLSv1_2
        assert config.mutual_tls is False

    def test_tls_config_custom_values(self):
        """Test TLSConfig with custom values."""
        config = TLSConfig(
            enabled=True,
            enforce_tls=True,
            verify_mode=ssl.CERT_OPTIONAL,
            min_tls_version=ssl.TLSVersion.TLSv1_3,
            mutual_tls=True,
        )
        assert config.enabled is True
        assert config.enforce_tls is True
        assert config.verify_mode == ssl.CERT_OPTIONAL
        assert config.min_tls_version == ssl.TLSVersion.TLSv1_3
        assert config.mutual_tls is True

    def test_tls_config_is_configured_without_certs(self):
        """Test that TLS is not configured without certificates."""
        config = TLSConfig(enabled=True, enforce_tls=True)
        assert config.is_configured() is False

    def test_tls_config_disabled(self):
        """Test that disabled TLS config returns False for is_configured."""
        config = TLSConfig(enabled=False)
        assert config.is_configured() is False

    def test_create_ssl_context_disabled(self):
        """Test that creating SSL context fails when TLS is disabled."""
        config = TLSConfig(enabled=False)
        with pytest.raises(ValueError, match="TLS is not enabled"):
            config.create_ssl_context()

    def test_create_ssl_context_enabled(self):
        """Test creating SSL context when TLS is enabled."""
        config = TLSConfig(enabled=True)
        # Should not raise an exception
        context = config.create_ssl_context()
        assert isinstance(context, ssl.SSLContext)


class TestTLSConfigManager:
    """Test TLS configuration manager."""

    def test_singleton_pattern(self):
        """Test that get_tls_config_manager returns singleton."""
        manager1 = get_tls_config_manager()
        manager2 = get_tls_config_manager()
        assert manager1 is manager2

    def test_load_from_environment(self):
        """Test loading TLS config from environment variables."""
        with patch.dict(os.environ, {
            "TLS_ENABLED": "true",
            "TLS_ENFORCE": "true",
            "TLS_VERIFY_MODE": "required",
            "TLS_MIN_VERSION": "1.3",
            "TLS_MUTUAL_TLS": "true",
        }):
            manager = TLSConfigManager()
            config = manager.load_from_environment()
            
            assert config.enabled is True
            assert config.enforce_tls is True
            assert config.verify_mode == ssl.CERT_REQUIRED
            assert config.min_tls_version == ssl.TLSVersion.TLSv1_3
            assert config.mutual_tls is True

    def test_service_specific_config(self):
        """Test registering and retrieving service-specific configs."""
        manager = TLSConfigManager()
        
        default_config = TLSConfig(enabled=True)
        service_config = TLSConfig(enabled=True, enforce_tls=False)
        
        manager.set_default_config(default_config)
        manager.register_service_config("test-service", service_config)
        
        # Should return service-specific config
        retrieved = manager.get_service_config("test-service")
        assert retrieved.enforce_tls is False
        
        # Should return default config for unknown service
        default_retrieved = manager.get_service_config("unknown-service")
        assert default_retrieved.enforce_tls is True

    def test_is_tls_required(self):
        """Test checking if TLS is required."""
        manager = TLSConfigManager()
        config = TLSConfig(enabled=True, enforce_tls=True)
        manager.set_default_config(config)
        
        assert manager.is_tls_required() is True
        assert manager.is_tls_required("any-service") is True


class TestSecureHTTPClient:
    """Test secure HTTP client."""

    def test_client_initialization(self):
        """Test secure HTTP client initialization."""
        client = SecureHTTPClient(service_name="test")
        assert client.service_name == "test"
        assert client.tls_required is True  # Default from config

    def test_validate_url_https(self):
        """Test that HTTPS URLs pass validation."""
        client = SecureHTTPClient(service_name="test")
        url = client._validate_url("https://example.com/api")
        assert url == "https://example.com/api"

    def test_validate_url_http_when_tls_required(self):
        """Test that HTTP URLs are rejected when TLS is required."""
        client = SecureHTTPClient(service_name="test")
        client.tls_required = True
        
        with pytest.raises(HTTPSTransportError):
            client._validate_url("http://example.com/api")

    def test_validate_url_http_when_tls_not_required(self):
        """Test that HTTP URLs are allowed when TLS is not required."""
        client = SecureHTTPClient(service_name="test")
        client.tls_required = False
        
        url = client._validate_url("http://example.com/api")
        assert url == "http://example.com/api"

    def test_validate_url_no_scheme_with_tls(self):
        """Test that URLs without scheme get HTTPS when TLS is required."""
        client = SecureHTTPClient(service_name="test")
        client.tls_required = True
        
        url = client._validate_url("example.com/api")
        assert url == "https://example.com/api"

    def test_enforce_https_function(self):
        """Test the enforce_https utility function."""
        # HTTPS should pass through
        assert enforce_https("https://example.com") == "https://example.com"
        
        # HTTP should be converted to HTTPS
        assert enforce_https("http://example.com") == "https://example.com"
        
        # No scheme should get HTTPS
        assert enforce_https("example.com") == "https://example.com"

    def test_create_secure_client_factory(self):
        """Test the secure client factory function."""
        client = create_secure_client(service_name="test-service")
        assert isinstance(client, SecureHTTPClient)
        assert client.service_name == "test-service"


class TestTLSValidator:
    """Test TLS validator."""

    def test_validate_url_https(self):
        """Test validating HTTPS URL."""
        validator = TLSValidator(strict=True)
        assert validator.validate_url("https://example.com") is True

    def test_validate_url_http_strict_mode(self):
        """Test that HTTP URL fails in strict mode."""
        validator = TLSValidator(strict=True)
        
        with pytest.raises(TLSEnforcementError):
            validator.validate_url("http://example.com")

    def test_validate_url_http_non_strict_mode(self):
        """Test that HTTP URL is allowed in non-strict mode."""
        validator = TLSValidator(strict=False)
        result = validator.validate_url("http://example.com")
        assert result is False  # Returns False but doesn't raise

    def test_validate_redis_url_secure(self):
        """Test validating secure Redis URL."""
        validator = TLSValidator(strict=True)
        assert validator.validate_redis_url("rediss://localhost:6379") is True

    def test_validate_redis_url_insecure_strict(self):
        """Test that insecure Redis URL fails in strict mode."""
        validator = TLSValidator(strict=True)
        
        with pytest.raises(TLSEnforcementError):
            validator.validate_redis_url("redis://localhost:6379")

    def test_validate_redis_url_insecure_non_strict(self):
        """Test that insecure Redis URL is allowed in non-strict mode."""
        validator = TLSValidator(strict=False)
        result = validator.validate_redis_url("redis://localhost:6379")
        assert result is False

    def test_validate_amqp_url_secure(self):
        """Test validating secure AMQP URL."""
        validator = TLSValidator(strict=True)
        assert validator.validate_amqp_url("amqps://localhost:5672") is True

    def test_validate_amqp_url_insecure(self):
        """Test that insecure AMQP URL fails in strict mode."""
        validator = TLSValidator(strict=True)
        
        with pytest.raises(TLSEnforcementError):
            validator.validate_amqp_url("amqp://localhost:5672")

    def test_validate_kafka_url_secure(self):
        """Test validating secure Kafka URL."""
        validator = TLSValidator(strict=True)
        assert validator.validate_kafka_url("SSL://localhost:9093") is True
        assert validator.validate_kafka_url("SASL_SSL://localhost:9093") is True

    def test_validate_kafka_url_insecure(self):
        """Test that insecure Kafka URL fails in strict mode."""
        validator = TLSValidator(strict=True)
        
        with pytest.raises(TLSEnforcementError):
            validator.validate_kafka_url("PLAINTEXT://localhost:9092")

    def test_validate_mongodb_url_secure_srv(self):
        """Test validating secure MongoDB SRV URL."""
        validator = TLSValidator(strict=True)
        assert validator.validate_mongodb_url("mongodb+srv://cluster.example.com") is True

    def test_validate_mongodb_url_secure_tls_param(self):
        """Test validating MongoDB URL with TLS parameter."""
        validator = TLSValidator(strict=True)
        assert validator.validate_mongodb_url("mongodb://localhost:27017/?tls=true") is True

    def test_validate_mongodb_url_insecure(self):
        """Test that insecure MongoDB URL fails in strict mode."""
        validator = TLSValidator(strict=True)
        
        with pytest.raises(TLSEnforcementError):
            validator.validate_mongodb_url("mongodb://localhost:27017")

    def test_violations_tracking(self):
        """Test that violations are tracked."""
        validator = TLSValidator(strict=False)
        
        # These should add violations but not raise
        validator.validate_url("http://example.com")
        validator.validate_redis_url("redis://localhost:6379")
        
        violations = validator.get_violations()
        assert len(violations) == 2
        assert any("HTTP URL" in v for v in violations)
        assert any("Redis URL" in v for v in violations)

    def test_clear_violations(self):
        """Test clearing violations."""
        validator = TLSValidator(strict=False)
        validator.validate_url("http://example.com")
        
        assert len(validator.get_violations()) == 1
        
        validator.clear_violations()
        assert len(validator.get_violations()) == 0


class TestURLTransformation:
    """Test URL transformation functions."""

    def test_ensure_https(self):
        """Test ensure_https function."""
        assert ensure_https("https://example.com") == "https://example.com"
        assert ensure_https("http://example.com") == "https://example.com"
        assert ensure_https("example.com") == "https://example.com"

    def test_ensure_rediss(self):
        """Test ensure_rediss function."""
        assert ensure_rediss("rediss://localhost:6379") == "rediss://localhost:6379"
        assert ensure_rediss("redis://localhost:6379") == "rediss://localhost:6379"
        assert ensure_rediss("localhost:6379") == "rediss://localhost:6379"

    def test_ensure_amqps(self):
        """Test ensure_amqps function."""
        from core.tls_enforcement import ensure_amqps
        
        assert ensure_amqps("amqps://localhost:5672") == "amqps://localhost:5672"
        assert ensure_amqps("amqp://localhost:5672") == "amqps://localhost:5672"
        assert ensure_amqps("localhost:5672") == "amqps://localhost:5672"


class TestURLDetection:
    """Test URL detection helper functions."""

    def test_is_http_url(self):
        """Test HTTP URL detection."""
        assert _is_http_url("http://example.com") is True
        assert _is_http_url("https://example.com") is True
        assert _is_http_url("ftp://example.com") is False
        assert _is_http_url("not-a-url") is False

    def test_is_redis_url(self):
        """Test Redis URL detection."""
        from core.tls_enforcement import _is_redis_url
        
        assert _is_redis_url("redis://localhost:6379") is True
        assert _is_redis_url("rediss://localhost:6379") is True
        assert _is_redis_url("http://localhost:6379") is False


class TestDecorators:
    """Test TLS enforcement decorators."""

    def test_require_tls_decorator(self):
        """Test require_tls decorator."""
        
        @require_tls
        def test_function(url):
            return url
        
        # Should work with HTTPS
        result = test_function("https://example.com")
        assert result == "https://example.com"
        
        # Should raise with HTTP in strict mode
        with pytest.raises(TLSEnforcementError):
            test_function("http://example.com")

    def test_require_https_urls_decorator(self):
        """Test require_https_urls decorator."""
        from core.tls_enforcement import require_https_urls
        
        @require_https_urls
        def test_function(url):
            return url
        
        # Should work with HTTPS
        result = test_function("https://example.com")
        assert result == "https://example.com"

    def test_require_secure_redis_decorator(self):
        """Test require_secure_redis decorator."""
        from core.tls_enforcement import require_secure_redis
        
        @require_secure_redis
        def test_function(url):
            return url
        
        # Should work with rediss://
        result = test_function("rediss://localhost:6379")
        assert result == "rediss://localhost:6379"
        
        # Should raise with redis:// in strict mode
        with pytest.raises(TLSEnforcementError):
            test_function("redis://localhost:6379")


class TestTLSMiddleware:
    """Test TLS middleware."""

    @pytest.mark.asyncio
    async def test_middleware_initialization(self):
        """Test TLS middleware initialization."""
        middleware = TLSMiddleware(
            enforce_tls=True,
            service_name="test",
            redirect_to_https=False,
        )
        assert middleware.enforce_tls is True
        assert middleware.redirect_to_https is False
        assert middleware.service_name == "test"

    def test_is_https_request_direct(self):
        """Test detecting HTTPS request directly."""
        middleware = TLSMiddleware()
        
        scope = {"scheme": "https"}
        assert middleware._is_https_request(scope) is True
        
        scope = {"scheme": "http"}
        assert middleware._is_https_request(scope) is False

    def test_is_https_request_forwarded(self):
        """Test detecting HTTPS request via X-Forwarded-Proto."""
        middleware = TLSMiddleware()
        
        scope = {
            "scheme": "http",
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        assert middleware._is_https_request(scope) is True

    def test_is_https_request_port_443(self):
        """Test detecting HTTPS request via port 443."""
        middleware = TLSMiddleware()
        
        scope = {
            "scheme": "http",
            "headers": [],
            "server": ("localhost", 443),
        }
        assert middleware._is_https_request(scope) is True


class TestIntegration:
    """Integration tests for TLS enforcement."""

    def test_full_tls_workflow(self):
        """Test complete TLS enforcement workflow."""
        # 1. Configure TLS
        config = TLSConfig(
            enabled=True,
            enforce_tls=True,
        )
        
        # 2. Create validator
        validator = TLSValidator(strict=True)
        
        # 3. Validate URLs
        assert validator.validate_url("https://api.example.com") is True
        
        # 4. Test with secure client
        client = SecureHTTPClient(service_name="test")
        validated_url = client._validate_url("https://api.example.com")
        assert validated_url == "https://api.example.com"

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {
            "TLS_ENABLED": "false",
            "TLS_ENFORCE": "false",
        }):
            manager = TLSConfigManager()
            config = manager.load_from_environment()
            
            assert config.enabled is False
            assert config.enforce_tls is False


class TestErrorHandling:
    """Test error handling in TLS enforcement."""

    def test_tls_enforcement_error_message(self):
        """Test that TLS enforcement errors have helpful messages."""
        error = TLSEnforcementError("Test error message")
        assert "Test error message" in str(error)

    def test_http_transport_error(self):
        """Test HTTP transport error."""
        error = HTTPSTransportError("HTTP not allowed")
        assert "HTTP not allowed" in str(error)

    def test_validator_with_service_config(self):
        """Test validator with service-specific config."""
        manager = get_tls_config_manager()
        
        # Create a service config that doesn't enforce TLS
        service_config = TLSConfig(enabled=True, enforce_tls=False)
        manager.register_service_config("lenient-service", service_config)
        
        # Validator should use service config
        validator = TLSValidator(service_name="lenient-service", strict=False)
        
        # Should not raise in non-strict mode
        result = validator.validate_url("http://example.com")
        assert result is False  # Returns False but doesn't raise


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
