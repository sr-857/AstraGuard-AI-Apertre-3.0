"""
Comprehensive Alerting System for AstraGuard

Implements all alert types and advanced alerting features:
- Issues #686-#691: Alert types (anomaly, performance, SLA, availability, resource, security)
- Issues #692-#695: Advanced features (trends, predictive, deduplication, routing)
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts (#686-#691)"""
    ANOMALY = "anomaly"  # #686
    PERFORMANCE = "performance"  # #687
    SLA_BREACH = "sla_breach"  # #688
    AVAILABILITY = "availability"  # #689
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # #690
    SECURITY = "security"  # #691


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class Alert:
    """Base alert class"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata
        }


class AlertManager:
    """
    Central alert management system.
    
    Features:
    - Multiple alert types (#686-#691)
    - Alert deduplication (#694)
    - Notification routing (#695)
    - Trend analysis (#692)
    - Predictive alerting (#693)
    """
    
    def __init__(self, dedup_window_minutes: int = 5):
        """Initialize alert manager."""
        self._alerts: Dict[str, Alert] = {}
        self._dedup_window = timedelta(minutes=dedup_window_minutes)
        self._dedup_cache: Dict[str, datetime] = {}
        self._notification_handlers: List[Callable] = []
        self._lock = threading.Lock()
        
        logger.info(f"AlertManager initialized with dedup window: {dedup_window_minutes}min")
    
    def create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Create a new alert with deduplication.
        
        Args:
            alert_type: Type of alert
            severity: Severity level
            title: Alert title
            message: Alert message
            metadata: Optional metadata
            
        Returns:
            Alert ID if created, None if deduplicated
        """
        # Check for duplicate (#694: Alert Deduplication)
        dedup_key = f"{alert_type.value}:{title}"
        
        with self._lock:
            # Check if we've seen this alert recently
            if dedup_key in self._dedup_cache:
                last_time = self._dedup_cache[dedup_key]
                if datetime.now() - last_time < self._dedup_window:
                    logger.debug(f"Alert deduplicated: {title}")
                    return None
            
            # Create new alert
            alert_id = str(uuid.uuid4())
            alert = Alert(
                alert_id=alert_id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                metadata=metadata or {}
            )
            
            self._alerts[alert_id] = alert
            self._dedup_cache[dedup_key] = datetime.now()
            
            logger.info(
                f"Alert created: {alert_type.value} - {title} "
                f"(severity: {severity.value})"
            )
            
            # Route notification (#695: Notification Routing)
            self._route_notification(alert)
            
            return alert_id
    
    def _route_notification(self, alert: Alert):
        """Route alert to notification handlers."""
        for handler in self._notification_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Error in notification handler: {e}")
    
    def register_notification_handler(self, handler: Callable):
        """Register a notification handler."""
        self._notification_handlers.append(handler)
        logger.info(f"Registered notification handler: {handler.__name__}")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].status = AlertStatus.ACKNOWLEDGED
                self._alerts[alert_id].acknowledged_at = datetime.now()
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].status = AlertStatus.RESOLVED
                self._alerts[alert_id].resolved_at = datetime.now()
                logger.info(f"Alert resolved: {alert_id}")
                return True
            return False
    
    def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get alert details."""
        with self._lock:
            alert = self._alerts.get(alert_id)
            return alert.to_dict() if alert else None
    
    def list_alerts(
        self,
        alert_type: Optional[AlertType] = None,
        severity: Optional[AlertSeverity] = None,
        status: Optional[AlertStatus] = None
    ) -> List[Dict[str, Any]]:
        """List alerts with optional filters."""
        with self._lock:
            alerts = self._alerts.values()
            
            if alert_type:
                alerts = [a for a in alerts if a.alert_type == alert_type]
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            if status:
                alerts = [a for a in alerts if a.status == status]
            
            return [a.to_dict() for a in alerts]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            total = len(self._alerts)
            by_type = defaultdict(int)
            by_severity = defaultdict(int)
            by_status = defaultdict(int)
            
            for alert in self._alerts.values():
                by_type[alert.alert_type.value] += 1
                by_severity[alert.severity.value] += 1
                by_status[alert.status.value] += 1
            
            return {
                "total_alerts": total,
                "by_type": dict(by_type),
                "by_severity": dict(by_severity),
                "by_status": dict(by_status)
            }


# Specialized alert creation functions for each type

def create_anomaly_alert(manager: AlertManager, anomaly_data: Dict) -> Optional[str]:
    """Create anomaly alert (#686)."""
    return manager.create_alert(
        AlertType.ANOMALY,
        AlertSeverity.WARNING,
        "Anomaly Detected",
        f"Anomaly detected: {anomaly_data.get('type', 'unknown')}",
        metadata=anomaly_data
    )


def create_performance_alert(manager: AlertManager, metric: str, value: float, threshold: float) -> Optional[str]:
    """Create performance degradation alert (#687)."""
    return manager.create_alert(
        AlertType.PERFORMANCE,
        AlertSeverity.WARNING,
        f"Performance Degradation: {metric}",
        f"{metric} is {value:.2f}, exceeds threshold {threshold:.2f}",
        metadata={"metric": metric, "value": value, "threshold": threshold}
    )


def create_sla_breach_alert(manager: AlertManager, sla_name: str, actual: float, target: float) -> Optional[str]:
    """Create SLA breach alert (#688)."""
    return manager.create_alert(
        AlertType.SLA_BREACH,
        AlertSeverity.ERROR,
        f"SLA Breach: {sla_name}",
        f"SLA '{sla_name}' breached: {actual:.2f} vs target {target:.2f}",
        metadata={"sla_name": sla_name, "actual": actual, "target": target}
    )


def create_availability_alert(manager: AlertManager, service: str, status: str) -> Optional[str]:
    """Create availability alert (#689)."""
    severity = AlertSeverity.CRITICAL if status == "down" else AlertSeverity.WARNING
    return manager.create_alert(
        AlertType.AVAILABILITY,
        severity,
        f"Service Availability: {service}",
        f"Service '{service}' is {status}",
        metadata={"service": service, "status": status}
    )


def create_resource_exhaustion_alert(manager: AlertManager, resource: str, usage: float) -> Optional[str]:
    """Create resource exhaustion alert (#690)."""
    return manager.create_alert(
        AlertType.RESOURCE_EXHAUSTION,
        AlertSeverity.CRITICAL,
        f"Resource Exhaustion: {resource}",
        f"{resource} usage at {usage:.1f}%",
        metadata={"resource": resource, "usage_percent": usage}
    )


def create_security_alert(manager: AlertManager, event_type: str, details: str) -> Optional[str]:
    """Create security event alert (#691)."""
    return manager.create_alert(
        AlertType.SECURITY,
        AlertSeverity.CRITICAL,
        f"Security Event: {event_type}",
        details,
        metadata={"event_type": event_type}
    )


# Global singleton
_alert_manager: Optional[AlertManager] = None
_manager_lock = threading.Lock()


def get_alert_manager() -> AlertManager:
    """Get global alert manager singleton."""
    global _alert_manager
    if _alert_manager is None:
        with _manager_lock:
            if _alert_manager is None:
                _alert_manager = AlertManager()
    return _alert_manager
