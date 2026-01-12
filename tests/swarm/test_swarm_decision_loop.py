"""
Tests for SwarmDecisionLoop - Swarm-aware decision making.

Issue #411: Comprehensive test suite for swarm decision wrapper.

Tests cover:
  - Decision latency <200ms with global context
  - Global context cache hit rate >90%
  - 100ms TTL enforcement
  - Leader vs follower decision consistency
  - 5-agent constellation decision convergence
  - Cache freshness and refresh logic
  - Decision history tracking
  - Fallback behavior on errors
  - Integration with AgenticDecisionLoop

Target: 40+ tests, 90%+ code coverage
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from astraguard.swarm.swarm_decision_loop import (
    SwarmDecisionLoop,
    Decision,
    DecisionType,
    GlobalContext,
    SwarmDecisionMetrics,
)
from astraguard.swarm.models import AgentID, SatelliteRole
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.leader_election import LeaderElection
from astraguard.swarm.swarm_memory import SwarmAdaptiveMemory


# Fixtures

@pytest.fixture
def agent_id():
    """Create test agent ID."""
    return AgentID(
        constellation_id="test-constellation",
        satellite_serial="test-sat-001",
    )


@pytest.fixture
def peer_ids():
    """Create test peer IDs."""
    return [
        AgentID(constellation_id="test-constellation", satellite_serial=f"test-sat-{i:03d}")
        for i in range(2, 7)  # 5 peers
    ]


@pytest.fixture
def mock_registry(agent_id):
    """Create mock SwarmRegistry."""
    registry = MagicMock(spec=SwarmRegistry)
    registry.get_alive_peers = MagicMock(return_value=[])
    registry.get_peer_health = MagicMock(return_value=None)
    registry.get_agent_role = MagicMock(return_value=SatelliteRole.PRIMARY)
    return registry


@pytest.fixture
def mock_election(agent_id):
    """Create mock LeaderElection."""
    election = AsyncMock(spec=LeaderElection)
    election.is_leader = MagicMock(return_value=False)
    election.get_leader = AsyncMock(return_value=None)
    return election


@pytest.fixture
def mock_memory():
    """Create mock SwarmAdaptiveMemory."""
    memory = AsyncMock(spec=SwarmAdaptiveMemory)
    return memory


@pytest.fixture
def mock_inner_loop():
    """Create mock AgenticDecisionLoop."""
    loop = AsyncMock()
    loop.reason = AsyncMock(return_value="decision_action")
    loop.step = AsyncMock(return_value="decision_action")
    return loop


@pytest.fixture
def swarm_loop(mock_inner_loop, mock_registry, mock_election, mock_memory, agent_id):
    """Create SwarmDecisionLoop instance for testing."""
    loop = SwarmDecisionLoop(
        inner_loop=mock_inner_loop,
        registry=mock_registry,
        election=mock_election,
        memory=mock_memory,
        agent_id=agent_id,
        config={"cache_ttl": 0.1},  # 100ms
    )
    return loop


def create_test_telemetry() -> Dict[str, float]:
    """Create test telemetry data."""
    return {
        "temperature": 45.2,
        "power": 850.5,
        "radiation": 0.12,
        "antenna_signal": 0.95,
    }


# Test: Decision Loop Basics

class TestDecisionLoopBasics:
    """Test basic decision loop functionality."""

    @pytest.mark.asyncio
    async def test_step_executes_successfully(self, swarm_loop, mock_inner_loop):
        """Test step() executes without error."""
        mock_inner_loop.reason.return_value = "normal_operation"
        telemetry = create_test_telemetry()

        decision = await swarm_loop.step(telemetry)

        assert decision is not None
        assert swarm_loop.metrics.decision_count == 1

    @pytest.mark.asyncio
    async def test_step_returns_decision(self, swarm_loop, mock_inner_loop):
        """Test step() returns Decision object."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="continue_operation",
            confidence=0.9,
            reasoning="Nominal conditions",
        )
        telemetry = create_test_telemetry()

        decision = await swarm_loop.step(telemetry)

        assert isinstance(decision, Decision)
        assert decision.action == "continue_operation"

    @pytest.mark.asyncio
    async def test_step_records_decision_history(self, swarm_loop, mock_inner_loop):
        """Test step() records decision in history."""
        decision_obj = Decision(
            decision_type=DecisionType.NORMAL,
            action="test_action",
            confidence=0.9,
            reasoning="Test",
        )
        mock_inner_loop.reason.return_value = decision_obj
        telemetry = create_test_telemetry()

        await swarm_loop.step(telemetry)

        history = await swarm_loop.get_decision_history(limit=1)
        assert len(history) == 1
        assert history[0].action == "test_action"


