"""
Centralized Secrets Management Module

Provides unified, secure secret access across the application with:
- Environment variable loading
- .env file support
- Startup validation
- Log masking for sensitive values
"""

import os
import re
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

# Try to import dotenv for .env file support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


logger = logging.getLogger(__name__)


class SecretManager:
    """
    Centralized secret management with validation and masking.
    
    Usage:
        from core.secrets import secrets_manager, get_secret, require_secrets
        
        # Validate required secrets at startup
        require_secrets(["API_KEY", "JWT_SECRET"])
        
        # Get a secret
        api_key = get_secret("API_KEY")
    """
    
    _instance: Optional["SecretManager"] = None
    _initialized: bool = False
    
    # Patterns that indicate a secret (for auto-masking in logs)
    SECRET_PATTERNS = [
        r".*password.*",
        r".*secret.*",
        r".*key.*",
        r".*token.*",
        r".*credential.*",
        r".*auth.*",
    ]
    
    def __new__(cls) -> "SecretManager":
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the secret manager."""
        if SecretManager._initialized:
            return
        
        self._secrets_cache: Dict[str, str] = {}
        self._loaded_from_file = False
        self._env_file_path: Optional[Path] = None
        
        # Auto-load .env file if available
        self._load_env_file()
        
        SecretManager._initialized = True
    
    def _load_env_file(self, env_path: Optional[str] = None) -> bool:
        """
        Load secrets from .env file.
        
        Args:
            env_path: Optional path to .env file. If None, searches for:
                      .env.local, .env, in project root
        
        Returns:
            True if .env file was loaded, False otherwise
        """
        if not DOTENV_AVAILABLE:
            logger.debug("python-dotenv not installed, skipping .env file loading")
            return False
        
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
            ]
        
        for path in search_paths:
            if path.exists():
                load_dotenv(path, override=False)
                self._loaded_from_file = True
                self._env_file_path = path
                logger.info(f"Loaded secrets from {path}")
                return True
        
        return False
    
    def get(
        self,
        name: str,
        default: Optional[str] = None,
        required: bool = False
    ) -> Optional[str]:
        """
        Get a secret value.
        
        Args:
            name: Name of the secret (environment variable name)
            default: Default value if secret is not set
            required: If True, raises ValueError when secret is missing
        
        Returns:
            The secret value, or default if not found
        
        Raises:
            ValueError: If required=True and secret is not found
        """
        # Check cache first
        if name in self._secrets_cache:
            return self._secrets_cache[name]
        
        # Get from environment
        value = os.environ.get(name)
        
        if value is None:
            if required:
                raise ValueError(
                    f"Required secret '{name}' is not set. "
                    f"Set it via environment variable or .env file."
                )
            return default
        
        # Cache the value
        self._secrets_cache[name] = value
        return value
    
    def require(self, names: List[str]) -> Dict[str, str]:
        """
        Validate that all required secrets exist.
        
        Args:
            names: List of secret names to validate
        
        Returns:
            Dictionary of secret name -> value
        
        Raises:
            ValueError: If any required secret is missing
        """
        missing = []
        secrets = {}
        
        for name in names:
            value = os.environ.get(name)
            if value is None:
                missing.append(name)
            else:
                secrets[name] = value
        
        if missing:
            raise ValueError(
                f"Missing required secrets: {', '.join(missing)}. "
                f"Set them via environment variables or .env file."
            )
        
        return secrets
    
    def is_secret_name(self, name: str) -> bool:
        """
        Check if a name looks like it contains sensitive data.
        
        Args:
            name: The name to check
        
        Returns:
            True if the name matches secret patterns
        """
        name_lower = name.lower()
        for pattern in self.SECRET_PATTERNS:
            if re.match(pattern, name_lower):
                return True
        return False
    
    def mask(self, value: str, visible_chars: int = 4) -> str:
        """
        Mask a secret value for safe logging.
        
        Args:
            value: The secret value to mask
            visible_chars: Number of characters to show at the end
        
        Returns:
            Masked string like "****abcd"
        """
        if not value:
            return ""
        
        if len(value) <= visible_chars:
            return "*" * len(value)
        
        masked_length = len(value) - visible_chars
        return "*" * masked_length + value[-visible_chars:]
    
    def get_masked(self, name: str, default: Optional[str] = None) -> str:
        """
        Get a secret value in masked form (safe for logging).
        
        Args:
            name: Name of the secret
            default: Default value if not found
        
        Returns:
            Masked secret value
        """
        value = self.get(name, default)
        if value is None:
            return "<not set>"
        return self.mask(value)
    
    def clear_cache(self) -> None:
        """Clear the secrets cache (useful for testing or secret rotation)."""
        self._secrets_cache.clear()
    
    def reload(self, env_path: Optional[str] = None) -> bool:
        """
        Reload secrets from .env file (supports secret rotation).
        
        Args:
            env_path: Optional path to .env file
        
        Returns:
            True if reload was successful
        """
        self.clear_cache()
        return self._load_env_file(env_path)


# Global singleton instance
secrets_manager = SecretManager()


# Convenience functions
def get_secret(
    name: str,
    default: Optional[str] = None,
    required: bool = False
) -> Optional[str]:
    """
    Get a secret value from environment.
    
    Args:
        name: Name of the secret (environment variable name)
        default: Default value if secret is not set
        required: If True, raises ValueError when secret is missing
    
    Returns:
        The secret value, or default if not found
    
    Raises:
        ValueError: If required=True and secret is not found
    
    Example:
        api_key = get_secret("API_KEY", required=True)
        optional_key = get_secret("OPTIONAL_KEY", default="fallback")
    """
    return secrets_manager.get(name, default, required)


def require_secrets(names: List[str]) -> Dict[str, str]:
    """
    Validate that all required secrets exist at startup.
    
    Args:
        names: List of secret names to validate
    
    Returns:
        Dictionary of secret name -> value
    
    Raises:
        ValueError: If any required secret is missing
    
    Example:
        # At application startup
        require_secrets(["API_KEY", "JWT_SECRET", "DATABASE_URL"])
    """
    return secrets_manager.require(names)


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Mask a secret value for safe logging.
    
    Args:
        value: The secret value to mask
        visible_chars: Number of characters to show at end (default: 4)
    
    Returns:
        Masked string like "****abcd"
    
    Example:
        logger.info(f"Using API key: {mask_secret(api_key)}")
        # Output: "Using API key: ****xyz1"
    """
    return secrets_manager.mask(value, visible_chars)


