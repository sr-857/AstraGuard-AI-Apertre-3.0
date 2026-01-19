"""
AstraGuard AI Backend - Main FastAPI Application

Central entry point for the AstraGuard AI reliability suite backend.
Integrates:
- Issue #14: Circuit Breaker pattern
- Issue #15: Retry logic with exponential backoff
- Issue #16: Health Monitor + Fallback Cascade

API Endpoints:
- /health/metrics - Prometheus metrics
- /health/state - Comprehensive health snapshot
- /health/cascade - Trigger fallback cascade
- /health/ready - Kubernetes readiness check
- /health/live - Kubernetes liveness check
"""

import logging
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import centralized secrets management
from core.secrets import get_secret

# Import modules
from backend.health_monitor import (
    router as health_router,
    HealthMonitor,
    set_health_monitor,
)
from backend.fallback_manager import FallbackManager
from backend.recovery_orchestrator import RecoveryOrchestrator
from backend.redis_client import RedisClient
from backend.distributed_coordinator import DistributedResilienceCoordinator
from core.component_health import SystemHealthMonitor
from core.circuit_breaker import get_all_circuit_breakers

# Import anomaly detector to register its circuit breaker
# (Must happen before health_monitor initialization)
import anomaly.anomaly_detector  # noqa: F401

