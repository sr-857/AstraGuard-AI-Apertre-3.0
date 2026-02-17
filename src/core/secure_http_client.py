"""
Secure HTTP Client Module

Provides HTTPS-enforcing HTTP client wrappers that ensure all internal
service communication happens over encrypted channels with proper
certificate validation.
"""

import re
import ssl
import logging
from typing import Optional, Dict, Any, Union, Callable
from urllib.parse import urlparse
import asyncio

# Import TLS configuration
from core.tls_config import get_tls_config, create_ssl_context, is_tls_required

logger = logging.getLogger(__name__)


class HTTPSTransportError(Exception):
    """Exception raised when HTTP is used instead of HTTPS."""
    pass


class TLSError(Exception):
    """Exception raised for TLS-related errors."""
    pass


class SecureHTTPClient:
    """
    Secure HTTP client that enforces HTTPS for all internal service communication.
    
    This client wrapper ensures:
    - All URLs use HTTPS scheme
    - TLS certificates are properly validated
    - Certificate pinning is supported
    - Non-TLS connections are rejected in production mode
    
    Supports both synchronous and asynchronous HTTP clients.
    """
    
    def __init__(
        self,
        service_name: Optional[str] = None,
        verify_ssl: bool = True,
        cert_file: Optional[str] = None,
        key_file: Optional[str] = None,
        ca_file: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """
        Initialize secure HTTP client.
        
        Args:
            service_name: Service name for service-specific TLS config
            verify_ssl: Whether to verify SSL certificates
            cert_file: Path to client certificate file (for mTLS)
            key_file: Path to client private key file (for mTLS)
            ca_file: Path to CA bundle file
            timeout: Default timeout for requests
            max_retries: Maximum number of retries for failed requests
        """
        self.service_name = service_name
        self.verify_ssl = verify_ssl
        self.cert_file = cert_file
        self.key_file = key_file
        self.ca_file = ca_file
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Get TLS configuration
        self.tls_config = get_tls_config(service_name)
        
        # Check if TLS is required
        self.tls_required = is_tls_required(service_name)
        
        # Initialize HTTP client (lazy initialization)
        self._client = None
        self._async_client = None
        
        logger.info(f"SecureHTTPClient initialized for service: {service_name}")
    
    def _validate_url(self, url: str) -> str:
        """
        Validate that URL uses HTTPS scheme.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated URL
            
        Raises:
            HTTPSTransportError: If URL doesn't use HTTPS and TLS is enforced
        """
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme == "https":
            return url
        
        if parsed.scheme == "http":
            if self.tls_required:
                error_msg = f"HTTP URL rejected - TLS is enforced: {url}"
                logger.error(error_msg)
                raise HTTPSTransportError(error_msg)
            else:
                logger.warning(f"Allowing HTTP URL (TLS not enforced): {url}")
                return url
        
        # No scheme specified - default to HTTPS if TLS is required
        if self.tls_required:
            https_url = f"https://{url}"
            logger.debug(f"Added HTTPS scheme to URL: {https_url}")
            return https_url
        
        return url
    
    def _get_ssl_context(self) -> ssl.SSLContext:
        """
        Get SSL context for secure connections.
        
        Returns:
            Configured SSLContext
        """
        try:
            return create_ssl_context(self.service_name)
        except Exception as e:
            if self.tls_required:
                raise TLSError(f"Failed to create SSL context: {e}")
            logger.warning(f"Using default SSL context: {e}")
            return ssl.create_default_context()
    
    def _get_client_kwargs(self) -> Dict[str, Any]:
        """
        Get keyword arguments for HTTP client initialization.
        
        Returns:
            Dictionary of client configuration
        """
        kwargs = {
            "timeout": self.timeout,
            "verify": self.verify_ssl,
        }
        
        # Add SSL context if TLS is enabled
        if self.tls_config.enabled:
            try:
                kwargs["ssl"] = self._get_ssl_context()
            except Exception as e:
                logger.warning(f"Could not create SSL context: {e}")
        
        return kwargs
    
    def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Any:
        """
        Make a secure HTTP request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            Response object
            
        Raises:
            HTTPSTransportError: If HTTP is used when TLS is enforced
        """
        # Validate URL
        secure_url = self._validate_url(url)
        
        # Import httpx here to avoid dependency issues
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for SecureHTTPClient. Install with: pip install httpx")
        
        # Initialize client if needed
        if self._client is None:
            client_kwargs = self._get_client_kwargs()
            self._client = httpx.Client(**client_kwargs)
        
        # Make request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, secure_url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        raise last_error
    
    async def arequest(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Any:
        """
        Make an async secure HTTP request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            Response object
            
        Raises:
            HTTPSTransportError: If HTTP is used when TLS is enforced
        """
        # Validate URL
        secure_url = self._validate_url(url)
        
        # Import httpx here to avoid dependency issues
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for SecureHTTPClient. Install with: pip install httpx")
        
        # Initialize async client if needed
        if self._async_client is None:
            client_kwargs = self._get_client_kwargs()
            self._async_client = httpx.AsyncClient(**client_kwargs)
        
        # Make request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self._async_client.request(method, secure_url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                last_error = e
                logger.warning(f"Async request attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise last_error
    
    def get(self, url: str, **kwargs) -> Any:
        """Make a secure GET request."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Any:
        """Make a secure POST request."""
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs) -> Any:
        """Make a secure PUT request."""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> Any:
        """Make a secure DELETE request."""
        return self.request("DELETE", url, **kwargs)
    
    async def aget(self, url: str, **kwargs) -> Any:
        """Make an async secure GET request."""
        return await self.arequest("GET", url, **kwargs)
    
    async def apost(self, url: str, **kwargs) -> Any:
        """Make an async secure POST request."""
        return await self.arequest("POST", url, **kwargs)
    
    async def aput(self, url: str, **kwargs) -> Any:
        """Make an async secure PUT request."""
        return await self.arequest("PUT", url, **kwargs)
    
    async def adelete(self, url: str, **kwargs) -> Any:
        """Make an async secure DELETE request."""
        return await self.arequest("DELETE", url, **kwargs)
    
    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
        logger.debug("SecureHTTPClient closed")
    
    async def aclose(self) -> None:
        """Close the async HTTP client."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        logger.debug("SecureHTTPClient async client closed")


def enforce_https(url: str, service_name: Optional[str] = None) -> str:
    """
    Enforce HTTPS on a URL.
    
    Args:
        url: URL to enforce HTTPS on
        service_name: Optional service name for TLS config lookup
        
    Returns:
        URL with HTTPS scheme
        
    Raises:
        HTTPSTransportError: If HTTP is used when TLS is enforced
    """
    parsed = urlparse(url)
    
    if parsed.scheme == "https":
        return url
    
    if parsed.scheme == "http":
        if is_tls_required(service_name):
            raise HTTPSTransportError(f"HTTP URL not allowed when TLS is enforced: {url}")
        logger.warning(f"HTTP URL allowed (TLS not enforced): {url}")
        return url
    
    # No scheme - add HTTPS if TLS is required
    if is_tls_required(service_name):
        return f"https://{url}"
    
    return url


def create_secure_client(
    service_name: Optional[str] = None,
    **kwargs
) -> SecureHTTPClient:
    """
    Factory function to create a secure HTTP client.
    
    Args:
        service_name: Service name for configuration
        **kwargs: Additional client options
        
    Returns:
        Configured SecureHTTPClient instance
    """
    return SecureHTTPClient(service_name=service_name, **kwargs)


# Decorator for enforcing HTTPS on function calls
def require_https(func: Callable) -> Callable:
    """
    Decorator to enforce HTTPS on URL parameters.
    
    This decorator checks all string arguments for URLs and ensures
    they use HTTPS when TLS is enforced.
    """
    def wrapper(*args, **kwargs):
        # Check positional arguments
        new_args = []
        for arg in args:
            if isinstance(arg, str) and _looks_like_url(arg):
                arg = enforce_https(arg)
            new_args.append(arg)
        
        # Check keyword arguments
        new_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str) and _looks_like_url(value):
                value = enforce_https(value)
            new_kwargs[key] = value
        
        return func(*new_args, **new_kwargs)
    
    return wrapper


def _looks_like_url(string: str) -> bool:
    """
    Check if a string looks like a URL.
    
    Args:
        string: String to check
        
    Returns:
        True if string looks like a URL
    """
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_pattern.match(string))


# Convenience functions for common HTTP operations
def secure_get(url: str, service_name: Optional[str] = None, **kwargs) -> Any:
    """Make a secure GET request using a temporary client."""
    client = create_secure_client(service_name)
    try:
        return client.get(url, **kwargs)
    finally:
        client.close()


def secure_post(url: str, service_name: Optional[str] = None, **kwargs) -> Any:
    """Make a secure POST request using a temporary client."""
    client = create_secure_client(service_name)
    try:
        return client.post(url, **kwargs)
    finally:
        client.close()


async def secure_aget(url: str, service_name: Optional[str] = None, **kwargs) -> Any:
    """Make an async secure GET request using a temporary client."""
    client = create_secure_client(service_name)
    try:
        return await client.aget(url, **kwargs)
    finally:
        await client.aclose()


async def secure_apost(url: str, service_name: Optional[str] = None, **kwargs) -> Any:
    """Make an async secure POST request using a temporary client."""
    client = create_secure_client(service_name)
    try:
        return await client.apost(url, **kwargs)
    finally:
        await client.aclose()
