from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AdapterParseError(Exception):
    pass


class MonitoringAdapter(ABC):
    """Abstract base class for monitoring adapters."""

    @abstractmethod
    def parse_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse incoming webhook payload into a list of normalized alert dicts.

        Normalized alert format (example):
        {
            "provider": "datadog",
            "component": "db",
            "severity": "critical",
            "message": "High error rate",
            "metadata": {...}
        }
        """
        raise NotImplementedError

    def ingest(self, alerts: List[Dict[str, Any]], health_monitor) -> None:
        """Ingest normalized alerts into AstraGuard's health monitor.

        Default behavior: for severity critical -> mark_failed, for severity warning/critical -> mark_degraded
        and for info -> mark_healthy.
        """
        for alert in alerts:
            comp = alert.get("component", "external_monitor")
            sev = (alert.get("severity") or "info").lower()
            msg = alert.get("message") or ""
            metadata = alert.get("metadata") or {}

            # Ensure component is registered
            health_monitor.component_health.register_component(comp)

            if sev in ("critical", "error", "failure"):
                health_monitor.component_health.mark_failed(comp, error_msg=msg, metadata=metadata)
            elif sev in ("warning", "warn", "degraded"):
                health_monitor.component_health.mark_degraded(comp, error_msg=msg, metadata=metadata)
            else:
                health_monitor.component_health.mark_healthy(comp, metadata=metadata)
