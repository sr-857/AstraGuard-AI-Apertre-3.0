# -*- coding: utf-8 -*-
"""
Unit Tests for Security Secrets Adapter Module

Tests for:
- SecretsAdapter protocol
- DevFileAdapter implementation
- VaultAdapter implementation
- AWSSecretsAdapter implementation
- Factory function get_adapter()
- Config loader secret reference resolution
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

# Import modules under test
from security.secrets_adapter import (
    SecretsAdapter,
    DevFileAdapter,
    VaultAdapter,
    AWSSecretsAdapter,
    get_adapter,
    get_secret,
    list_secrets,
    _global_adapter,
)
from config.config_loader import (
    resolve_secret_references,
    load_config_with_secrets,
    _is_secret_reference,
    _resolve_single_secret,
)


class TestDevFileAdapter:
    """Tests for DevFileAdapter."""
    
    def test_get_secret_from_env(self):
        """Test getting a secret from environment variable."""
        adapter = DevFileAdapter(fallback_to_env=True)
        with patch.dict(os.environ, {"TEST_SECRET": "test_value"}):
            result = adapter.get_secret("TEST_SECRET")
            assert result == "test_value"
    
    def test_get_secret_with_default(self):
        """Test getting a secret with default value."""
        adapter = DevFileAdapter(fallback_to_env=True)
        result = adapter.get_secret("NONEXISTENT_SECRET", default="fallback")
        assert result == "fallback"
    
    def test_get_secret_returns_none_when_not_found(self):
        """Test that None is returned when secret not found."""
        adapter = DevFileAdapter(fallback_to_env=False)
        os.environ.pop("MISSING_SECRET", None)
        result = adapter.get_secret("MISSING_SECRET")
        assert result is None
    
    def test_list_secrets_with_prefix(self):
        """Test listing secrets with a prefix filter."""
        adapter = DevFileAdapter(fallback_to_env=True)
        with patch.dict(os.environ, {
            "APP_API_KEY": "key1",
            "APP_SECRET": "secret1",
            "OTHER_VALUE": "other"
        }):
            result = adapter.list_secrets("APP_")
            assert "APP_API_KEY" in result
            assert "APP_SECRET" in result
            assert "OTHER_VALUE" not in result
    
    def test_get_secret_from_env_file(self):
        """Test getting a secret from .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("FILE_SECRET=from_file\n")
            
            adapter = DevFileAdapter(env_path=str(env_file), fallback_to_env=False)
            result = adapter.get_secret("FILE_SECRET")
            assert result == "from_file"
    
    def test_reload_clears_and_reloads(self):
        """Test that reload clears and reloads secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("RELOAD_TEST=original\n")
            
            adapter = DevFileAdapter(env_path=str(env_file), fallback_to_env=False)
            assert adapter.get_secret("RELOAD_TEST") == "original"
            
            # Update file
            env_file.write_text("RELOAD_TEST=updated\n")
            adapter.reload()
            
            assert adapter.get_secret("RELOAD_TEST") == "updated"
    
    def test_get_secret_with_metadata(self):
        """Test get_secret_with_metadata returns proper structure."""
        adapter = DevFileAdapter(fallback_to_env=True)
        with patch.dict(os.environ, {"META_TEST": "meta_value"}):
            result = adapter.get_secret_with_metadata("META_TEST")
            assert result["value"] == "meta_value"
            assert result["name"] == "META_TEST"
            assert result["adapter"] == "DevFileAdapter"
            assert "retrieved_at" in result


class TestVaultAdapter:
    """Tests for VaultAdapter (mocked)."""
    
    @patch("security.secrets_adapter.HAS_VAULT", True)
    @patch("security.secrets_adapter.hvac")
    def test_vault_adapter_init(self, mock_hvac):
        """Test VaultAdapter initialization."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_hvac.Client.return_value = mock_client
        
        adapter = VaultAdapter(
            url="http://vault.example.com:8200",
            token="test-token"
        )
        
        mock_hvac.Client.assert_called_once()
        assert adapter is not None
    
    @patch("security.secrets_adapter.HAS_VAULT", True)
    @patch("security.secrets_adapter.hvac")
    def test_vault_adapter_get_secret(self, mock_hvac):
        """Test getting a secret from Vault."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "vault_secret"}}
        }
        mock_hvac.Client.return_value = mock_client
        
        adapter = VaultAdapter(
            url="http://vault.example.com:8200",
            token="test-token"
        )
        
        result = adapter.get_secret("my_secret")
        assert result == "vault_secret"
    
    @patch("security.secrets_adapter.HAS_VAULT", True)
    @patch("security.secrets_adapter.hvac")
    def test_vault_adapter_caching(self, mock_hvac):
        """Test that Vault adapter caches secrets."""
        mock_client = MagicMock()
        mock_client.is_authenticated.return_value = True
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "cached_value"}}
        }
        mock_hvac.Client.return_value = mock_client
        
        adapter = VaultAdapter(
            url="http://vault.example.com:8200",
            token="test-token",
            cache_ttl_seconds=300
        )
        
        # First call
        result1 = adapter.get_secret("cache_test")
        # Second call (should use cache)
        result2 = adapter.get_secret("cache_test")
        
        assert result1 == result2 == "cached_value"
        # Should only call Vault once due to caching
        assert mock_client.secrets.kv.v2.read_secret_version.call_count == 1
    
    @patch("security.secrets_adapter.HAS_VAULT", False)
    def test_vault_adapter_raises_without_hvac(self):
        """Test that VaultAdapter raises ImportError without hvac."""
        with pytest.raises(ImportError, match="hvac package required"):
            VaultAdapter()


class TestAWSSecretsAdapter:
    """Tests for AWSSecretsAdapter (mocked)."""
    
    @patch("security.secrets_adapter.HAS_AWS", True)
    @patch("security.secrets_adapter.boto3")
    def test_aws_adapter_init(self, mock_boto3):
        """Test AWSSecretsAdapter initialization."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session
        
        adapter = AWSSecretsAdapter(region="us-west-2")
        
        mock_boto3.Session.assert_called_once()
        assert adapter is not None
    
    @patch("security.secrets_adapter.HAS_AWS", True)
    @patch("security.secrets_adapter.boto3")
    def test_aws_adapter_get_secret(self, mock_boto3):
        """Test getting a secret from AWS Secrets Manager."""
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": '{"value": "aws_secret"}'
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session
        
        adapter = AWSSecretsAdapter(region="us-west-2")
        result = adapter.get_secret("my_aws_secret")
        
        assert result == "aws_secret"
    
    @patch("security.secrets_adapter.HAS_AWS", False)
    def test_aws_adapter_raises_without_boto3(self):
        """Test that AWSSecretsAdapter raises ImportError without boto3."""
        with pytest.raises(ImportError, match="boto3 package required"):
            AWSSecretsAdapter()


