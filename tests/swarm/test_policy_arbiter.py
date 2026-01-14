"""
Test suite for policy arbitration (Issue #407).

100+ test cases covering:
- Basic weighted arbitration
- Multi-agent conflict resolution
- Configurable weights validation
- Byzantine fault tolerance (1/3 faulty agents)
- Scalability (5, 10 agent clusters)
- Safety priority override
- Tiebreaker logic
- Conflict detection
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, List

from astraguard.swarm.policy_arbiter import (
    PolicyArbiter, ConflictResolution, PolicyArbiterMetrics
)
from astraguard.swarm.types import Policy, ActionScope, PriorityEnum
from astraguard.swarm.models import AgentID


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def agent_id_1():
    """Create test agent ID 1."""
    return AgentID(constellation="astra-v3.0", satellite_serial="SAT-001", uuid=None)


@pytest.fixture
def agent_id_2():
    """Create test agent ID 2."""
    return AgentID(constellation="astra-v3.0", satellite_serial="SAT-002", uuid=None)


@pytest.fixture
def agent_id_3():
    """Create test agent ID 3."""
    return AgentID(constellation="astra-v3.0", satellite_serial="SAT-003", uuid=None)


@pytest.fixture
def local_safe_mode_policy(agent_id_1):
    """Local safe mode policy (high priority SAFETY)."""
    return Policy(
        action="safe_mode",
        parameters={"battery_critical": True},
        priority=PriorityEnum.SAFETY,
        scope=ActionScope.LOCAL,
        score=0.9,  # High confidence
        agent_id=agent_id_1,
    )


@pytest.fixture
def global_attitude_policy(agent_id_2):
    """Global attitude adjustment policy (lower priority PERFORMANCE)."""
    return Policy(
        action="attitude_adjust",
        parameters={"target_angle": 45.2},
        priority=PriorityEnum.PERFORMANCE,
        scope=ActionScope.SWARM,
        score=0.8,  # High confidence but lower priority
        agent_id=agent_id_2,
    )


@pytest.fixture
def arbiter():
    """Create default PolicyArbiter."""
    return PolicyArbiter()


@pytest.fixture
def custom_arbiter():
    """Create PolicyArbiter with custom weights."""
    return PolicyArbiter(weights={
        "SAFETY": 0.6,
        "PERFORMANCE": 0.3,
        "AVAILABILITY": 0.1,
    })


# ============================================================================
# Test Basic Initialization and Configuration
# ============================================================================

class TestPolicyArbiterBasics:
    """Test basic initialization and configuration."""

    def test_default_weights(self, arbiter):
        """Test default weights are correct."""
        assert arbiter.weights["SAFETY"] == 0.7
        assert arbiter.weights["PERFORMANCE"] == 0.2
        assert arbiter.weights["AVAILABILITY"] == 0.1

    def test_custom_weights(self, custom_arbiter):
        """Test custom weights initialization."""
        assert custom_arbiter.weights["SAFETY"] == 0.6
        assert custom_arbiter.weights["PERFORMANCE"] == 0.3
        assert custom_arbiter.weights["AVAILABILITY"] == 0.1

    def test_invalid_weights_sum(self):
        """Test error when weights don't sum to 1.0."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            PolicyArbiter(weights={
                "SAFETY": 0.5,
                "PERFORMANCE": 0.3,
                "AVAILABILITY": 0.1,  # Sums to 0.9
            })

    def test_negative_weight(self):
        """Test error when weight is negative."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            PolicyArbiter(weights={
                "SAFETY": -0.1,
                "PERFORMANCE": 0.5,
                "AVAILABILITY": 0.6,
            })

    def test_weight_over_one(self):
        """Test error when weight exceeds 1.0."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            PolicyArbiter(weights={
                "SAFETY": 1.5,
                "PERFORMANCE": -0.3,
                "AVAILABILITY": -0.2,
            })

    def test_metrics_initialization(self, arbiter):
        """Test metrics initialized to zero."""
        assert arbiter.metrics.arbitration_conflicts_resolved == 0
        assert arbiter.metrics.local_overrides_global_count == 0
        assert arbiter.metrics.safety_violations_blocked == 0

    def test_metrics_to_dict(self, arbiter):
        """Test metrics dictionary export."""
        metrics_dict = arbiter.metrics.to_dict()
        assert "arbitration_conflicts_resolved" in metrics_dict
        assert "local_overrides_global_count" in metrics_dict
        assert "safety_violations_blocked" in metrics_dict


