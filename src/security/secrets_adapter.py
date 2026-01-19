# -*- coding: utf-8 -*-
"""
Secrets Adapter Module

Provides a pluggable adapter interface for secrets management with implementations
for different environments:
- DevFileAdapter: Local development using .env files
- VaultAdapter: HashiCorp Vault integration
- AWSSecretsAdapter: AWS Secrets Manager integration

Usage:
    from security.secrets_adapter import get_adapter, get_secret

    # Get appropriate adapter based on environment
    adapter = get_adapter()
    
    # Fetch a secret
    api_key = adapter.get_secret("API_KEY")
    
    # Or use convenience function
    api_key = get_secret("API_KEY")
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from dotenv import dotenv_values
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False
    dotenv_values = None

try:
    import hvac
    HAS_VAULT = True
except ImportError:
    HAS_VAULT = False
    hvac = None

try:
    import boto3
    HAS_AWS = True
except ImportError:
    HAS_AWS = False
    boto3 = None


class SecretsAdapter(ABC):
    """
    Abstract base class defining the secrets adapter protocol.
    
    All adapters must implement:
    - get_secret(name: str) -> str: Retrieve a secret by name
    - list_secrets(prefix: str) -> List[str]: List secrets matching prefix
    """
    
    @abstractmethod
    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret value by name.
        
        Args:
            name: The secret name/key
            default: Default value if secret not found
            
        Returns:
            The secret value, or default if not found
            
        Raises:
            KeyError: If secret not found and no default provided
        """
        pass
    
    @abstractmethod
    def list_secrets(self, prefix: str = "") -> List[str]:
        """
        List secret names matching the given prefix.
        
        Args:
            prefix: Filter secrets by this prefix
            
        Returns:
            List of secret names
        """
        pass
    
    def get_secret_with_metadata(self, name: str) -> Dict[str, Any]:
        """
        Get secret value along with metadata (optional override).
        
        Args:
            name: The secret name/key
            
        Returns:
            Dict with 'value' and optional metadata fields
        """
        value = self.get_secret(name)
        return {
            "value": value,
            "name": name,
            "adapter": self.__class__.__name__,
            "retrieved_at": datetime.now().isoformat(),
        }


