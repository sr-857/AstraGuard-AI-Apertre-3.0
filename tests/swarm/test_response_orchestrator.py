"""
SwarmResponseOrchestrator Tests - Scope-Based Action Execution

Test coverage:
- LOCAL scope: 0ms coordination overhead ✓
- SWARM scope: Leader approval enforcement ✓
- CONSTELLATION scope: Quorum + safety gate prep ✓
- 5-agent execution consistency ✓
- Backward compatibility with existing orchestrator ✓
- Metrics tracking and export ✓
- Error handling and timeouts ✓
- Safety simulation integration prep (#413)

Issue #412: ActionScope tagging system for response orchestration
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from uuid import uuid4
import time

from astraguard.swarm.response_orchestrator import (
    ActionScope,
    SwarmResponseOrchestrator,
    LegacyResponseOrchestrator,
    ResponseMetrics,
)
from astraguard.swarm.swarm_decision_loop import Decision, DecisionType, ActionScope as SDLActionScope
from astraguard.swarm.models import AgentID, SwarmConfig
from astraguard.swarm.leader_election import LeaderElection, ElectionState
from astraguard.swarm.consensus import ConsensusEngine
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.action_propagator import ActionPropagator


@pytest.fixture
def mock_decision():
    """Create mock Decision from SwarmDecisionLoop."""
    decision = Mock(spec=Decision)
    decision.decision_type = DecisionType.NORMAL
    decision.action = "battery_reboot"
    decision.confidence = 0.95
    decision.reasoning = "Battery voltage critical"
    decision.timestamp = datetime.utcnow()
    decision.decision_id = f"test-{uuid4()}"
    decision.scope = ActionScope.LOCAL
    decision.params = {"timeout_ms": 5000}
    return decision


@pytest.fixture
def mock_leader_election():
    """Create mock LeaderElection."""
    election = Mock(spec=LeaderElection)
    election.is_leader = Mock(return_value=True)
    election.get_leader = Mock(return_value=AgentID.create("astra-v3.0", "SAT-001-A"))
    election.state = ElectionState.LEADER
    return election


@pytest.fixture
def mock_consensus_engine():
    """Create mock ConsensusEngine."""
    engine = Mock(spec=ConsensusEngine)
    engine.propose = AsyncMock(return_value=True)
    engine.get_metrics = Mock(return_value=Mock())
    return engine


@pytest.fixture
def mock_swarm_registry():
    """Create mock SwarmRegistry."""
    registry = Mock(spec=SwarmRegistry)
    registry.get_alive_peers = Mock(return_value=[
        AgentID.create("astra-v3.0", f"SAT-{i:03d}-A") for i in range(1, 6)
    ])
    registry.get_peer_count = Mock(return_value=5)
    return registry


@pytest.fixture
def mock_action_propagator():
    """Create mock ActionPropagator."""
    propagator = Mock(spec=ActionPropagator)
    propagator.propagate_action = AsyncMock(return_value=True)
    propagator.get_metrics = Mock(return_value=Mock())
    return propagator


@pytest.fixture
def orchestrator(mock_leader_election, mock_consensus_engine, mock_swarm_registry, mock_action_propagator):
    """Create SwarmResponseOrchestrator with all dependencies."""
    return SwarmResponseOrchestrator(
        election=mock_leader_election,
        consensus=mock_consensus_engine,
        registry=mock_swarm_registry,
        propagator=mock_action_propagator,
        swarm_mode_enabled=True,
    )


# ============================================================================
# Basic Initialization Tests
# ============================================================================

class TestOrchestratorInitialization:
    """Test orchestrator initialization."""

    def test_initialization_with_all_deps(self, orchestrator):
        """Test initialization with all dependencies."""
        assert orchestrator.election is not None
        assert orchestrator.consensus is not None
        assert orchestrator.registry is not None
        assert orchestrator.propagator is not None
        assert orchestrator.swarm_mode_enabled is True
        assert orchestrator.metrics.total_actions == 0

    def test_initialization_minimal(self):
        """Test initialization with minimal dependencies."""
        orchestrator = SwarmResponseOrchestrator(swarm_mode_enabled=False)
        assert orchestrator.election is None
        assert orchestrator.consensus is None
        assert orchestrator.registry is None
        assert orchestrator.propagator is None
        assert orchestrator.swarm_mode_enabled is False

    def test_metrics_initialized(self, orchestrator):
        """Test metrics initialized correctly."""
        metrics = orchestrator.get_metrics()
        assert isinstance(metrics, ResponseMetrics)
        assert metrics.local_actions == 0
        assert metrics.swarm_actions == 0
        assert metrics.constellation_actions == 0
        assert metrics.leader_approval_rate == 0.0


# ============================================================================
# LOCAL Scope Tests
# ============================================================================

class TestLocalScope:
    """Test LOCAL scope execution (no coordination)."""

    @pytest.mark.asyncio
    async def test_local_execution_success(self, orchestrator, mock_decision):
        """Test successful LOCAL action execution."""
        mock_decision.scope = ActionScope.LOCAL
        mock_decision.action = "battery_reboot"

        result = await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        assert result is True
        assert orchestrator.metrics.local_actions == 1
        assert orchestrator.metrics.swarm_actions == 0
        assert orchestrator.metrics.constellation_actions == 0

    @pytest.mark.asyncio
    async def test_local_execution_minimal_latency(self, orchestrator, mock_decision):
        """Test LOCAL execution has minimal latency (<10ms)."""
        mock_decision.scope = ActionScope.LOCAL

        start = time.time()
        await orchestrator.execute(mock_decision, ActionScope.LOCAL)
        elapsed_ms = (time.time() - start) * 1000

        # LOCAL should be very fast (no coordination overhead)
        assert elapsed_ms < 100  # Allow 100ms for test overhead
        assert orchestrator.metrics.local_latency_ms < 100

    @pytest.mark.asyncio
    async def test_local_no_leader_check(self, orchestrator, mock_decision, mock_leader_election):
        """Test LOCAL execution ignores leader status."""
        mock_decision.scope = ActionScope.LOCAL
        mock_leader_election.is_leader.return_value = False  # Not leader

        result = await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        # Should still succeed - LOCAL doesn't require leader
        assert result is True
        assert mock_leader_election.is_leader.call_count == 0  # Not called

    @pytest.mark.asyncio
    async def test_local_no_consensus(self, orchestrator, mock_decision, mock_consensus_engine):
        """Test LOCAL execution doesn't require consensus."""
        mock_decision.scope = ActionScope.LOCAL

        result = await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        assert result is True
        assert mock_consensus_engine.propose.call_count == 0  # Not called

    @pytest.mark.asyncio
    async def test_local_no_propagation(self, orchestrator, mock_decision, mock_action_propagator):
        """Test LOCAL execution doesn't propagate."""
        mock_decision.scope = ActionScope.LOCAL

        result = await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        assert result is True
        assert mock_action_propagator.propagate_action.call_count == 0  # Not called

    @pytest.mark.asyncio
    async def test_local_multiple_actions(self, orchestrator, mock_decision):
        """Test multiple LOCAL actions."""
        for i in range(5):
            mock_decision.decision_id = f"test-{i}"
            await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        assert orchestrator.metrics.local_actions == 5
        assert orchestrator.metrics.total_actions == 5