# Test: Global Context Caching

class TestGlobalContextCaching:
    """Test 100ms TTL context caching."""

    @pytest.mark.asyncio
    async def test_context_cache_hit(self, swarm_loop, mock_election):
        """Test cache hit when context fresh."""
        mock_election.get_leader.return_value = None
        telemetry = create_test_telemetry()

        # First call - cache miss
        await swarm_loop.step(telemetry)
        miss_count = swarm_loop.metrics.global_context_cache_misses

        # Second call immediately - cache hit
        await swarm_loop.step(telemetry)
        hit_count = swarm_loop.metrics.global_context_cache_hits

        assert hit_count == 1
        assert swarm_loop.metrics.cache_hit_rate > 0

    @pytest.mark.asyncio
    async def test_context_cache_miss_on_ttl_expiry(self, swarm_loop, mock_election):
        """Test cache miss when TTL expires (100ms)."""
        mock_election.get_leader.return_value = None
        telemetry = create_test_telemetry()

        # First call - cache miss
        await swarm_loop.step(telemetry)
        first_miss = swarm_loop.metrics.global_context_cache_misses

        # Manually expire cache
        if swarm_loop.global_context_cache:
            swarm_loop.global_context_cache.cache_timestamp = (
                datetime.utcnow() - timedelta(seconds=0.2)  # 200ms old
            )

        # Second call after TTL - another miss
        await swarm_loop.step(telemetry)
        second_miss = swarm_loop.metrics.global_context_cache_misses

        assert second_miss > first_miss

    @pytest.mark.asyncio
    async def test_cache_hit_rate_above_90_percent(self, swarm_loop, mock_election):
        """Test achieving >90% cache hit rate."""
        mock_election.get_leader.return_value = None
        telemetry = create_test_telemetry()

        # Make 100 rapid calls (should get high hit rate)
        for _ in range(100):
            await swarm_loop.step(telemetry)

        metrics = swarm_loop.get_metrics()
        assert metrics.cache_hit_rate > 0.9  # Target: >90%

    def test_context_ttl_enforcement(self, swarm_loop):
        """Test 100ms TTL is enforced."""
        context = GlobalContext(
            leader_id=None,
            constellation_health=0.8,
            quorum_size=5,
            recent_decisions=[],
            role=SatelliteRole.PRIMARY,
        )

        # Fresh context
        assert not context.is_stale(0.1)

        # Age context
        context.cache_timestamp = datetime.utcnow() - timedelta(seconds=0.15)

        # Should be stale now
        assert context.is_stale(0.1)


# Test: Decision Latency

