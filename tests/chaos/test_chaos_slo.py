"""
Chaos Tests for SLO Maintenance

Validates that Service Level Objectives are maintained during chaos:
- Error rate SLO
- Latency SLO
- Availability SLO
- Composite SLO validation
"""

import pytest
import asyncio
import logging

from chaos.actions.failure_injection import inject_model_loader_failure, stop_failure_injection
from chaos.actions.network_chaos import inject_latency, remove_latency
from chaos.actions.service_chaos import stop_service, start_service
from chaos.validation.slo_validator import SLOValidator

logger = logging.getLogger(__name__)


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_error_rate_slo():
    """
    Test that error rate SLO is maintained during chaos.
    
    Acceptance Criteria:
    - Error rate remains below 1% during failures
    - Error rate returns to normal after recovery
    """
    slo_validator = SLOValidator(max_error_rate=0.01)
    
    # Inject moderate failures
    await inject_model_loader_failure(duration_seconds=20, failure_rate=0.3)
    
    # Monitor error rate during chaos
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=25)
    
    # Stop failures
    await stop_failure_injection()
    
    # Assertions
    assert slo_result.error_rate_compliant, \
        f"Error rate SLO violated: {slo_result.error_rate:.2%} > 1%"
    assert slo_result.error_rate < 0.01, \
        f"Error rate too high: {slo_result.error_rate:.2%}"
    
    logger.info(f"Error rate SLO test passed: {slo_result.error_rate:.2%}")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_latency_slo():
    """
    Test that latency SLO is maintained during chaos.
    
    Acceptance Criteria:
    - P99 latency remains below 500ms during network chaos
    - Latency returns to normal after chaos stops
    """
    slo_validator = SLOValidator(max_p99_latency=0.5)  # 500ms
    
    # Inject network latency
    await inject_latency(duration_seconds=20, latency_ms=200, jitter_ms=50)
    
    # Monitor latency during chaos
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=25)
    
    # Remove latency
    await remove_latency()
    
    # Assertions
    assert slo_result.latency_compliant, \
        f"Latency SLO violated: P99={slo_result.p99_latency:.3f}s > 500ms"
    assert slo_result.p99_latency < 0.5, \
        f"P99 latency too high: {slo_result.p99_latency:.3f}s"
    
    logger.info(f"Latency SLO test passed: P99={slo_result.p99_latency:.3f}s")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_availability_slo():
    """
    Test that availability SLO is maintained during chaos.
    
    Acceptance Criteria:
    - Availability remains above 99.9% during failures
    - No extended outages
    """
    slo_validator = SLOValidator(min_availability=0.999)
    
    # Inject failures
    await inject_model_loader_failure(duration_seconds=15, failure_rate=0.2)
    
    # Monitor availability
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=20)
    
    # Stop failures
    await stop_failure_injection()
    
    # Assertions
    assert slo_result.availability_compliant, \
        f"Availability SLO violated: {slo_result.availability:.3%} < 99.9%"
    assert slo_result.availability >= 0.999, \
        f"Availability too low: {slo_result.availability:.3%}"
    
    logger.info(f"Availability SLO test passed: {slo_result.availability:.3%}")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_composite_slo():
    """
    Test that all SLOs are maintained simultaneously during chaos.
    
    Acceptance Criteria:
    - All SLOs (error rate, latency, availability) maintained
    - Composite SLO score above threshold
    """
    slo_validator = SLOValidator(
        max_error_rate=0.01,
        max_p99_latency=0.5,
        min_availability=0.999,
    )
    
    # Inject multiple chaos types
    await inject_model_loader_failure(duration_seconds=15, failure_rate=0.2)
    await inject_latency(duration_seconds=15, latency_ms=100, jitter_ms=20)
    
    # Monitor all SLOs
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=20)
    
    # Stop chaos
    await stop_failure_injection()
    await remove_latency()
    
    # Assertions - all SLOs must be maintained
    assert slo_result.slo_maintained, \
        f"Composite SLO violated:\\n" \
        f"  Error rate: {slo_result.error_rate:.2%} (compliant: {slo_result.error_rate_compliant})\\n" \
        f"  Latency: {slo_result.p99_latency:.3f}s (compliant: {slo_result.latency_compliant})\\n" \
        f"  Availability: {slo_result.availability:.3%} (compliant: {slo_result.availability_compliant})"
    
    assert slo_result.error_rate_compliant
    assert slo_result.latency_compliant
    assert slo_result.availability_compliant
    
    logger.info("Composite SLO test passed - all SLOs maintained")


