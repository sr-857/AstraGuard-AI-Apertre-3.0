"""
AstraGuard AI REST API Service

FastAPI-based REST API for telemetry ingestion and anomaly detection.
"""

import os
import time
from datetime import datetime
from typing import List
from collections import deque
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import FastAPI, HTTPException, status, Depends
from contextlib import asynccontextmanager
import secrets

from api.models import (
    TelemetryInput,
    TelemetryBatch,
    AnomalyResponse,
    BatchAnomalyResponse,
    SystemStatus,
    PhaseUpdateRequest,
    PhaseUpdateResponse,
    MemoryStats,
    AnomalyHistoryQuery,
    AnomalyHistoryResponse,
    HealthCheckResponse,
)
from state_machine.state_engine import StateMachine, MissionPhase
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
from anomaly.anomaly_detector import detect_anomaly, load_model
from classifier.fault_classifier import classify
from core.component_health import get_health_monitor
from memory_engine.memory_store import AdaptiveMemoryStore
from fastapi.responses import Response
from core.metrics import get_metrics_text, get_metrics_content_type
import numpy as np

# Observability imports
try:
    from astraguard.observability import (
        startup_metrics_server,
        track_request,
        track_anomaly_detection,
        ANOMALY_DETECTIONS,
        REQUEST_COUNT,
        DETECTION_LATENCY,
    )
    from astraguard.tracing import initialize_tracing, setup_auto_instrumentation, instrument_fastapi, span_anomaly_detection
    from astraguard.logging_config import setup_json_logging, get_logger, log_request, log_detection, log_error
    OBSERVABILITY_ENABLED = True
except ImportError:
    OBSERVABILITY_ENABLED = False
    print("Warning: Observability modules not available. Running without monitoring.")


# Configuration
MAX_ANOMALY_HISTORY_SIZE = 10000  # Maximum number of anomalies to keep in memory

# Global state
state_machine = None
policy_loader = None
phase_aware_handler = None
memory_store = None
latest_telemetry_data = None # Store latest telemetry for dashboard
anomaly_history = deque(maxlen=MAX_ANOMALY_HISTORY_SIZE)  # Bounded deque prevents memory exhaustion
start_time = time.time()


def initialize_components():
    """Initialize application components (called on startup or in tests)."""
    global state_machine, policy_loader, phase_aware_handler, memory_store

    if state_machine is None:
        state_machine = StateMachine()
    if policy_loader is None:
        policy_loader = MissionPhasePolicyLoader()
    if phase_aware_handler is None:
        phase_aware_handler = PhaseAwareAnomalyHandler(state_machine, policy_loader)
    if memory_store is None:
        memory_store = AdaptiveMemoryStore()


