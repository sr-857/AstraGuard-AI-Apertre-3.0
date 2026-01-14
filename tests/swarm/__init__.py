"""
AstraGuard Swarm Simulator Test Suite

Issue #414: Multi-agent Docker swarm simulator
Comprehensive testing infrastructure for swarm intelligence pipeline (#397-413)

Module Structure:
  - golden_paths.py: Pre-defined success scenarios (4 core + 20 edge cases)
  - failure_injector.py: Chaos engineering framework (12 failure types)
  - test_swarm_sim.py: Test orchestrator (coordinator + runners)

Usage:
  # Run all tests
  pytest tests/swarm/test_swarm_sim.py -v
  
  # Specific test
  pytest tests/swarm/test_swarm_sim.py::test_golden_path_1_healthy_boot -v
  
  # With coverage
  pytest tests/swarm/ --cov=astraguard --cov-report=html
"""

__version__ = "1.0.0"
__author__ = "AstraGuard Development Team"
__description__ = "Swarm Simulator Test Suite"

try:
    from .golden_paths import (
        GoldenPath,
        GoldenPath1_HealthyBoot,
        GoldenPath2_AnomalyResponse,
        GoldenPath3_NetworkPartition,
        GoldenPath4_LeaderCrash,
        SwarmPhase,
        AgentState,
        ConstellationState,
    )

    from .failure_injector import (
        FailureInjector,
        FailureType,
        FailureConfig,
    )

    from .test_swarm_sim import (
        SwarmSimulatorOrchestrator,
        TestResult,
        SwarmTestSummary,
    )

    __all__ = [
        # Golden paths
        "GoldenPath",
        "GoldenPath1_HealthyBoot",
        "GoldenPath2_AnomalyResponse",
        "GoldenPath3_NetworkPartition",
        "GoldenPath4_LeaderCrash",
        "SwarmPhase",
        "AgentState",
        "ConstellationState",
        
        # Failure injection
        "FailureInjector",
        "FailureType",
        "FailureConfig",
        
        # Orchestration
        "SwarmSimulatorOrchestrator",
        "TestResult",
        "SwarmTestSummary",
    ]
except ImportError:
    # Handle import errors gracefully
    __all__ = []
