"""
TLS Enforcement Module

Provides decorators, validators, and middleware for enforcing TLS/SSL
on all internal service communication. Ensures that microservices
communicate only over encrypted channels.
"""

import re
import ssl
import logging
from typing import Optional, Callable, Any, Dict, List
from functools import wraps
from urllib.parse import urlparse

from core.tls_config import get_tls_config, is_tls_required, TLSConfig
from core.secure_http_client import HTTPSTransportError, enforce_https

logger = logging.getLogger(__name__)


class TLSEnforcementError(Exception):
    """Exception raised when TLS enforcement fails."""
    pass


class TLSValidator:
    """
    Validator for ensuring TLS compliance in service communication.
    
    Validates URLs, connections, and configurations to ensure
    all internal communication uses TLS encryption.
    """
    
    def __init__(self, service_name: Optional[str] = None, strict: bool = True):
        """
        Initialize TLS validator.
        
        Args:
            service_name: Service name for service-specific configuration
            strict: If True, reject any non-TLS communication
        """
        self.service_name = service_name
        self.strict = strict
        self.tls_config = get_tls_config(service_name)
        self.violations: List[str] = []
        
        logger.debug(f"TLSValidator initialized for service: {service_name}")
    
    def validate_url(self, url: str, context: Optional[str] = None) -> bool:
        """
        Validate that a URL uses HTTPS.
        
        Args:
            url: URL to validate
            context: Optional context for error messages
            
        Returns:
            True if URL is valid (uses HTTPS)
            
        Raises:
            TLSEnforcementError: If URL doesn't use HTTPS and strict mode is enabled
        """
        parsed = urlparse(url)
        context_str = f" ({context})" if context else ""
        
        if parsed.scheme == "https":
            logger.debug(f"URL validated (HTTPS){context_str}: {url}")
            return True
        
        if parsed.scheme == "http":
            error_msg = f"HTTP URL detected{context_str}: {url}"
            self.violations.append(error_msg)
            
            if self.strict or self.tls_config.enforce_tls:
                logger.error(error_msg)
                raise TLSEnforcementError(
                    f"TLS enforcement failed: HTTP URL not allowed{context_str}. "
                    f"Use HTTPS instead: {url}"
                )
            else:
                logger.warning(f"{error_msg} - allowed in non-strict mode")
                return False
        
        # No scheme specified
        if self.strict:
            error_msg = f"URL without scheme detected{context_str}: {url}"
            self.violations.append(error_msg)
            raise TLSEnforcementError(
                f"TLS enforcement failed: URL must specify HTTPS scheme{context_str}: {url}"
            )
        
        return False
    
    def validate_redis_url(self, url: str) -> bool:
        """
        Validate that a Redis URL uses TLS (rediss://).
        
        Args:
            url: Redis URL to validate
            
        Returns:
            True if URL uses secure Redis protocol
            
        Raises:
            TLSEnforcementError: If URL doesn't use rediss:// and TLS is enforced
        """
        parsed = urlparse(url)
        
        if parsed.scheme == "rediss":
            logger.debug(f"Redis URL validated (secure): {url}")
            return True
        
        if parsed.scheme == "redis":
            error_msg = f"Unencrypted Redis URL detected: {url}"
            self.violations.append(error_msg)
            
            if self.strict or self.tls_config.enforce_tls:
                logger.error(error_msg)
                raise TLSEnforcementError(
                    f"TLS enforcement failed: Redis URL must use rediss:// for encryption. "
                    f"Change: {url} -> {url.replace('redis://', 'rediss://')}"
                )
            else:
                logger.warning(f"{error_msg} - allowed in non-strict mode")
                return False
        
        return False
    
    def validate_amqp_url(self, url: str) -> bool:
        """
        Validate that an AMQP (RabbitMQ) URL uses TLS (amqps://).
        
        Args:
            url: AMQP URL to validate
            
        Returns:
            True if URL uses secure AMQP protocol
            
        Raises:
            TLSEnforcementError: If URL doesn't use amqps:// and TLS is enforced
        """
        parsed = urlparse(url)
        
        if parsed.scheme == "amqps":
            logger.debug(f"AMQP URL validated (secure): {url}")
            return True
        
        if parsed.scheme == "amqp":
            error_msg = f"Unencrypted AMQP URL detected: {url}"
            self.violations.append(error_msg)
            
            if self.strict or self.tls_config.enforce_tls:
                logger.error(error_msg)
                raise TLSEnforcementError(
                    f"TLS enforcement failed: AMQP URL must use amqps:// for encryption. "
                    f"Change: {url} -> {url.replace('amqp://', 'amqps://')}"
                )
            else:
                logger.warning(f"{error_msg} - allowed in non-strict mode")
                return False
        
        return False
    
    def validate_kafka_url(self, url: str) -> bool:
        """
        Validate that a Kafka URL uses TLS.
        
        Args:
            url: Kafka URL to validate
            
        Returns:
            True if URL uses secure protocol
            
        Raises:
            TLSEnforcementError: If URL doesn't use secure protocol and TLS is enforced
        """
        # Kafka URLs typically use SSL:// or SASL_SSL://
        if url.startswith("SSL://") or url.startswith("SASL_SSL://"):
            logger.debug(f"Kafka URL validated (secure): {url}")
            return True
        
        if url.startswith("PLAINTEXT://") or url.startswith("SASL_PLAINTEXT://"):
            error_msg = f"Unencrypted Kafka URL detected: {url}"
            self.violations.append(error_msg)
            
            if self.strict or self.tls_config.enforce_tls:
                logger.error(error_msg)
                raise TLSEnforcementError(
                    f"TLS enforcement failed: Kafka URL must use SSL:// or SASL_SSL://. "
                    f"Change: {url} -> {url.replace('PLAINTEXT://', 'SSL://')}"
                )
            else:
                logger.warning(f"{error_msg} - allowed in non-strict mode")
                return False
        
        return False
    
    def validate_mongodb_url(self, url: str) -> bool:
        """
        Validate that a MongoDB URL uses TLS.
        
        Args:
            url: MongoDB URL to validate
            
        Returns:
            True if URL uses secure protocol
            
        Raises:
            TLSEnforcementError: If URL doesn't use TLS and TLS is enforced
        """
        parsed = urlparse(url)
        
        # MongoDB with TLS uses mongodb+srv:// or has tls=true parameter
        if parsed.scheme == "mongodb+srv":
            logger.debug(f"MongoDB URL validated (secure - SRV): {url}")
            return True
        
        if parsed.scheme == "mongodb":
            # Check for tls=true parameter
            if "tls=true" in url or "ssl=true" in url:
                logger.debug(f"MongoDB URL validated (TLS enabled): {url}")
                return True
            
            error_msg = f"MongoDB URL without TLS detected: {url}"
            self.violations.append(error_msg)
            
            if self.strict or self.tls_config.enforce_tls:
                logger.error(error_msg)
                raise TLSEnforcementError(
                    f"TLS enforcement failed: MongoDB URL must enable TLS. "
                    f"Add ?tls=true to URL or use mongodb+srv://"
                )
            else:
                logger.warning(f"{error_msg} - allowed in non-strict mode")
                return False
        
        return False
    
    def validate_all_urls(self, urls: List[str], context: Optional[str] = None) -> List[str]:
        """
        Validate multiple URLs.
        
        Args:
            urls: List of URLs to validate
            context: Optional context for error messages
            
        Returns:
            List of valid URLs
            
        Raises:
            TLSEnforcementError: If any URL fails validation in strict mode
        """
        valid_urls = []
        
        for url in urls:
            try:
                if self.validate_url(url, context):
                    valid_urls.append(url)
            except TLSEnforcementError:
                if self.strict:
                    raise
        
        return valid_urls
    
    def get_violations(self) -> List[str]:
        """Get list of all TLS violations detected."""
        return self.violations.copy()
    
    def clear_violations(self) -> None:
        """Clear the violations list."""
        self.violations.clear()


