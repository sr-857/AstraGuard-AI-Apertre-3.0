"""
SLO Validation for Chaos Testing

Validates that Service Level Objectives are maintained during chaos experiments.
"""

import asyncio
import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class SLOValidationResult:
    """Result of SLO validation."""
    slo_maintained: bool
    error_rate_compliant: bool
    latency_compliant: bool
    availability_compliant: bool
    error_rate: float
    p99_latency: float
    availability: float
    violations: List[str]
    timestamp: datetime


class SLOValidator:
    """
    Validates SLO compliance during chaos experiments.
    
    Default SLOs:
    - Error rate < 1%
    - P99 latency < 500ms
    - Availability > 99.9%
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        max_error_rate: float = 0.01,
        max_p99_latency: float = 0.5,
        min_availability: float = 0.999,
    ):
        """
        Initialize SLO validator.
        
        Args:
            base_url: Base URL of AstraGuard service
            max_error_rate: Maximum acceptable error rate (0.0-1.0)
            max_p99_latency: Maximum acceptable P99 latency in seconds
            min_availability: Minimum acceptable availability (0.0-1.0)
        """
        self.base_url = base_url
        self.max_error_rate = max_error_rate
        self.max_p99_latency = max_p99_latency
        self.min_availability = min_availability

    async def validate_slo_compliance(
        self,
        duration_seconds: int = 60,
    ) -> SLOValidationResult:
        """
        Validate SLO compliance during chaos.
        
        Args:
            duration_seconds: Duration to monitor SLOs
            
        Returns:
            SLOValidationResult with compliance status
        """
        logger.info(f"Starting SLO validation for {duration_seconds}s")
        
        violations = []
        
        # Collect metrics over time
        metrics_samples = []
        start_time = datetime.utcnow()
        
        async with aiohttp.ClientSession() as session:
            while (datetime.utcnow() - start_time).total_seconds() < duration_seconds:
                try:
                    metrics = await self._collect_metrics(session)
                    metrics_samples.append(metrics)
                except Exception as e:
                    violations.append(f"Metrics collection failed: {e}")
                
                await asyncio.sleep(5)  # Sample every 5 seconds
        
        # Calculate SLO compliance
        if not metrics_samples:
            return SLOValidationResult(
                slo_maintained=False,
                error_rate_compliant=False,
                latency_compliant=False,
                availability_compliant=False,
                error_rate=1.0,
                p99_latency=999.0,
                availability=0.0,
                violations=["No metrics collected"],
                timestamp=datetime.utcnow(),
            )
        
        # Aggregate metrics
        error_rate = self._calculate_error_rate(metrics_samples)
        p99_latency = self._calculate_p99_latency(metrics_samples)
        availability = self._calculate_availability(metrics_samples)
        
        # Check compliance
        error_rate_ok = error_rate <= self.max_error_rate
        latency_ok = p99_latency <= self.max_p99_latency
        availability_ok = availability >= self.min_availability
        
        if not error_rate_ok:
            violations.append(
                f"Error rate {error_rate:.2%} exceeds threshold {self.max_error_rate:.2%}"
            )
        
        if not latency_ok:
            violations.append(
                f"P99 latency {p99_latency:.3f}s exceeds threshold {self.max_p99_latency:.3f}s"
            )
        
        if not availability_ok:
            violations.append(
                f"Availability {availability:.3%} below threshold {self.min_availability:.3%}"
            )
        
        slo_maintained = error_rate_ok and latency_ok and availability_ok
        
        logger.info(
            f"SLO validation complete: maintained={slo_maintained}, "
            f"error_rate={error_rate:.2%}, p99={p99_latency:.3f}s, "
            f"availability={availability:.3%}"
        )
        
        return SLOValidationResult(
            slo_maintained=slo_maintained,
            error_rate_compliant=error_rate_ok,
            latency_compliant=latency_ok,
            availability_compliant=availability_ok,
            error_rate=error_rate,
            p99_latency=p99_latency,
            availability=availability,
            violations=violations,
            timestamp=datetime.utcnow(),
        )

    async def _collect_metrics(
        self,
        session: aiohttp.ClientSession,
    ) -> Dict[str, float]:
        """
        Collect metrics from Prometheus endpoint.
        
        Args:
            session: HTTP session
            
        Returns:
            Dictionary of metric values
        """
        metrics = {
            "error_rate": 0.0,
            "latency_p99": 0.0,
            "request_count": 0,
            "error_count": 0,
        }
        
        try:
            async with session.get(
                f"{self.base_url}/health/metrics",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    metrics_text = await resp.text()
                    
                    # Parse error rate
                    error_rate = self._parse_metric(
                        metrics_text, "astra_error_rate"
                    )
                    if error_rate is not None:
                        metrics["error_rate"] = error_rate
                    
                    # Parse latency
                    latency = self._parse_metric(
                        metrics_text, "astra_latency_p99"
                    )
                    if latency is not None:
                        metrics["latency_p99"] = latency
                    
                    # Parse request count
                    request_count = self._parse_metric(
                        metrics_text, "astra_requests_total"
                    )
                    if request_count is not None:
                        metrics["request_count"] = request_count
                    
                    # Parse error count
                    error_count = self._parse_metric(
                        metrics_text, "astra_errors_total"
                    )
                    if error_count is not None:
                        metrics["error_count"] = error_count
        except Exception as e:
            logger.warning(f"Failed to collect metrics: {e}")
        
        return metrics

    def _parse_metric(
        self,
        metrics_text: str,
        metric_name: str,
    ) -> Optional[float]:
        """
        Parse a metric value from Prometheus text format.
        
        Args:
            metrics_text: Prometheus metrics text
            metric_name: Name of metric to find
            
        Returns:
            Metric value or None if not found
        """
        # Match metric lines like: metric_name{label="value"} 0.123
        pattern = rf"^{metric_name}(?:{{[^}}]*}})?\\s+([\\d.eE+-]+)$"
        
        for line in metrics_text.split("\\n"):
            match = re.match(pattern, line.strip())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        
        return None

    def _calculate_error_rate(
        self,
        samples: List[Dict[str, float]],
    ) -> float:
        """
        Calculate average error rate from samples.
        
        Args:
            samples: List of metric samples
            
        Returns:
            Average error rate
        """
        total_requests = sum(s.get("request_count", 0) for s in samples)
        total_errors = sum(s.get("error_count", 0) for s in samples)
        
        if total_requests == 0:
            return 0.0
        
        return total_errors / total_requests

    def _calculate_p99_latency(
        self,
        samples: List[Dict[str, float]],
    ) -> float:
        """
        Calculate P99 latency from samples.
        
        Args:
            samples: List of metric samples
            
        Returns:
            P99 latency in seconds
        """
        latencies = [s.get("latency_p99", 0) for s in samples if s.get("latency_p99", 0) > 0]
        
        if not latencies:
            return 0.0
        
        # Simple average for now - in production would use proper percentile calculation
        return sum(latencies) / len(latencies)

    def _calculate_availability(
        self,
        samples: List[Dict[str, float]],
    ) -> float:
        """
        Calculate availability from samples.
        
        Args:
            samples: List of metric samples
            
        Returns:
            Availability as fraction (0.0-1.0)
        """
        # Count successful samples (where we got metrics)
        successful_samples = sum(
            1 for s in samples
            if s.get("request_count", 0) > 0 or s.get("error_rate", 0) > 0
        )
        
        if not samples:
            return 0.0
        
        return successful_samples / len(samples)


# Convenience function
async def validate_slo_compliance(
    base_url: str = "http://localhost:8000",
    duration_seconds: int = 60,
) -> SLOValidationResult:
    """
    Validate SLO compliance.
    
    Args:
        base_url: Base URL of service
        duration_seconds: Duration to monitor
        
    Returns:
        SLOValidationResult
    """
    validator = SLOValidator(base_url)
    return await validator.validate_slo_compliance(duration_seconds)
