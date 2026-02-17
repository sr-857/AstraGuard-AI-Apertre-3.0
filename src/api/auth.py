"""
API Authentication Module

Provides FastAPI integration for authentication and authorization.
Uses core authentication logic for API key management and RBAC.
"""

import os
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Awaitable, Tuple
from functools import lru_cache
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

# API key validation cache (TTL-based)
_validation_cache: Dict[str, Tuple[APIKey, datetime]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

@lru_cache(maxsize=1)
def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance (cached)."""
    return APIKeyManager()



# FastAPI security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    request: Request, 
    api_key: Optional[str] = Depends(api_key_header)
) -> APIKey:
    """
    FastAPI dependency for validating API keys with TTL-based caching.

    Retrieves the 'X-API-Key' header, validates it against the active key store,
    checks for expiration and rate limits, and returns the key object if valid.
    
    Uses a 5-minute TTL cache to avoid redundant validation for repeated requests.

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

    # Check cache first
    if api_key in _validation_cache:
        cached_key, cached_time = _validation_cache[api_key]
        if datetime.now() - cached_time < timedelta(seconds=_CACHE_TTL_SECONDS):
            # Cache hit - still valid, only check rate limit
            key_manager = get_api_key_manager()
            try:
                key_manager.check_rate_limit(api_key)
                return cached_key
            except ValueError as e:
                # Rate limit exceeded - remove from cache and raise
                _validation_cache.pop(api_key, None)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=str(e)
                )

    # Cache miss or expired - perform full validation
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

        # Cache the validated key
        _validation_cache[api_key] = (key, datetime.now())

        return key
        
    except ValueError as e:
        # Log authentication failures with debugging context (lazy evaluation)
        if logger.isEnabledFor(logging.WARNING):
            logger.warning(
                "Authentication failed: %s",
                e,
                extra={
                    "api_key_prefix": api_key[:8] + "..." if len(api_key) > 8 else api_key,
                    "client_ip": request.client.host if request.client else "unknown",
                    "endpoint": request.url.path
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


# Pre-compiled regex for efficient API key pair validation
_KEY_PAIR_PATTERN = re.compile(r'^\s*([^:]+?)\s*:\s*(.+?)\s*$')

# Initialize API keys from environment variable (optional)
def initialize_from_env() -> None:
    """Initialize API keys from environment variables with optimized parsing."""
    api_keys_env: Optional[str] = get_secret("api_keys")
    
    if api_keys_env:
        try:
            # Expected format: name1:key1,name2:key2
            key_manager = get_api_key_manager()
            initialized_count = 0
            
            # Pre-filter empty entries for efficiency
            key_pairs = [kp.strip() for kp in api_keys_env.split(",") if kp.strip()]
            
            # Batch process all key pairs
            new_keys = []
            for key_pair in key_pairs:
                # Use regex for validation (more efficient than multiple string ops)
                match = _KEY_PAIR_PATTERN.match(key_pair)
                if not match:
                    logger.warning(f"Skipping malformed API key pair: '{key_pair[:20]}...'")
                    continue
                
                name, key_value = match.groups()
                
                # Skip entries with empty name or value
                if not name or not key_value:
                    logger.warning("Skipping API key pair with empty name or value")
                    continue

                # Check if key already exists
                if key_value not in key_manager.api_keys:
                    key = APIKey(
                        key=key_value,
                        name=name,
                        created_at=datetime.now(),
                        permissions={"read", "write"},
                        metadata={"source": "environment"}
                    )
                    new_keys.append((key_value, key))
                    initialized_count += 1
            
            # Batch add all new keys
            for key_value, key in new_keys:
                key_manager.api_keys[key_value] = key
                key_hash = hashlib.sha256(key_value.encode()).hexdigest()
                key_manager.key_hashes[key_hash] = key_value

            # Save once after all keys are added
            if new_keys:
                key_manager._save_keys()  # type: ignore[attr-defined]
                logger.info(
                    f"Initialized {initialized_count} API keys from environment",
                    extra={"initialized_count": initialized_count}
                )

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
