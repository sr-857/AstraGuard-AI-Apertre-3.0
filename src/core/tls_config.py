"""
TLS Configuration Management Module

Provides centralized TLS/SSL configuration for all internal service communication.
Supports mutual TLS (mTLS), certificate validation, and TLS version enforcement.
"""

import os
import ssl
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path
import certifi

logger = logging.getLogger(__name__)


@dataclass
class TLSConfig:
    """
    TLS configuration for secure internal service communication.
    
    Attributes:
        enabled: Whether TLS is enabled for internal communication
        enforce_tls: If True, reject non-TLS connections
        cert_file: Path to TLS certificate file
        key_file: Path to TLS private key file
        ca_file: Path to CA bundle for certificate validation
        verify_mode: SSL verification mode (CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED)
        min_tls_version: Minimum TLS version (TLSv1_2 or TLSv1_3)
        mutual_tls: Whether to require client certificates (mTLS)
        cipher_suites: Optional list of allowed cipher suites
    """
    enabled: bool = True
    enforce_tls: bool = True
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED
    min_tls_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    mutual_tls: bool = False
    cipher_suites: Optional[str] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.enabled and self.enforce_tls:
            if not self.cert_file or not os.path.exists(self.cert_file):
                logger.warning(f"TLS certificate file not found: {self.cert_file}")
            if not self.key_file or not os.path.exists(self.key_file):
                logger.warning(f"TLS key file not found: {self.key_file}")
    
    def create_ssl_context(self, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH) -> ssl.SSLContext:
        """
        Create and configure an SSL context based on this configuration.
        
        Args:
            purpose: SSL purpose (SERVER_AUTH for clients, CLIENT_AUTH for servers)
            
        Returns:
            Configured SSLContext instance
            
        Raises:
            ValueError: If TLS is not properly configured
        """
        if not self.enabled:
            raise ValueError("TLS is not enabled")
        
        # Create SSL context with minimum TLS version
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT if purpose == ssl.Purpose.SERVER_AUTH else ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = self.min_tls_version
        
        # Configure certificate validation
        context.verify_mode = self.verify_mode
        
        # Load CA certificates
        if self.ca_file and os.path.exists(self.ca_file):
            context.load_verify_locations(self.ca_file)
            logger.debug(f"Loaded CA certificates from {self.ca_file}")
        else:
            # Use system default CA bundle
            context.load_verify_locations(certifi.where())
            logger.debug("Using system default CA bundle")
        
        # Load client certificate for mTLS
        if self.cert_file and self.key_file:
            if os.path.exists(self.cert_file) and os.path.exists(self.key_file):
                context.load_cert_chain(self.cert_file, self.key_file)
                logger.debug(f"Loaded client certificate from {self.cert_file}")
            else:
                logger.warning("Certificate or key file not found, mTLS not available")
        
        # Configure cipher suites if specified
        if self.cipher_suites:
            context.set_ciphers(self.cipher_suites)
        
        return context
    
    def is_configured(self) -> bool:
        """Check if TLS is properly configured with valid certificates."""
        if not self.enabled:
            return False
        
        if self.enforce_tls:
            # For enforced TLS, we need valid certificates
            if not self.cert_file or not os.path.exists(self.cert_file):
                return False
            if not self.key_file or not os.path.exists(self.key_file):
                return False
        
        return True