# Decorators for TLS enforcement

def require_tls(func: Callable) -> Callable:
    """
    Decorator to enforce TLS on function calls.
    
    This decorator validates that any URL parameters in the function
    call use HTTPS when TLS is enforced.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        validator = TLSValidator(strict=True)
        
        # Validate positional arguments
        for i, arg in enumerate(args):
            if isinstance(arg, str):
                if _is_http_url(arg):
                    validator.validate_url(arg, f"arg[{i}]")
                elif _is_redis_url(arg):
                    validator.validate_redis_url(arg)
                elif _is_amqp_url(arg):
                    validator.validate_amqp_url(arg)
        
        # Validate keyword arguments
        for key, value in kwargs.items():
            if isinstance(value, str):
                if _is_http_url(value):
                    validator.validate_url(value, f"kwarg[{key}]")
                elif _is_redis_url(value):
                    validator.validate_redis_url(value)
                elif _is_amqp_url(value):
                    validator.validate_amqp_url(value)
        
        return func(*args, **kwargs)
    
    return wrapper


def require_https_urls(func: Callable) -> Callable:
    """
    Decorator to enforce HTTPS on all URL parameters.
    
    Similar to require_tls but specifically for HTTP/HTTPS URLs.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        validator = TLSValidator(strict=True)
        
        # Check all string arguments
        for i, arg in enumerate(args):
            if isinstance(arg, str) and _is_http_url(arg):
                validator.validate_url(arg, f"arg[{i}]")
        
        for key, value in kwargs.items():
            if isinstance(value, str) and _is_http_url(value):
                validator.validate_url(value, f"kwarg[{key}]")
        
        return func(*args, **kwargs)
    
    return wrapper