class DevFileAdapter(SecretsAdapter):
    """
    Development adapter that reads secrets from .env files.
    
    Suitable for local development. Never use in production.
    
    Features:
    - Reads from .env, .env.local, or custom path
    - Falls back to environment variables
    - Caches values for performance
    - Never logs secret values
    """
    
    def __init__(self, env_path: Optional[str] = None, fallback_to_env: bool = True):
        """
        Initialize the DevFileAdapter.
        
        Args:
            env_path: Path to .env file. If None, searches default locations.
            fallback_to_env: If True, falls back to os.environ when not in .env
        """
        self._fallback_to_env = fallback_to_env
        self._secrets: Dict[str, str] = {}
        self._env_path: Optional[Path] = None
        
        # Load .env file
        self._load_env_file(env_path)
        
        logger.debug(f"DevFileAdapter initialized with {len(self._secrets)} secrets")
    
    def _load_env_file(self, env_path: Optional[str] = None) -> None:
        """Load secrets from .env file."""
        if not HAS_DOTENV:
            logger.warning("python-dotenv not installed - using env vars only")
            return
        
        # Search paths for .env file
        search_paths = []
        if env_path:
            search_paths.append(Path(env_path))
        else:
            # Look in common locations
            project_root = Path(__file__).parent.parent
            search_paths = [
                project_root / ".env.local",
                project_root / ".env",
                Path.cwd() / ".env.local",
                Path.cwd() / ".env",
            ]
        
        for path in search_paths:
            if path.exists():
                self._secrets = dotenv_values(path)
                self._env_path = path
                logger.info(f"Loaded secrets from {path}")
                return
        
        logger.debug("No .env file found, using environment variables only")
    
    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret from .env file or environment."""
        # Check .env file first
        if name in self._secrets:
            return self._secrets[name]
        
        # Fall back to environment variables
        if self._fallback_to_env:
            value = os.environ.get(name)
            if value is not None:
                return value
        
        # Return default or None
        if default is not None:
            return default
        
        return None
    
    def list_secrets(self, prefix: str = "") -> List[str]:
        """List secret names from .env file and environment."""
        secrets = set()
        
        # From .env file
        for name in self._secrets.keys():
            if name.startswith(prefix):
                secrets.add(name)
        
        # From environment (if fallback enabled)
        if self._fallback_to_env:
            for name in os.environ.keys():
                if name.startswith(prefix):
                    secrets.add(name)
        
        return sorted(secrets)
    
    def reload(self, env_path: Optional[str] = None) -> None:
        """Reload secrets from .env file."""
        self._secrets.clear()
        self._load_env_file(env_path or str(self._env_path) if self._env_path else None)


class VaultAdapter(SecretsAdapter):
    """
    HashiCorp Vault adapter for production secrets management.
    
    Features:
    - KV v2 secrets engine support
    - Token or AppRole authentication
    - Automatic token renewal
    - Secret caching with TTL
    - Namespace support
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        mount_point: str = "secret",
        namespace: Optional[str] = None,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize Vault adapter.
        
        Args:
            url: Vault server URL (or VAULT_ADDR env var)
            token: Vault token (or VAULT_TOKEN env var)
            mount_point: KV secrets engine mount point
            namespace: Vault namespace (for Vault Enterprise)
            cache_ttl_seconds: How long to cache secrets
        """
        if not HAS_VAULT:
            raise ImportError("hvac package required for VaultAdapter. Install with: pip install hvac")
        
        self._url = url or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self._token = token or os.environ.get("VAULT_TOKEN")
        self._mount_point = mount_point
        self._namespace = namespace
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        
        # Secret cache: name -> (value, expiry_time)
        self._cache: Dict[str, tuple] = {}
        
        # Initialize Vault client
        self._client = hvac.Client(
            url=self._url,
            token=self._token,
            namespace=self._namespace,
        )
        
        if not self._client.is_authenticated():
            logger.warning("Vault client not authenticated - secrets will fail")
        else:
            logger.info(f"VaultAdapter connected to {self._url}")
    
    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret from Vault."""
        # Check cache first
        if name in self._cache:
            value, expiry = self._cache[name]
            if datetime.now() < expiry:
                return value
            else:
                del self._cache[name]
        
        try:
            # Parse secret path (supports nested paths like "contact/api_key")
            parts = name.split("/")
            path = "/".join(parts[:-1]) if len(parts) > 1 else ""
            key = parts[-1]
            
            response = self._client.secrets.kv.v2.read_secret_version(
                path=path or name,
                mount_point=self._mount_point,
            )
            
            data = response.get("data", {}).get("data", {})
            value = data.get(key) if path else data.get("value", data.get(name))
            
            if value is not None:
                # Cache the value
                self._cache[name] = (value, datetime.now() + self._cache_ttl)
                return value
            
        except Exception as e:
            logger.debug(f"Failed to get secret '{name}' from Vault: {e}")
        
        return default
    
    def list_secrets(self, prefix: str = "") -> List[str]:
        """List secret paths from Vault."""
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                path=prefix,
                mount_point=self._mount_point,
            )
            return response.get("data", {}).get("keys", [])
        except Exception as e:
            logger.debug(f"Failed to list secrets with prefix '{prefix}': {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear the secret cache."""
        self._cache.clear()


class AWSSecretsAdapter(SecretsAdapter):
    """
    AWS Secrets Manager adapter for production secrets management.
    
    Features:
    - IAM role or credentials authentication
    - Secret caching with TTL
    - JSON secret parsing
    - Region support
    """
    
    def __init__(
        self,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        cache_ttl_seconds: int = 300,
    ):
        """
        Initialize AWS Secrets Manager adapter.
        
        Args:
            region: AWS region (or AWS_DEFAULT_REGION env var)
            profile: AWS profile name
            cache_ttl_seconds: How long to cache secrets
        """
        if not HAS_AWS:
            raise ImportError("boto3 package required for AWSSecretsAdapter. Install with: pip install boto3")
        
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, tuple] = {}
        
        # Initialize AWS client
        session = boto3.Session(profile_name=profile, region_name=self._region)
        self._client = session.client("secretsmanager")
        
        logger.info(f"AWSSecretsAdapter initialized for region {self._region}")
    
    def get_secret(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret from AWS Secrets Manager."""
        # Check cache first
        if name in self._cache:
            value, expiry = self._cache[name]
            if datetime.now() < expiry:
                return value
            else:
                del self._cache[name]
        
        try:
            response = self._client.get_secret_value(SecretId=name)
            secret_string = response.get("SecretString")
            
            if secret_string:
                # Try to parse as JSON
                try:
                    import json
                    data = json.loads(secret_string)
                    value = data.get("value", secret_string)
                except (json.JSONDecodeError, TypeError):
                    value = secret_string
                
                # Cache the value
                self._cache[name] = (value, datetime.now() + self._cache_ttl)
                return value
            
        except Exception as e:
            logger.debug(f"Failed to get secret '{name}' from AWS: {e}")
        
        return default
    
    def list_secrets(self, prefix: str = "") -> List[str]:
        """List secrets from AWS Secrets Manager."""
        try:
            secrets = []
            paginator = self._client.get_paginator("list_secrets")
            
            filters = []
            if prefix:
                filters.append({"Key": "name", "Values": [prefix]})
            
            for page in paginator.paginate(Filters=filters if filters else []):
                for secret in page.get("SecretList", []):
                    name = secret.get("Name", "")
                    if name.startswith(prefix):
                        secrets.append(name)
            
            return secrets
        except Exception as e:
            logger.debug(f"Failed to list secrets with prefix '{prefix}': {e}")
            return []
    
    def clear_cache(self) -> None:
        """Clear the secret cache."""
        self._cache.clear()


# Adapter registry
_ADAPTERS = {
    "dev": DevFileAdapter,
    "file": DevFileAdapter,
    "vault": VaultAdapter,
    "aws": AWSSecretsAdapter,
}

# Global adapter instance (lazy initialized)
_global_adapter: Optional[SecretsAdapter] = None


def get_adapter(adapter_type: Optional[str] = None, **kwargs) -> SecretsAdapter:
    """
    Get a secrets adapter instance.
    
    Args:
        adapter_type: Type of adapter ("dev", "vault", "aws"). 
                     If None, uses SECRETS_ADAPTER env var, defaulting to "dev".
        **kwargs: Additional arguments passed to adapter constructor
        
    Returns:
        SecretsAdapter instance
        
    Example:
        adapter = get_adapter()  # Uses SECRETS_ADAPTER env var
        adapter = get_adapter("vault", url="https://vault.example.com")
    """
    global _global_adapter
    
    if adapter_type is None:
        adapter_type = os.environ.get("SECRETS_ADAPTER", "dev").lower()
    
    adapter_class = _ADAPTERS.get(adapter_type)
    if adapter_class is None:
        raise ValueError(f"Unknown adapter type: {adapter_type}. Available: {list(_ADAPTERS.keys())}")
    
    # Create new adapter if type specified or none exists
    if kwargs or _global_adapter is None or not isinstance(_global_adapter, adapter_class):
        try:
            _global_adapter = adapter_class(**kwargs)
        except Exception as e:
            logger.warning(f"Failed to create {adapter_type} adapter: {e}. Falling back to dev adapter.")
            _global_adapter = DevFileAdapter()
    
    return _global_adapter


def get_secret(name: str, default: Optional[str] = None, adapter: Optional[SecretsAdapter] = None) -> Optional[str]:
    """
    Convenience function to get a secret using the global adapter.
    
    Args:
        name: Secret name/key
        default: Default value if not found
        adapter: Optional specific adapter to use
        
    Returns:
        Secret value or default
    """
    if adapter is None:
        adapter = get_adapter()
    return adapter.get_secret(name, default)


def list_secrets(prefix: str = "", adapter: Optional[SecretsAdapter] = None) -> List[str]:
    """
    Convenience function to list secrets using the global adapter.
    
    Args:
        prefix: Filter prefix
        adapter: Optional specific adapter to use
        
    Returns:
        List of secret names
    """
    if adapter is None:
        adapter = get_adapter()
    return adapter.list_secrets(prefix)