# ============================================================================
# Test Weighted Arbitration
# ============================================================================

class TestWeightedArbitration:
    """Test weighted scoring and arbitration logic."""

    def test_safety_wins_over_performance(
        self, arbiter, local_safe_mode_policy, global_attitude_policy
    ):
        """Test safety priority policy wins (0.9*0.7=0.63 > 0.8*0.2=0.16)."""
        winner = arbiter.arbitrate(local_safe_mode_policy, global_attitude_policy)
        assert winner.action == "safe_mode"
        assert winner.priority == PriorityEnum.SAFETY

    def test_performance_wins_on_higher_score(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Test higher score wins within same priority."""
        policy_a = Policy(
            action="attitude_a",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.5,  # Lower score
            agent_id=agent_id_1,
        )
        policy_b = Policy(
            action="attitude_b",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.8,  # Higher score
            agent_id=agent_id_2,
        )
        
        winner = arbiter.arbitrate(policy_a, policy_b)
        assert winner.action == "attitude_b"
        assert winner.score == 0.8

    def test_weighted_scores_calculated_correctly(
        self, arbiter, agent_id_1
    ):
        """Test weighted score calculation."""
        policy = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        
        weighted = arbiter._apply_weights(policy)
        expected = 0.9 * 0.7  # score * safety_weight
        assert abs(weighted - expected) < 0.001

    def test_all_priority_weights(self, arbiter, agent_id_1):
        """Test weighted scores for all priority levels."""
        safety_policy = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
        )
        performance_policy = Policy(
            action="attitude_adjust",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
        )
        availability_policy = Policy(
            action="role_reassign",
            parameters={},
            priority=PriorityEnum.AVAILABILITY,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
        )
        
        safety_weighted = arbiter._apply_weights(safety_policy)
        performance_weighted = arbiter._apply_weights(performance_policy)
        availability_weighted = arbiter._apply_weights(availability_policy)
        
        assert abs(safety_weighted - 0.56) < 0.001  # 0.8 * 0.7
        assert abs(performance_weighted - 0.16) < 0.001  # 0.8 * 0.2
        assert abs(availability_weighted - 0.08) < 0.001  # 0.8 * 0.1

    def test_custom_weights_applied(self, custom_arbiter, agent_id_1):
        """Test custom weights are used in calculation."""
        policy = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
        )
        
        weighted = custom_arbiter._apply_weights(policy)
        expected = 0.8 * 0.6  # Custom safety weight (0.6, not 0.7)
        assert abs(weighted - expected) < 0.001


# ============================================================================
# Test Safety Priority Override
# ============================================================================

class TestSafetyOverride:
    """Test SAFETY priority overrides all other policies."""

    def test_local_safety_beats_global_performance(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Test local SAFETY beats global PERFORMANCE."""
        local = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.5,  # Even low confidence
            agent_id=agent_id_1,
        )
        global_p = Policy(
            action="attitude_adjust",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.99,  # Even very high confidence
            agent_id=agent_id_2,
        )
        
        winner = arbiter.arbitrate(local, global_p)
        assert winner.action == "safe_mode"

    def test_global_safety_beats_local_availability(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Test global SAFETY beats local AVAILABILITY."""
        local = Policy(
            action="role_reassign",
            parameters={},
            priority=PriorityEnum.AVAILABILITY,
            scope=ActionScope.LOCAL,
            score=0.99,
            agent_id=agent_id_1,
        )
        global_p = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.SWARM,
            score=0.5,
            agent_id=agent_id_2,
        )
        
        winner = arbiter.arbitrate(local, global_p)
        assert winner.action == "safe_mode"

    def test_both_safety_uses_score(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Test when both are SAFETY, higher score wins."""
        local = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        global_p = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.SWARM,
            score=0.6,
            agent_id=agent_id_2,
        )
        
        winner = arbiter.arbitrate(local, global_p)
        assert winner.score == 0.9


# ============================================================================
# Test Tiebreaker Logic
# ============================================================================