def require_secure_redis(func: Callable) -> Callable:
    """
    Decorator to enforce secure Redis connections (rediss://).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        validator = TLSValidator(strict=True)
        
        # Check all string arguments for Redis URLs
        for i, arg in enumerate(args):
            if isinstance(arg, str) and _is_redis_url(arg):
                validator.validate_redis_url(arg)
        
        for key, value in kwargs.items():
            if isinstance(value, str) and _is_redis_url(value):
                validator.validate_redis_url(value)
        
        return func(*args, **kwargs)
    
    return wrapper


# Helper functions for URL detection

def _is_http_url(string: str) -> bool:
    """Check if string is an HTTP/HTTPS URL."""
    return bool(re.match(r'^https?://', string, re.IGNORECASE))


def _is_redis_url(string: str) -> bool:
    """Check if string is a Redis URL."""
    return bool(re.match(r'^rediss?://', string, re.IGNORECASE))


def _is_amqp_url(string: str) -> bool:
    """Check if string is an AMQP URL."""
    return bool(re.match(r'^amqps?://', string, re.IGNORECASE))


def _is_kafka_url(string: str) -> bool:
    """Check if string is a Kafka URL."""
    return bool(re.match(r'^(SSL|SASL_SSL|PLAINTEXT|SASL_PLAINTEXT)://', string, re.IGNORECASE))


def _is_mongodb_url(string: str) -> bool:
    """Check if string is a MongoDB URL."""
    return bool(re.match(r'^mongodb(\+srv)?://', string, re.IGNORECASE))


# URL transformation functions

def ensure_https(url: str) -> str:
    """
    Ensure a URL uses HTTPS scheme.
    
    Args:
        url: URL to transform
        
    Returns:
        URL with HTTPS scheme
    """
    if url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    if not url.startswith("https://"):
        return f"https://{url}"
    return url


def ensure_rediss(url: str) -> str:
    """
    Ensure a Redis URL uses rediss:// scheme.
    
    Args:
        url: Redis URL to transform
        
    Returns:
        URL with rediss:// scheme
    """
    if url.startswith("redis://"):
        return url.replace("redis://", "rediss://", 1)
    if not url.startswith("rediss://"):
        return f"rediss://{url}"
    return url


def ensure_amqps(url: str) -> str:
    """
    Ensure an AMQP URL uses amqps:// scheme.
    
    Args:
        url: AMQP URL to transform
        
    Returns:
        URL with amqps:// scheme
    """
    if url.startswith("amqp://"):
        return url.replace("amqp://", "amqps://", 1)
    if not url.startswith("amqps://"):
        return f"amqps://{url}"
    return url


# Middleware for FastAPI/Starlette

class TLSMiddleware:
    """
    Middleware for enforcing TLS in web applications.
    
    Can be used with FastAPI/Starlette to:
    - Redirect HTTP to HTTPS
    - Add security headers
    - Reject non-TLS requests
    """
    
    def __init__(
        self,
        enforce_tls: bool = True,
        redirect_to_https: bool = False,
        hsts_max_age: int = 31536000,
        service_name: Optional[str] = None
    ):
        """
        Initialize TLS middleware.
        
        Args:
            enforce_tls: Whether to enforce TLS (reject HTTP)
            redirect_to_https: Whether to redirect HTTP to HTTPS
            hsts_max_age: HSTS max-age in seconds
            service_name: Service name for configuration
        """
        self.enforce_tls = enforce_tls
        self.redirect_to_https = redirect_to_https
        self.hsts_max_age = hsts_max_age
        self.service_name = service_name
        
        # Check if TLS is required from config
        if service_name:
            self.enforce_tls = is_tls_required(service_name)
        
        logger.info(f"TLSMiddleware initialized (enforce={self.enforce_tls})")
    
    async def __call__(self, scope, receive, send):
        """
        ASGI middleware call.
        
        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope["type"] != "http":
            # Not an HTTP request, pass through
            await self.app(scope, receive, send)
            return
        
        # Check if request is HTTPS
        is_https = self._is_https_request(scope)
        
        if not is_https and self.enforce_tls:
            if self.redirect_to_https:
                # Redirect to HTTPS
                await self._redirect_to_https(scope, send)
                return
            else:
                # Reject HTTP request
                await self._reject_http(scope, send)
                return
        
        # Add security headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                
                # Add HSTS header
                headers.append(
                    (b"strict-transport-security", f"max-age={self.hsts_max_age}; includeSubDomains".encode())
                )
                
                # Add other security headers
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
    
    def _is_https_request(self, scope: Dict) -> bool:
        """Check if the request is HTTPS."""
        # Check various indicators of HTTPS
        if scope.get("scheme") == "https":
            return True
        
        headers = dict(scope.get("headers", []))
        
        # Check X-Forwarded-Proto header (from load balancer/proxy)
        forwarded_proto = headers.get(b"x-forwarded-proto", b"").decode()
        if forwarded_proto == "https":
            return True
        
        # Check if server port is 443
        server_port = scope.get("server", (None, None))[1]
        if server_port == 443:
            return True
        
        return False
    
    async def _redirect_to_https(self, scope, send):
        """Redirect HTTP request to HTTPS."""
        host = dict(scope.get("headers", [])).get(b"host", b"localhost").decode()
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode()
        
        https_url = f"https://{host}{path}"
        if query_string:
            https_url += f"?{query_string}"
        
        await send({
            "type": "http.response.start",
            "status": 301,
            "headers": [
                (b"location", https_url.encode()),
                (b"content-type", b"text/plain"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"Redirecting to HTTPS...",
        })
    
    async def _reject_http(self, scope, send):
        """Reject HTTP request with 403 Forbidden."""
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                (b"content-type", b"application/json"),
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error": "TLS required", "message": "This endpoint requires HTTPS encryption"}',
        })


# Convenience function for creating TLS middleware
def create_tls_middleware(
    enforce_tls: bool = True,
    service_name: Optional[str] = None,
    **kwargs
) -> TLSMiddleware:
    """
    Factory function to create TLS middleware.
    
    Args:
        enforce_tls: Whether to enforce TLS
        service_name: Service name for configuration
        **kwargs: Additional middleware options
        
    Returns:
        Configured TLSMiddleware instance
    """
    return TLSMiddleware(
        enforce_tls=enforce_tls,
        service_name=service_name,
        **kwargs
    )
