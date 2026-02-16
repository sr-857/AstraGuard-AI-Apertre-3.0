"""
AstraGuard AI REST API Service

FastAPI-based REST API for telemetry ingestion and anomaly detection.
"""

import os
import json
import time
import asyncio
from typing import List, Optional, Any, Union
from datetime import datetime, timedelta
from collections import deque
from asyncio import Lock
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Deque, Dict, List, Optional, Tuple, Union
import secrets
import asyncio
from core.secrets import get_secret, mask_secret
from pydantic import BaseModel


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
    UserCreateRequest,
    UserResponse,
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyCreateResponse,
    LoginRequest,
    TokenResponse,
)
from core.auth import (
    get_auth_manager,
    get_current_user,
    require_admin,
    require_operator,
    require_phase_update,
    require_analyst,
    UserRole,
    Permission,
    User,
    APIKey,
)
from api.auth import get_api_key
from api.logging_middleware import RequestLoggingMiddleware, get_correlation_id
from state_machine.state_engine import StateMachine, MissionPhase
from config.mission_phase_policy_loader import MissionPhasePolicyLoader
from anomaly_agent.phase_aware_handler import PhaseAwareAnomalyHandler
from anomaly.anomaly_detector import detect_anomaly, load_model, is_model_loaded, is_heuristic_active
from classifier.fault_classifier import classify
from core.component_health import get_health_monitor
from memory_engine.memory_store import AdaptiveMemoryStore
from security_engine.predictive_maintenance import (
    get_predictive_maintenance_engine,
    TimeSeriesData,
    PredictionResult
)
from fastapi.responses import Response
from core.metrics import (
    get_metrics_text,
    get_metrics_content_type,
    STARTUP_DURATION_SECONDS,
    SYSTEM_CPU_USAGE,
    SYSTEM_MEMORY_USAGE
)
from core.rate_limiter import RateLimiter, RateLimitMiddleware, get_rate_limit_config
from backend.redis_client import RedisClient
import numpy as np
from numpy.typing import NDArray
from astraguard.logging_config import get_logger
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from api.batch_processing import process_telemetry_chunk

logger = get_logger(__name__)

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
    OBSERVABILITY_ENABLED: bool = True
except ImportError:
    OBSERVABILITY_ENABLED = False
    print("Warning: Observability modules not available. Running without monitoring.")


# Configuration
MAX_ANOMALY_HISTORY_SIZE: int = 10000  # Maximum number of anomalies to keep in memory

# Global state
state_machine: Optional[StateMachine] = None
policy_loader: Optional[MissionPhasePolicyLoader] = None
phase_aware_handler: Optional[PhaseAwareAnomalyHandler] = None
memory_store: Optional[AdaptiveMemoryStore] = None
predictive_engine: Optional[Any] = None
latest_telemetry_data: Optional[Dict[str, Any]] = None  # Store latest telemetry for dashboard
anomaly_history: Deque[AnomalyResponse] = deque(maxlen=MAX_ANOMALY_HISTORY_SIZE)  # Bounded deque prevents memory exhaustion
active_faults: Dict[str, float] = {}  # Stores active chaos experiments: {fault_type: expiration_timestamp}

# Locks for global state protection
telemetry_lock: Lock = Lock()
anomaly_lock: Lock = Lock()
faults_lock: Lock = Lock()
start_time: float = time.time()


# Rate limiting
redis_client: Optional[RedisClient] = None
telemetry_limiter: Optional[RateLimiter] = None
api_limiter: Optional[RateLimiter] = None
process_pool: Optional[ProcessPoolExecutor] = None


async def initialize_components() -> None:
    """Initialize application components (called on startup or in tests)."""
    global state_machine, policy_loader, phase_aware_handler, memory_store, predictive_engine

    # Pre-import sklearn to avoid circular import issues in concurrent background tasks
    try:
        import sklearn.base
        import sklearn.ensemble
        import sklearn.preprocessing
    except ImportError:
        pass

    if state_machine is None:
        state_machine = StateMachine()
    if policy_loader is None:
        policy_loader = MissionPhasePolicyLoader()
    if phase_aware_handler is None:
        phase_aware_handler = PhaseAwareAnomalyHandler(state_machine, policy_loader)
    if memory_store is None:
        memory_store = AdaptiveMemoryStore()
    if predictive_engine is None:
        predictive_engine = await get_predictive_maintenance_engine(memory_store, background_init=True)