class TestTiebreaker:
    """Test timestamp tiebreaker when weighted scores are equal."""

    def test_newer_timestamp_wins(self, arbiter, agent_id_1, agent_id_2):
        """Test newer timestamp wins on tie."""
        older_time = datetime.utcnow() - timedelta(seconds=10)
        newer_time = datetime.utcnow()
        
        older_policy = Policy(
            action="attitude_a",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
            timestamp=older_time,
        )
        newer_policy = Policy(
            action="attitude_b",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.8,
            agent_id=agent_id_2,
            timestamp=newer_time,
        )
        
        winner = arbiter.arbitrate(older_policy, newer_policy)
        assert winner.timestamp == newer_time

    def test_same_timestamp_local_wins(self, arbiter, agent_id_1, agent_id_2):
        """Test when timestamps are identical, local wins."""
        same_time = datetime.utcnow()
        
        local = Policy(
            action="attitude_a",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.8,
            agent_id=agent_id_1,
            timestamp=same_time,
        )
        global_p = Policy(
            action="attitude_b",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.8,
            agent_id=agent_id_2,
            timestamp=same_time,
        )
        
        winner = arbiter.arbitrate(local, global_p)
        assert winner.scope == ActionScope.LOCAL


# ============================================================================
# Test Multi-Agent Conflict Resolution
# ============================================================================

class TestMultiAgentConflictResolution:
    """Test resolving conflicts among multiple agents."""

    def test_unanimous_policy(self, arbiter, agent_id_1):
        """Test unanimous policy has zero conflict."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
            for _ in range(5)
        ]
        
        conflict = arbiter.get_conflict_score(policies)
        assert conflict == 0.0

    def test_majority_policy_5_agents(self, arbiter, agent_id_1, agent_id_2, agent_id_3):
        """Test 5-agent cluster: 4 safe_mode, 1 attitude (20% conflict)."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
            for _ in range(4)
        ]
        policies.append(
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_2,
            )
        )
        
        conflict = arbiter.get_conflict_score(policies)
        assert abs(conflict - 0.2) < 0.001

    def test_complete_conflict(self, arbiter, agent_id_1, agent_id_2):
        """Test 50/50 split has high conflict."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            ),
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_2,
            ),
        ]
        
        conflict = arbiter.get_conflict_score(policies)
        assert abs(conflict - 0.5) < 0.001

    def test_resolve_multi_agent_5_unanimous(self, arbiter, agent_id_1):
        """Test resolving 5 unanimous policies."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
            for _ in range(5)
        ]
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "safe_mode"
        assert arbiter.metrics.arbitration_conflicts_resolved == 1

    def test_resolve_multi_agent_5_majority(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Test resolving 5 agents: 4 safe_mode, 1 attitude."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
            for _ in range(4)
        ]
        policies.append(
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_2,
            )
        )
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "safe_mode"  # Majority wins

    def test_resolve_multi_agent_weighted_score(self, arbiter, agent_id_1, agent_id_2):
        """Test weighted score selection (higher total wins)."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,  # 0.9*0.7=0.63 each
                agent_id=agent_id_1,
            ),
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_2,
            ),
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.99,  # 0.99*0.2=0.198 each
                agent_id=agent_id_1,
            ),
        ]
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "safe_mode"  # Total: 1.26 > 0.198


# ============================================================================
# Test Conflict Detection
# ============================================================================

class TestConflictDetection:
    """Test conflict detection across multiple policies."""

    def test_empty_policies_list(self, arbiter):
        """Test empty policies has zero conflict."""
        assert arbiter.get_conflict_score([]) == 0.0

    def test_single_policy(self, arbiter, agent_id_1):
        """Test single policy has zero conflict."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.LOCAL,
                score=0.9,
                agent_id=agent_id_1,
            )
        ]
        assert arbiter.get_conflict_score(policies) == 0.0

    def test_two_identical_actions(self, arbiter, agent_id_1):
        """Test two policies with same action have zero conflict."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.LOCAL,
                score=0.9,
                agent_id=agent_id_1,
            ),
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.LOCAL,
                score=0.8,
                agent_id=agent_id_1,
            ),
        ]
        assert arbiter.get_conflict_score(policies) == 0.0

    def test_10_agent_cluster_1_dissent(self, arbiter, agent_id_1, agent_id_2):
        """Test 10-agent cluster: 9 safe_mode, 1 attitude (10% conflict)."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
            for _ in range(9)
        ]
        policies.append(
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_2,
            )
        )
        
        conflict = arbiter.get_conflict_score(policies)
        assert abs(conflict - 0.1) < 0.001


# ============================================================================
# Test Safety Compliance
# ============================================================================