import os
import json
import base64
import hashlib
import logging
from typing import Dict, Optional, Any, List, Union
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Optional external integrations
try:
    import hvac
    HAS_VAULT = True
except ImportError:
    HAS_VAULT = False

try:
    import boto3
    HAS_AWS = True
except ImportError:
    HAS_AWS = False

logger = logging.getLogger(__name__)

@dataclass
class SecretMetadata:
    """Metadata for a stored secret."""
    key: str
    version: int
    created_at: datetime
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    description: Optional[str] = None

@dataclass
class SecretValue:
    """Represents a secret with its metadata."""
    value: str
    metadata: SecretMetadata

class SecretsManager:
    """
    Comprehensive secrets management with encryption, rotation, and external integration.
    """

    def __init__(
        self,
        storage_path: str = ".secrets",
        master_key: Optional[str] = None,
        vault_url: Optional[str] = None,
        vault_token: Optional[str] = None,
        aws_region: Optional[str] = None,
        aws_profile: Optional[str] = None
    ):
        """
        Initialize the secrets manager.

        Args:
            storage_path: Path for local encrypted storage
            master_key: Master encryption key (env var or provided)
            vault_url: HashiCorp Vault URL for external storage
            vault_token: Vault authentication token
            aws_region: AWS region for Secrets Manager
            aws_profile: AWS profile for authentication
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        # Initialize encryption
        self.master_key = master_key or os.getenv("SECRETS_MASTER_KEY")
        if not self.master_key:
            raise ValueError("Master key must be provided via parameter or SECRETS_MASTER_KEY env var")

        self.fernet = self._derive_fernet_key(self.master_key)

        # External integrations
        self.vault_client = None
        self.aws_client = None

        if vault_url and vault_token and HAS_VAULT:
            self.vault_client = hvac.Client(url=vault_url, token=vault_token)

        if aws_region and HAS_AWS:
            session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
            self.aws_client = session.client('secretsmanager')

        # In-memory cache for performance
        self._cache: Dict[str, SecretValue] = {}
        self._cache_ttl = timedelta(minutes=5)

        logger.info("SecretsManager initialized successfully")

    def _derive_fernet_key(self, master_key: str) -> Fernet:
        """Derive Fernet key from master key using PBKDF2."""
        salt = b'astraguard_secrets_salt'  # Fixed salt for consistency
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        return Fernet(key)

    def _get_secret_path(self, key: str, version: int = None) -> Path:
        """Get filesystem path for a secret."""
        if version is None:
            # Get latest version
            versions = [f for f in self.storage_path.glob(f"{key}.v*.enc")]
            if not versions:
                raise KeyError(f"Secret '{key}' not found")
            version = max(int(f.stem.split('.v')[1]) for f in versions)

        return self.storage_path / f"{key}.v{version}.enc"

    def _encrypt_data(self, data: Dict[str, Any]) -> bytes:
        """Encrypt data dictionary."""
        json_data = json.dumps(data, default=str)
        return self.fernet.encrypt(json_data.encode())

    def _decrypt_data(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Decrypt data dictionary."""
        try:
            json_data = self.fernet.decrypt(encrypted_data).decode()
            return json.loads(json_data)
        except InvalidToken:
            raise ValueError("Invalid encryption key or corrupted data")

    def store_secret(
        self,
        key: str,
        value: str,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        use_external: bool = False
    ) -> SecretMetadata:
        """
        Store a secret securely.

        Args:
            key: Secret identifier
            value: Secret value
            description: Optional description
            expires_in_days: Days until expiration
            use_external: Store in external manager instead of local

        Returns:
            SecretMetadata for the stored secret
        """
        if use_external:
            return self._store_external(key, value, description, expires_in_days)

        # Get next version
        try:
            current_version = self.get_secret_metadata(key).version
            version = current_version + 1
        except KeyError:
            version = 1

        metadata = SecretMetadata(
            key=key,
            version=version,
            created_at=datetime.now(),
            description=description,
            expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None
        )

        secret_data = {
            'value': value,
            'metadata': asdict(metadata)
        }

        encrypted_data = self._encrypt_data(secret_data)
        secret_path = self._get_secret_path(key, version)

        with open(secret_path, 'wb') as f:
            f.write(encrypted_data)

        # Update cache
        self._cache[key] = SecretValue(value, metadata)

        logger.info(f"Stored secret '{key}' version {version}")
        return metadata

    def get_secret(self, key: str, version: Optional[int] = None) -> str:
        """
        Retrieve a secret value.

        Args:
            key: Secret identifier
            version: Specific version (latest if None)

        Returns:
            Decrypted secret value
        """
        # Check cache first
        if key in self._cache:
            cached = self._cache[key]
            if datetime.now() - cached.metadata.created_at < self._cache_ttl:
                return cached.value

        # Try external first
        try:
            return self._get_external(key, version)
        except (KeyError, NotImplementedError):
            pass

        # Get from local storage
        secret_path = self._get_secret_path(key, version)
        if not secret_path.exists():
            raise KeyError(f"Secret '{key}' not found")

        with open(secret_path, 'rb') as f:
            encrypted_data = f.read()

        secret_data = self._decrypt_data(encrypted_data)
        metadata_dict = secret_data['metadata']
        metadata = SecretMetadata(**metadata_dict)

        # Check expiration
        if metadata.expires_at and datetime.now() > metadata.expires_at:
            raise ValueError(f"Secret '{key}' has expired")

        value = secret_data['value']

        # Update cache
        self._cache[key] = SecretValue(value, metadata)

        return value

    def rotate_secret(self, key: str, new_value: Optional[str] = None) -> SecretMetadata:
        """
        Rotate a secret with a new value or generate one.

        Args:
            key: Secret to rotate
            new_value: New value (generate if None)

        Returns:
            New secret metadata
        """
        if new_value is None:
            # Generate a secure random value
            import secrets
            new_value = secrets.token_urlsafe(32)

        # Store new version
        metadata = self.store_secret(key, new_value, description=f"Rotated at {datetime.now()}")

        # Mark old versions as rotated
        old_metadata = self.get_secret_metadata(key, metadata.version - 1)
        old_metadata.rotated_at = datetime.now()

        # Update old metadata file
        old_path = self._get_secret_path(key, old_metadata.version)
        with open(old_path, 'rb') as f:
            encrypted_data = f.read()

        old_data = self._decrypt_data(encrypted_data)
        old_data['metadata'] = asdict(old_metadata)

        with open(old_path, 'wb') as f:
            f.write(self._encrypt_data(old_data))

        logger.info(f"Rotated secret '{key}' to version {metadata.version}")
        return metadata

    def get_secret_metadata(self, key: str, version: Optional[int] = None) -> SecretMetadata:
        """Get metadata for a secret."""
        secret_path = self._get_secret_path(key, version)
        with open(secret_path, 'rb') as f:
            encrypted_data = f.read()

        secret_data = self._decrypt_data(encrypted_data)
        metadata_dict = secret_data['metadata']
        return SecretMetadata(**metadata_dict)

    def list_secrets(self) -> List[SecretMetadata]:
        """List all stored secrets."""
        secrets = []
        for file_path in self.storage_path.glob("*.enc"):
            try:
                key_version = file_path.stem
                key, version_str = key_version.rsplit('.v', 1)
                version = int(version_str)

                # Only include latest version
                if version == self.get_secret_metadata(key).version:
                    secrets.append(self.get_secret_metadata(key))
            except Exception as e:
                logger.warning(f"Failed to read secret metadata from {file_path}: {e}")

        return secrets

    def delete_secret(self, key: str, version: Optional[int] = None) -> None:
        """Delete a secret or specific version."""
        if version is None:
            # Delete all versions
            for file_path in self.storage_path.glob(f"{key}.v*.enc"):
                file_path.unlink()
        else:
            secret_path = self._get_secret_path(key, version)
            secret_path.unlink()

        # Clear cache
        if key in self._cache:
            del self._cache[key]

        logger.info(f"Deleted secret '{key}'")

    def health_check(self) -> Dict[str, Any]:
        """Perform health checks on secret accessibility."""
        results = {
            'local_storage': False,
            'encryption': False,
            'vault': False,
            'aws_secrets_manager': False,
            'total_secrets': 0
        }

        # Check local storage
        try:
            test_key = f"health_check_{datetime.now().timestamp()}"
            self.store_secret(test_key, "test_value")
            retrieved = self.get_secret(test_key)
            assert retrieved == "test_value"
            self.delete_secret(test_key)
            results['local_storage'] = True
            results['encryption'] = True
        except Exception as e:
            logger.error(f"Local storage health check failed: {e}")

        # Count secrets
        try:
            results['total_secrets'] = len(self.list_secrets())
        except Exception as e:
            logger.error(f"Failed to count secrets: {e}")

        # Check external integrations
        if self.vault_client:
            try:
                results['vault'] = self.vault_client.is_authenticated()
            except Exception as e:
                logger.error(f"Vault health check failed: {e}")

        if self.aws_client:
            try:
                self.aws_client.list_secrets(MaxResults=1)
                results['aws_secrets_manager'] = True
            except Exception as e:
                logger.error(f"AWS Secrets Manager health check failed: {e}")

        return results

    # External integration methods
    def _store_external(self, key: str, value: str, description: str = None, expires_in_days: int = None) -> SecretMetadata:
        """Store secret in external manager."""
        if self.vault_client and self.vault_client.is_authenticated():
            # Store in Vault
            data = {'value': value}
            if description:
                data['description'] = description
            if expires_in_days:
                data['expires_at'] = (datetime.now() + timedelta(days=expires_in_days)).isoformat()

            self.vault_client.secrets.kv.v2.create_or_update_secret_version(
                path=key,
                secret=data
            )
            return SecretMetadata(
                key=key,
                version=1,  # Vault handles versioning
                created_at=datetime.now(),
                description=description,
                expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None
            )

        elif self.aws_client:
            # Store in AWS Secrets Manager
            secret_string = json.dumps({'value': value})
            kwargs = {
                'Name': key,
                'SecretString': secret_string,
                'Description': description or f"Secret for {key}"
            }
            if expires_in_days:
                kwargs['Tags'] = [{'Key': 'ExpiresInDays', 'Value': str(expires_in_days)}]

            response = self.aws_client.create_secret(**kwargs)
            return SecretMetadata(
                key=key,
                version=1,
                created_at=datetime.now(),
                description=description,
                expires_at=datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None
            )

        else:
            raise NotImplementedError("No external secret manager configured")

    def _get_external(self, key: str, version: Optional[int] = None) -> str:
        """Retrieve secret from external manager."""
        if self.vault_client and self.vault_client.is_authenticated():
            try:
                response = self.vault_client.secrets.kv.v2.read_secret_version(path=key, version=version or 'latest')
                return response['data']['data']['value']
            except Exception:
                raise KeyError(f"Secret '{key}' not found in Vault")

        elif self.aws_client:
            try:
                response = self.aws_client.get_secret_value(SecretId=key)
                secret_data = json.loads(response['SecretString'])
                return secret_data['value']
            except Exception:
                raise KeyError(f"Secret '{key}' not found in AWS Secrets Manager")

        else:
            raise NotImplementedError("No external secret manager configured")