def _check_credential_security():
    """
    Check and warn about insecure credential configurations at startup.

    Security Checks:
    1. Warn if METRICS_USER/METRICS_PASSWORD are not set
    2. Warn if using common/weak credentials
    3. Set global flag if using defaults
    """
    global _USING_DEFAULT_CREDENTIALS

    metrics_user = os.getenv("METRICS_USER")
    metrics_password = os.getenv("METRICS_PASSWORD")

    # Check if credentials are set
    if not metrics_user or not metrics_password:
        print("\n" + "=" * 70)
        print("⚠️  SECURITY WARNING: Metrics authentication not configured!")
        print("=" * 70)
        print("METRICS_USER and METRICS_PASSWORD environment variables are not set.")
        print("The /metrics endpoint will return HTTP 500 until configured.")
        print()
        print("To fix this:")
        print("  1. Set environment variables:")
        print("     export METRICS_USER=your_username")
        print("     export METRICS_PASSWORD=your_secure_password")
        print("  2. Or add to .env file:")
        print("     METRICS_USER=your_username")
        print("     METRICS_PASSWORD=your_secure_password")
        print("=" * 70 + "\n")
        return

    # List of weak/common credentials to warn about
    weak_credentials = [
        ("admin", "admin"),
        ("admin", "password"),
        ("root", "root"),
        ("admin", "12345"),
        ("admin", "123456"),
        ("user", "user"),
        ("test", "test"),
    ]

    # Check for weak credentials
    for weak_user, weak_pass in weak_credentials:
        if metrics_user == weak_user and metrics_password == weak_pass:
            _USING_DEFAULT_CREDENTIALS = True
            print("\n" + "=" * 70)
            print("🔴 CRITICAL SECURITY WARNING: Using default/weak credentials!")
            print("=" * 70)
            print(f"Detected credentials: {metrics_user}/{weak_pass}")
            print()
            print("⚠️  THESE CREDENTIALS ARE PUBLICLY KNOWN AND INSECURE!")
            print()
            print("IMMEDIATE ACTION REQUIRED:")
            print("  1. Change credentials before deploying to production")
            print("  2. Use strong, randomly-generated passwords (20+ characters)")
            print("  3. Consider using secrets management (Vault, AWS Secrets Manager)")
            print()
            print("Generate secure password:")
            print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
            print("=" * 70 + "\n")
            break

    # Check for short passwords
    if len(metrics_password) < 12:
        print("\n" + "=" * 70)
        print("⚠️  WARNING: Weak password detected!")
        print("=" * 70)
        print(f"Password length: {len(metrics_password)} characters")
        print("Recommended minimum: 16 characters")
        print()
        print("Consider using a stronger password:")
        print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("=" * 70 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Security: Check credentials at startup
    _check_credential_security()

    # Initialize components
    initialize_components()
    
    # Pre-load anomaly detection model async
    await load_model()

    # Initialize observability (if available)
    if OBSERVABILITY_ENABLED:
        try:
            logger = get_logger(__name__)
            setup_json_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
            initialize_tracing()
            setup_auto_instrumentation()
            instrument_fastapi(app)
            startup_metrics_server(port=9090)
            logger.info("event", "observability_initialized", service="astra-guard", version="1.0.0")
        except Exception as e:
            print(f"Warning: Observability initialization failed: {e}")

    yield

    # Cleanup
    if memory_store:
        memory_store.save()


# Initialize FastAPI app
app = FastAPI(
    title="AstraGuard AI API",
    description="REST API for telemetry ingestion and real-time anomaly detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration from environment variables
# Security: Never use allow_origins=["*"] with allow_credentials=True in production
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000"
).split(",")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Configured via ALLOWED_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

security = HTTPBasic()

# Credential validation flag (set during startup)
_USING_DEFAULT_CREDENTIALS = False

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Validate HTTP Basic Auth credentials for metrics endpoint.

    Security Notes:
    - Credentials MUST be set via METRICS_USER and METRICS_PASSWORD env vars
    - Default credentials trigger startup warning but are allowed for development
    - Use secrets.compare_digest for timing-attack resistance

    Args:
        credentials: HTTP Basic Auth credentials from request

    Returns:
        Username if valid

    Raises:
        HTTPException 401: Invalid credentials
        HTTPException 500: Credentials not configured
    """
    correct_username = os.getenv("METRICS_USER")
    correct_password = os.getenv("METRICS_PASSWORD")

    # Security: Require credentials to be explicitly set
    if not correct_username or not correct_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Metrics authentication not configured. Set METRICS_USER and METRICS_PASSWORD environment variables.",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    current_username_bytes = credentials.username.encode("utf8")
    correct_username_bytes = correct_username.encode("utf8")
    is_correct_username = secrets.compare_digest(
        current_username_bytes, correct_username_bytes
    )
    
    current_password_bytes = credentials.password.encode("utf8")
    correct_password_bytes = correct_password.encode("utf8")
    is_correct_password = secrets.compare_digest(
        current_password_bytes, correct_password_bytes
    )
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_model=HealthCheckResponse)
async def root():
    """Root endpoint - health check."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now()
    )