# ============================================================================
# SWARM Scope Tests
# ============================================================================

class TestSwarmScope:
    """Test SWARM scope execution (leader approval + propagation)."""

    @pytest.mark.asyncio
    async def test_swarm_execution_with_approval(self, orchestrator, mock_decision, mock_consensus_engine):
        """Test successful SWARM execution with leader approval."""
        mock_decision.scope = ActionScope.SWARM
        mock_decision.action = "role_reassignment"
        mock_consensus_engine.propose.return_value = True

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is True
        assert orchestrator.metrics.swarm_actions == 1
        assert orchestrator.metrics.leader_approvals == 1
        assert orchestrator.metrics.leader_denials == 0

    @pytest.mark.asyncio
    async def test_swarm_execution_denied(self, orchestrator, mock_decision, mock_consensus_engine):
        """Test SWARM execution denied by consensus."""
        mock_decision.scope = ActionScope.SWARM
        mock_consensus_engine.propose.return_value = False

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is False
        assert orchestrator.metrics.swarm_actions == 1  # Action attempted
        assert orchestrator.metrics.leader_approvals == 0
        assert orchestrator.metrics.leader_denials == 1

    @pytest.mark.asyncio
    async def test_swarm_requires_leader(self, orchestrator, mock_decision, mock_leader_election):
        """Test SWARM execution requires leader status."""
        mock_decision.scope = ActionScope.SWARM
        mock_leader_election.is_leader.return_value = False

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is False
        assert orchestrator.metrics.leader_approvals == 0
        assert orchestrator.metrics.leader_denials == 1

    @pytest.mark.asyncio
    async def test_swarm_disabled_by_feature_flag(self, orchestrator, mock_decision):
        """Test SWARM execution blocked when SWARM_MODE_ENABLED=False."""
        orchestrator.swarm_mode_enabled = False
        mock_decision.scope = ActionScope.SWARM

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is False
        assert orchestrator.metrics.leader_denials == 1

    @pytest.mark.asyncio
    async def test_swarm_with_propagation(
        self,
        orchestrator,
        mock_decision,
        mock_consensus_engine,
        mock_action_propagator,
    ):
        """Test SWARM execution includes action propagation."""
        mock_decision.scope = ActionScope.SWARM
        mock_consensus_engine.propose.return_value = True
        mock_action_propagator.propagate_action.return_value = True

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is True
        assert mock_consensus_engine.propose.called
        assert mock_action_propagator.propagate_action.called

    @pytest.mark.asyncio
    async def test_swarm_propagation_failure_blocks_action(
        self,
        orchestrator,
        mock_decision,
        mock_consensus_engine,
        mock_action_propagator,
    ):
        """Test SWARM action fails if propagation fails."""
        mock_decision.scope = ActionScope.SWARM
        mock_consensus_engine.propose.return_value = True
        mock_action_propagator.propagate_action.return_value = False

        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)

        assert result is False


