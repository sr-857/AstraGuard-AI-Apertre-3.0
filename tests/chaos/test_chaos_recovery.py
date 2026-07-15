"""
Chaos Tests for Recovery Validation

Validates system recovery capabilities:
- Recovery orchestrator activation
- Automatic healing actions
- Recovery time objectives
- Graceful degradation and recovery
"""

import pytest
import asyncio
import logging

from chaos.actions.service_chaos import stop_service, start_service
from chaos.actions.resource_chaos import consume_memory, release_resources
from chaos.validation.recovery_validator import RecoveryValidator
from chaos.validation.incident_reporter import IncidentReporter

logger = logging.getLogger(__name__)


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_recovery_orchestrator_activation():
    """
    Test that recovery orchestrator activates during failures.
    
    Acceptance Criteria:
    - Recovery orchestrator detects failures
    - Recovery actions are triggered
    - System eventually recovers
    """
    # Stop a critical service
    await stop_service("redis", duration_seconds=20)
    
    # Wait for detection
    await asyncio.sleep(10)
    
    # Validate recovery
    validator = RecoveryValidator(max_recovery_time=45)
    result = await validator.validate_recovery()
    
    # Restart service (in case auto-restart didn't work)
    await start_service("redis")
    
    # Assertions
    assert result.recovered, \
        f"Service did not recover: errors={result.errors}"
    assert result.recovery_time_seconds < 45, \
        f"Recovery took too long: {result.recovery_time_seconds}s"
    
    logger.info(f"Recovery orchestrator test passed: {result.recovery_time_seconds:.1f}s")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_automatic_service_recovery():
    """
    Test automatic recovery when service is stopped.
    
    Acceptance Criteria:
    - System detects service unavailability
    - Fallback mode activates
    - Service recovers automatically when restarted
    """
    # Stop service with auto-restart
    await stop_service("redis", duration_seconds=15)
    
    # Wait for degradation
    await asyncio.sleep(8)
    
    # Check system degraded
    validator = RecoveryValidator()
    result = await validator.validate_recovery(timeout=5)
    
    assert result.health_status == "DEGRADED", \
        f"Expected DEGRADED, got {result.health_status}"
    
    # Wait for auto-recovery
    result = await validator.validate_recovery(timeout=30)
    
    # Assertions
    assert result.recovered, "Service did not auto-recover"
    assert result.health_status in ["HEALTHY", "DEGRADED"], \
        f"Unexpected final status: {result.health_status}"
    
    logger.info(f"Auto-recovery test passed: {result.recovery_time_seconds:.1f}s")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_recovery_time_objective():
    """
    Test that recovery meets time objectives.
    
    Acceptance Criteria:
    - Recovery completes within RTO (Recovery Time Objective)
    - RTO for critical services: 30 seconds
    """
    RTO_SECONDS = 30
    
    # Trigger failure
    await stop_service("redis", duration_seconds=10)
    
    # Measure recovery time
    start_time = asyncio.get_event_loop().time()
    
    validator = RecoveryValidator(max_recovery_time=RTO_SECONDS + 10)
    result = await validator.validate_recovery()
    
    elapsed = asyncio.get_event_loop().time() - start_time
    
    # Ensure service is started
    await start_service("redis")
    
    # Assertions
    assert result.recovered, f"Service did not recover within {RTO_SECONDS + 10}s"
    assert elapsed <= RTO_SECONDS, \
        f"Recovery time {elapsed:.1f}s exceeded RTO of {RTO_SECONDS}s"
    
    logger.info(f"RTO test passed: {elapsed:.1f}s (target: {RTO_SECONDS}s)")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_resource_pressure_recovery():
    """
    Test recovery from resource pressure.
    
    Acceptance Criteria:
    - System detects resource exhaustion
    - Safe mode activates
    - System recovers when resources freed
    """
    # Consume resources
    await consume_memory(duration_seconds=20, memory_mb=256)
    
    # Wait for detection
    await asyncio.sleep(10)
    
    # Check system entered safe mode
    validator = RecoveryValidator()
    result = await validator.validate_recovery(timeout=5)
    
    assert result.fallback_mode == "SAFE", \
        f"Expected SAFE mode, got {result.fallback_mode}"
    
    # Release resources
    await release_resources()
    
    # Wait for recovery
    await asyncio.sleep(10)
    
    # Validate recovery
    result = await validator.validate_recovery(timeout=20)
    
    # Assertions
    assert result.recovered, "System did not recover from resource pressure"
    assert result.fallback_mode == "PRIMARY", \
        f"Expected PRIMARY mode after recovery, got {result.fallback_mode}"
    
    logger.info(f"Resource pressure recovery test passed")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_incident_reporting():
    """
    Test that incidents are properly reported during chaos.
    
    Acceptance Criteria:
    - Incidents are created for failures
    - Incident contains relevant details
    - Incident can be retrieved and resolved
    """
    reporter = IncidentReporter()
    
    # Simulate a failure scenario
    await stop_service("redis", duration_seconds=5)
    await asyncio.sleep(3)
    
    # Report incident
    incident_id = await reporter.report(
        experiment_name="test_recovery",
        failure_type="service_unavailable",
        severity="HIGH",
        details={"service": "redis", "duration": 5},
    )
    
    # Restart service
    await start_service("redis")
    
    # Verify incident was created
    incident = reporter.get_incident(incident_id)
    assert incident is not None, "Incident was not created"
    assert incident["experiment_name"] == "test_recovery"
    assert incident["severity"] == "HIGH"
    assert incident["status"] == "open"
    
    # Resolve incident
    resolved = reporter.resolve(incident_id, "Service recovered automatically")
    assert resolved, "Failed to resolve incident"
    
    # Verify resolution
    incident = reporter.get_incident(incident_id)
    assert incident["status"] == "resolved"
    assert incident["resolution"] == "Service recovered automatically"
    
    logger.info(f"Incident reporting test passed: {incident_id}")


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.asyncio
async def test_cascading_failure_recovery():
    """
    Test recovery from cascading failures.
    
    Acceptance Criteria:
    - System handles multiple simultaneous failures
    - Recovery orchestrator manages dependencies
    - Full system recovery achieved
    """
    validator = RecoveryValidator(max_recovery_time=90)
    
    # Trigger multiple failures
    await stop_service("redis", duration_seconds=25)
    await consume_memory(duration_seconds=25, memory_mb=128)
    
    # Wait for cascading effects
    await asyncio.sleep(15)
    
    # Check system is in safe mode
    result = await validator.validate_recovery(timeout=5)
    assert result.fallback_mode == "SAFE", \
        f"Expected SAFE mode for cascading failures, got {result.fallback_mode}"
    
    # Release resources and restart service
    await release_resources()
    await start_service("redis")
    
    # Wait for full recovery
    result = await validator.validate_recovery(timeout=60)
    
    # Assertions
    assert result.recovered, "System did not recover from cascading failures"
    assert result.health_status == "HEALTHY", \
        f"Expected HEALTHY after recovery, got {result.health_status}"
    assert result.fallback_mode == "PRIMARY", \
        f"Expected PRIMARY mode, got {result.fallback_mode}"
    
    logger.info(f"Cascading failure recovery test passed: {result.recovery_time_seconds:.1f}s")
