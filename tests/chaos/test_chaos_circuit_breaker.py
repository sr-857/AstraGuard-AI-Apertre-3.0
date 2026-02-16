"""
Chaos Tests for Circuit Breaker Resilience

Validates circuit breaker behavior under failure conditions:
- Opens after threshold failures
- Allows graceful degradation
- Recovers when failures stop
- Maintains SLOs during chaos
"""

import pytest
import asyncio
import logging

from chaos.actions.failure_injection import (
    inject_model_loader_failure,
    stop_failure_injection,
)
from chaos.validation.recovery_validator import RecoveryValidator
from chaos.validation.slo_validator import SLOValidator

logger = logging.getLogger(__name__)


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_failures():
    """
    Test that circuit breaker opens after repeated failures.
    
    Acceptance Criteria:
    - Circuit breaker transitions to OPEN after threshold failures
    - System status becomes DEGRADED
    """
    # Inject failures
    await inject_model_loader_failure(duration_seconds=15, failure_rate=0.9)
    
    # Wait for circuit breaker to open
    await asyncio.sleep(10)
    
    # Validate circuit breaker opened
    validator = RecoveryValidator()
    result = await validator.validate_recovery(timeout=20)
    
    # Stop failures
    await stop_failure_injection()
    
    # Assertions
    assert result.circuit_breaker_state in ["OPEN", "HALF_OPEN"], \
        f"Expected circuit breaker OPEN or HALF_OPEN, got {result.circuit_breaker_state}"
    assert result.health_status in ["DEGRADED", "HEALTHY"], \
        f"Expected DEGRADED or HEALTHY, got {result.health_status}"
    
    logger.info(f"Circuit breaker test passed: state={result.circuit_breaker_state}")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_circuit_breaker_recovery():
    """
    Test that circuit breaker recovers when failures stop.
    
    Acceptance Criteria:
    - Circuit breaker transitions from OPEN to HALF_OPEN to CLOSED
    - System recovers within max_recovery_time
    """
    # First, trigger circuit breaker to open
    await inject_model_loader_failure(duration_seconds=10, failure_rate=1.0)
    await asyncio.sleep(8)
    
    # Stop failures to allow recovery
    await stop_failure_injection()
    
    # Validate recovery
    validator = RecoveryValidator(max_recovery_time=30)
    result = await validator.validate_recovery()
    
    # Assertions
    assert result.recovered, \
        f"Service did not recover: errors={result.errors}"
    assert result.circuit_breaker_state in ["CLOSED", "HALF_OPEN"], \
        f"Expected CLOSED or HALF_OPEN, got {result.circuit_breaker_state}"
    assert result.recovery_time_seconds < 30, \
        f"Recovery took too long: {result.recovery_time_seconds}s"
    
    logger.info(f"Circuit breaker recovery test passed: {result.recovery_time_seconds:.1f}s")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_circuit_breaker_slo_maintenance():
    """
    Test that SLOs are maintained during circuit breaker chaos.
    
    Acceptance Criteria:
    - Error rate remains below threshold during chaos
    - P99 latency remains acceptable
    """
    # Start SLO validation
    slo_validator = SLOValidator(max_error_rate=0.05, max_p99_latency=1.0)
    
    # Inject failures in background
    await inject_model_loader_failure(duration_seconds=20, failure_rate=0.5)
    
    # Validate SLOs during chaos
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=25)
    
    # Stop failures
    await stop_failure_injection()
    
    # Assertions
    assert slo_result.error_rate_compliant, \
        f"Error rate exceeded threshold: {slo_result.error_rate:.2%}"
    assert slo_result.latency_compliant, \
        f"P99 latency exceeded threshold: {slo_result.p99_latency:.3f}s"
    
    logger.info(
        f"SLO maintenance test passed: "
        f"error_rate={slo_result.error_rate:.2%}, "
        f"p99={slo_result.p99_latency:.3f}s"
    )


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_circuit_breaker_graceful_degradation():
    """
    Test that system degrades gracefully when circuit breaker opens.
    
    Acceptance Criteria:
    - System does not crash
    - Fallback mode activates appropriately
    - Service remains partially functional
    """
    # Inject failures
    await inject_model_loader_failure(duration_seconds=15, failure_rate=0.8)
    
    # Wait for degradation
    await asyncio.sleep(10)
    
    # Validate graceful degradation
    validator = RecoveryValidator()
    result = await validator.validate_recovery(timeout=5)
    
    # Stop failures
    await stop_failure_injection()
    
    # Assertions - system should be DEGRADED but not FAILED
    assert result.health_status != "FAILED", \
        "System crashed instead of degrading gracefully"
    assert result.health_status in ["DEGRADED", "HEALTHY"], \
        f"Unexpected health status: {result.health_status}"
    
    logger.info(f"Graceful degradation test passed: status={result.health_status}")


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.asyncio
async def test_circuit_breaker_full_lifecycle():
    """
    Test complete circuit breaker lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
    
    This is a comprehensive test that validates the entire circuit breaker state machine.
    """
    validator = RecoveryValidator(max_recovery_time=60)
    
    # Phase 1: Normal operation (CLOSED)
    logger.info("Phase 1: Verifying normal operation")
    result = await validator.validate_recovery(timeout=5)
    assert result.circuit_breaker_state == "CLOSED", \
        f"Expected CLOSED initially, got {result.circuit_breaker_state}"
    
    # Phase 2: Trigger failures (CLOSED -> OPEN)
    logger.info("Phase 2: Triggering failures")
    await inject_model_loader_failure(duration_seconds=20, failure_rate=1.0)
    await asyncio.sleep(15)
    
    # Verify OPEN state
    result = await validator.validate_recovery(timeout=5)
    assert result.circuit_breaker_state == "OPEN", \
        f"Expected OPEN after failures, got {result.circuit_breaker_state}"
    
    # Phase 3: Stop failures (OPEN -> HALF_OPEN -> CLOSED)
    logger.info("Phase 3: Stopping failures, waiting for recovery")
    await stop_failure_injection()
    
    # Wait for recovery
    result = await validator.validate_recovery(timeout=45)
    
    # Verify recovery
    assert result.recovered, "Service did not recover"
    assert result.circuit_breaker_state == "CLOSED", \
        f"Expected CLOSED after recovery, got {result.circuit_breaker_state}"
    
    logger.info("Full lifecycle test passed: CLOSED -> OPEN -> CLOSED")
