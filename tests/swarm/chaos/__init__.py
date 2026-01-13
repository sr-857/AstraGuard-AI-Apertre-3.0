"""
AstraGuard Chaos Engineering Test Suite

Issue #415: Swarm chaos engineering suite for AstraGuard v3.0
Production-grade chaos testing to validate swarm resilience.

Module Structure:
  - chaos_injector.py: Advanced chaos methods (packet loss, latency cascades, etc.)
  - test_chaos_suite.py: 5 scenarios × 3 sizes test matrix
  - conftest.py: Pytest configuration

Usage:
  # Run full chaos campaign
  pytest tests/swarm/chaos/test_chaos_suite.py -v
  
  # Specific scenario
  pytest tests/swarm/chaos/test_chaos_suite.py::test_network_partition_50pct -v
  
  # With coverage
  pytest tests/swarm/chaos/ --cov=astraguard --cov-report=html

Success Criteria:
  - 95%+ consensus rate under 50% partition
  - Leader failover <10s
  - Message delivery >99% under 50% packet loss
  - Zero cascading failures
  - Role compliance >90% under agent churn
"""

__version__ = "1.0.0"
__author__ = "AstraGuard Development Team"
__description__ = "Chaos Engineering Test Suite"

from .chaos_injector import ChaosInjectorExtensions
from .test_chaos_suite import ChaosSuite, ChaosTestResult, ChaosTestSummary

__all__ = [
    "ChaosInjectorExtensions",
    "ChaosSuite",
    "ChaosTestResult",
    "ChaosTestSummary",
]
