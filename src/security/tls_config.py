"""
SSL/TLS Configuration for AstraGuard

Provides TLS 1.3 configuration and certificate management.
"""

import ssl
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TLSConfig:
    """
    TLS configuration manager.
    
    Features:
    - TLS 1.3 enforcement
    - Strong cipher suites
    - Certificate validation
    """
    
    def __init__(self):
        """Initialize TLS config."""
        self.min_version = ssl.TLSVersion.TLSv1_3
        self.ciphers = ":".join([
            "ECDHE+AESGCM",
            "ECDHE+CHACHA20",
            "DHE+AESGCM",
            "DHE+CHACHA20",
            "!aNULL",
            "!eNULL",
            "!EXPORT",
            "!DES",
            "!MD5",
            "!PSK",
            "!RC4"
        ])
        
        logger.info("TLS config initialized with TLS 1.3")
    
    def create_ssl_context(
        self,
        certfile: Optional[str] = None,
        keyfile: Optional[str] = None
    ) -> ssl.SSLContext:
        """
        Create SSL context with secure settings.
        
        Args:
            certfile: Path to certificate file
            keyfile: Path to private key file
            
        Returns:
            Configured SSL context
        """
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        
        # Enforce TLS 1.3
        context.minimum_version = self.min_version
        
        # Set cipher suites
        context.set_ciphers(self.ciphers)
        
        # Load certificate if provided
        if certfile and keyfile:
            context.load_cert_chain(certfile, keyfile)
        
        logger.info("SSL context created with TLS 1.3")
        return context


# Global instance
_tls_config: Optional[TLSConfig] = None


def get_tls_config() -> TLSConfig:
    """Get global TLS config."""
    global _tls_config
    if _tls_config is None:
        _tls_config = TLSConfig()
    return _tls_config
