"""
API Key Management for AstraGuard

Implements API key generation, hashing, and validation.
"""

import secrets
import hashlib
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    API key management system.
    
    Features:
    - Secure key generation
    - Key hashing (never store plaintext)
    - Usage tracking
    - Key rotation
    """
    
    def __init__(self):
        """Initialize API key manager."""
        self._keys: Dict[str, Dict] = {}  # hash -> metadata
        logger.info("API key manager initialized")
    
    def generate_key(self, user_id: str, name: str) -> str:
        """
        Generate new API key.
        
        Args:
            user_id: User ID
            name: Key name/description
            
        Returns:
            API key (only time it's visible)
        """
        # Generate key
        key = f"ak_{secrets.token_urlsafe(32)}"
        
        # Hash for storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Store metadata
        self._keys[key_hash] = {
            "user_id": user_id,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "usage_count": 0
        }
        
        logger.info(f"API key generated for user {user_id}")
        return key
    
    def validate_key(self, key: str) -> Optional[str]:
        """
        Validate API key.
        
        Args:
            key: API key to validate
            
        Returns:
            User ID if valid, None otherwise
        """
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        if key_hash in self._keys:
            # Update usage
            self._keys[key_hash]["last_used"] = datetime.now().isoformat()
            self._keys[key_hash]["usage_count"] += 1
            
            return self._keys[key_hash]["user_id"]
        
        return None
    
    def revoke_key(self, key: str) -> bool:
        """Revoke an API key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        if key_hash in self._keys:
            del self._keys[key_hash]
            logger.info(f"API key revoked")
            return True
        
        return False


# Global instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager
