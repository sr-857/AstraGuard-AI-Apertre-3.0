"""Simple New Relic webhook adapter (minimal parsing for PoC)."""
from .base import MonitoringAdapter, AdapterParseError
from typing import Any, Dict, List


class NewRelicAdapter(MonitoringAdapter):
    def parse_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []
        try:
            # New Relic alerts webhook has a variety of shapes. Handle common ones.
            if "condition_name" in payload or "policy_name" in payload:
                comp = payload.get("condition_name", payload.get("policy_name", "newrelic_alert"))
                sev = payload.get("severity", payload.get("level", "info"))
                msg = payload.get("details", payload.get("description", ""))
                alerts.append({
                    "provider": "newrelic",
                    "component": str(comp),
                    "severity": str(sev),
                    "message": str(msg),
                    "metadata": payload,
                })
            elif "violations" in payload and isinstance(payload["violations"], list):
                for v in payload["violations"]:
                    alerts.append({
                        "provider": "newrelic",
                        "component": v.get("condition_name", "newrelic_violation"),
                        "severity": v.get("severity", "warning"),
                        "message": v.get("description", ""),
                        "metadata": v,
                    })
            else:
                raise AdapterParseError("Unrecognized New Relic payload")

            return alerts
        except Exception as e:
            raise AdapterParseError(f"NewRelic parse error: {e}")
