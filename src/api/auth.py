"""
API Authentication Module

Provides FastAPI integration for authentication and authorization.
Uses core authentication logic for API key management and RBAC.
"""

import os
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Awaitable
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
import logging
from core.auth import APIKey, APIKeyManager
from core.secrets import get_secret

logger = logging.getLogger(__name__)


def _generate_request_id() -> str:
    """Generate a unique request ID for correlation tracking."""
    return str(uuid.uuid4())


def _mask_api_key(api_key: str) -> str:
    """
    Mask API key for safe logging.
    
    Only shows first 8 characters followed by asterisks to prevent token leakage.
    
    Args:
        api_key: The API key to mask
        
    Returns:
        Masked API key suitable for logging (e.g., "abc12345********")
    """
    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:8] + "********"

# Global API key manager instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
        logger.info("API key manager initialized")
    return _api_key_manager


# FastAPI security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    request: Request, 
    api_key: Optional[str] = Depends(api_key_header)
) -> APIKey:
    """
    FastAPI dependency for validating API keys.

    Retrieves the 'X-API-Key' header, validates it against the active key store,
    checks for expiration and rate limits, and returns the key object if valid.

    Args:
        request (Request): The incoming FastAPI request.
        api_key (str): The raw API key string from the header.

    Returns:
        APIKey: The validated API key object containing metadata and permissions.

    Raises:
        HTTPException(401): If the key is missing from headers.
        HTTPException(401): If the key is invalid, expired, or rate-limited.
    """
    # Generate correlation ID for this authentication attempt
    request_id = _generate_request_id()
    client_ip = request.client.host if request and request.client else "unknown"
    request_path = request.url.path if request else "unknown"
    request_method = request.method if request else "unknown"
    
    # Log authentication attempt
    logger.info(
        "Authentication attempt",
        extra={
            "request_id": request_id,
            "client_ip": client_ip,
            "path": request_path,
            "method": request_method,
            "has_api_key": bool(api_key)
        }
    )
    
    if not api_key:
        logger.warning(
            "Authentication failed: Missing API key",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "path": request_path,
                "reason": "no_api_key_header"
            }
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )
    
    api_key = api_key.strip()
    key_prefix = api_key[:8] if len(api_key) >= 8 else api_key[:4]

    key_manager = get_api_key_manager()
    masked_key = _mask_api_key(api_key)

    try:
        # Validate the key
        logger.debug(
            "Validating API key",
            extra={
                "request_id": request_id,
                "masked_key": masked_key,
                "client_ip": client_ip
            }
        )
        
        key = key_manager.validate_key(api_key)
        
        logger.debug(
            "API key validated successfully",
            extra={
                "request_id": request_id,
                "masked_key": masked_key,
                "key_name": key.name,
                "permissions": list(key.permissions)
            }
        )

    try:
        # Check rate limit
        key_manager.check_rate_limit(api_key)

        # Log successful authentication
        logger.info(
            "Authentication successful",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "path": request_path,
                "key_name": key.name,
                "permissions": list(key.permissions),
                "masked_key": masked_key
            }
        )
        return key
        
    except ValueError as e:
        error_msg = str(e).lower()
        
        # Determine failure reason for logging
        if "expired" in error_msg:
            reason = "key_expired"
        elif "not found" in error_msg or "invalid" in error_msg:
            reason = "invalid_key"
        elif "rate limit" in error_msg:
            reason = "rate_limit_exceeded"
        else:
            reason = "validation_failed"
        
        logger.warning(
            "Authentication failed: Key validation error",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "path": request_path,
                "masked_key": masked_key,
                "reason": reason,
                "error": str(e)
            }
        )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    return key




def require_permission(permission: str) -> Callable[[APIKey], Awaitable[APIKey]]:
    """
    Create a dependency that requires a specific permission scope.

    Used as a decorator or dependency in FastAPI routes to enforce granular
    access control (RbAC) based on the permissions associated with the API key.

    Args:
        permission (str): The permission identifier (e.g., 'read', 'write', 'admin').

    Returns:
        Callable: A FastAPI dependency function that validates the permission.
    """
    async def permission_checker(api_key: APIKey = Depends(get_api_key)) -> APIKey:
        logger.debug(
            "Checking permission",
            extra={
                "key_name": api_key.name,
                "required_permission": permission,
                "available_permissions": list(api_key.permissions),
                "has_permission": permission in api_key.permissions
            }
        )
        
        if permission not in api_key.permissions:
            logger.warning(
                "Authorization failed: Insufficient permissions",
                extra={
                    "key_name": api_key.name,
                    "required_permission": permission,
                    "available_permissions": list(api_key.permissions),
                    "reason": "permission_denied"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        
        logger.info(
            "Authorization successful",
            extra={
                "key_name": api_key.name,
                "granted_permission": permission
            }
        )
        
        return api_key

    return permission_checker


# Initialize API keys from environment variable (optional)
def initialize_from_env():
    """Initialize API keys from environment variables."""
    logger.info("Attempting to initialize API keys from environment")
    
    api_keys_env: Optional[str] = get_secret("api_keys")
    
    if not api_keys_env:
        logger.info("No API keys found in environment, skipping initialization")
        return
    
    try:
        # Expected format: name1:key1,name2:key2
        key_manager = get_api_key_manager()
        keys_processed = 0
        keys_skipped = 0
        
        for key_pair in api_keys_env.split(","):
            if ":" not in key_pair:
                logger.warning(
                    "Invalid API key format in environment",
                    extra={"reason": "missing_colon_separator"}
                )
                keys_skipped += 1
                continue
                
            name_part, key_value_part = key_pair.split(":", 1)
            name = name_part.strip()
            key_value = key_value_part.strip()
            
            if not name or not key_value:
                logger.warning(
                    "Invalid API key format: empty name or value",
                    extra={"has_name": bool(name), "has_value": bool(key_value)}
                )
                keys_skipped += 1
                continue

            # Check if key already exists
            if key_value in key_manager.api_keys:
                logger.debug(
                    "API key already exists, skipping",
                    extra={
                        "key_name": name,
                        "masked_key": _mask_api_key(key_value)
                    }
                )
                keys_skipped += 1
                continue
                
            # Create new API key
            key = APIKey(
                key=key_value,
                name=name,
                created_at=datetime.now(),
                permissions={"read", "write"},
                metadata={"source": "environment"}
            )
            key_manager.api_keys[key_value] = key
            key_hash = hashlib.sha256(key_value.encode()).hexdigest()
            key_manager.key_hashes[key_hash] = key_value
            
            logger.info(
                "API key loaded from environment",
                extra={
                    "key_name": name,
                    "masked_key": _mask_api_key(key_value),
                    "permissions": list(key.permissions)
                }
            )
            keys_processed += 1

        key_manager._save_keys()  # type: ignore[attr-defined]
        
        logger.info(
            "API key initialization completed",
            extra={
                "keys_processed": keys_processed,
                "keys_skipped": keys_skipped,
                "total_keys": keys_processed + keys_skipped
            }
        )

    except Exception as e:
        logger.error(
            "Failed to initialize API keys from environment",
            extra={
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