# Configure logging
log_level = get_secret("log_level", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# SECURITY CONFIGURATION
# ============================================================================

# Chaos engineering endpoints are only available when explicitly enabled
CHAOS_ENABLED = get_secret("chaos_enabled", False)
CHAOS_ADMIN_KEY = get_secret("chaos_admin_key", "")


async def verify_chaos_admin_access(x_chaos_admin_key: str = Header(None)) -> None:
    """Verify admin access to chaos engineering endpoints.
    
    Validates:
    1. Chaos engineering is explicitly enabled (ENABLE_CHAOS=true)
    2. Caller provides correct admin API key (CHAOS_ADMIN_KEY)
    
    Args:
        x_chaos_admin_key: Admin API key from X-Chaos-Admin-Key header
        
    Raises:
        HTTPException: 403 if chaos is disabled, 401 if auth fails
    """
    if not CHAOS_ENABLED:
        logger.warning(
            "🚫 Unauthorized chaos injection attempt - feature disabled. "
            "Set ENABLE_CHAOS=true to enable."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chaos engineering is disabled. Set ENABLE_CHAOS=true to enable.",
        )
    
    if not CHAOS_ADMIN_KEY:
        logger.error(
            "🚫 Chaos engineering enabled but CHAOS_ADMIN_KEY not configured. "
            "Set CHAOS_ADMIN_KEY environment variable for security."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chaos endpoint not properly configured.",
        )
    
    if not x_chaos_admin_key or x_chaos_admin_key != CHAOS_ADMIN_KEY:
        logger.warning(
            "🚫 Unauthorized chaos injection attempt - invalid admin key"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Initialize health monitor and fallback manager
health_monitor: HealthMonitor = None
fallback_manager: FallbackManager = None
recovery_orchestrator: RecoveryOrchestrator = None
component_health: SystemHealthMonitor = None

# Initialize distributed coordinator (Issue #18)
redis_client: RedisClient = None
distributed_coordinator: DistributedResilienceCoordinator = None


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Startup: Initialize monitoring systems
    Shutdown: Cleanup resources
    """
    # ========== STARTUP ==========
    logger.info("🚀 AstraGuard AI Backend starting...")

    global health_monitor, fallback_manager, component_health, redis_client, distributed_coordinator, recovery_orchestrator

    try:
        # Initialize component health monitor
        component_health = SystemHealthMonitor()

        # Get registered circuit breaker (from anomaly_detector module)
        circuit_breakers = get_all_circuit_breakers()
        model_loader_cb = circuit_breakers.get("anomaly_model_loader")

        # Initialize health monitor (Issue #16)
        health_monitor = HealthMonitor(
            circuit_breaker=model_loader_cb,  # Use registered CB from Issue #14
            retry_tracker=None,  # Will integrate with Retry from Issue #15
            failure_window_seconds=3600,
        )

        # Initialize fallback manager (Issue #16)
        fallback_manager = FallbackManager(
            circuit_breaker=model_loader_cb,  # Use registered CB from Issue #14
            anomaly_detector=None,
            heuristic_detector=None,
        )

        # Initialize recovery orchestrator (Issue #17)
        recovery_orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
            config_path="config/recovery.yaml",
        )

        # Initialize Redis client (Issue #18)
        import os

        redis_url = get_secret("redis_url")
        redis_client = RedisClient(redis_url=redis_url)
        redis_connected = await redis_client.connect()

        if redis_connected:
            # Initialize distributed coordinator (Issue #18)
            distributed_coordinator = DistributedResilienceCoordinator(
                redis_client=redis_client,
                health_monitor=health_monitor,
                recovery_orchestrator=recovery_orchestrator,
                fallback_manager=fallback_manager,
            )
            await distributed_coordinator.startup()
            logger.info("✅ Distributed Resilience Coordinator initialized")
        else:
            logger.warning("⚠️  Redis connection failed, running in standalone mode")

        # Register health monitor with FastAPI
        set_health_monitor(health_monitor)

        # Register core components
        component_health.register_component(
            "anomaly_detector",
            metadata={"version": "1.0", "type": "ml"},
        )
        component_health.register_component(
            "memory_store",
            metadata={"version": "1.0", "type": "cache"},
        )
        component_health.register_component(
            "policy_engine",
            metadata={"version": "1.0", "type": "rule_engine"},
        )

        logger.info("✅ Health Monitor initialized")
        logger.info("✅ Fallback Manager initialized")
        logger.info("✅ Component Health Monitor initialized")

        # Start background health polling task
        health_task = asyncio.create_task(background_health_polling())
        logger.info("✅ Background health polling started")

        # Start recovery orchestrator background task (Issue #17)
        recovery_task = asyncio.create_task(recovery_orchestrator.run())
        logger.info("✅ Recovery Orchestrator started")

        yield  # Application runs here

        # ========== SHUTDOWN ==========
        logger.info("🛑 AstraGuard AI Backend shutting down...")

        # Shutdown distributed coordinator
        if distributed_coordinator:
            await distributed_coordinator.shutdown()
            logger.info("✅ Distributed Coordinator shutdown")

        # Close Redis connection
        if redis_client and redis_client.connected:
            await redis_client.close()
            logger.info("✅ Redis connection closed")

        health_task.cancel()
        recovery_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass

        logger.info("✅ Background tasks cancelled")
        logger.info("✅ Cleanup complete")

    except Exception as e:
        logger.error(f"❌ Startup error: {e}", exc_info=True)
        raise


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


async def background_health_polling():
    """
    Background task for periodic health evaluation and cascade triggering.

    Runs every 10 seconds:
    1. Evaluates current system health
    2. Triggers fallback cascade if needed
    3. Updates metrics
    """
    poll_interval = 10  # seconds

    logger.info(f"Background health polling started (interval: {poll_interval}s)")

    while True:
        try:
            await asyncio.sleep(poll_interval)

            if not health_monitor or not fallback_manager:
                continue

            # Get current health state
            state = await health_monitor.get_comprehensive_state()

            # Evaluate cascade
            new_mode = await fallback_manager.cascade(state)

            # Log if mode changed
            logger.debug(f"Fallback mode: {new_mode.value}")

        except asyncio.CancelledError:
            logger.info("Background health polling stopped")
            break
        except Exception as e:
            logger.error(f"Error in background health polling: {e}", exc_info=True)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="AstraGuard AI Backend",
        description="Reliability suite backend with observability",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========== ROUTES ==========

    # Health monitor routes (Issue #16)
    app.include_router(health_router)

    # External monitoring integrations (Issue #183)
    from backend.monitoring_integrations import router as monitoring_router
    app.include_router(monitoring_router)

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "AstraGuard AI Backend",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health/state",
            "metrics": "/health/metrics",
            "recovery": "/recovery/status",
        }

    # Status endpoint
    @app.get("/status")
    async def status():
        """Get backend status."""
        if not health_monitor:
            return {"status": "initializing"}

        state = await health_monitor.get_comprehensive_state()
        return {
            "status": "running",
            "system_health": state.get("system", {}).get("status"),
            "fallback_mode": (
                fallback_manager.get_mode_string() if fallback_manager else "unknown"
            ),
            "uptime_seconds": state.get("uptime_seconds", 0),
        }

    # Recovery Orchestrator endpoints (Issue #17)
    @app.get("/recovery/status")
    async def recovery_status():
        """Get recovery orchestrator status and metrics."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}

        return {
            "status": "running" if recovery_orchestrator._running else "stopped",
            "metrics": recovery_orchestrator.get_metrics(),
            "cooldowns": recovery_orchestrator.get_cooldown_status(),
            "last_actions": recovery_orchestrator.get_action_history(limit=10),
        }

    @app.get("/recovery/history")
    async def recovery_history(limit: int = 50):
        """Get recovery action history."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}

        return {"actions": recovery_orchestrator.get_action_history(limit=limit)}

    @app.get("/recovery/cooldowns")
    async def recovery_cooldowns():
        """Get current cooldown status for recovery actions."""
        if not recovery_orchestrator:
            return {"error": "Recovery orchestrator not initialized"}

        return recovery_orchestrator.get_cooldown_status()

    # Distributed Coordinator endpoints (Issue #18)
    @app.get("/cluster/consensus")
    async def cluster_consensus():
        """Get quorum-based cluster consensus decision."""
        if not distributed_coordinator:
            return {
                "error": "Distributed coordinator not initialized (standalone mode)"
            }

        consensus = await distributed_coordinator.get_cluster_consensus()
        return consensus.dict()

    @app.get("/cluster/health")
    async def cluster_health():
        """Get aggregated health status of entire cluster."""
        if not distributed_coordinator:
            return {
                "error": "Distributed coordinator not initialized (standalone mode)"
            }

        return await distributed_coordinator.get_cluster_health()

    @app.get("/cluster/metrics")
    async def cluster_metrics():
        """Get distributed coordinator metrics."""
        if not distributed_coordinator:
            return {
                "error": "Distributed coordinator not initialized (standalone mode)"
            }

        return await distributed_coordinator.get_metrics()

    @app.get("/cluster/leader")
    async def cluster_leader():
        """Get current cluster leader."""
        if not distributed_coordinator:
            return {
                "error": "Distributed coordinator not initialized (standalone mode)"
            }

        leader = await redis_client.get_leader()
        return {
            "leader": leader or "NONE",
            "is_leader": distributed_coordinator.is_leader,
            "instance_id": distributed_coordinator.instance_id,
        }

    # ========== CHAOS ENGINEERING ENDPOINTS (Issue #19) ==========

    @app.post("/_chaos/{fault_type}")
    async def inject_chaos(
        fault_type: str,
        _verified: None = Depends(verify_chaos_admin_access),
    ):
        """Inject controlled chaos for resilience testing.

        **ADMIN ONLY** - Requires:
        - ENABLE_CHAOS=true environment variable
        - Valid CHAOS_ADMIN_KEY in request header (X-Chaos-Admin-Key)

        Supported fault types:
        - model_loader: Simulate model loading failure
        - network_latency: Inject network latency
        - redis_failure: Simulate Redis service failure

        Args:
            fault_type: Type of fault to inject

        Returns:
            Status of chaos injection
        """
        from backend.chaos_engine import ChaosEngine

        try:
            logger.info(f"🧪 Chaos injection starting: {fault_type}")
            engine = ChaosEngine()
            await engine.startup()

            result = await engine.inject_faults(fault_type, duration_seconds=30)

            await engine.shutdown()

            if result:
                logger.info(f"✅ Chaos injection completed: {fault_type}")
                return {
                    "status": "success",
                    "fault_type": fault_type,
                    "duration_seconds": 30,
                }
            else:
                logger.warning(f"⚠️  Chaos injection failed: {fault_type}")
                return {
                    "status": "failed",
                    "fault_type": fault_type,
                    "error": "Injection did not recover within timeout",
                }
        except Exception as e:
            logger.error(f"❌ Chaos injection error: {e}", exc_info=True)
            return {"status": "error", "fault_type": fault_type, "error": str(e)}

    # ========== ERROR HANDLERS ==========

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        """Handle general exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return {
            "error": "Internal server error",
            "detail": str(exc),
        }

    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

app = create_app()

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info("Starting AstraGuard AI Backend...")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
