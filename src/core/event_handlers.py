"""
Core Event Handlers.
Implements handlers for core system events, orchestrating reactions to
telemetry, anomalies, and state changes.
"""

import logging
from core.events import Event, TelemetryReceived, AnomalyDetected, StateTransitioned, RecoveryInitiated
from core.event_bus import get_event_bus
import asyncio

logger = logging.getLogger(__name__)

async def handle_telemetry(event: TelemetryReceived):
    """
    Handle new telemetry ingestion. 
    In the future, this could trigger anomaly detection asynchronously.
    """
    logger.debug(f"[Handler] Received telemetry from {event.source}")
    # Here we could push to a data lake, update real-time dashboards (via websockets), etc.

async def handle_anomaly(event: AnomalyDetected):
    """
    Handle detected anomalies.
    """
    if event.is_anomaly:
        logger.warning(f"[Handler] Anomaly detected! Score: {event.anomaly_score:.2f}")
        # Could trigger additional diagnostics here
    else:
        logger.debug(f"[Handler] Normal telemetry processed. Score: {event.anomaly_score:.2f}")

async def handle_state_transition(event: StateTransitioned):
    """
    Handle system state or mission phase changes.
    """
    logger.info(f"[Handler] System transition: {event.previous_state} -> {event.new_state} "
                f"(Reason: {event.reason})")
    
    if event.new_state == "SAFE_MODE":
        logger.critical("[Handler] SYSTEM ENTERED SAFE MODE. Initiating emergency protocols.")
        # Trigger emergency downlink, shut down non-essential subsystems, etc.

async def handle_recovery(event: RecoveryInitiated):
    """
    Monitor recovery actions.
    """
    logger.info(f"[Handler] Recovery initiated for {event.target_component}. Plan ID: {event.recovery_plan_id}")

def register_core_handlers():
    """Register all core handlers with the event bus."""
    bus = get_event_bus()
    bus.subscribe(TelemetryReceived, handle_telemetry)
    bus.subscribe(AnomalyDetected, handle_anomaly)
    bus.subscribe(StateTransitioned, handle_state_transition)
    bus.subscribe(RecoveryInitiated, handle_recovery)
    logger.info("Core event handlers registered.")