@app.get("/metrics", tags=["monitoring"])
async def get_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns Prometheus-formatted metrics including:
    - HTTP request count and latency
    - Anomaly detection metrics
    - Circuit breaker state
    - Retry attempts
    - Recovery actions
    """
    if not OBSERVABILITY_ENABLED:
        return {"error": "Observability not enabled"}
    
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from starlette.responses import Response
    
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now()
    )


@app.get("/metrics")
async def metrics(username: str = Depends(get_current_username)):
    """Prometheus metrics endpoint."""
    return Response(
        content=get_metrics_text(), 
        media_type=get_metrics_content_type()
    )


@app.post("/api/v1/telemetry", response_model=AnomalyResponse, status_code=status.HTTP_200_OK)
async def submit_telemetry(telemetry: TelemetryInput):
    """
    Submit single telemetry point for anomaly detection.

    Returns:
        AnomalyResponse with detection results and recommended actions
    """
    request_start = time.time()
    
    try:
        if OBSERVABILITY_ENABLED:
            with track_request("anomaly_detection"):
                with span_anomaly_detection(data_size=1, model_name="detector_v1"):
                    response = await _process_telemetry(telemetry, request_start)
        else:
            response = await _process_telemetry(telemetry, request_start)

        if OBSERVABILITY_ENABLED and response.is_anomaly:
            logger = get_logger(__name__)
            ANOMALY_DETECTIONS.labels(severity=response.severity_level.lower()).inc()
            log_detection(
                logger,
                severity=response.severity_level,
                detected_type=response.anomaly_type,
                confidence=response.confidence,
                instance_id="telemetry"
            )

        return response

    except Exception as e:
        if OBSERVABILITY_ENABLED:
            logger = get_logger(__name__)
            log_error(logger, e, {"endpoint": "/api/v1/telemetry"})
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(e)}"
        ) from e


async def _process_telemetry(telemetry: TelemetryInput, request_start: float) -> AnomalyResponse:
    """Internal telemetry processing logic."""
    # Convert telemetry to dict
    data = {
        "voltage": telemetry.voltage,
        "temperature": telemetry.temperature,
        "gyro": telemetry.gyro,
        "current": telemetry.current or 0.0,
        "wheel_speed": telemetry.wheel_speed or 0.0,
    }

    # Update global latest telemetry
    global latest_telemetry_data
    latest_telemetry_data = {
        "data": data,
        "timestamp": datetime.now()
    }

    # Detect anomaly (uses heuristic if model not loaded)
    is_anomaly, anomaly_score = await detect_anomaly(data)

    # Classify fault type
    anomaly_type = classify(data)

    # Get phase-aware decision if anomaly detected
    if is_anomaly:
        decision = phase_aware_handler.handle_anomaly(
            anomaly_type=anomaly_type,
            severity_score=anomaly_score,
            confidence=0.85,
            anomaly_metadata={"telemetry": data}
        )

        response = AnomalyResponse(
            is_anomaly=True,
            anomaly_score=anomaly_score,
            anomaly_type=decision['anomaly_type'],
            severity_score=decision['severity_score'],
            severity_level=decision['policy_decision']['severity'],
            mission_phase=decision['mission_phase'],
            recommended_action=decision['recommended_action'],
            escalation_level=decision['policy_decision']['escalation_level'],
            is_allowed=decision['policy_decision']['is_allowed'],
            allowed_actions=decision['policy_decision']['allowed_actions'],
            should_escalate_to_safe_mode=decision['should_escalate_to_safe_mode'],
            confidence=decision['detection_confidence'],
            reasoning=decision['reasoning'],
            recurrence_count=decision['recurrence_info']['count'],
            timestamp=telemetry.timestamp if telemetry.timestamp else datetime.now()
        )

        # Store in history
        anomaly_history.append(response)

        # Store in memory with embedding (simple feature vector)
        embedding = np.array([
            telemetry.voltage,
            telemetry.temperature,
            abs(telemetry.gyro),
            telemetry.current or 0.0,
            telemetry.wheel_speed or 0.0
        ])
        memory_store.write(
            embedding=embedding,
            metadata={
                "anomaly_type": anomaly_type,
                "severity": anomaly_score,
                "critical": decision['should_escalate_to_safe_mode']
            },
            timestamp=telemetry.timestamp
        )

    else:
        # No anomaly
        response = AnomalyResponse(
            is_anomaly=False,
            anomaly_score=anomaly_score,
            anomaly_type="normal",
            severity_score=0.0,
            severity_level="LOW",
            mission_phase=state_machine.get_current_phase().value,
            recommended_action="NO_ACTION",
            escalation_level="NO_ACTION",
            is_allowed=True,
            allowed_actions=[],
            should_escalate_to_safe_mode=False,
            confidence=0.9,
            reasoning="All telemetry parameters within normal range",
            recurrence_count=0,
            timestamp=telemetry.timestamp if telemetry.timestamp else datetime.now()
        )

    # Record latency in observability (if enabled)
    if OBSERVABILITY_ENABLED:
        elapsed_ms = (time.time() - request_start) * 1000
        DETECTION_LATENCY.observe(elapsed_ms / 1000.0)

    return response


@app.get("/api/v1/telemetry/latest")
async def get_latest_telemetry():
    """Get the most recent telemetry data point."""
    if latest_telemetry_data is None:
        return {"data": None, "message": "No telemetry received yet"}
    return latest_telemetry_data


@app.post("/api/v1/telemetry/batch", response_model=BatchAnomalyResponse)
async def submit_telemetry_batch(batch: TelemetryBatch):
    """
    Submit batch of telemetry points for anomaly detection.

    Returns:
        BatchAnomalyResponse with aggregated results
    """
    results = []
    anomalies_detected = 0

    for telemetry in batch.telemetry:
        result = await submit_telemetry(telemetry)
        results.append(result)
        if result.is_anomaly:
            anomalies_detected += 1

    return BatchAnomalyResponse(
        total_processed=len(results),
        anomalies_detected=anomalies_detected,
        results=results
    )


@app.get("/api/v1/status", response_model=SystemStatus)
async def get_status():
    """Get system health and status."""
    health_monitor = get_health_monitor()
    components = health_monitor.get_all_health()

    return SystemStatus(
        status="healthy" if all(
            c.get("status") == "HEALTHY" for c in components.values()
        ) else "degraded",
        mission_phase=state_machine.get_current_phase().value,
        components=components,
        uptime_seconds=time.time() - start_time,
        timestamp=datetime.now()
    )


@app.get("/api/v1/phase", response_model=dict)
async def get_phase():
    """Get current mission phase."""
    current_phase = state_machine.get_current_phase()
    constraints = phase_aware_handler.get_phase_constraints(current_phase)

    return {
        "phase": current_phase.value,
        "description": state_machine.get_phase_description(current_phase),
        "constraints": constraints,
        "history": state_machine.get_phase_history(),
        "timestamp": datetime.now()
    }


@app.post("/api/v1/phase", response_model=PhaseUpdateResponse)
async def update_phase(request: PhaseUpdateRequest):
    """Update mission phase."""
    try:
        target_phase = MissionPhase(request.phase.value)

        if request.force:
            # Force transition (e.g., emergency SAFE_MODE)
            if target_phase == MissionPhase.SAFE_MODE:
                result = state_machine.force_safe_mode()
            else:
                result = state_machine.set_phase(target_phase)
        else:
            # Normal transition with validation
            result = state_machine.set_phase(target_phase)

        return PhaseUpdateResponse(
            success=result['success'],
            previous_phase=result['previous_phase'],
            new_phase=result['new_phase'],
            message=result['message'],
            timestamp=datetime.now()
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phase transition failed: {str(e)}"
        ) from e


@app.get("/api/v1/memory/stats", response_model=MemoryStats)
async def get_memory_stats():
    """Query memory store statistics."""
    stats = memory_store.get_stats()

    return MemoryStats(
        total_events=stats['total_events'],
        critical_events=stats['critical_events'],
        avg_age_hours=stats['avg_age_hours'],
        max_recurrence=stats['max_recurrence'],
        timestamp=datetime.now()
    )


@app.get("/api/v1/history/anomalies", response_model=AnomalyHistoryResponse)
async def get_anomaly_history(
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 100,
    severity_min: float = None
):
    """Retrieve anomaly history with optional filtering."""
    # Convert deque to list for filtering operations
    filtered = list(anomaly_history)

    # Filter by time range
    if start_time:
        filtered = [a for a in filtered if a.timestamp >= start_time]
    if end_time:
        filtered = [a for a in filtered if a.timestamp <= end_time]

    # Filter by severity
    if severity_min is not None:
        filtered = [a for a in filtered if a.severity_score >= severity_min]

    # Apply limit (get last N items)
    filtered = filtered[-limit:] if len(filtered) > limit else filtered

    return AnomalyHistoryResponse(
        count=len(filtered),
        anomalies=filtered,
        start_time=start_time,
        end_time=end_time
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