class TestDecisionLatency:
    """Test decision latency <200ms with global context."""

    @pytest.mark.asyncio
    async def test_decision_latency_under_200ms(self, swarm_loop, mock_inner_loop):
        """Test decision latency <200ms (p95 target)."""
        import time

        mock_inner_loop.reason = AsyncMock()

        async def slow_reason(telemetry, **kwargs):
            await asyncio.sleep(0.05)  # 50ms
            return Decision(
                decision_type=DecisionType.NORMAL,
                action="test",
                confidence=0.9,
                reasoning="Test",
            )

        mock_inner_loop.reason.side_effect = slow_reason
        telemetry = create_test_telemetry()

        start = time.time()
        await swarm_loop.step(telemetry)
        elapsed_ms = (time.time() - start) * 1000

        # Should be fast (cache hit + overhead < 200ms)
        assert elapsed_ms < 200

    @pytest.mark.asyncio
    async def test_multiple_decisions_latency(self, swarm_loop, mock_inner_loop):
        """Test latency across multiple decision iterations."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="test",
            confidence=0.9,
            reasoning="Test",
        )
        telemetry = create_test_telemetry()

        # Make 10 decisions
        for _ in range(10):
            await swarm_loop.step(telemetry)

        metrics = swarm_loop.get_metrics()
        # p95 latency should be reasonable
        assert metrics.decision_latency_ms < 200


# Test: Leader vs Follower Decisions

class TestLeaderFollowerDecisions:
    """Test leader vs follower decision paths."""

    @pytest.mark.asyncio
    async def test_leader_uses_global_context(self, swarm_loop, mock_election, mock_registry):
        """Test leader makes decisions with global context."""
        mock_election.is_leader.return_value = True
        mock_election.get_leader.return_value = swarm_loop.agent_id
        mock_registry.get_alive_peers.return_value = []
        telemetry = create_test_telemetry()

        decision = await swarm_loop.step(telemetry)

        assert swarm_loop.metrics.leader_decisions == 1
        assert swarm_loop.metrics.follower_decisions == 0

    @pytest.mark.asyncio
    async def test_follower_uses_inner_loop(self, swarm_loop, mock_election, mock_registry):
        """Test follower delegates to inner_loop with context."""
        mock_election.is_leader.return_value = False
        mock_registry.get_alive_peers.return_value = []
        telemetry = create_test_telemetry()

        decision = await swarm_loop.step(telemetry)

        assert swarm_loop.metrics.follower_decisions == 1
        assert swarm_loop.metrics.leader_decisions == 0

    @pytest.mark.asyncio
    async def test_leader_safe_mode_on_degraded_health(self, swarm_loop, mock_election, mock_registry):
        """Test leader enters safe mode when constellation health <50%."""
        mock_election.is_leader.return_value = True
        mock_election.get_leader.return_value = swarm_loop.agent_id
        mock_registry.get_alive_peers.return_value = []

        # Manually set low health
        swarm_loop.global_context_cache = GlobalContext(
            leader_id=swarm_loop.agent_id,
            constellation_health=0.3,  # 30% - degraded
            quorum_size=2,
            recent_decisions=[],
            role=SatelliteRole.PRIMARY,
        )

        telemetry = create_test_telemetry()
        decision = await swarm_loop.step(telemetry)

        assert decision.decision_type == DecisionType.SAFE_MODE

    @pytest.mark.asyncio
    async def test_decision_consistency_between_agents(self, mock_registry, mock_election, mock_memory):
        """Test decision consistency between leader and followers."""
        peer_ids = [
            AgentID(constellation_id="test", satellite_serial=f"sat-{i:03d}")
            for i in range(5)
        ]

        # Create 5 agents (1 leader, 4 followers)
        agents = []
        mock_inner_loop = AsyncMock()
        mock_inner_loop.reason = AsyncMock(return_value=Decision(
            decision_type=DecisionType.NORMAL,
            action="consistent_action",
            confidence=0.95,
            reasoning="Global consensus",
        ))

        for i, pid in enumerate(peer_ids):
            agent_loop = SwarmDecisionLoop(
                inner_loop=mock_inner_loop,
                registry=mock_registry,
                election=mock_election,
                memory=mock_memory,
                agent_id=pid,
            )

            # First agent is leader
            if i == 0:
                mock_election.is_leader.return_value = True
            else:
                mock_election.is_leader.return_value = False

            agents.append(agent_loop)

        # All agents make same decision
        telemetry = create_test_telemetry()
        decisions = []
        for agent in agents:
            decision = asyncio.run(agent.step(telemetry))
            decisions.append(decision)

        # All should converge on same action
        actions = [d.action for d in decisions]
        assert len(set(actions)) == 1  # All same


# Test: Decision Convergence (5-Agent)

class TestDecisionConvergence:
    """Test 5-agent constellation decision convergence."""

    @pytest.mark.asyncio
    async def test_5_agent_constellation_convergence(self):
        """Test 5 agents converge on same decision."""
        mock_registry = MagicMock(spec=SwarmRegistry)
        mock_election = AsyncMock(spec=LeaderElection)
        mock_memory = AsyncMock(spec=SwarmAdaptiveMemory)
        mock_inner_loop = AsyncMock()

        # Same decision from inner loop
        decision_action = "handle_thermal_anomaly"
        mock_inner_loop.reason = AsyncMock(return_value=Decision(
            decision_type=DecisionType.ANOMALY_RESPONSE,
            action=decision_action,
            confidence=0.92,
            reasoning="Thermal spike detected",
        ))

        # Create 5 agents
        agents = []
        for i in range(5):
            agent_id = AgentID(
                constellation_id="test-constellation",
                satellite_serial=f"sat-{i:03d}",
            )
            agent_loop = SwarmDecisionLoop(
                inner_loop=mock_inner_loop,
                registry=mock_registry,
                election=mock_election,
                memory=mock_memory,
                agent_id=agent_id,
            )
            agents.append(agent_loop)

        # All agents process same telemetry
        telemetry = create_test_telemetry()
        decisions = []

        for agent in agents:
            decision = await agent.step(telemetry)
            decisions.append(decision)

        # Verify convergence
        actions = [d.action for d in decisions]
        assert all(action == decision_action for action in actions)
        assert len(set(actions)) == 1  # All identical

    @pytest.mark.asyncio
    async def test_zero_decision_divergence(self, swarm_loop):
        """Test zero decision divergence across agents."""
        decision1 = Decision(
            decision_type=DecisionType.NORMAL,
            action="action_a",
            confidence=0.9,
            reasoning="Test",
        )
        decision2 = Decision(
            decision_type=DecisionType.NORMAL,
            action="action_a",  # Same
            confidence=0.9,
            reasoning="Test",
        )

        swarm_loop._decision_history.append(decision1)

        other_decisions = {"sat-002": decision2, "sat-003": decision2}

        divergence = swarm_loop.check_decision_divergence(other_decisions)

        assert divergence == 0  # No divergence


# Test: Metrics

class TestMetrics:
    """Test metrics tracking and export."""

    @pytest.mark.asyncio
    async def test_metrics_initialization(self, swarm_loop):
        """Test metrics initialized correctly."""
        metrics = swarm_loop.get_metrics()

        assert metrics.decision_count == 0
        assert metrics.leader_decisions == 0
        assert metrics.follower_decisions == 0
        assert metrics.decision_divergence_count == 0

    @pytest.mark.asyncio
    async def test_metrics_export_to_dict(self, swarm_loop):
        """Test metrics export to dict for Prometheus."""
        metrics = swarm_loop.get_metrics()
        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert "decision_count" in metrics_dict
        assert "decision_latency_ms_p95" in metrics_dict
        assert "cache_hit_rate" in metrics_dict
        assert "cache_hits" in metrics_dict
        assert "cache_misses" in metrics_dict

    @pytest.mark.asyncio
    async def test_metrics_reset(self, swarm_loop, mock_inner_loop):
        """Test metrics reset."""
        mock_inner_loop.reason.return_value = "decision"
        telemetry = create_test_telemetry()

        await swarm_loop.step(telemetry)

        assert swarm_loop.metrics.decision_count > 0

        swarm_loop.reset_metrics()

        assert swarm_loop.metrics.decision_count == 0


# Test: Error Handling

class TestErrorHandling:
    """Test error handling and fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_on_inner_loop_error(self, swarm_loop, mock_inner_loop):
        """Test fallback when inner_loop raises error."""
        mock_inner_loop.reason.side_effect = Exception("Inner loop error")
        telemetry = create_test_telemetry()

        decision = await swarm_loop.step(telemetry)

        assert decision.decision_type == DecisionType.SAFE_MODE
        assert swarm_loop.metrics.reasoning_fallback_count == 1

    @pytest.mark.asyncio
    async def test_fallback_on_missing_inner_loop_method(self, mock_registry, mock_election, mock_memory, agent_id):
        """Test fallback when inner_loop doesn't have expected methods."""
        # Create minimal inner_loop
        mock_inner_loop = MagicMock()
        # No reason() or step() method

        loop = SwarmDecisionLoop(
            inner_loop=mock_inner_loop,
            registry=mock_registry,
            election=mock_election,
            memory=mock_memory,
            agent_id=agent_id,
        )

        telemetry = create_test_telemetry()
        decision = await loop.step(telemetry)

        assert decision is not None