@pytest.mark.chaos
@pytest.mark.asyncio
async def test_slo_recovery():
    """
    Test that SLOs are restored after chaos stops.
    
    Acceptance Criteria:
    - SLOs may degrade during chaos
    - SLOs return to normal levels after recovery
    """
    slo_validator = SLOValidator()
    
    # Phase 1: Normal operation - establish baseline
    logger.info("Phase 1: Establishing baseline")
    baseline = await slo_validator.validate_slo_compliance(duration_seconds=10)
    
    # Phase 2: Chaos - SLOs may degrade
    logger.info("Phase 2: Injecting chaos")
    await inject_model_loader_failure(duration_seconds=15, failure_rate=0.5)
    await asyncio.sleep(10)
    
    # Phase 3: Recovery - SLOs should restore
    logger.info("Phase 3: Stopping chaos, measuring recovery")
    await stop_failure_injection()
    
    # Wait for recovery
    await asyncio.sleep(10)
    
    # Measure post-chaos SLOs
    post_chaos = await slo_validator.validate_slo_compliance(duration_seconds=10)
    
    # Assertions - post-chaos should match baseline
    assert post_chaos.error_rate <= baseline.error_rate * 1.5, \
        f"Error rate did not recover: {post_chaos.error_rate:.2%} vs baseline {baseline.error_rate:.2%}"
    assert post_chaos.p99_latency <= baseline.p99_latency * 1.5, \
        f"Latency did not recover: {post_chaos.p99_latency:.3f}s vs baseline {baseline.p99_latency:.3f}s"
    assert post_chaos.availability >= baseline.availability * 0.99, \
        f"Availability did not recover: {post_chaos.availability:.3%} vs baseline {baseline.availability:.3%}"
    
    logger.info("SLO recovery test passed")


@pytest.mark.chaos
@pytest.mark.slow
@pytest.mark.asyncio
async def test_slo_under_cascading_failures():
    """
    Test SLO maintenance under cascading failure scenarios.
    
    Acceptance Criteria:
    - Critical SLOs maintained even during cascading failures
    - Degradation is graceful and bounded
    """
    slo_validator = SLOValidator(
        max_error_rate=0.05,  # Relaxed threshold for cascading failures
        max_p99_latency=1.0,  # Relaxed threshold
        min_availability=0.99,  # Relaxed threshold
    )
    
    # Trigger cascading failures
    await stop_service("redis", duration_seconds=25)
    await inject_model_loader_failure(duration_seconds=25, failure_rate=0.3)
    await inject_latency(duration_seconds=25, latency_ms=300, jitter_ms=50)
    
    # Monitor SLOs during cascading chaos
    slo_result = await slo_validator.validate_slo_compliance(duration_seconds=30)
    
    # Stop all chaos
    await start_service("redis")
    await stop_failure_injection()
    await remove_latency()
    
    # Assertions - even with relaxed thresholds, SLOs should be maintained
    assert slo_result.error_rate < 0.05, \
        f"Error rate too high under cascading failures: {slo_result.error_rate:.2%}"
    assert slo_result.p99_latency < 1.0, \
        f"Latency too high under cascading failures: {slo_result.p99_latency:.3f}s"
    assert slo_result.availability >= 0.99, \
        f"Availability too low under cascading failures: {slo_result.availability:.3%}"
    
    logger.info(f"Cascading failure SLO test passed: error_rate={slo_result.error_rate:.2%}, "
                f"latency={slo_result.p99_latency:.3f}s, availability={slo_result.availability:.3%}")
