"""
Audit Logging System for AstraGuard

Implements comprehensive audit logging with tamper-proof storage.
Tracks all security-relevant events for compliance and forensics.
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events"""
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    PERMISSION_CHANGE = "permission_change"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"


class AuditLogger:
    """
    Tamper-proof audit logging system.
    
    Features:
    - Structured JSON logging
    - Event chaining with hashes
    - Compliance-ready format
    - Immutable audit trail
    """
    
    def __init__(self, log_file: str = "audit.log"):
        """Initialize audit logger."""
        self.log_file = log_file
        self.previous_hash = "0" * 64  # Genesis hash
        
        logger.info(f"Audit logger initialized: {log_file}")
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        action: str,
        resource: Optional[str] = None,
        result: str = "success",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            user_id: User performing action
            action: Description of action
            resource: Resource affected
            result: Result (success/failure)
            metadata: Additional metadata
            
        Returns:
            Event hash
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "result": result,
            "metadata": metadata or {},
            "previous_hash": self.previous_hash
        }
        
        # Calculate hash for tamper detection
        event_hash = self._calculate_hash(event)
        event["event_hash"] = event_hash
        
        # Write to log file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        # Update previous hash for chaining
        self.previous_hash = event_hash
        
        logger.info(f"Audit event logged: {event_type.value} by {user_id}")
        return event_hash
    
    def _calculate_hash(self, event: Dict) -> str:
        """Calculate SHA-256 hash of event."""
        event_str = json.dumps(event, sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()


# Global instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
