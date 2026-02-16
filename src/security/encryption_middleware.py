"""
FastAPI Middleware for Automatic Encryption

Provides:
- Automatic request/response encryption
- Field-level encryption for sensitive data
- Transparent encryption handling
- Performance optimization
"""

import json
import base64
import logging
import time
from typing import Dict, Any, Optional, Callable, List, Set
from dataclasses import dataclass
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .encryption import get_encryption_engine, EncryptedData
from .field_encryption import get_field_encryption, encrypt_sensitive_fields, decrypt_sensitive_fields
from .compliance import log_encryption_event

logger = logging.getLogger(__name__)


@dataclass
class EncryptionMiddlewareConfig:
    """Configuration for encryption middleware."""
    encrypt_request_body: bool = False
    encrypt_response_body: bool = True
    field_level_encryption: bool = True
    sensitive_fields: List[str] = None
    auto_detect_sensitive: bool = True
    exclude_paths: List[str] = None
    performance_mode: bool = True  # Optimize for <5ms overhead
    
    def __post_init__(self):
        if self.sensitive_fields is None:
            self.sensitive_fields = [
                "password", "ssn", "credit_card", "api_key", "secret",
                "token", "email", "phone", "address", "dob"
            ]
        if self.exclude_paths is None:
            self.exclude_paths = ["/health", "/metrics", "/docs", "/openapi.json"]


class EncryptionMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic encryption.
    
    Automatically encrypts sensitive fields in request/response bodies.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        config: Optional[EncryptionMiddlewareConfig] = None,
    ):
        super().__init__(app)
        self.config = config or EncryptionMiddlewareConfig()
        self.field_encryption = get_field_encryption()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request/response with encryption.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
        
        Returns:
            Response with encrypted data if applicable
        """
        # Skip excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.config.exclude_paths):
            return await call_next(request)
        
        start_time = time.perf_counter()
        
        # Process request
        if self.config.encrypt_request_body and request.method in ["POST", "PUT", "PATCH"]:
            request = await self._process_request(request)
        
        # Get response
        response = await call_next(request)
        
        # Process response
        if self.config.encrypt_response_body:
            response = await self._process_response(response, path)
        
        # Log performance
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if elapsed_ms > 5:
            logger.warning(f"Encryption middleware took {elapsed_ms:.2f}ms")
        
        return response
    
    async def _process_request(self, request: Request) -> Request:
        """Process and potentially decrypt request body."""
        content_type = request.headers.get("content-type", "")
        
        if "application/json" not in content_type:
            return request
        
        try:
            body = await request.body()
            if not body:
                return request
            
            data = json.loads(body)
            
            # Check if body contains encrypted fields
            if self._has_encrypted_fields(data):
                # Decrypt fields
                decrypted = decrypt_sensitive_fields(data)
                
                # Replace request body
                request._body = json.dumps(decrypted).encode()
                
                log_encryption_event(
                    "decrypt_request",
                    details={"path": request.url.path},
                )
        
        except Exception as e:
            logger.error(f"Failed to process encrypted request: {e}")
        
        return request
    
    async def _process_response(self, response: Response, path: str) -> Response:
        """Process and encrypt response body."""
        content_type = response.headers.get("content-type", "")
        
        if "application/json" not in content_type:
            return response
        
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            if not body:
                return response
            
            data = json.loads(body)
            
            # Encrypt sensitive fields
            if self.config.field_level_encryption:
                encrypted = encrypt_sensitive_fields(
                    data,
                    fields=self.config.sensitive_fields,
                    auto_detect=self.config.auto_detect_sensitive,
                )
                
                # Check if any fields were encrypted
                if encrypted != data:
                    # Rebuild response
                    new_body = json.dumps(encrypted).encode()
                    
                    # Create new response
                    new_response = Response(
                        content=new_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )
                    
                    log_encryption_event(
                        "encrypt_response",
                        details={"path": path, "fields_encrypted": True},
                    )
                    
                    return new_response
        
        except Exception as e:
            logger.error(f"Failed to encrypt response: {e}")
        
        return response
    
    def _has_encrypted_fields(self, data: Dict[str, Any]) -> bool:
        """Check if data contains encrypted fields."""
        for value in data.values():
            if isinstance(value, dict) and value.get("__encrypted"):
                return True
        return False


class TransparentEncryptionDecorator:
    """
    Decorator for transparent encryption of function results.
    
    Automatically encrypts return values based on configuration.
    """
    
    def __init__(
        self,
        fields: Optional[List[str]] = None,
        auto_detect: bool = True,
        mode: str = "field_level",
    ):
        """
        Initialize decorator.
        
        Args:
            fields: Fields to encrypt
            auto_detect: Auto-detect sensitive fields
            mode: Encryption mode (field_level, full_payload)
        """
        self.fields = fields
        self.auto_detect = auto_detect
        self.mode = mode
    
    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            return self._encrypt_result(result)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return self._encrypt_result(result)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    def _encrypt_result(self, result: Any) -> Any:
        """Encrypt function result."""
        if not isinstance(result, dict):
            return result
        
        if self.mode == "field_level":
            return encrypt_sensitive_fields(
                result,
                fields=self.fields,
                auto_detect=self.auto_detect,
            )
        
        return result


def encrypt_response(
    fields: Optional[List[str]] = None,
    auto_detect: bool = True,
):
    """
    Decorator to encrypt response fields.
    
    Usage:
        @encrypt_response(fields=["ssn", "credit_card"])
        async def get_user(user_id: str):
            return {"name": "John", "ssn": "123-45-6789"}
    
    Args:
        fields: Fields to encrypt
        auto_detect: Auto-detect sensitive fields
    
    Returns:
        Decorator function
    """
    return TransparentEncryptionDecorator(
        fields=fields,
        auto_detect=auto_detect,
        mode="field_level",
    )


class EncryptionAtRestMiddleware:
    """
    Middleware for encryption at rest (database storage).
    
    Automatically encrypts data before database storage.
    """
    
    def __init__(
        self,
        encrypted_fields: List[str],
        auto_detect: bool = False,
    ):
        self.encrypted_fields = encrypted_fields
        self.auto_detect = auto_detect
        self.field_encryption = get_field_encryption()
    
    def before_save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt data before saving to database.
        
        Args:
            data: Data to save
        
        Returns:
            Encrypted data
        """
        return encrypt_sensitive_fields(
            data,
            fields=self.encrypted_fields,
            auto_detect=self.auto_detect,
        )
    
    def after_load(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt data after loading from database.
        
        Args:
            data: Loaded data
        
        Returns:
            Decrypted data
        """
        return decrypt_sensitive_fields(data)


# Convenience functions
def setup_encryption_middleware(
    app: ASGIApp,
    encrypt_responses: bool = True,
    encrypt_requests: bool = False,
    sensitive_fields: Optional[List[str]] = None,
) -> EncryptionMiddleware:
    """
    Setup encryption middleware for FastAPI app.
    
    Args:
        app: FastAPI application
        encrypt_responses: Encrypt response bodies
        encrypt_requests: Decrypt request bodies
        sensitive_fields: Fields to encrypt
    
    Returns:
        Configured middleware
    """
    config = EncryptionMiddlewareConfig(
        encrypt_request_body=encrypt_requests,
        encrypt_response_body=encrypt_responses,
        field_level_encryption=True,
        sensitive_fields=sensitive_fields,
        auto_detect_sensitive=True,
    )
    
    middleware = EncryptionMiddleware(app, config)
    logger.info("Encryption middleware configured")
    
    return middleware