def _check_credential_security() -> None:
    """
    Check and warn about insecure credential configurations at startup.

    Security Checks:
    1. Warn if METRICS_USER/METRICS_PASSWORD are not set
    2. Warn if using common/weak credentials
    3. Set global flag if using defaults
    """
    global _USING_DEFAULT_CREDENTIALS

    metrics_user: Optional[str] = get_secret("METRICS_USER") or get_secret("metrics_user")
    metrics_password: Optional[str] = get_secret("METRICS_PASSWORD") or get_secret("metrics_password")

    # Check if credentials are set
    if not metrics_user or not metrics_password:
        print("\n" + "=" * 70)
        print("[WARNING] SECURITY WARNING: Metrics authentication not configured!")
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
    weak_credentials: List[Tuple[str, str]] = [
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
            print("[CRITICAL] SECURITY WARNING: Using default/weak credentials!")
            print("=" * 70)
            print(f"Detected credentials: {mask_secret(metrics_user)}/{mask_secret(metrics_password)}")
            print()
            print("[WARNING] THESE CREDENTIALS ARE PUBLICLY KNOWN AND INSECURE!")
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
        print("[WARNING] Weak password detected!")
        print("=" * 70)
        print(f"Password length: {len(metrics_password)} characters")
        print("Recommended minimum: 16 characters")
        print()
        print("Consider using a stronger password:")
        print("  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
        print("=" * 70 + "\n")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    global redis_client, telemetry_limiter, api_limiter, process_pool

    # Initialize process pool for CPU-bound tasks
    try:
        max_workers = max(1, cpu_count())
        process_pool = ProcessPoolExecutor(max_workers=max_workers)
        logger.info(f"Initialized ProcessPoolExecutor with {max_workers} workers")
    except Exception as e:
        logger.error(f"Failed to initialize process pool: {e}")

    # Security: Check credentials at startup
    _check_credential_security()

    # Helper for Redis init
    async def init_redis_and_rate_limit():
        global redis_client, telemetry_limiter, api_limiter
        try:
            redis_url: Optional[str] = get_secret("redis_url")
            redis_client = RedisClient(redis_url=redis_url)
            await redis_client.connect()

            # Get rate limit configurations
            rate_configs: Dict[str, Tuple[int, int]] = get_rate_limit_config()

            # Create rate limiters
            telemetry_limiter = RateLimiter(
                redis_client.redis,
                "telemetry",
                rate_configs["telemetry"][0],  # rate_per_second
                rate_configs["telemetry"][1]   # burst_capacity
            )
            api_limiter = RateLimiter(
                redis_client.redis,
                "api",
                rate_configs["api"][0],  # rate_per_second
                rate_configs["api"][1]   # burst_capacity
            )
            print("[OK] Rate limiting initialized successfully")
        except Exception as e:
            print(f"[WARNING] Rate limiting initialization failed: {e}")
            print("Rate limiting will be disabled")

    # Initialize components and Redis in parallel
    await asyncio.gather(
        initialize_components(),
        init_redis_and_rate_limit()
    )

    # Pre-load anomaly detection model async in background
    asyncio.create_task(load_model())

    # Initialize observability (if available)
    if OBSERVABILITY_ENABLED:
        try:
            setup_json_logging(log_level=get_secret("log_level", "INFO"))
            initialize_tracing()
            setup_auto_instrumentation()
            instrument_fastapi(app)
            startup_metrics_server(port=9090)
            logger.info("event", "observability_initialized", service="astra-guard", version="1.0.0")
        except Exception as e:
            print(f"Warning: Observability initialization failed: {e}")

    # Record startup duration
    startup_duration = time.time() - start_time
    STARTUP_DURATION_SECONDS.set(startup_duration)
    logger.info(f"Startup completed in {startup_duration:.2f}s")

    yield

    # Cleanup
    if process_pool:
        process_pool.shutdown()
    if memory_store:
        await memory_store.save()
    if redis_client:
        await redis_client.close()


# Initialize FastAPI app
app = FastAPI(
    title="AstraGuard AI API",
    description="REST API for telemetry ingestion and real-time anomaly detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Include routers
from api.contact import router as contact_router
app.include_router(contact_router)

# CORS configuration from environment variables
# Security: Never use allow_origins=["*"] with allow_credentials=True in production
allowed_origins_str = get_secret("allowed_origins") or "http://localhost:3000,http://localhost:8000"
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_str.split(",")]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Configured via ALLOWED_ORIGINS env var
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# Request logging middleware
log_level = get_secret("log_level", "INFO")
sample_rate = float(get_secret("log_sample_rate", "0.1"))  # 10% sampling for high-traffic endpoints
app.add_middleware(
    RequestLoggingMiddleware,
    log_level=log_level,
    sample_rate=sample_rate,
)

security = HTTPBasic()

# Credential validation flag (set during startup)
_USING_DEFAULT_CREDENTIALS = False

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)) -> str:
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
    correct_username = get_secret("METRICS_USER") or get_secret("metrics_user")
    correct_password = get_secret("METRICS_PASSWORD") or get_secret("metrics_password")

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


