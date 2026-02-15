"""
Secret Rotation System for AstraGuard

Implements automated secret rotation with grace periods and versioning.
Supports multiple secret types and integrates with secret managers.
"""

import logging
import secrets
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """Types of secrets"""
    API_KEY = "api_key"
    DATABASE_PASSWORD = "database_password"
    ENCRYPTION_KEY = "encryption_key"
    JWT_SECRET = "jwt_secret"
    OAUTH_CLIENT_SECRET = "oauth_client_secret"


@dataclass
class SecretVersion:
    """A version of a secret"""
    version_id: str
    value: str
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }


class SecretRotation:
    """
    Automated secret rotation with versioning.
    
    Features:
    - Automatic secret generation
    - Version management with grace periods
    - Multiple active versions during rotation
    - Configurable rotation schedules
    """
    
    def __init__(
        self,
        grace_period_hours: int = 24,
        rotation_interval_days: int = 90
    ):
        """
        Initialize secret rotation.
        
        Args:
            grace_period_hours: Hours to keep old secret active
            rotation_interval_days: Days between rotations
        """
        self.grace_period = timedelta(hours=grace_period_hours)
        self.rotation_interval = timedelta(days=rotation_interval_days)
        
        self._secrets: Dict[str, List[SecretVersion]] = {}
        self._lock = threading.Lock()
        
        logger.info(
            f"Secret rotation initialized: grace={grace_period_hours}h, "
            f"interval={rotation_interval_days}d"
        )
    
    def generate_secret(self, secret_type: SecretType, length: int = 32) -> str:
        """
        Generate a new secret value.
        
        Args:
            secret_type: Type of secret
            length: Length of secret
            
        Returns:
            Generated secret
        """
        if secret_type == SecretType.API_KEY:
            # API key format: prefix + random
            return f"sk_live_{secrets.token_urlsafe(length)}"
        elif secret_type == SecretType.JWT_SECRET:
            # JWT secret: strong random string
            return secrets.token_urlsafe(length)
        elif secret_type == SecretType.ENCRYPTION_KEY:
            # Encryption key: 32 bytes for AES-256
            return secrets.token_urlsafe(32)
        else:
            # Default: URL-safe random string
            return secrets.token_urlsafe(length)
    
    def rotate_secret(
        self,
        secret_name: str,
        secret_type: SecretType,
        custom_value: Optional[str] = None
    ) -> str:
        """
        Rotate a secret to a new version.
        
        Args:
            secret_name: Name of the secret
            secret_type: Type of secret
            custom_value: Optional custom value (otherwise generated)
            
        Returns:
            New secret version ID
        """
        with self._lock:
            # Generate new secret value
            if custom_value:
                new_value = custom_value
            else:
                new_value = self.generate_secret(secret_type)
            
            # Create new version
            version_id = f"v{len(self._secrets.get(secret_name, [])) + 1}"
            new_version = SecretVersion(
                version_id=version_id,
                value=new_value,
                expires_at=datetime.now() + self.rotation_interval
            )
            
            # Add to versions list
            if secret_name not in self._secrets:
                self._secrets[secret_name] = []
            
            self._secrets[secret_name].append(new_version)
            
            # Mark old versions for expiry (with grace period)
            for old_version in self._secrets[secret_name][:-1]:
                if old_version.is_active:
                    old_version.expires_at = datetime.now() + self.grace_period
            
            logger.info(
                f"Secret rotated: {secret_name} -> {version_id}, "
                f"grace period: {self.grace_period}"
            )
            
            return version_id
    
    def get_current_secret(self, secret_name: str) -> Optional[str]:
        """
        Get the current active secret value.
        
        Args:
            secret_name: Name of the secret
            
        Returns:
            Current secret value or None
        """
        with self._lock:
            versions = self._secrets.get(secret_name, [])
            if not versions:
                return None
            
            # Return most recent active version
            for version in reversed(versions):
                if version.is_active:
                    return version.value
            
            return None
    
    def validate_secret(self, secret_name: str, value: str) -> bool:
        """
        Validate if a secret value is currently valid.
        
        Args:
            secret_name: Name of the secret
            value: Secret value to validate
            
        Returns:
            True if valid, False otherwise
        """
        with self._lock:
            versions = self._secrets.get(secret_name, [])
            
            for version in versions:
                if not version.is_active:
                    continue
                
                # Check if expired
                if version.expires_at and datetime.now() > version.expires_at:
                    version.is_active = False
                    continue
                
                # Check if value matches
                if version.value == value:
                    return True
            
            return False
    
    def cleanup_expired_secrets(self) -> int:
        """
        Remove expired secret versions.
        
        Returns:
            Number of versions removed
        """
        removed_count = 0
        
        with self._lock:
            for secret_name in list(self._secrets.keys()):
                versions = self._secrets[secret_name]
                
                # Filter out expired versions
                active_versions = []
                for version in versions:
                    if version.expires_at and datetime.now() > version.expires_at:
                        version.is_active = False
                        removed_count += 1
                        logger.info(f"Expired secret version: {secret_name}/{version.version_id}")
                    else:
                        active_versions.append(version)
                
                self._secrets[secret_name] = active_versions
        
        logger.info(f"Cleaned up {removed_count} expired secret versions")
        return removed_count
    
    def get_secret_info(self, secret_name: str) -> Dict[str, Any]:
        """Get information about a secret's versions."""
        with self._lock:
            versions = self._secrets.get(secret_name, [])
            
            return {
                "secret_name": secret_name,
                "total_versions": len(versions),
                "active_versions": sum(1 for v in versions if v.is_active),
                "versions": [v.to_dict() for v in versions]
            }


# Global singleton
_secret_rotation: Optional[SecretRotation] = None
_rotation_lock = threading.Lock()


def get_secret_rotation() -> SecretRotation:
    """Get global secret rotation singleton."""
    global _secret_rotation
    if _secret_rotation is None:
        with _rotation_lock:
            if _secret_rotation is None:
                _secret_rotation = SecretRotation()
    return _secret_rotation
