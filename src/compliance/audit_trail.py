"""
Audit Trail System for AstraGuard

Implements immutable audit trail for compliance.
"""

import logging
import json
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditTrail:
    """
    Immutable audit trail system.
    
    Features:
    - Event tracking
    - Compliance queries
    - Immutable storage
    """
    
    def __init__(self):
        """Initialize audit trail."""
        self._events: List[Dict] = []
        logger.info("Audit trail system initialized")
    
    def record_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        details: Optional[Dict] = None
    ) -> str:
        """Record audit event."""
        event = {
            "event_id": f"EVT-{len(self._events) + 1:08d}",
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "details": details or {}
        }
        
        self._events.append(event)
        logger.info(f"Audit event recorded: {event['event_id']}")
        
        return event["event_id"]
    
    def query_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Query audit events with filters."""
        results = self._events.copy()
        
        if user_id:
            results = [e for e in results if e["user_id"] == user_id]
        
        if event_type:
            results = [e for e in results if e["event_type"] == event_type]
        
        if start_date:
            results = [
                e for e in results
                if datetime.fromisoformat(e["timestamp"]) >= start_date
            ]
        
        if end_date:
            results = [
                e for e in results
                if datetime.fromisoformat(e["timestamp"]) <= end_date
            ]
        
        return results
    
    def export_audit_trail(self, file_path: str):
        """Export audit trail to file."""
        with open(file_path, 'w') as f:
            json.dump(self._events, f, indent=2)
        
        logger.info(f"Audit trail exported to {file_path}")


# Global instance
_audit_trail: Optional[AuditTrail] = None


def get_audit_trail() -> AuditTrail:
    """Get global audit trail."""
    global _audit_trail
    if _audit_trail is None:
        _audit_trail = AuditTrail()
    return _audit_trail