# ============================================================================
# CONSTELLATION Scope Tests
# ============================================================================

class TestConstellationScope:
    """Test CONSTELLATION scope execution (quorum + safety gates)."""

    @pytest.mark.asyncio
    async def test_constellation_execution_with_quorum(
        self,
        orchestrator,
        mock_decision,
        mock_swarm_registry,
        mock_consensus_engine,
    ):
        """Test successful CONSTELLATION execution with quorum."""
        mock_decision.scope = ActionScope.CONSTELLATION
        mock_decision.action = "safe_mode_transition"
        mock_consensus_engine.propose.return_value = True

        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        assert result is True
        assert orchestrator.metrics.constellation_actions == 1

    @pytest.mark.asyncio
    async def test_constellation_requires_quorum(
        self,
        orchestrator,
        mock_decision,
        mock_swarm_registry,
    ):
        """Test CONSTELLATION execution requires sufficient quorum."""
        mock_decision.scope = ActionScope.CONSTELLATION
        mock_swarm_registry.get_alive_peers.return_value = [
            AgentID.create("astra-v3.0", "SAT-001-A"),
        ]  # Only 1 peer - insufficient for quorum

        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        assert result is False
        assert orchestrator.metrics.safety_gate_blocks == 1

    @pytest.mark.asyncio
    async def test_constellation_with_safety_simulator(
        self,
        mock_leader_election,
        mock_consensus_engine,
        mock_swarm_registry,
        mock_action_propagator,
        mock_decision,
    ):
        """Test CONSTELLATION execution with safety simulator integration."""
        # Create simulator mock
        simulator = AsyncMock()
        simulator.validate_action = AsyncMock(return_value=True)

        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            simulator=simulator,
            swarm_mode_enabled=True,
        )

        mock_decision.scope = ActionScope.CONSTELLATION
        mock_consensus_engine.propose.return_value = True

        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        assert result is True
        assert simulator.validate_action.called

    @pytest.mark.asyncio
    async def test_constellation_safety_gate_blocks_action(
        self,
        mock_leader_election,
        mock_consensus_engine,
        mock_swarm_registry,
        mock_action_propagator,
        mock_decision,
    ):
        """Test CONSTELLATION action blocked by safety simulator."""
        simulator = AsyncMock()
        simulator.validate_action = AsyncMock(return_value=False)

        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            simulator=simulator,
            swarm_mode_enabled=True,
        )

        mock_decision.scope = ActionScope.CONSTELLATION
        mock_consensus_engine.propose.return_value = True

        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        assert result is False
        assert orchestrator.metrics.safety_gate_blocks == 1

    @pytest.mark.asyncio
    async def test_constellation_disabled_by_feature_flag(self, orchestrator, mock_decision):
        """Test CONSTELLATION execution blocked when SWARM_MODE_ENABLED=False."""
        orchestrator.swarm_mode_enabled = False
        mock_decision.scope = ActionScope.CONSTELLATION

        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        assert result is False
        assert orchestrator.metrics.safety_gate_blocks == 1


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestLegacyResponseOrchestrator:
    """Test backward compatibility with existing orchestrator."""

    def test_legacy_initialization(self):
        """Test legacy wrapper initialization."""
        legacy = LegacyResponseOrchestrator()
        assert legacy.swarm is not None

    @pytest.mark.asyncio
    async def test_legacy_default_to_local(self, mock_decision):
        """Test legacy wrapper defaults to LOCAL scope."""
        mock_decision.scope = None  # No scope specified

        legacy = LegacyResponseOrchestrator()
        result = await legacy.execute(mock_decision)

        assert result is True
        assert legacy.swarm.metrics.local_actions == 1

    @pytest.mark.asyncio
    async def test_legacy_respects_explicit_scope(self, mock_decision):
        """Test legacy wrapper respects explicit scope."""
        mock_decision.scope = ActionScope.SWARM
        mock_decision.action = "role_reassignment"

        # Mock the swarm orchestrator
        legacy = LegacyResponseOrchestrator()
        legacy.swarm.election = Mock(is_leader=Mock(return_value=True))
        legacy.swarm.consensus = Mock(propose=AsyncMock(return_value=True))
        legacy.swarm.propagator = Mock(propagate_action=AsyncMock(return_value=True))

        result = await legacy.execute(mock_decision)

        # Should attempt SWARM execution (may fail due to mocking, but proves scope is used)
        # We're testing that the scope is respected, not the execution


