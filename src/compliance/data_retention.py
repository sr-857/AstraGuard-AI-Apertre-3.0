"""
Data Retention Policy for AstraGuard

Implements configurable data retention with automated deletion.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class DataType(str, Enum):
    """Types of data with retention policies"""
    AUDIT_LOGS = "audit_logs"
    USER_DATA = "user_data"
    TELEMETRY = "telemetry"
    BACKUPS = "backups"
    TEMP_FILES = "temp_files"


class DataRetentionPolicy:
    """
    Data retention policy manager.
    
    Features:
    - Configurable retention periods
    - Automated deletion scheduling
    - Compliance reporting
    """
    
    def __init__(self):
        """Initialize retention policies."""
        self.policies: Dict[DataType, int] = {
            DataType.AUDIT_LOGS: 2555,  # 7 years (compliance)
            DataType.USER_DATA: 1825,   # 5 years
            DataType.TELEMETRY: 90,     # 90 days
            DataType.BACKUPS: 30,       # 30 days
            DataType.TEMP_FILES: 7,     # 7 days
        }
        
        logger.info("Data retention policies initialized")
    
    def set_retention_period(self, data_type: DataType, days: int):
        """Set retention period for data type."""
        self.policies[data_type] = days
        logger.info(f"Retention policy updated: {data_type} = {days} days")
    
    def get_retention_period(self, data_type: DataType) -> int:
        """Get retention period for data type."""
        return self.policies.get(data_type, 365)
    
    def should_delete(self, data_type: DataType, created_at: datetime) -> bool:
        """Check if data should be deleted based on retention policy."""
        retention_days = self.get_retention_period(data_type)
        age = datetime.now() - created_at
        
        return age.days > retention_days
    
    def get_deletion_date(self, data_type: DataType, created_at: datetime) -> datetime:
        """Calculate when data should be deleted."""
        retention_days = self.get_retention_period(data_type)
        return created_at + timedelta(days=retention_days)


# Global instance
_retention_policy: Optional[DataRetentionPolicy] = None


def get_retention_policy() -> DataRetentionPolicy:
    """Get global retention policy."""
    global _retention_policy
    if _retention_policy is None:
        _retention_policy = DataRetentionPolicy()
    return _retention_policy
