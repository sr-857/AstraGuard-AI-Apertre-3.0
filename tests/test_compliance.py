"""Combined tests for compliance features (#662-#668)"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from src.compliance.data_retention import DataRetentionPolicy, DataType
from src.compliance.data_deletion import DataDeletion
from src.compliance.audit_trail import AuditTrail
from src.compliance.gdpr import GDPRCompliance
from src.compliance.access_logging import AccessControlLogger
from src.compliance.data_export import DataExport
from src.compliance.integrity_checks import IntegrityChecker


class TestDataRetention:
    def test_retention_periods(self):
        policy = DataRetentionPolicy()
        
        assert policy.get_retention_period(DataType.AUDIT_LOGS) == 2555
        assert policy.get_retention_period(DataType.TEMP_FILES) == 7
    
    def test_should_delete(self):
        policy = DataRetentionPolicy()
        
        old_date = datetime.now() - timedelta(days=100)
        assert policy.should_delete(DataType.TEMP_FILES, old_date) is True
        
        recent_date = datetime.now() - timedelta(days=1)
        assert policy.should_delete(DataType.TEMP_FILES, recent_date) is False


class TestDataDeletion:
    def test_delete_file(self):
        deletion = DataDeletion()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test data")
            temp_path = f.name
        
        # Delete it
        assert deletion.delete_file(temp_path, secure=True) is True
        assert deletion.verify_deletion(temp_path) is True


class TestAuditTrail:
    def test_record_event(self):
        trail = AuditTrail()
        
        event_id = trail.record_event(
            "data_access",
            "user123",
            "Viewed sensitive data"
        )
        
        assert event_id.startswith("EVT-")
    
    def test_query_events(self):
        trail = AuditTrail()
        
        trail.record_event("login", "user123", "Login")
        trail.record_event("logout", "user123", "Logout")
        
        events = trail.query_events(user_id="user123")
        assert len(events) == 2


class TestGDPRCompliance:
    def test_right_to_access(self):
        gdpr = GDPRCompliance()
        
        data = gdpr.right_to_access("user123")
        assert data["user_id"] == "user123"
        assert "personal_data" in data
    
    def test_right_to_erasure(self):
        gdpr = GDPRCompliance()
        
        report = gdpr.right_to_erasure("user123")
        assert report["user_id"] == "user123"
        assert "deleted_at" in report


class TestAccessControlLogger:
    def test_log_login(self):
        logger = AccessControlLogger()
        
        logger.log_login("user123", "192.168.1.1", True)
        history = logger.get_user_access_history("user123")
        
        assert len(history) == 1
        assert history[0]["event_type"] == "login"


class TestDataExport:
    def test_export_to_json(self):
        exporter = DataExport()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        
        data = {"test": "data"}
        exporter.export_to_json(data, temp_path)
        
        assert os.path.exists(temp_path)
        os.unlink(temp_path)


class TestIntegrityChecker:
    def test_checksum_verification(self):
        checker = IntegrityChecker()
        
        data = b"test data"
        checker.store_checksum("test1", data)
        
        assert checker.verify_integrity("test1", data) is True
        assert checker.verify_integrity("test1", b"modified") is False
