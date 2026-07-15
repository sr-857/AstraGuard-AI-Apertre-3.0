"""Tests for Alerting System (#686-#695)"""

import pytest
from src.core.alerts.alert_manager import (
    AlertManager,
    AlertType,
    AlertSeverity,
    AlertStatus,
    get_alert_manager,
    create_anomaly_alert,
    create_performance_alert,
    create_sla_breach_alert,
    create_availability_alert,
    create_resource_exhaustion_alert,
    create_security_alert
)


class TestAlertManager:
    @pytest.fixture
    def manager(self):
        return AlertManager(dedup_window_minutes=1)
    
    def test_create_alert(self, manager):
        alert_id = manager.create_alert(
            AlertType.ANOMALY,
            AlertSeverity.WARNING,
            "Test Alert",
            "Test message"
        )
        assert alert_id is not None
    
    def test_alert_deduplication(self, manager):
        # Create first alert
        id1 = manager.create_alert(
            AlertType.ANOMALY,
            AlertSeverity.WARNING,
            "Duplicate Test",
            "Message 1"
        )
        
        # Try to create duplicate
        id2 = manager.create_alert(
            AlertType.ANOMALY,
            AlertSeverity.WARNING,
            "Duplicate Test",
            "Message 2"
        )
        
        assert id1 is not None
        assert id2 is None  # Deduplicated
    
    def test_acknowledge_alert(self, manager):
        alert_id = manager.create_alert(
            AlertType.PERFORMANCE,
            AlertSeverity.WARNING,
            "Test",
            "Test"
        )
        
        assert manager.acknowledge_alert(alert_id) is True
        alert = manager.get_alert(alert_id)
        assert alert["status"] == AlertStatus.ACKNOWLEDGED.value
    
    def test_resolve_alert(self, manager):
        alert_id = manager.create_alert(
            AlertType.SLA_BREACH,
            AlertSeverity.ERROR,
            "Test",
            "Test"
        )
        
        assert manager.resolve_alert(alert_id) is True
        alert = manager.get_alert(alert_id)
        assert alert["status"] == AlertStatus.RESOLVED.value
    
    def test_list_alerts_with_filters(self, manager):
        manager.create_alert(AlertType.ANOMALY, AlertSeverity.WARNING, "A1", "M1")
        manager.create_alert(AlertType.SECURITY, AlertSeverity.CRITICAL, "S1", "M2")
        
        anomaly_alerts = manager.list_alerts(alert_type=AlertType.ANOMALY)
        assert len(anomaly_alerts) >= 1
        
        critical_alerts = manager.list_alerts(severity=AlertSeverity.CRITICAL)
        assert len(critical_alerts) >= 1
    
    def test_get_statistics(self, manager):
        manager.create_alert(AlertType.ANOMALY, AlertSeverity.WARNING, "A", "M")
        manager.create_alert(AlertType.SECURITY, AlertSeverity.CRITICAL, "S", "M")
        
        stats = manager.get_statistics()
        assert stats["total_alerts"] >= 2
        assert "by_type" in stats
        assert "by_severity" in stats
    
    def test_specialized_alert_functions(self, manager):
        # Test all specialized alert creation functions
        assert create_anomaly_alert(manager, {"type": "test"}) is not None
        assert create_performance_alert(manager, "cpu", 95.0, 80.0) is not None
        assert create_sla_breach_alert(manager, "response_time", 2.5, 1.0) is not None
        assert create_availability_alert(manager, "api", "down") is not None
        assert create_resource_exhaustion_alert(manager, "memory", 98.5) is not None
        assert create_security_alert(manager, "unauthorized_access", "Details") is not None
    
    def test_singleton(self):
        m1 = get_alert_manager()
        m2 = get_alert_manager()
        assert m1 is m2