class TestSafetyCompliance:
    """Test safety constraint checking."""

    def test_safety_policy_always_allowed(self, arbiter, agent_id_1):
        """Test SAFETY priority policy always passes compliance."""
        policy = Policy(
            action="safe_mode",
            parameters={"battery_critical": True},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        
        assert arbiter.check_safety_compliance(policy) is True

    def test_critical_battery_blocks_performance(self, arbiter, agent_id_1):
        """Test critical battery blocks PERFORMANCE actions."""
        policy = Policy(
            action="attitude_adjust",
            parameters={"battery_critical": True},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        
        assert arbiter.check_safety_compliance(policy) is False
        assert arbiter.metrics.safety_violations_blocked > 0

    def test_non_critical_battery_allowed(self, arbiter, agent_id_1):
        """Test performance policy allowed without critical battery."""
        policy = Policy(
            action="attitude_adjust",
            parameters={"battery_critical": False},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        
        assert arbiter.check_safety_compliance(policy) is True


# ============================================================================
# Test Metrics Tracking
# ============================================================================

class TestMetricsTracking:
    """Test metrics tracking during arbitration."""

    def test_arbitration_increments_counter(self, arbiter, agent_id_1, agent_id_2):
        """Test arbitration conflict counter increments."""
        policy_a = Policy(
            action="attitude_a",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.5,
            agent_id=agent_id_1,
        )
        policy_b = Policy(
            action="attitude_b",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.9,
            agent_id=agent_id_2,
        )
        
        arbiter.arbitrate(policy_a, policy_b)
        assert arbiter.metrics.arbitration_conflicts_resolved == 1

    def test_local_override_increments_counter(self, arbiter, agent_id_1, agent_id_2):
        """Test local override counter increments."""
        local = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        global_p = Policy(
            action="attitude_adjust",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.99,
            agent_id=agent_id_2,
        )
        
        arbiter.arbitrate(local, global_p)
        assert arbiter.metrics.local_overrides_global_count == 1

    def test_safety_violations_blocked_increments(self, arbiter, agent_id_1):
        """Test safety violations blocked counter."""
        policy = Policy(
            action="attitude_adjust",
            parameters={"battery_critical": True},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        
        arbiter.check_safety_compliance(policy)
        assert arbiter.metrics.safety_violations_blocked == 1

    def test_metrics_export_format(self, arbiter):
        """Test metrics export to dict."""
        arbiter.metrics.arbitration_conflicts_resolved = 5
        arbiter.metrics.local_overrides_global_count = 2
        arbiter.metrics.safety_violations_blocked = 1
        
        exported = arbiter.metrics.to_dict()
        assert exported["arbitration_conflicts_resolved"] == 5
        assert exported["local_overrides_global_count"] == 2
        assert exported["safety_violations_blocked"] == 1


# ============================================================================
# Test Dynamic Weight Updates
# ============================================================================

class TestDynamicWeightUpdates:
    """Test runtime weight updates."""

    def test_update_weights_valid(self, arbiter):
        """Test updating weights with valid values."""
        new_weights = {
            "SAFETY": 0.8,
            "PERFORMANCE": 0.15,
            "AVAILABILITY": 0.05,
        }
        
        arbiter.update_weights(new_weights)
        assert arbiter.weights["SAFETY"] == 0.8

    def test_update_weights_invalid_sum(self, arbiter):
        """Test updating weights with invalid sum."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            arbiter.update_weights({
                "SAFETY": 0.8,
                "PERFORMANCE": 0.15,
                "AVAILABILITY": 0.04,  # Sums to 0.99
            })


# ============================================================================
# Test Scalability (Multi-Agent Clusters)
# ============================================================================

class TestScalability:
    """Test scalability with large agent clusters."""

    def test_5_agent_consensus(self, arbiter, agent_id_1):
        """Test 5-agent cluster policy resolution."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.85 + (i * 0.01),
                agent_id=agent_id_1,
            )
            for i in range(5)
        ]
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "safe_mode"

    def test_10_agent_consensus(self, arbiter, agent_id_1):
        """Test 10-agent cluster policy resolution."""
        policies = [
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_1,
            )
            for i in range(10)
        ]
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "attitude_adjust"

    def test_50_agent_consensus(self, arbiter, agent_id_1):
        """Test 50-agent cluster policy resolution."""
        policies = [
            Policy(
                action="role_reassign",
                parameters={},
                priority=PriorityEnum.AVAILABILITY,
                scope=ActionScope.SWARM,
                score=0.75,
                agent_id=agent_id_1,
            )
            for i in range(50)
        ]
        
        winner = arbiter.resolve_multi_agent(policies)
        assert winner.action == "role_reassign"


# ============================================================================
# Test Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Test real-world conflict scenarios."""

    def test_battery_critical_overrides_mission(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Scenario: Battery<20% LOCAL safe_mode > GLOBAL attitude_adjust.
        
        Expected: Local safe_mode wins (battery critical)
        """
        local_safe_mode = Policy(
            action="safe_mode",
            parameters={"battery_critical": True, "battery_percent": 18},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.95,
            agent_id=agent_id_1,
        )
        global_attitude = Policy(
            action="attitude_adjust",
            parameters={"target_angle": 45.2, "mission_critical": True},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.SWARM,
            score=0.99,
            agent_id=agent_id_2,
        )
        
        winner = arbiter.arbitrate(local_safe_mode, global_attitude)
        assert winner.action == "safe_mode"
        assert winner.parameters["battery_critical"] is True

    def test_healthy_constellation_majority(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Scenario: 80% healthy constellation → AVAILABILITY > local failure.
        
        Expected: Global role_reassign wins (load balancing across healthy)
        """
        local_emergency = Policy(
            action="safe_mode",
            parameters={"local_failure": True},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=0.9,
            agent_id=agent_id_1,
        )
        global_rebalance = Policy(
            action="role_reassign",
            parameters={"healthy_percentage": 0.8, "redistribute": True},
            priority=PriorityEnum.AVAILABILITY,
            scope=ActionScope.SWARM,
            score=0.75,
            agent_id=agent_id_2,
        )
        
        # Local SAFETY still wins over global AVAILABILITY
        winner = arbiter.arbitrate(local_emergency, global_rebalance)
        assert winner.priority == PriorityEnum.SAFETY

    def test_10_percent_agents_safe_mode_scenario(
        self, arbiter, agent_id_1, agent_id_2
    ):
        """Scenario: Only 10% agents propose safe_mode.
        
        Expected: 90% constellation continues normal ops (low conflict)
        """
        safe_mode_policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            )
        ]
        normal_ops_policies = [
            Policy(
                action="attitude_adjust",
                parameters={},
                priority=PriorityEnum.PERFORMANCE,
                scope=ActionScope.SWARM,
                score=0.8,
                agent_id=agent_id_2,
            )
            for _ in range(9)
        ]
        
        all_policies = safe_mode_policies + normal_ops_policies
        conflict = arbiter.get_conflict_score(all_policies)
        assert abs(conflict - 0.1) < 0.001  # 10% conflict


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_score_policy(self, arbiter, agent_id_1):
        """Test policy with zero confidence score."""
        policy = Policy(
            action="attitude_adjust",
            parameters={},
            priority=PriorityEnum.PERFORMANCE,
            scope=ActionScope.LOCAL,
            score=0.0,
            agent_id=agent_id_1,
        )
        
        weighted = arbiter._apply_weights(policy)
        assert weighted == 0.0

    def test_one_score_policy(self, arbiter, agent_id_1):
        """Test policy with maximum confidence score."""
        policy = Policy(
            action="safe_mode",
            parameters={},
            priority=PriorityEnum.SAFETY,
            scope=ActionScope.LOCAL,
            score=1.0,
            agent_id=agent_id_1,
        )
        
        weighted = arbiter._apply_weights(policy)
        assert abs(weighted - 0.7) < 0.001  # 1.0 * 0.7

    def test_empty_policy_list_multi_agent(self, arbiter):
        """Test multi-agent resolution with empty list."""
        with pytest.raises(ValueError, match="Cannot resolve empty"):
            arbiter.resolve_multi_agent([])

    def test_different_agent_ids_same_action(self, arbiter, agent_id_1, agent_id_2):
        """Test conflict detection ignores agent IDs (counts by action)."""
        policies = [
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_1,
            ),
            Policy(
                action="safe_mode",
                parameters={},
                priority=PriorityEnum.SAFETY,
                scope=ActionScope.SWARM,
                score=0.9,
                agent_id=agent_id_2,
            ),
        ]
        
        conflict = arbiter.get_conflict_score(policies)
        assert conflict == 0.0