# ============================================================================
# Helper Functions
# ============================================================================

async def check_chaos_injection(fault_type: str) -> bool:
    """Check if a chaos fault is currently active."""
    async with faults_lock:
        if fault_type in active_faults:
            expiration: float = active_faults[fault_type]
            if time.time() > expiration:
                del active_faults[fault_type]
                return False
            return True
        return False


async def cleanup_expired_faults() -> None:
    """Clean up expired chaos faults."""
    current_time: float = time.time()
    async with faults_lock:
        expired: List[str] = [k for k, v in active_faults.items() if current_time > v]
        for k in expired:
            del active_faults[k]


async def inject_chaos_fault(fault_type: str, duration_seconds: int) -> Dict[str, Any]:
    """Inject a chaos fault for the specified duration."""
    expiration: float = time.time() + duration_seconds
    async with faults_lock:
        active_faults[fault_type] = expiration
    return {
        "status": "injected",
        "fault": fault_type,
        "expires_at": expiration
    }


def create_response(status: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """Create a standardized API response with timestamp."""
    response = {
        "status": status,
        "timestamp": datetime.now()
    }
    if data:
        response.update(data)
    response.update(kwargs)
    return response


# ============================================================================
# API Endpoints
# ============================================================================
@app.get("/", response_model=HealthCheckResponse)
async def root() -> HealthCheckResponse:
    """Root endpoint - health check."""
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now()
    )


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    try:
        # Get component health status
        health_monitor = get_health_monitor()
        components = health_monitor.get_all_health()

        # Determine overall status
        all_healthy = all(
            c.get("status") == "HEALTHY" for c in components.values()
        )

        # Get system uptime
        uptime = time.time() - start_time

        # Get current mission phase
        try:
            if state_machine is not None:
                mission_phase = state_machine.get_current_phase().value
            else:
                mission_phase = "UNKNOWN"
        except:
            mission_phase = "UNKNOWN"

        # Enhanced health response with more details
        return HealthCheckResponse(
            status="healthy" if all_healthy else "degraded",
            version="1.0.0",
            timestamp=datetime.now(),
            uptime_seconds=round(uptime, 2),
            mission_phase=mission_phase,
            components_status={
                name: {
                    "status": comp.get("status", "UNKNOWN"),
                    "last_check": comp.get("timestamp"),
                    "details": comp.get("details", "")
                }
                for name, comp in components.items()
            }
        )
    except Exception as e:
        # If health check fails, return degraded status
        return HealthCheckResponse(
            status="unhealthy",
            version="1.0.0",
            timestamp=datetime.now(),
            error=str(e)
        )


