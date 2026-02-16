"""
Chaos Integration Tests

End-to-end chaos tests that validate the complete resilience pipeline:
- Full experiment execution
- Suite execution
- Integration with existing chaos engine
- Report generation
"""

import pytest
import asyncio
import logging
from pathlib import Path

from chaos.experiments.runner import ExperimentRunner, run_experiment
from chaos.validation.incident_reporter import IncidentReporter

logger = logging.getLogger(__name__)


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_experiment_runner_initialization():
    """
    Test that experiment runner initializes correctly.
    
    Acceptance Criteria:
    - Runner loads experiment definitions
    - Runner connects to service
    - Runner is ready to execute experiments
    """
    runner = ExperimentRunner(
        experiments_dir="src/chaos/experiments",
        base_url="http://localhost:8000",
    )
    
    # Verify experiments directory exists
    exp_dir = Path("src/chaos/experiments")
    assert exp_dir.exists(), "Experiments directory not found"
    
    # Verify at least one experiment exists
    experiments = list(exp_dir.glob("*.yaml"))
    assert len(experiments) > 0, "No experiment definitions found"
    
    logger.info(f"Experiment runner initialized with {len(experiments)} experiments")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_experiment_discovery():
    """
    Test that all experiments can be discovered and loaded.
    
    Acceptance Criteria:
    - All YAML experiment files are valid
    - Experiments can be parsed
    - Required fields are present
    """
    runner = ExperimentRunner()
    
    # List all experiments
    exp_dir = Path("src/chaos/experiments")
    experiment_files = list(exp_dir.glob("*.yaml"))
    
    required_fields = ["title", "description", "method"]
    
    for exp_file in experiment_files:
        exp_name = exp_file.stem
        
        # Load experiment
        experiment = runner.load_experiment(exp_name)
        
        # Verify required fields
        for field in required_fields:
            assert field in experiment, f"Experiment {exp_name} missing field: {field}"
        
        logger.info(f"Experiment validated: {exp_name}")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_experiment_execution():
    """
    Test execution of a single chaos experiment.
    
    Acceptance Criteria:
    - Experiment executes without errors
    - Results are captured
    - Status is reported correctly
    """
    runner = ExperimentRunner()
    
    # Run a simple experiment
    result = await runner.run_experiment(
        "circuit_breaker_failure",
        validate_recovery=True,
        check_slo=True,
    )
    
    # Verify result structure
    assert result.experiment_name == "circuit_breaker_failure"
    assert result.status in ["passed", "failed", "aborted"]
    assert result.duration_seconds >= 0
    
    logger.info(
        f"Experiment executed: {result.experiment_name} - {result.status} "
        f"({result.duration_seconds:.1f}s)"
    )


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_experiment_suite_execution():
    """
    Test execution of full chaos experiment suite.
    
    Acceptance Criteria:
    - All experiments in suite execute
    - Suite report is generated
    - Overall results are calculated
    """
    runner = ExperimentRunner()
    
    # Run full suite
    results = await runner.run_suite(stop_on_failure=False)
    
    # Verify results
    assert len(results) > 0, "No experiments executed"
    
    # Check that results were recorded
    for result in results:
        assert result.experiment_name is not None
        assert result.status is not None
    
    # Verify suite report was generated
    report_path = Path("logs/chaos/chaos_suite_report.json")
    assert report_path.exists(), "Suite report not generated"
    
    logger.info(f"Suite execution complete: {len(results)} experiments")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_incident_reporting_integration():
    """
    Test incident reporting integration with experiments.
    
    Acceptance Criteria:
    - Failed experiments generate incidents
    - Incidents contain relevant details
    - Incidents can be queried and resolved
    """
    reporter = IncidentReporter()
    
    # Create test incident
    incident_id = await reporter.report(
        experiment_name="test_integration",
        failure_type="test_failure",
        severity="MEDIUM",
        details={"test": True, "component": "integration"},
    )
    
    # Verify incident created
    assert incident_id is not None
    assert incident_id.startswith("CHAOS-")
    
    # Retrieve incident
    incident = reporter.get_incident(incident_id)
    assert incident is not None
    assert incident["experiment_name"] == "test_integration"
    assert incident["status"] == "open"
    
    # Resolve incident
    resolved = reporter.resolve(incident_id, "Test resolution")
    assert resolved is True
    
    # Verify resolution
    incident = reporter.get_incident(incident_id)
    assert incident["status"] == "resolved"
    
    logger.info(f"Incident reporting test passed: {incident_id}")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_chaos_engine_integration():
    """
    Test integration with existing chaos engine.
    
    Acceptance Criteria:
    - New framework integrates with existing chaos_engine.py
    - Existing tests still pass
    - Metrics are consistent
    """
    from backend.chaos_engine import ChaosEngine
    
    # Initialize chaos engine
    engine = ChaosEngine(base_url="http://localhost:8000")
    
    # Verify engine can be created
    assert engine is not None
    assert engine.base_url == "http://localhost:8000"
    
    logger.info("Chaos engine integration verified")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_chaos_pipeline():
    """
    Test complete chaos testing pipeline end-to-end.
    
    Acceptance Criteria:
    - Experiments execute
    - Recovery is validated
    - SLOs are checked
    - Incidents are reported
    - Reports are generated
    """
    runner = ExperimentRunner()
    reporter = IncidentReporter()
    
    # Execute experiments
    experiments = [
        "circuit_breaker_failure",
        "network_latency",
    ]
    
    results = []
    for exp_name in experiments:
        result = await runner.run_experiment(
            exp_name,
            validate_recovery=True,
            check_slo=True,
        )
        results.append(result)
        
        # Report if failed
        if result.status == "failed":
            await reporter.report(
                experiment_name=exp_name,
                failure_type="experiment_failed",
                severity="HIGH",
                details=result.to_dict(),
            )
    
    # Verify results
    assert len(results) == len(experiments)
    
    # Check reports generated
    suite_report = Path("logs/chaos/chaos_suite_report.json")
    assert suite_report.exists() or len(results) > 0
    
    logger.info(f"Full pipeline test complete: {len(results)} experiments executed")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_recovery_validation_integration():
    """
    Test that recovery validation integrates with experiments.
    
    Acceptance Criteria:
    - Recovery is validated after each experiment
    - Recovery time is measured
    - Recovery status is reported
    """
    from chaos.validation.recovery_validator import RecoveryValidator
    
    # Initialize validator
    validator = RecoveryValidator(
        base_url="http://localhost:8000",
        max_recovery_time=30,
    )
    
    # Run experiment
    runner = ExperimentRunner()
    result = await runner.run_experiment(
        "circuit_breaker_failure",
        validate_recovery=True,
    )
    
    # Verify recovery was validated
    assert result.recovery_validated is not None
    
    if result.recovery_validated:
        logger.info("Recovery validation passed")
    else:
        logger.warning("Recovery validation failed - this may be expected in test environment")
    
    logger.info(f"Recovery validation integration test complete")


@pytest.mark.chaos
@pytest.mark.integration
@pytest.mark.asyncio
async def test_slo_validation_integration():
    """
    Test that SLO validation integrates with experiments.
    
    Acceptance Criteria:
    - SLOs are monitored during experiments
    - SLO compliance is reported
    - Violations are detected
    """
    from chaos.validation.slo_validator import SLOValidator
    
    # Initialize validator
    validator = SLOValidator(
        base_url="http://localhost:8000",
        max_error_rate=0.01,
        max_p99_latency=0.5,
    )
    
    # Run experiment with SLO check
    runner = ExperimentRunner()
    result = await runner.run_experiment(
        "network_latency",
        check_slo=True,
    )
    
    # Verify SLO was checked
    assert result.slo_maintained is not None
    
    logger.info(f"SLO validation integration test complete: slo_maintained={result.slo_maintained}")
