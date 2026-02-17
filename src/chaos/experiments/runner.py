"""
Chaos Experiment Runner for AstraGuard AI

Executes chaos experiments using Chaos Toolkit and validates system resilience.
"""

import asyncio
import logging
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

from chaos.lib.run import run_experiment as ct_run_experiment
from chaos.lib.experiment import Experiment
from chaos.lib.configuration import Configuration

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Result of a chaos experiment execution."""
    experiment_name: str
    status: str  # "passed", "failed", "aborted"
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    steady_state_met: bool
    probes_results: List[Dict[str, Any]]
    recovery_validated: bool
    slo_maintained: bool
    incident_id: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "experiment_name": self.experiment_name,
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "steady_state_met": self.steady_state_met,
            "probes_results": self.probes_results,
            "recovery_validated": self.recovery_validated,
            "slo_maintained": self.slo_maintained,
            "incident_id": self.incident_id,
            "error_message": self.error_message,
        }


class ExperimentRunner:
    """
    Runner for chaos experiments with AstraGuard-specific validation.
    
    Features:
    - Load and execute YAML experiment definitions
    - Validate service recovery after failures
    - Check SLO maintenance during chaos
    - Generate incident reports for failures
    """

    def __init__(
        self,
        experiments_dir: str = "src/chaos/experiments",
        base_url: str = "http://localhost:8000",
    ):
        """
        Initialize experiment runner.
        
        Args:
            experiments_dir: Directory containing experiment YAML files
            base_url: Base URL of AstraGuard service
        """
        self.experiments_dir = Path(experiments_dir)
        self.base_url = base_url
        self.results: List[ExperimentResult] = []
        
        logger.info(f"ExperimentRunner initialized (experiments: {experiments_dir})")

    def load_experiment(self, experiment_name: str) -> Dict[str, Any]:
        """
        Load experiment definition from YAML file.
        
        Args:
            experiment_name: Name of experiment (without .yaml extension)
            
        Returns:
            Experiment definition dictionary
        """
        experiment_path = self.experiments_dir / f"{experiment_name}.yaml"
        
        if not experiment_path.exists():
            raise FileNotFoundError(f"Experiment not found: {experiment_path}")
        
        with open(experiment_path, "r") as f:
            experiment = yaml.safe_load(f)
        
        logger.info(f"Loaded experiment: {experiment_name}")
        return experiment

    async def run_experiment(
        self,
        experiment_name: str,
        validate_recovery: bool = True,
        check_slo: bool = True,
    ) -> ExperimentResult:
        """
        Execute a chaos experiment with validation.
        
        Args:
            experiment_name: Name of experiment to run
            validate_recovery: Whether to validate service recovery
            check_slo: Whether to check SLO maintenance
            
        Returns:
            ExperimentResult with execution details
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting chaos experiment: {experiment_name}")
        
        try:
            # Load experiment definition
            experiment_def = self.load_experiment(experiment_name)
            
            # Execute with Chaos Toolkit
            experiment = Experiment(experiment_def)
            config = Configuration()
            
            # Run the experiment
            journal = ct_run_experiment(experiment, config)
            
            # Parse results
            status = journal.get("status", "failed")
            steady_state_met = status == "passed"
            
            # Validate recovery if requested
            recovery_validated = True
            if validate_recovery and status != "aborted":
                recovery_validated = await self._validate_recovery()
            
            # Check SLOs if requested
            slo_maintained = True
            if check_slo and status != "aborted":
                slo_maintained = await self._check_slo_compliance()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Generate incident report if experiment failed
            incident_id = None
            if status == "failed":
                incident_id = await self._generate_incident_report(
                    experiment_name, journal
                )
            
            result = ExperimentResult(
                experiment_name=experiment_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                steady_state_met=steady_state_met,
                probes_results=journal.get("probes", []),
                recovery_validated=recovery_validated,
                slo_maintained=slo_maintained,
                incident_id=incident_id,
            )
            
            self.results.append(result)
            
            logger.info(
                f"Experiment {experiment_name} completed: {status} "
                f"(recovery: {recovery_validated}, slo: {slo_maintained})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Experiment {experiment_name} failed with error: {e}")
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            result = ExperimentResult(
                experiment_name=experiment_name,
                status="failed",
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                steady_state_met=False,
                probes_results=[],
                recovery_validated=False,
                slo_maintained=False,
                error_message=str(e),
            )
            
            self.results.append(result)
            return result

    async def run_suite(
        self,
        experiments: Optional[List[str]] = None,
        stop_on_failure: bool = False,
    ) -> List[ExperimentResult]:
        """
        Run a suite of chaos experiments.
        
        Args:
            experiments: List of experiment names (None = all experiments)
            stop_on_failure: Stop suite execution on first failure
            
        Returns:
            List of ExperimentResult for all executed experiments
        """
        if experiments is None:
            # Discover all experiments
            experiments = [
                p.stem for p in self.experiments_dir.glob("*.yaml")
                if p.stem != "experiment_template"
            ]
        
        logger.info(f"Running chaos suite with {len(experiments)} experiments")
        
        results = []
        for exp_name in experiments:
            result = await self.run_experiment(exp_name)
            results.append(result)
            
            if stop_on_failure and result.status == "failed":
                logger.warning(f"Stopping suite due to failure in {exp_name}")
                break
        
        # Generate suite report
        await self._generate_suite_report(results)
        
        return results

    async def _validate_recovery(self) -> bool:
        """Validate that service has recovered after chaos injection."""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                async with session.get(
                    f"{self.base_url}/health/state",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return False
                    
                    state = await resp.json()
                    system_status = state.get("system", {}).get("status")
                    
                    # Service is recovered if healthy or degraded (not failed)
                    return system_status in ["HEALTHY", "DEGRADED"]
                    
        except Exception as e:
            logger.error(f"Recovery validation failed: {e}")
            return False

    async def _check_slo_compliance(self) -> bool:
        """Check if SLOs were maintained during chaos."""
        import aiohttp
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get metrics from Prometheus endpoint
                async with session.get(
                    f"{self.base_url}/health/metrics",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return False
                    
                    metrics_text = await resp.text()
                    
                    # Check key SLO indicators
                    # - Error rate < 1%
                    # - P99 latency < 500ms
                    # - Availability > 99.9%
                    
                    # Parse metrics (simplified check)
                    error_rate_ok = "astra_error_rate" not in metrics_text or \
                        self._parse_metric_value(metrics_text, "astra_error_rate") < 0.01
                    
                    latency_ok = "astra_latency_p99" not in metrics_text or \
                        self._parse_metric_value(metrics_text, "astra_latency_p99") < 0.5
                    
                    return error_rate_ok and latency_ok
                    
        except Exception as e:
            logger.error(f"SLO check failed: {e}")
            return False

    def _parse_metric_value(self, metrics_text: str, metric_name: str) -> float:
        """Parse metric value from Prometheus text format."""
        for line in metrics_text.split("\n"):
            if line.startswith(metric_name):
                # Extract value from line like: metric_name{label="value"} 0.123
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return float(parts[-1])
                    except ValueError:
                        pass
        return 0.0

    async def _generate_incident_report(
        self,
        experiment_name: str,
        journal: Dict[str, Any],
    ) -> str:
        """Generate incident report for failed experiment."""
        from chaos.validation.incident_reporter import IncidentReporter
        
        reporter = IncidentReporter()
        
        incident_id = await reporter.report(
            experiment_name=experiment_name,
            failure_type=journal.get("fault_type", "unknown"),
            severity="HIGH" if journal.get("deviated", False) else "MEDIUM",
            details=journal,
        )
        
        return incident_id

    async def _generate_suite_report(self, results: List[ExperimentResult]) -> str:
        """Generate summary report for experiment suite."""
        report_path = Path("logs/chaos/chaos_suite_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_experiments": len(results),
            "passed": sum(1 for r in results if r.status == "passed"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "aborted": sum(1 for r in results if r.status == "aborted"),
            "recovery_success_rate": sum(
                1 for r in results if r.recovery_validated
            ) / len(results) if results else 0,
            "slo_compliance_rate": sum(
                1 for r in results if r.slo_maintained
            ) / len(results) if results else 0,
            "experiments": [r.to_dict() for r in results],
        }
        
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Suite report saved: {report_path}")
        return str(report_path)

    def get_results(self) -> List[ExperimentResult]:
        """Get all experiment results."""
        return self.results.copy()


# Convenience function for standalone execution
async def run_experiment(
    experiment_name: str,
    experiments_dir: str = "src/chaos/experiments",
    base_url: str = "http://localhost:8000",
) -> ExperimentResult:
    """
    Run a single chaos experiment.
    
    Args:
        experiment_name: Name of experiment to run
        experiments_dir: Directory containing experiment files
        base_url: Base URL of AstraGuard service
        
    Returns:
        ExperimentResult
    """
    runner = ExperimentRunner(experiments_dir, base_url)
    return await runner.run_experiment(experiment_name)
