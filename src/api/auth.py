"""
API Authentication Module

Provides FastAPI integration for authentication and authorization.
Uses core authentication logic for API key management and RBAC.
"""

import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Set
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
import logging
from core.auth import APIKey, APIKeyManager, get_api_key_manager
from core.secrets import get_secret

logger = logging.getLogger(__name__)

# Global API key manager instance
_api_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get the global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# FastAPI security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(request: Request, api_key: str = Depends(api_key_header)) -> APIKey:
    """
    FastAPI dependency for API key authentication.

    Args:
        request: FastAPI request object
        api_key: API key from header

    Returns:
        APIKey object if valid

    Raises:
        HTTPException: If authentication fails
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Include 'X-API-Key' header."
        )

    key_manager = get_api_key_manager()

    try:
        # Validate the key
        key = key_manager.validate_key(api_key)

        # Check rate limit
        key_manager.check_rate_limit(api_key)

        return key
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


def require_permission(permission: str):
    """
    Create a dependency that requires a specific permission.

    Args:
        permission: The permission required (read, write, admin)

    Returns:
        FastAPI dependency function
    """
    async def permission_checker(api_key: APIKey = Depends(get_api_key)) -> APIKey:
        if permission not in api_key.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return api_key

    return permission_checker


# Initialize API keys from environment variable (optional)
def initialize_from_env():
    """Initialize API keys from environment variables."""
    api_keys_env = get_secret("api_keys")
    if api_keys_env:
        try:
            # Expected format: name1:key1,name2:key2
            key_manager = get_api_key_manager()
            for key_pair in api_keys_env.split(","):
                if ":" in key_pair:
                    name, key_value = key_pair.split(":", 1)
                    name = name.strip()
                    key_value = key_value.strip()

                    # Check if key already exists
                    if key_value not in key_manager.api_keys:
                        key = APIKey(
                            key=key_value,
                            name=name,
                            created_at=datetime.now(),
                            permissions={"read", "write"},
                            metadata={"source": "environment"}
                        )
                        key_manager.api_keys[key_value] = key
                        key_manager.key_hashes[hashlib.sha256(key_value.encode()).hexdigest()] = key_value

            key_manager._save_keys()
            logger.info("Initialized API keys from environment")

        except Exception as e:
            logger.error(f"Failed to initialize API keys from environment: {e}")