"""
Access Control Logging for AstraGuard

Tracks login/logout and permission changes.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AccessControlLogger:
    """
    Access control event logging.
    
    Features:
    - Login/logout tracking
    - Permission change tracking
    - Access attempt logging
    """
    
    def __init__(self):
        """Initialize access control logger."""
        self._events: List[Dict] = []
        logger.info("Access control logger initialized")
    
    def log_login(self, user_id: str, ip_address: str, success: bool):
        """Log login attempt."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "login",
            "user_id": user_id,
            "ip_address": ip_address,
            "success": success
        }
        
        self._events.append(event)
        logger.info(f"Login logged: {user_id} - {'success' if success else 'failed'}")
    
    def log_logout(self, user_id: str):
        """Log logout."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "logout",
            "user_id": user_id
        }
        
        self._events.append(event)
        logger.info(f"Logout logged: {user_id}")
    
    def log_permission_change(
        self,
        user_id: str,
        changed_by: str,
        old_permissions: List[str],
        new_permissions: List[str]
    ):
        """Log permission change."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "permission_change",
            "user_id": user_id,
            "changed_by": changed_by,
            "old_permissions": old_permissions,
            "new_permissions": new_permissions
        }
        
        self._events.append(event)
        logger.info(f"Permission change logged for user: {user_id}")
    
    def get_user_access_history(self, user_id: str) -> List[Dict]:
        """Get access history for user."""
        return [e for e in self._events if e.get("user_id") == user_id]


# Global instance
_access_logger: Optional[AccessControlLogger] = None


def get_access_logger() -> AccessControlLogger:
    """Get global access control logger."""
    global _access_logger
    if _access_logger is None:
        _access_logger = AccessControlLogger()
    return _access_logger