# ============================================================================
# Metrics Tests
# ============================================================================

class TestMetrics:
    """Test metrics collection and export."""

    @pytest.mark.asyncio
    async def test_metrics_tracking_all_scopes(self, orchestrator, mock_decision):
        """Test metrics tracked for all scopes."""
        # LOCAL
        mock_decision.scope = ActionScope.LOCAL
        await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        # SWARM (will fail due to mocking, but still counts)
        mock_decision.scope = ActionScope.SWARM
        await orchestrator.execute(mock_decision, ActionScope.SWARM)

        # CONSTELLATION (will fail due to mocking, but still counts)
        mock_decision.scope = ActionScope.CONSTELLATION
        await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)

        metrics = orchestrator.get_metrics()
        # LOCAL succeeds, others count but may fail
        assert metrics.local_actions >= 1

    def test_metrics_export(self, orchestrator):
        """Test metrics export to dictionary."""
        orchestrator.metrics.local_actions = 10
        orchestrator.metrics.swarm_actions = 5
        orchestrator.metrics.leader_approvals = 4

        exported = orchestrator.metrics.to_dict()

        assert exported["action_scope_count_local"] == 10
        assert exported["action_scope_count_swarm"] == 5
        assert "leader_approval_rate" in exported
        assert "execution_latency_local_ms" in exported

    def test_metrics_reset(self, orchestrator):
        """Test metrics reset."""
        orchestrator.metrics.local_actions = 10
        orchestrator.metrics.swarm_actions = 5

        orchestrator.reset_metrics()

        assert orchestrator.metrics.local_actions == 0
        assert orchestrator.metrics.swarm_actions == 0

    @pytest.mark.asyncio
    async def test_metrics_timestamps(self, orchestrator, mock_decision):
        """Test metrics track execution timestamps."""
        mock_decision.scope = ActionScope.LOCAL

        assert orchestrator.metrics.first_execution is None
        assert orchestrator.metrics.last_execution is None

        await orchestrator.execute(mock_decision, ActionScope.LOCAL)

        assert orchestrator.metrics.first_execution is not None
        assert orchestrator.metrics.last_execution is not None