class TestGetAdapterFactory:
    """Tests for get_adapter factory function."""
    
    def test_get_adapter_default_returns_dev(self):
        """Test that default adapter is DevFileAdapter."""
        # Clear any cached adapter
        import security.secrets_adapter as sa
        sa._global_adapter = None
        
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SECRETS_ADAPTER", None)
            adapter = get_adapter()
            assert isinstance(adapter, DevFileAdapter)
    
    def test_get_adapter_respects_env_var(self):
        """Test that SECRETS_ADAPTER env var is respected."""
        import security.secrets_adapter as sa
        sa._global_adapter = None
        
        with patch.dict(os.environ, {"SECRETS_ADAPTER": "dev"}):
            adapter = get_adapter()
            assert isinstance(adapter, DevFileAdapter)
    
    def test_get_adapter_explicit_type(self):
        """Test explicit adapter type selection."""
        adapter = get_adapter("dev")
        assert isinstance(adapter, DevFileAdapter)
    
    def test_get_adapter_invalid_type_raises(self):
        """Test that invalid adapter type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown adapter type"):
            get_adapter("invalid_adapter")


class TestSecretReferenceResolution:
    """Tests for secret reference resolution in config_loader."""
    
    def test_is_secret_reference_valid(self):
        """Test _is_secret_reference with valid references."""
        assert _is_secret_reference("secrets://api_key") is True
        assert _is_secret_reference("secrets://path/to/secret") is True
        assert _is_secret_reference("secrets://DB_PASSWORD") is True
    
    def test_is_secret_reference_invalid(self):
        """Test _is_secret_reference with invalid values."""
        assert _is_secret_reference("plain_value") is False
        assert _is_secret_reference("http://example.com") is False
        assert _is_secret_reference(123) is False
        assert _is_secret_reference(None) is False
        assert _is_secret_reference({"key": "value"}) is False
    
    def test_resolve_secret_references_simple(self):
        """Test resolving simple secret references."""
        adapter = MagicMock()
        adapter.get_secret.return_value = "resolved_value"
        
        config = {
            "api_key": "secrets://API_KEY",
            "regular_value": "plain_text"
        }
        
        result = resolve_secret_references(config, adapter=adapter)
        
        assert result["api_key"] == "resolved_value"
        assert result["regular_value"] == "plain_text"
    
    def test_resolve_secret_references_nested(self):
        """Test resolving nested secret references."""
        adapter = MagicMock()
        adapter.get_secret.side_effect = lambda name, default=None: {
            "DB_PASSWORD": "db_pass",
            "API_KEY": "api_key_value"
        }.get(name, default)
        
        config = {
            "database": {
                "host": "localhost",
                "password": "secrets://DB_PASSWORD"
            },
            "api": {
                "key": "secrets://API_KEY"
            }
        }
        
        result = resolve_secret_references(config, adapter=adapter)
        
        assert result["database"]["password"] == "db_pass"
        assert result["api"]["key"] == "api_key_value"
        assert result["database"]["host"] == "localhost"
    
    def test_resolve_secret_references_list(self):
        """Test resolving secrets in lists."""
        adapter = MagicMock()
        adapter.get_secret.side_effect = lambda name, default=None: {
            "KEY1": "value1",
            "KEY2": "value2"
        }.get(name, default)
        
        config = {
            "keys": ["secrets://KEY1", "secrets://KEY2", "plain_value"]
        }
        
        result = resolve_secret_references(config, adapter=adapter)
        
        assert result["keys"] == ["value1", "value2", "plain_value"]
    
    def test_resolve_secret_references_missing_raises(self):
        """Test that missing secrets raise ValueError when raise_on_missing=True."""
        adapter = MagicMock()
        adapter.get_secret.return_value = None
        
        config = {"key": "secrets://MISSING_SECRET"}
        
        with pytest.raises(ValueError, match="not found"):
            resolve_secret_references(config, adapter=adapter, raise_on_missing=True)
    
    def test_resolve_secret_references_missing_silent(self):
        """Test that missing secrets are left as-is when raise_on_missing=False."""
        adapter = MagicMock()
        adapter.get_secret.return_value = None
        
        config = {"key": "secrets://MISSING_SECRET"}
        
        result = resolve_secret_references(config, adapter=adapter, raise_on_missing=False)
        
        assert result["key"] == "secrets://MISSING_SECRET"


class TestLoadConfigWithSecrets:
    """Tests for load_config_with_secrets function."""
    
    def test_load_and_resolve_yaml(self):
        """Test loading YAML config and resolving secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.yaml"
            config_file.write_text("""
api:
  key: secrets://API_KEY
  url: https://api.example.com
database:
  host: localhost
  password: secrets://DB_PASSWORD
""")
            
            adapter = MagicMock()
            adapter.get_secret.side_effect = lambda name, default=None: {
                "API_KEY": "resolved_api_key",
                "DB_PASSWORD": "resolved_db_pass"
            }.get(name, default)
            
            result = load_config_with_secrets(str(config_file), adapter=adapter)
            
            assert result["api"]["key"] == "resolved_api_key"
            assert result["api"]["url"] == "https://api.example.com"
            assert result["database"]["password"] == "resolved_db_pass"
            assert result["database"]["host"] == "localhost"
    
    def test_load_and_resolve_json(self):
        """Test loading JSON config and resolving secrets."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "test.json"
            config_file.write_text('''
{
    "secret_value": "secrets://SECRET",
    "plain_value": "hello"
}
''')
            
            adapter = MagicMock()
            adapter.get_secret.return_value = "resolved_secret"
            
            result = load_config_with_secrets(str(config_file), adapter=adapter)
            
            assert result["secret_value"] == "resolved_secret"
            assert result["plain_value"] == "hello"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""
    
    def test_get_secret_function(self):
        """Test get_secret convenience function."""
        adapter = MagicMock()
        adapter.get_secret.return_value = "convenience_value"
        
        result = get_secret("TEST_KEY", adapter=adapter)
        
        assert result == "convenience_value"
        adapter.get_secret.assert_called_once_with("TEST_KEY", None)
    
    def test_list_secrets_function(self):
        """Test list_secrets convenience function."""
        adapter = MagicMock()
        adapter.list_secrets.return_value = ["SECRET_A", "SECRET_B"]
        
        result = list_secrets("SECRET_", adapter=adapter)
        
        assert result == ["SECRET_A", "SECRET_B"]
        adapter.list_secrets.assert_called_once_with("SECRET_")


class TestIntegration:
    """Integration tests for the secrets adapter system."""
    
    def test_full_workflow_with_dev_adapter(self):
        """Test complete workflow using DevFileAdapter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env file
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("""
API_KEY=my_api_key_123
DB_PASSWORD=super_secret_password
JWT_SECRET=jwt_secret_value
""")
            
            # Create config file with secret references
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text("""
app:
  name: TestApp
  environment: development
api:
  key: secrets://API_KEY
database:
  connection_string: postgres://user:secrets://DB_PASSWORD@localhost/db
auth:
  jwt_secret: secrets://JWT_SECRET
""")
            
            # Initialize adapter
            adapter = DevFileAdapter(env_path=str(env_file))
            
            # Verify individual secrets
            assert adapter.get_secret("API_KEY") == "my_api_key_123"
            assert adapter.get_secret("DB_PASSWORD") == "super_secret_password"
            
            # Load and resolve config
            result = load_config_with_secrets(str(config_file), adapter=adapter)
            
            assert result["app"]["name"] == "TestApp"
            assert result["api"]["key"] == "my_api_key_123"
            assert result["auth"]["jwt_secret"] == "jwt_secret_value"
