"""
HIPAA Compliance for AstraGuard

Implements PHI protection and access controls for HIPAA compliance.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HIPAACompliance:
    """
    HIPAA compliance implementation.
    
    Features:
    - PHI (Protected Health Information) protection
    - Access controls
    - Audit requirements
    - Breach notification
    """
    
    def __init__(self):
        """Initialize HIPAA compliance."""
        self._phi_access_log: List[Dict] = []
        logger.info("HIPAA compliance initialized")
    
    def log_phi_access(
        self,
        user_id: str,
        patient_id: str,
        action: str,
        justification: str
    ):
        """
        Log PHI access (HIPAA requirement).
        
        Args:
            user_id: User accessing PHI
            patient_id: Patient whose PHI is accessed
            action: Action performed
            justification: Reason for access
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "patient_id": patient_id,
            "action": action,
            "justification": justification
        }
        
        self._phi_access_log.append(log_entry)
        logger.info(f"PHI access logged: {user_id} -> {patient_id}")
    
    def encrypt_phi(self, phi_data: str) -> str:
        """
        Encrypt PHI data (HIPAA requirement).
        
        Args:
            phi_data: PHI to encrypt
            
        Returns:
            Encrypted PHI
        """
        # Use encryption module
        from src.security.encryption import encrypt_field
        return encrypt_field(phi_data)
    
    def decrypt_phi(self, encrypted_phi: str) -> str:
        """
        Decrypt PHI data.
        
        Args:
            encrypted_phi: Encrypted PHI
            
        Returns:
            Decrypted PHI
        """
        from src.security.encryption import decrypt_field
        return decrypt_field(encrypted_phi)
    
    def check_minimum_necessary(
        self,
        user_role: str,
        requested_fields: List[str]
    ) -> List[str]:
        """
        Enforce minimum necessary rule (HIPAA).
        
        Args:
            user_role: Role of requesting user
            requested_fields: Fields requested
            
        Returns:
            Allowed fields based on role
        """
        # Define role-based access
        role_permissions = {
            "doctor": ["name", "dob", "diagnosis", "medications", "history"],
            "nurse": ["name", "dob", "medications", "vitals"],
            "billing": ["name", "dob", "insurance"],
            "admin": ["name", "dob"]
        }
        
        allowed = role_permissions.get(user_role, [])
        return [f for f in requested_fields if f in allowed]
    
    def generate_breach_notification(
        self,
        affected_patients: List[str],
        breach_date: datetime,
        breach_description: str
    ) -> Dict:
        """
        Generate HIPAA breach notification.
        
        Args:
            affected_patients: List of affected patient IDs
            breach_date: Date of breach
            breach_description: Description of breach
            
        Returns:
            Breach notification report
        """
        notification = {
            "breach_id": f"BREACH-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "affected_count": len(affected_patients),
            "breach_date": breach_date.isoformat(),
            "discovery_date": datetime.now().isoformat(),
            "description": breach_description,
            "notification_required": len(affected_patients) >= 500  # HHS notification threshold
        }
        
        logger.critical(f"HIPAA breach notification generated: {notification['breach_id']}")
        
        return notification
    
    def get_phi_access_audit(
        self,
        patient_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[Dict]:
        """Get PHI access audit log."""
        results = self._phi_access_log.copy()
        
        if patient_id:
            results = [e for e in results if e["patient_id"] == patient_id]
        
        if user_id:
            results = [e for e in results if e["user_id"] == user_id]
        
        return results


# Global instance
_hipaa_compliance: Optional[HIPAACompliance] = None


def get_hipaa_compliance() -> HIPAACompliance:
    """Get global HIPAA compliance."""
    global _hipaa_compliance
    if _hipaa_compliance is None:
        _hipaa_compliance = HIPAACompliance()
    return _hipaa_compliance
