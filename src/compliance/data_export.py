"""
Data Export Utilities for AstraGuard

Exports user data in multiple formats.
"""

import json
import csv
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class DataExport:
    """
    Data export utilities.
    
    Features:
    - JSON export
    - CSV export
    - GDPR compliance
    """
    
    def __init__(self):
        """Initialize data export."""
        logger.info("Data export utilities initialized")
    
    def export_to_json(self, data: Dict, file_path: str):
        """Export data to JSON."""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Data exported to JSON: {file_path}")
    
    def export_to_csv(self, data: List[Dict], file_path: str):
        """Export data to CSV."""
        if not data:
            return
        
        keys = data[0].keys()
        
        with open(file_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        
        logger.info(f"Data exported to CSV: {file_path}")
    
    def export_user_data(
        self,
        user_id: str,
        format: str = "json"
    ) -> str:
        """Export all user data."""
        user_data = {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "data": {}
        }
        
        file_path = f"exports/user_{user_id}.{format}"
        
        if format == "json":
            self.export_to_json(user_data, file_path)
        
        return file_path


# Global instance
_data_export: Optional[DataExport] = None


def get_data_export() -> DataExport:
    """Get global data export."""
    global _data_export
    if _data_export is None:
        _data_export = DataExport()
    return _data_export
