"""Simple Datadog webhook adapter (minimal parsing for PoC)."""
from .base import MonitoringAdapter, AdapterParseError
from typing import Any, Dict, List


class DatadogAdapter(MonitoringAdapter):
    def parse_payload(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts = []

        # Datadog events can either be event or monitor webhook payloads.
        # This is a simplified parser for common fields used in tests.
        try:
            # Monitor webhook shape: {"event": {...}} or top-level fields like "alert_type"
            if "alert_type" in payload or "event_type" in payload or "title" in payload:
                comp = payload.get("check", payload.get("title", "datadog_event"))
                severity = payload.get("alert_type", payload.get("event_type", "info"))
                msg = payload.get("text", payload.get("message", payload.get("body", "")))
                alerts.append({
                    "provider": "datadog",
                    "component": str(comp),
                    "severity": str(severity),
                    "message": str(msg),
                    "metadata": payload,
                })
            elif "events" in payload and isinstance(payload["events"], list):
                for e in payload["events"]:
                    alerts.append({
                        "provider": "datadog",
                        "component": e.get("title", "datadog_event"),
                        "severity": e.get("alert_type", e.get("event_type", "info")),
                        "message": e.get("text", e.get("body", "")),
                        "metadata": e,
                    })
            else:
                raise AdapterParseError("Unrecognized Datadog payload")

            return alerts
        except Exception as e:
            raise AdapterParseError(f"Datadog parse error: {e}")