@app.get("/health/live")
async def health_live() -> Dict[str, Any]:
    """
    Liveness probe endpoint.
    
    Returns 200 if the service is running and can handle requests.
    This is a lightweight check that doesn't verify dependencies.
    
    Used by Kubernetes/Docker for liveness probes.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/ready")
async def ready() -> Response:
    """
    Readiness probe endpoint for Kubernetes.
    Returns 503 until models are loaded or heuristic mode is active.
    """
    model_ready = is_model_loaded() or is_heuristic_active()

    if not model_ready:
        return Response(
            content=json.dumps({"status": "loading"}),
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return Response(
        content=json.dumps({"status": "ready"}),
        media_type="application/json",
        status_code=status.HTTP_200_OK
    )


@app.get("/health/ready")
async def health_ready() -> Response:
    """
    Readiness probe endpoint.
    
    Returns 200 if the service is ready to accept traffic.
    Checks all critical dependencies:
    - Redis connectivity
    - Database connection (if applicable)
    - Component health
    
    Used by Kubernetes/Docker for readiness probes.
    Returns 503 if any critical dependency is unavailable.
    """
    checks = {
        "redis": {"status": "unknown", "message": ""},
        "components": {"status": "unknown", "message": ""},
        "overall": {"status": "unknown", "ready": False}
    }
    
    all_ready = True
    
    # Check Redis connectivity
    try:
        if redis_client is not None:
            # Try to ping Redis
            await redis_client.redis.ping()
            checks["redis"] = {
                "status": "healthy",
                "message": "Redis connection active"
            }
        else:
            checks["redis"] = {
                "status": "not_configured",
                "message": "Redis client not initialized (optional)"
            }
            # Redis is optional, don't fail readiness
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }
        all_ready = False
    
    # Check component health
    try:
        health_monitor = get_health_monitor()
        components = health_monitor.get_all_health()
        
        unhealthy_components = [
            name for name, comp in components.items()
            if comp.get("status") != "HEALTHY"
        ]
        
        if unhealthy_components:
            checks["components"] = {
                "status": "degraded",
                "message": f"Unhealthy components: {', '.join(unhealthy_components)}"
            }
            all_ready = False
        else:
            checks["components"] = {
                "status": "healthy",
                "message": f"All {len(components)} components healthy"
            }
    except Exception as e:
        checks["components"] = {
            "status": "error",
            "message": f"Component health check failed: {str(e)}"
        }
        all_ready = False
    
    # Set overall status
    checks["overall"] = {
        "status": "ready" if all_ready else "not_ready",
        "ready": all_ready
    }
    
    # Return appropriate HTTP status code
    status_code = status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    
    response_data = {
        "status": "ready" if all_ready else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": checks
    }
    
    return Response(
        content=json.dumps(response_data, default=str),
        media_type="application/json",
        status_code=status_code
    )


@app.get("/metrics", tags=["monitoring"])
async def metrics(username: str = Depends(get_current_username)) -> Response:
    """Prometheus metrics endpoint (Authenticated)."""
    # Update system metrics on scrape
    try:
        import psutil
        SYSTEM_CPU_USAGE.set(psutil.cpu_percent(interval=None))
        SYSTEM_MEMORY_USAGE.set(psutil.virtual_memory().percent)
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to collect system metrics: {e}")

    return Response(
        content=get_metrics_text(), 
        media_type=get_metrics_content_type()
    )


@app.post("/api/v1/telemetry", response_model=AnomalyResponse, status_code=status.HTTP_200_OK)
async def submit_telemetry(telemetry: TelemetryInput, current_user: User = Depends(require_operator)) -> AnomalyResponse:
    """
    Submit single telemetry point for anomaly detection.

    Requires API key authentication with 'write' permission.

    Returns:
        AnomalyResponse with detection results and recommended actions
    """
    request_start = time.time()
    
    # CHAOS INJECTION HOOK
    # 1. Network Latency Injection
    if await check_chaos_injection("network_latency"):
        time.sleep(2.0)  # Simulate 2s latency

    # 2. Model Loader Failure Injection
    if await check_chaos_injection("model_loader"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chaos Injection: Model Loader Failed"
        )
    
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
    # Type assertions for initialized globals
    assert state_machine is not None
    assert phase_aware_handler is not None
    assert memory_store is not None
    
    # Convert telemetry to dict
    data = {
        "voltage": telemetry.voltage,
        "temperature": telemetry.temperature,
        "gyro": telemetry.gyro,
        "current": telemetry.current or 0.0,
        "wheel_speed": telemetry.wheel_speed or 0.0,
    }

    # Update global latest telemetry
    async with telemetry_lock:
        global latest_telemetry_data
        latest_telemetry_data = {
            "data": data,
            "timestamp": datetime.now()
        }

    # Run detect_anomaly() and classify() concurrently for better performance
    # detect_anomaly is async, classify is sync (run in thread pool)
    (is_anomaly, anomaly_score), anomaly_type = await asyncio.gather(
        detect_anomaly(data),
        asyncio.to_thread(classify, data)
    )

    # Predictive Maintenance: Add training data and check for predictions
    predictive_actions = []
    if predictive_engine:
        try:
            # Create time-series data point
            ts_data = TimeSeriesData(
                timestamp=datetime.now(),
                cpu_usage=telemetry.cpu_usage or 0.0,
                memory_usage=telemetry.memory_usage or 0.0,
                network_latency=telemetry.network_latency or 0.0,
                disk_io=telemetry.disk_io or 0.0,
                error_rate=telemetry.error_rate or 0.0,
                response_time=telemetry.response_time or 0.0,
                active_connections=telemetry.active_connections or 0,
                failure_occurred=is_anomaly
            )

            # Add training data
            await predictive_engine.add_training_data(ts_data)

            # Check for failure predictions
            predictions = await predictive_engine.predict_failures(ts_data)

            if predictions:
                logger.info(f"Predictive maintenance: {len(predictions)} failure predictions made")

                # Trigger preventive actions
                actions = await predictive_engine.trigger_preventive_actions(predictions)
                predictive_actions = actions

                # Log predictions for monitoring
                for prediction in predictions:
                    logger.warning(f"PREDICTED FAILURE: {prediction.failure_type.value} "
                                 f"at {prediction.predicted_time} (prob: {prediction.probability:.2f})")

        except Exception as e:
            logger.error(f"Predictive maintenance failed: {e}")
            # Don't fail the request if predictive maintenance fails

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
        async with anomaly_lock:
            anomaly_history.append(response)

        # Store in memory with embedding (simple feature vector)
        embedding = np.array([
            telemetry.voltage,
            telemetry.temperature,
            abs(telemetry.gyro),
            telemetry.current or 0.0,
            telemetry.wheel_speed or 0.0
        ])
        await memory_store.write(
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
async def get_latest_telemetry(api_key: APIKey = Depends(get_api_key)) -> Dict[str, Any]:
    """Get the most recent telemetry data point."""
    async with telemetry_lock:
        if latest_telemetry_data is None:
            # Maintain backward-compatible contract: structured "no_data" response with HTTP 200
            return create_response("no_data", None)
        return create_response("success", latest_telemetry_data.copy())


@app.post("/api/v1/telemetry/batch", response_model=BatchAnomalyResponse)
async def submit_telemetry_batch(batch: TelemetryBatch, current_user: User = Depends(require_operator)) -> BatchAnomalyResponse:
    """
    Submit batch of telemetry points for anomaly detection.
    Optimized for high throughput using vectorization and multiprocessing.
    """
    request_start = time.time()

    # Prepare columnar data for batch processing
    n_items = len(batch.telemetry)
    columnar_data = {
        "voltage": [t.voltage for t in batch.telemetry],
        "temperature": [t.temperature for t in batch.telemetry],
        "gyro": [t.gyro for t in batch.telemetry],
        "current": [t.current or 0.0 for t in batch.telemetry],
        "wheel_speed": [t.wheel_speed or 0.0 for t in batch.telemetry],
    }
    timestamps = [t.timestamp or datetime.now() for t in batch.telemetry]

    # Split into chunks for parallel processing
    num_workers = max(1, cpu_count()) if process_pool else 1
    # For small batches, don't split too much to avoid overhead
    if n_items < 100:
        chunk_size = n_items
    else:
        chunk_size = (n_items + num_workers - 1) // num_workers

    futures = []
    loop = asyncio.get_running_loop()

    # Submit chunks to process pool
    for i in range(0, n_items, chunk_size):
        end = min(i + chunk_size, n_items)
        # Create chunk slices
        chunk_slice = {k: v[i:end] for k, v in columnar_data.items()}
        ts_slice = timestamps[i:end]

        if process_pool:
            futures.append(loop.run_in_executor(
                process_pool,
                process_telemetry_chunk,
                chunk_slice,
                ts_slice
            ))
        else:
            # Fallback if pool not initialized
            futures.append(asyncio.to_thread(
                process_telemetry_chunk,
                chunk_slice,
                ts_slice
            ))

    # Wait for all chunks
    results_lists = await asyncio.gather(*futures, return_exceptions=True)

    # Process results and apply phase logic (Main Thread)
    processed_results = []
    anomalies_detected = 0

    assert state_machine is not None
    assert phase_aware_handler is not None

    current_phase = state_machine.get_current_phase().value

    # Flatten results (handling exceptions)
    flat_results = []
    for res in results_lists:
        if isinstance(res, Exception):
            logger.error(f"Batch chunk processing failed: {res}")
            # We can't recover items from failed chunk easily unless we map back.
            # For now, we lose these items.
            continue
        flat_results.extend(res)

    # Apply phase logic and side effects (Memory Store, Predictive Engine)
    # We do this in main thread because these components are stateful/async
    # Ideally we should batch these too, but interfaces are singular.
    # To optimize, we run these concurrently using gather.

    async def post_process(idx, res):
        nonlocal anomalies_detected
        is_anomaly = res["is_anomaly"]
        score = res["anomaly_score"]
        anomaly_type = res["anomaly_type"]
        ts = res["timestamp"]

        # Reconstruct data dict for metadata
        data_point = {
            "voltage": columnar_data["voltage"][idx],
            "temperature": columnar_data["temperature"][idx],
            "gyro": columnar_data["gyro"][idx],
            "current": columnar_data["current"][idx],
            "wheel_speed": columnar_data["wheel_speed"][idx],
        }

        # Override is_anomaly if classifier says normal (Model tends to be aggressive)
        if anomaly_type == "normal":
            is_anomaly = False

        # Predictive Maintenance (Optional - skip for perf if critical? No, keep it)
        if predictive_engine:
            try:
                ts_data = TimeSeriesData(
                    timestamp=ts,
                    cpu_usage=0.0, # Default as input doesn't have it
                    memory_usage=0.0,
                    network_latency=0.0,
                    disk_io=0.0,
                    error_rate=0.0,
                    response_time=0.0,
                    active_connections=0,
                    failure_occurred=is_anomaly
                )
                # Fire and forget training data to avoid waiting?
                # await predictive_engine.add_training_data(ts_data)
                # For batch, we might skip prediction per item to save time?
                pass
            except Exception:
                pass

        if is_anomaly:
            decision = phase_aware_handler.handle_anomaly(
                anomaly_type=anomaly_type,
                severity_score=score,
                confidence=0.85,
                anomaly_metadata={"telemetry": data_point}
            )

            # Async memory write
            embedding = np.array([
                data_point["voltage"],
                data_point["temperature"],
                abs(data_point["gyro"]),
                data_point["current"],
                data_point["wheel_speed"]
            ])
            # Fire and forget write or await?
            await memory_store.write(
                embedding=embedding,
                metadata={
                    "anomaly_type": anomaly_type,
                    "severity": score,
                    "critical": decision['should_escalate_to_safe_mode']
                },
                timestamp=ts
            )

            return AnomalyResponse(
                is_anomaly=True,
                anomaly_score=score,
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
                timestamp=ts
            )
        else:
            return AnomalyResponse(
                is_anomaly=False,
                anomaly_score=score,
                anomaly_type="normal",
                severity_score=0.0,
                severity_level="LOW",
                mission_phase=current_phase,
                recommended_action="NO_ACTION",
                escalation_level="NO_ACTION",
                is_allowed=True,
                allowed_actions=[],
                should_escalate_to_safe_mode=False,
                confidence=0.9,
                reasoning="All telemetry parameters within normal range",
                recurrence_count=0,
                timestamp=ts
            )

    # Run post-processing in parallel (concurrently)
    # This keeps I/O operations (memory_store.write) concurrent
    post_process_tasks = [post_process(i, res) for i, res in enumerate(flat_results)]
    raw_results = await asyncio.gather(*post_process_tasks, return_exceptions=True)

    final_results = []
    for r in raw_results:
        if isinstance(r, Exception):
            logger.error(f"Post-processing failed for item: {r}")
            # Add error response?
            final_results.append(AnomalyResponse(
                is_anomaly=False,
                anomaly_score=0.0,
                anomaly_type="processing_error",
                severity_score=0.0,
                severity_level="LOW",
                mission_phase="UNKNOWN",
                recommended_action="RETRY",
                escalation_level="NO_ACTION",
                is_allowed=True,
                allowed_actions=[],
                should_escalate_to_safe_mode=False,
                confidence=0.0,
                reasoning=f"Processing failed: {str(r)}",
                recurrence_count=0,
                timestamp=datetime.now()
            ))
        else:
            final_results.append(r)

    anomalies_detected = sum(1 for r in final_results if r.is_anomaly)

    if OBSERVABILITY_ENABLED:
        elapsed = time.time() - request_start
        # Log batch metrics?
        pass

    return BatchAnomalyResponse(
        total_processed=len(final_results),
        anomalies_detected=anomalies_detected,
        results=final_results
    )


@app.get("/api/v1/status", response_model=SystemStatus)
async def get_status(api_key: APIKey = Depends(get_api_key)) -> SystemStatus:
    """Get system health and status.

    Requires API key authentication with 'read' permission.
    """
    assert state_machine is not None
    
    health_monitor = get_health_monitor()
    components = health_monitor.get_all_health()

    # CHAOS INJECTION HOOK: Redis Failure
    if await check_chaos_injection("redis_failure"):
        # Simulate Redis being down/degraded
        if "memory_store" in components:
            components["memory_store"]["status"] = "DEGRADED"
            components["memory_store"]["details"] = "ConnectionRefusedError: Chaos Injection"

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
async def get_phase(api_key: APIKey = Depends(get_api_key)) -> Dict[str, Any]:
    """Get current mission phase.

    Requires API key authentication with 'read' permission.
    """
    assert state_machine is not None
    assert phase_aware_handler is not None
    
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
async def update_phase(request: PhaseUpdateRequest, current_user: User = Depends(require_phase_update)) -> PhaseUpdateResponse:
    """Update mission phase."""
    assert state_machine is not None
    
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
async def get_memory_stats(api_key: APIKey = Depends(get_api_key)) -> MemoryStats:
    """Query memory store statistics.

    Requires API key authentication with 'read' permission.
    """
    assert memory_store is not None
    
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
    api_key: str = Depends(get_api_key),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    severity_min: Optional[float] = None
) -> AnomalyHistoryResponse:
    """Retrieve anomaly history with optional filtering."""
    # Convert deque to list for filtering operations
    async with anomaly_lock:
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


# Authentication endpoints
@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT token."""
    auth_manager = get_auth_manager()
    token = auth_manager.authenticate_user(request.username, request.password)
    return TokenResponse(access_token=token, token_type="bearer")