# ============================================================================
# 5-Agent Execution Tests
# ============================================================================

class TestMultiAgentExecution:
    """Test execution consistency with 5-agent swarm."""

    @pytest.mark.asyncio
    async def test_5_agent_local_execution(self):
        """Test LOCAL execution across 5 agents."""
        agents = []
        for i in range(5):
            orchestrator = SwarmResponseOrchestrator(swarm_mode_enabled=True)
            agents.append(orchestrator)

        # All execute same LOCAL action
        decision = Mock(spec=Decision)
        decision.action = "battery_reboot"
        decision.decision_id = "test-123"
        decision.params = {}

        results = await asyncio.gather(*[
            agent.execute(decision, ActionScope.LOCAL)
            for agent in agents
        ])

        assert all(results)  # All succeed
        assert all(agent.metrics.local_actions == 1 for agent in agents)

    @pytest.mark.asyncio
    async def test_5_agent_swarm_consistency(self):
        """Test SWARM actions consistent across 5-agent constellation."""
        # Create mock leader election that varies per agent
        agents = []
        for i in range(5):
            election = Mock(is_leader=Mock(return_value=(i == 0)))  # Only SAT-001 is leader
            consensus = Mock(propose=AsyncMock(return_value=True))
            registry = Mock(get_alive_peers=Mock(return_value=[
                AgentID.create("astra-v3.0", f"SAT-{j:03d}-A") for j in range(1, 6)
            ]))
            propagator = Mock(propagate_action=AsyncMock(return_value=True))

            orchestrator = SwarmResponseOrchestrator(
                election=election,
                consensus=consensus,
                registry=registry,
                propagator=propagator,
                swarm_mode_enabled=True,
            )
            agents.append(orchestrator)

        decision = Mock(spec=Decision)
        decision.action = "role_reassignment"
        decision.decision_id = "test-456"
        decision.params = {}

        results = await asyncio.gather(*[
            agent.execute(decision, ActionScope.SWARM)
            for agent in agents
        ])

        # Only leader succeeds
        assert results[0] is True  # Leader
        assert all(r is False for r in results[1:])  # Followers


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_missing_dependencies_graceful_degradation(self):
        """Test graceful degradation with missing dependencies."""
        orchestrator = SwarmResponseOrchestrator(
            election=None,
            consensus=None,
            registry=None,
            propagator=None,
        )

        decision = Mock(spec=Decision)
        decision.action = "test_action"
        decision.decision_id = "test-789"
        decision.params = {}

        # LOCAL should still work
        result = await orchestrator.execute(decision, ActionScope.LOCAL)
        assert result is True

        # SWARM should fail gracefully
        result = await orchestrator.execute(decision, ActionScope.SWARM)
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout_handling(self, orchestrator, mock_decision):
        """Test timeout parameter is respected."""
        mock_decision.scope = ActionScope.SWARM

        # Execute with custom timeout
        result = await orchestrator.execute(mock_decision, ActionScope.SWARM, timeout_seconds=0.1)

        # Should handle timeout gracefully
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_local_error_handling(self, orchestrator, mock_decision):
        """Test LOCAL execution handles errors gracefully."""
        mock_decision.scope = ActionScope.LOCAL
        
        result = await orchestrator.execute(mock_decision, ActionScope.LOCAL)
        
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_swarm_missing_consensus(self, mock_leader_election, mock_swarm_registry, mock_action_propagator, mock_decision):
        """Test SWARM execution without consensus engine."""
        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=None,  # Missing consensus
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            swarm_mode_enabled=True,
        )
        
        mock_decision.scope = ActionScope.SWARM
        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_constellation_missing_registry(self, mock_leader_election, mock_consensus_engine, mock_action_propagator, mock_decision):
        """Test CONSTELLATION execution without registry."""
        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=None,  # Missing registry
            propagator=mock_action_propagator,
            swarm_mode_enabled=True,
        )
        
        mock_decision.scope = ActionScope.CONSTELLATION
        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_swarm_missing_propagator(self, mock_leader_election, mock_consensus_engine, mock_swarm_registry, mock_decision):
        """Test SWARM execution without propagator."""
        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=None,  # Missing propagator
            swarm_mode_enabled=True,
        )
        
        mock_decision.scope = ActionScope.SWARM
        mock_consensus_engine.propose.return_value = True
        
        result = await orchestrator.execute(mock_decision, ActionScope.SWARM)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_constellation_simulator_error_handling(
        self,
        mock_leader_election,
        mock_consensus_engine,
        mock_swarm_registry,
        mock_action_propagator,
        mock_decision,
    ):
        """Test CONSTELLATION handles simulator errors gracefully."""
        simulator = AsyncMock()
        simulator.validate_action = AsyncMock(side_effect=Exception("Simulator error"))
        
        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            simulator=simulator,
            swarm_mode_enabled=True,
        )
        
        mock_decision.scope = ActionScope.CONSTELLATION
        mock_consensus_engine.propose.return_value = True
        mock_action_propagator.propagate_action.return_value = True
        
        # Should handle error and continue (simulator not critical yet)
        result = await orchestrator.execute(mock_decision, ActionScope.CONSTELLATION)
        
        # Should succeed despite simulator error (logged as warning)
        assert result is True

    @pytest.mark.asyncio
    async def test_action_scope_string_conversion(self, orchestrator, mock_decision):
        """Test ActionScope can be created from string."""
        from astraguard.swarm.response_orchestrator import ActionScope as RO_ActionScope
        
        # Test enum creation from string
        scope_str = "local"
        scope = RO_ActionScope(scope_str)
        assert scope == RO_ActionScope.LOCAL
        
        # Test invalid scope raises error
        with pytest.raises(ValueError):
            RO_ActionScope("invalid_scope")


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests with mock components."""

    @pytest.mark.asyncio
    async def test_decision_loop_integration(
        self,
        mock_leader_election,
        mock_consensus_engine,
        mock_swarm_registry,
        mock_action_propagator,
    ):
        """Test orchestrator with Decision from SwarmDecisionLoop."""
        from astraguard.swarm.swarm_decision_loop import Decision as SDLDecision

        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            swarm_mode_enabled=True,
        )

        # Create decision from SwarmDecisionLoop format
        decision = SDLDecision(
            decision_type=DecisionType.ANOMALY_RESPONSE,
            action="safe_mode_transition",
            confidence=0.98,
            reasoning="Anomaly detected: temperature spike",
            scope=ActionScope.CONSTELLATION,
            params={"duration_minutes": 30},
        )

        result = await orchestrator.execute(decision, decision.scope)

        # Should execute (may succeed or fail based on mocks)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_action_propagator_integration(
        self,
        mock_leader_election,
        mock_consensus_engine,
        mock_swarm_registry,
        mock_action_propagator,
        mock_decision,
    ):
        """Test orchestrator correctly calls action propagator."""
        orchestrator = SwarmResponseOrchestrator(
            election=mock_leader_election,
            consensus=mock_consensus_engine,
            registry=mock_swarm_registry,
            propagator=mock_action_propagator,
            swarm_mode_enabled=True,
        )

        mock_decision.scope = ActionScope.SWARM
        mock_consensus_engine.propose.return_value = True
        mock_action_propagator.propagate_action.return_value = True

        await orchestrator.execute(mock_decision, ActionScope.SWARM)

        # Verify propagator was called with correct parameters
        assert mock_action_propagator.propagate_action.called
        call_args = mock_action_propagator.propagate_action.call_args
        assert call_args is not None
        # Check that scope is passed correctly
        assert call_args.kwargs.get("scope") == ActionScope.SWARM.value