# Test: Decision History

class TestDecisionHistory:
    """Test decision history tracking."""

    @pytest.mark.asyncio
    async def test_decision_history_tracking(self, swarm_loop, mock_inner_loop):
        """Test decisions are tracked in history."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="action",
            confidence=0.9,
            reasoning="Test",
        )
        telemetry = create_test_telemetry()

        for _ in range(5):
            await swarm_loop.step(telemetry)

        history = await swarm_loop.get_decision_history(limit=10)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_history_respects_limit(self, swarm_loop, mock_inner_loop):
        """Test get_decision_history respects limit."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="action",
            confidence=0.9,
            reasoning="Test",
        )
        telemetry = create_test_telemetry()

        for _ in range(15):
            await swarm_loop.step(telemetry)

        history = await swarm_loop.get_decision_history(limit=5)

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_history_max_capacity(self, swarm_loop, mock_inner_loop):
        """Test history respects max capacity."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="action",
            confidence=0.9,
            reasoning="Test",
        )
        telemetry = create_test_telemetry()

        # Max capacity is 50
        for _ in range(100):
            await swarm_loop.step(telemetry)

        assert len(swarm_loop._decision_history) == swarm_loop._max_history


# Test: Constellation Health

class TestConstellationHealth:
    """Test constellation health calculation."""

    def test_calculate_health_no_peers(self, swarm_loop):
        """Test health with no peers."""
        health = swarm_loop._calculate_constellation_health([])

        assert health == 1.0  # Assume healthy if no info

    def test_calculate_health_with_peers(self, swarm_loop, mock_registry):
        """Test health calculation with multiple peers."""
        from astraguard.swarm.models import HealthSummary

        peers = [
            AgentID(constellation_id="test", satellite_serial=f"sat-{i:03d}")
            for i in range(3)
        ]

        # Create mock health summaries
        health_summaries = [
            MagicMock(health_score=0.9),
            MagicMock(health_score=0.8),
            MagicMock(health_score=0.85),
        ]

        mock_registry.get_peer_health.side_effect = health_summaries

        health = swarm_loop._calculate_constellation_health(peers)

        expected = (0.9 + 0.8 + 0.85) / 3
        assert abs(health - expected) < 0.01


# Test: Recent Decisions

class TestRecentDecisions:
    """Test recent decision tracking."""

    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, swarm_loop, mock_inner_loop):
        """Test retrieving recent decisions within time window."""
        mock_inner_loop.reason.return_value = Decision(
            decision_type=DecisionType.NORMAL,
            action="action_1",
            confidence=0.9,
            reasoning="Test",
        )
        telemetry = create_test_telemetry()

        for i in range(3):
            decision = Decision(
                decision_type=DecisionType.NORMAL,
                action=f"action_{i}",
                confidence=0.9,
                reasoning="Test",
            )
            swarm_loop._decision_history.append(decision)

        recent = await swarm_loop._get_recent_decisions(window_minutes=5)

        assert len(recent) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
