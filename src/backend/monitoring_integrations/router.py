"""FastAPI router for monitoring integrations."""
import logging
from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any

from backend.health_monitor import get_health_monitor
from .datadog_adapter import DatadogAdapter
from .newrelic_adapter import NewRelicAdapter
from .base import AdapterParseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# In-memory registry for integrations (simple PoC)
_INTEGRATIONS: Dict[str, Dict[str, Any]] = {}

_ADAPTERS = {
    "datadog": DatadogAdapter(),
    "newrelic": NewRelicAdapter(),
}


@router.post("/register")
async def register_integration(payload: Dict[str, Any]):
    """Register a new monitoring integration.

    Expected payload: {"provider": "datadog", "name": "team-datadog", "config": {...}}
    """
    provider = payload.get("provider")
    name = payload.get("name")
    config = payload.get("config", {})

    if not provider or not name:
        raise HTTPException(status_code=400, detail="provider and name are required")

    # Keep simple: store config in memory
    _INTEGRATIONS[name] = {"provider": provider, "config": config}
    logger.info(f"Registered integration {name} for provider {provider}")

    return {"status": "registered", "name": name, "provider": provider}


@router.post("/{provider}/webhook")
async def provider_webhook(provider: str, request: Request):
    """Generic webhook endpoint for supported providers.

    This endpoint accepts provider-specific webhook payloads and routes
    them to the appropriate adapter.
    """
    body = await request.json()
    adapter = _ADAPTERS.get(provider.lower())
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Provider not supported: {provider}")

    try:
        alerts = adapter.parse_payload(body)
    except AdapterParseError as e:
        logger.warning(f"Adapter parse error for {provider}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected parse error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse payload")

    try:
        health_monitor = get_health_monitor()
        adapter.ingest(alerts, health_monitor)
    except Exception as e:
        logger.error(f"Error ingesting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to ingest alerts")

    return {"ingested": len(alerts)}