@app.post("/api/v1/auth/users", response_model=UserResponse)
async def create_user(request: UserCreateRequest, current_user: User = Depends(require_admin)) -> UserResponse:
    """Create a new user (admin only)."""
    auth_manager = get_auth_manager()
    user = await auth_manager.create_user(
        username=request.username,
        password=request.password,
        role=request.role,
        email=request.email
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.value,
        email=user.email,
        created_at=user.created_at,
        is_active=user.is_active
    )


@app.get("/api/v1/auth/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        email=current_user.email,
        created_at=current_user.created_at,
        is_active=current_user.is_active
    )


@app.post("/api/v1/auth/apikeys", response_model=APIKeyCreateResponse)
async def create_api_key(request: APIKeyCreateRequest, current_user: User = Depends(get_current_user)) -> APIKeyCreateResponse:
    """Create a new API key for the current user."""
    auth_manager = get_auth_manager()
    api_key = await auth_manager.create_api_key(
        user_id=current_user.id,
        name=request.name,
        permissions=request.permissions
    )
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=api_key.key,
        permissions=api_key.permissions,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at
    )


@app.get("/api/v1/auth/apikeys", response_model=List[APIKeyResponse])
async def list_api_keys(current_user: User = Depends(get_current_user)) -> List[APIKeyResponse]:
    """List API keys for the current user."""
    auth_manager = get_auth_manager()
    api_keys = await auth_manager.get_user_api_keys(current_user.id)
    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            permissions=key.permissions,
            created_at=key.created_at,
            expires_at=key.expires_at,
            last_used=key.last_used
        )
        for key in api_keys
    ]


@app.delete("/api/v1/auth/apikeys/{key_id}")
async def revoke_api_key(key_id: str, current_user: User = Depends(get_current_user)) -> Dict[str, str]:
    """Revoke an API key."""
    auth_manager = get_auth_manager()
    auth_manager.revoke_api_key(key_id, current_user.id)
    return {"message": "API key revoked successfully"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
