"""
Data Integrity Checks for AstraGuard

Implements checksum verification and tamper detection.
"""

import hashlib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IntegrityChecker:
    """
    Data integrity verification.
    
    Features:
    - Checksum calculation
    - Tamper detection
    - Integrity reporting
    """
    
    def __init__(self):
        """Initialize integrity checker."""
        self._checksums: Dict[str, str] = {}
        logger.info("Integrity checker initialized")
    
    def calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA-256 checksum."""
        return hashlib.sha256(data).hexdigest()
    
    def store_checksum(self, data_id: str, data: bytes):
        """Calculate and store checksum."""
        checksum = self.calculate_checksum(data)
        self._checksums[data_id] = checksum
        logger.info(f"Checksum stored for {data_id}")
    
    def verify_integrity(self, data_id: str, data: bytes) -> bool:
        """Verify data integrity."""
        if data_id not in self._checksums:
            logger.warning(f"No checksum found for {data_id}")
            return False
        
        current_checksum = self.calculate_checksum(data)
        stored_checksum = self._checksums[data_id]
        
        if current_checksum != stored_checksum:
            logger.error(f"Integrity check failed for {data_id}")
            return False
        
        return True
    
    def get_integrity_report(self) -> Dict:
        """Get integrity report."""
        return {
            "total_items": len(self._checksums),
            "checksums": self._checksums.copy()
        }


# Global instance
_integrity_checker: Optional[IntegrityChecker] = None


def get_integrity_checker() -> IntegrityChecker:
    """Get global integrity checker."""
    global _integrity_checker
    if _integrity_checker is None:
        _integrity_checker = IntegrityChecker()
    return _integrity_checker
