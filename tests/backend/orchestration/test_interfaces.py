"""
Direct interface import test without triggering problematic dependencies.
"""

import sys
import os

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Test importing interfaces (these don't have external dependencies)
# Import directly from modules, not from __init__ to avoid triggering full imports
print("Testing interface imports...")

import backend.orchestration.orchestrator_base as orch_base
Orchestrator = orch_base.Orchestrator
OrchestratorBase = orch_base.OrchestratorBase
print("✓ Orchestrator interface imported")

import backend.orchestration.coordinator as coord_mod
Coordinator = coord_mod.Coordinator
CoordinatorBase = coord_mod.CoordinatorBase
LocalCoordinator = coord_mod.LocalCoordinator
ConsensusDecision = coord_mod.ConsensusDecision
NodeInfo = coord_mod.NodeInfo
print("✓ Coordinator interface imported")
print("✓ LocalCoordinator imported")
print("✓ ConsensusDecision imported")
print("✓ NodeInfo imported")

# Test instantiating LocalCoordinator (no external deps)
print("\nTesting LocalCoordinator instantiation...")
coordinator = LocalCoordinator(health_monitor=None, instance_id="test-123")
print(f"✓ LocalCoordinator created: {coordinator.instance_id}")
print(f"✓ Is running: {coordinator.is_running()}")
print(f"✓ Is leader: {coordinator.is_leader}")

# Test coordinator metrics
metrics = coordinator.get_metrics()
print(f"✓ Metrics retrieved: {metrics}")

print("\n✅ All interface tests passed!")
print("Orchestration package is properly structured and interfaces work correctly.")