class TLSConfigManager:
    """
    Manages TLS configurations for different services and environments.
    
    Provides centralized configuration loading from environment variables
    and configuration files.
    """
    
    def __init__(self):
        self._configs: Dict[str, TLSConfig] = {}
        self._default_config: Optional[TLSConfig] = None
    
    def load_from_environment(self, prefix: str = "TLS_") -> TLSConfig:
        """
        Load TLS configuration from environment variables.
        
        Environment variables:
            {prefix}ENABLED: Enable TLS (default: true)
            {prefix}ENFORCE: Enforce TLS only (default: true)
            {prefix}CERT_FILE: Path to certificate file
            {prefix}KEY_FILE: Path to private key file
            {prefix}CA_FILE: Path to CA bundle file
            {prefix}VERIFY_MODE: Verification mode (none, optional, required)
            {prefix}MIN_VERSION: Minimum TLS version (1.2, 1.3)
            {prefix}MUTUAL_TLS: Enable mutual TLS (default: false)
            {prefix}CIPHER_SUITES: Allowed cipher suites
        
        Args:
            prefix: Prefix for environment variable names
            
        Returns:
            TLSConfig instance
        """
        # Parse boolean values
        def get_bool(key: str, default: bool = False) -> bool:
            value = os.getenv(f"{prefix}{key}", str(default).lower())
            return value.lower() in ('true', '1', 'yes', 'on')
        
        # Parse verification mode
        verify_mode_str = os.getenv(f"{prefix}VERIFY_MODE", "required").lower()
        verify_modes = {
            "none": ssl.CERT_NONE,
            "optional": ssl.CERT_OPTIONAL,
            "required": ssl.CERT_REQUIRED,
        }
        verify_mode = verify_modes.get(verify_mode_str, ssl.CERT_REQUIRED)
        
        # Parse TLS version
        min_version_str = os.getenv(f"{prefix}MIN_VERSION", "1.2")
        min_version = ssl.TLSVersion.TLSv1_2
        if min_version_str == "1.3":
            min_version = ssl.TLSVersion.TLSv1_3
        
        config = TLSConfig(
            enabled=get_bool("ENABLED", True),
            enforce_tls=get_bool("ENFORCE", True),
            cert_file=os.getenv(f"{prefix}CERT_FILE"),
            key_file=os.getenv(f"{prefix}KEY_FILE"),
            ca_file=os.getenv(f"{prefix}CA_FILE"),
            verify_mode=verify_mode,
            min_tls_version=min_version,
            mutual_tls=get_bool("MUTUAL_TLS", False),
            cipher_suites=os.getenv(f"{prefix}CIPHER_SUITES"),
        )
        
        logger.info(f"Loaded TLS configuration from environment with prefix {prefix}")
        return config
    
    def set_default_config(self, config: TLSConfig) -> None:
        """Set the default TLS configuration."""
        self._default_config = config
        logger.info("Default TLS configuration set")
    
    def get_default_config(self) -> TLSConfig:
        """Get the default TLS configuration."""
        if self._default_config is None:
            # Load from environment if not set
            self._default_config = self.load_from_environment()
        return self._default_config
    
    def register_service_config(self, service_name: str, config: TLSConfig) -> None:
        """
        Register a service-specific TLS configuration.
        
        Args:
            service_name: Name of the service
            config: TLS configuration for the service
        """
        self._configs[service_name] = config
        logger.info(f"Registered TLS configuration for service: {service_name}")
    
    def get_service_config(self, service_name: str) -> TLSConfig:
        """
        Get TLS configuration for a specific service.
        
        Falls back to default configuration if service-specific config not found.
        
        Args:
            service_name: Name of the service
            
        Returns:
            TLSConfig instance
        """
        if service_name in self._configs:
            return self._configs[service_name]
        
        logger.debug(f"Using default TLS config for service: {service_name}")
        return self.get_default_config()
    
    def is_tls_required(self, service_name: Optional[str] = None) -> bool:
        """
        Check if TLS is required for a service.
        
        Args:
            service_name: Optional service name to check
            
        Returns:
            True if TLS is enabled and enforced
        """
        config = self.get_service_config(service_name) if service_name else self.get_default_config()
        return config.enabled and config.enforce_tls


# Global TLS configuration manager instance
_tls_config_manager: Optional[TLSConfigManager] = None


def get_tls_config_manager() -> TLSConfigManager:
    """
    Get the global TLS configuration manager instance.
    
    Returns:
        TLSConfigManager singleton instance
    """
    global _tls_config_manager
    if _tls_config_manager is None:
        _tls_config_manager = TLSConfigManager()
    return _tls_config_manager


def get_tls_config(service_name: Optional[str] = None) -> TLSConfig:
    """
    Convenience function to get TLS configuration.
    
    Args:
        service_name: Optional service name for service-specific config
        
    Returns:
        TLSConfig instance
    """
    return get_tls_config_manager().get_service_config(service_name)


def is_tls_required(service_name: Optional[str] = None) -> bool:
    """
    Convenience function to check if TLS is required.
    
    Args:
        service_name: Optional service name to check
        
    Returns:
        True if TLS is required
    """
    return get_tls_config_manager().is_tls_required(service_name)


def create_ssl_context(
    service_name: Optional[str] = None,
    purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH
) -> ssl.SSLContext:
    """
    Convenience function to create SSL context.
    
    Args:
        service_name: Optional service name for service-specific config
        purpose: SSL purpose
        
    Returns:
        Configured SSLContext
    """
    config = get_tls_config(service_name)
    return config.create_ssl_context(purpose)