# Global instance for easy access
_secrets_manager: Optional[SecretsManager] = None

def init_secrets_manager(**kwargs) -> SecretsManager:
    """Initialize the global secrets manager."""
    global _secrets_manager
    _secrets_manager = SecretsManager(**kwargs)
    return _secrets_manager

def get_secrets_manager() -> SecretsManager:
    """Get the global secrets manager instance."""
    if _secrets_manager is None:
        raise RuntimeError("Secrets manager not initialized. Call init_secrets_manager() first.")
    return _secrets_manager

# Convenience functions
def store_secret(key: str, value: str, **kwargs) -> SecretMetadata:
    """Store a secret using the global manager."""
    return get_secrets_manager().store_secret(key, value, **kwargs)

def get_secret_v2(key: str, default: Optional[str] = None, **kwargs) -> Optional[str]:
    """Get a secret using the global SecretsManager. Returns default if secret not found."""
    try:
        return get_secrets_manager().get_secret(key, **kwargs)
    except (KeyError, RuntimeError):
        return default

def rotate_secret(key: str, **kwargs) -> SecretMetadata:
    """Rotate a secret using the global manager."""
    return get_secrets_manager().rotate_secret(key, **kwargs)

def list_secrets() -> List[SecretMetadata]:
    """List secrets using the global manager."""
    return get_secrets_manager().list_secrets()

def health_check() -> Dict[str, Any]:
    """Perform health check using the global manager."""
    return get_secrets_manager().health_check()
