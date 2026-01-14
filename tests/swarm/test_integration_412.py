"""
Full Stack Integration Test for Issue #412: ActionScope Tagging System

Tests the complete pipeline from SwarmDecisionLoop (#411) through
ResponseOrchestrator (#412) with all dependencies (#397-411).

5-agent constellation test with:
- LOCAL actions (immediate execution)
- SWARM actions (leader approval + propagation)
- CONSTELLATION actions (quorum + safety gates)

This validates integration across:
  #397: Models (AgentID, SatelliteRole)
  #400: SwarmRegistry (peer discovery)
  #405: LeaderElection (leader enforcement)
  #406: ConsensusEngine (quorum voting)
  #408: ActionPropagator (action broadcast)
  #411: SwarmDecisionLoop (decision generation)
  #412: ResponseOrchestrator (scope-based execution)
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock
from typing import List

from astraguard.swarm.response_orchestrator import (
    ActionScope,
    SwarmResponseOrchestrator,
    ResponseMetrics,
)
from astraguard.swarm.swarm_decision_loop import Decision, DecisionType, ActionScope as SDLActionScope
from astraguard.swarm.models import AgentID, SatelliteRole
from astraguard.swarm.registry import SwarmRegistry, PeerState
from astraguard.swarm.leader_election import LeaderElection, ElectionState
from astraguard.swarm.consensus import ConsensusEngine
from astraguard.swarm.action_propagator import ActionPropagator


class MockConstellation:
    """Simulates a 5-agent constellation for integration testing."""

    def __init__(self, leader_index: int = 0):
        """Initialize 5-agent constellation."""
        self.agents: List[AgentID] = [
            AgentID.create("astra-v3.0", f"SAT-{i:03d}-A") for i in range(1, 6)
        ]
        self.leader_index = leader_index
        self.leader_id = self.agents[leader_index]
        self.orchestrators: List[SwarmResponseOrchestrator] = []
        self.actions_executed = []  # Track executed actions
        self.election_states = {agent: ElectionState.FOLLOWER for agent in self.agents}
        self.election_states[self.leader_id] = ElectionState.LEADER

    def _create_mock_election(self, agent_idx: int) -> Mock:
        """Create mock LeaderElection for an agent."""
        election = Mock(spec=LeaderElection)
        agent = self.agents[agent_idx]
        election.is_leader = Mock(return_value=(agent == self.leader_id))
        election.get_leader = Mock(return_value=self.leader_id)
        election.state = ElectionState.LEADER if agent == self.leader_id else ElectionState.FOLLOWER
        return election

    def _create_mock_consensus(self) -> Mock:
        """Create mock ConsensusEngine."""
        engine = Mock(spec=ConsensusEngine)
        engine.propose = AsyncMock(return_value=True)  # Always approve
        return engine

    def _create_mock_registry(self) -> Mock:
        """Create mock SwarmRegistry."""
        registry = Mock(spec=SwarmRegistry)
        registry.get_alive_peers = Mock(return_value=self.agents)
        registry.get_peer_count = Mock(return_value=len(self.agents))
        return registry

    def _create_mock_propagator(self) -> Mock:
        """Create mock ActionPropagator."""
        propagator = Mock(spec=ActionPropagator)
        propagator.propagate_action = AsyncMock(return_value=True)
        return propagator

    async def initialize(self):
        """Initialize 5-agent constellation with orchestrators."""
        for i in range(5):
            orchestrator = SwarmResponseOrchestrator(
                election=self._create_mock_election(i),
                consensus=self._create_mock_consensus(),
                registry=self._create_mock_registry(),
                propagator=self._create_mock_propagator(),
                swarm_mode_enabled=True,
            )
            self.orchestrators.append(orchestrator)

    async def execute_on_all(
        self,
        decision: Decision,
        scope: ActionScope,
    ) -> List[bool]:
        """Execute decision on all agents."""
        results = await asyncio.gather(*[
            orchestrator.execute(decision, scope)
            for orchestrator in self.orchestrators
        ])
        return results

    async def execute_on_leader(
        self,
        decision: Decision,
        scope: ActionScope,
    ) -> bool:
        """Execute decision on leader only."""
        return await self.orchestrators[self.leader_index].execute(decision, scope)

    def get_metrics_summary(self) -> dict:
        """Get aggregated metrics from all agents."""
        return {
            "local_actions_total": sum(o.metrics.local_actions for o in self.orchestrators),
            "swarm_actions_total": sum(o.metrics.swarm_actions for o in self.orchestrators),
            "constellation_actions_total": sum(o.metrics.constellation_actions for o in self.orchestrators),
            "leader_approvals_total": sum(o.metrics.leader_approvals for o in self.orchestrators),
            "leader_denials_total": sum(o.metrics.leader_denials for o in self.orchestrators),
        }


@pytest.fixture
async def constellation_5_agent():
    """Create and initialize 5-agent constellation."""
    constellation = MockConstellation(leader_index=0)
    await constellation.initialize()
    return constellation


class TestIntegration412FullStack:
    """Full-stack integration tests for Issue #412."""

    @pytest.mark.asyncio
    async def test_5_agent_local_execution(self, constellation_5_agent):
        """Test LOCAL actions execute on all 5 agents."""
        constellation = constellation_5_agent

        decision = Decision(
            decision_type=DecisionType.NORMAL,
            action="battery_reboot",
            confidence=0.99,
            reasoning="Battery voltage critical",
            scope=ActionScope.LOCAL,
            params={"timeout_ms": 5000},
        )

        results = await constellation.execute_on_all(decision, ActionScope.LOCAL)

        # All agents should succeed
        assert all(results), f"Expected all True, got {results}"
        assert len(results) == 5

        # All should count local action
        summary = constellation.get_metrics_summary()
        assert summary["local_actions_total"] == 5

    @pytest.mark.asyncio
    async def test_5_agent_swarm_leader_only(self, constellation_5_agent):
        """Test SWARM actions execute only on leader."""
        constellation = constellation_5_agent

        decision = Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="role_reassignment",
            confidence=0.95,
            reasoning="Optimize satellite roles",
            scope=ActionScope.SWARM,
            params={"new_role": "BACKUP"},
        )

        results = await constellation.execute_on_all(decision, ActionScope.SWARM)

        # Only leader should succeed
        assert results[0] is True, "Leader should succeed"
        assert all(r is False for r in results[1:]), "Followers should fail"

        # Only leader should count SWARM actions
        summary = constellation.get_metrics_summary()
        assert summary["swarm_actions_total"] == 5  # All counted attempt
        assert summary["leader_approvals_total"] == 1  # Only leader approves
        assert summary["leader_denials_total"] == 4  # Followers denied

    @pytest.mark.asyncio
    async def test_5_agent_constellation_quorum(self, constellation_5_agent):
        """Test CONSTELLATION actions execute on all with quorum."""
        constellation = constellation_5_agent

        decision = Decision(
            decision_type=DecisionType.SAFE_MODE,
            action="safe_mode_transition",
            confidence=0.92,
            reasoning="Anomaly detected: thermal spike",
            scope=ActionScope.CONSTELLATION,
            params={"duration_minutes": 30},
        )

        results = await constellation.execute_on_all(decision, ActionScope.CONSTELLATION)

        # All should succeed (quorum available)
        assert all(results), f"Expected all True (quorum available), got {results}"

        summary = constellation.get_metrics_summary()
        assert summary["constellation_actions_total"] == 5

    @pytest.mark.asyncio
    async def test_scope_consistency_across_agents(self, constellation_5_agent):
        """Test scope execution is consistent across constellation."""
        constellation = constellation_5_agent

        # Create 3 decisions with different scopes
        local_decision = Decision(
            decision_type=DecisionType.NORMAL,
            action="thermal_throttle",
            confidence=0.95,
            reasoning="Local thermal management",
            scope=ActionScope.LOCAL,
            params={},
        )

        swarm_decision = Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="role_change",
            confidence=0.90,
            reasoning="Optimize constellation roles",
            scope=ActionScope.SWARM,
            params={},
        )

        constellation_decision = Decision(
            decision_type=DecisionType.SAFE_MODE,
            action="safe_mode",
            confidence=0.88,
            reasoning="Emergency safe mode",
            scope=ActionScope.CONSTELLATION,
            params={},
        )

        # Execute all
        local_results = await constellation.execute_on_all(local_decision, ActionScope.LOCAL)
        swarm_results = await constellation.execute_on_all(swarm_decision, ActionScope.SWARM)
        constellation_results = await constellation.execute_on_all(
            constellation_decision,
            ActionScope.CONSTELLATION,
        )

        # LOCAL: all succeed
        assert all(local_results)

        # SWARM: only leader succeeds
        assert local_results[0] is True
        assert all(r is False for r in swarm_results[1:])

        # CONSTELLATION: all succeed (quorum available)
        assert all(constellation_results)

    @pytest.mark.asyncio
    async def test_leader_election_change(self, constellation_5_agent):
        """Test behavior when leader changes."""
        constellation = constellation_5_agent

        # Simulate leader election change
        original_leader = constellation.leader_id
        new_leader_idx = 2
        constellation.leader_id = constellation.agents[new_leader_idx]

        # Update election mocks
        for i in range(5):
            constellation.orchestrators[i].election.is_leader = Mock(
                return_value=(constellation.agents[i] == constellation.leader_id)
            )

        # Execute SWARM action on new leader
        decision = Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="role_reassignment",
            confidence=0.95,
            reasoning="New leader takes action",
            scope=ActionScope.SWARM,
            params={},
        )

        results = await constellation.execute_on_all(decision, ActionScope.SWARM)

        # Now index 2 (new leader) should succeed
        assert results[new_leader_idx] is True
        assert all(results[i] is False for i in range(5) if i != new_leader_idx)

    @pytest.mark.asyncio
    async def test_quorum_unavailable(self, constellation_5_agent):
        """Test CONSTELLATION fails with insufficient quorum."""
        constellation = constellation_5_agent

        # Simulate only 1 agent alive (below 2/3 quorum)
        for orchestrator in constellation.orchestrators:
            orchestrator.registry.get_alive_peers = Mock(
                return_value=constellation.agents[:1]
            )

        decision = Decision(
            decision_type=DecisionType.SAFE_MODE,
            action="safe_mode",
            confidence=0.90,
            reasoning="Need quorum",
            scope=ActionScope.CONSTELLATION,
            params={},
        )

        results = await constellation.execute_on_all(decision, ActionScope.CONSTELLATION)

        # All should fail (insufficient quorum)
        assert all(r is False for r in results)

        summary = constellation.get_metrics_summary()
        # All would attempt but fail on quorum check
        assert summary["constellation_actions_total"] == 5

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, constellation_5_agent):
        """Test metrics aggregation across constellation."""
        constellation = constellation_5_agent

        # Execute mixed workload
        for i in range(3):
            local_decision = Decision(
                decision_type=DecisionType.NORMAL,
                action=f"local_action_{i}",
                confidence=0.95,
                reasoning="Local execution",
                scope=ActionScope.LOCAL,
                params={},
            )
            await constellation.execute_on_all(local_decision, ActionScope.LOCAL)

        for i in range(2):
            swarm_decision = Decision(
                decision_type=DecisionType.RESOURCE_OPTIMIZATION,
                action=f"swarm_action_{i}",
                confidence=0.90,
                reasoning="Swarm execution",
                scope=ActionScope.SWARM,
                params={},
            )
            await constellation.execute_on_leader(swarm_decision, ActionScope.SWARM)

        summary = constellation.get_metrics_summary()

        # 3 LOCAL × 5 agents = 15
        assert summary["local_actions_total"] == 15

        # 2 SWARM actions on leader only = 2 (only leader executes SWARM)
        assert summary["swarm_actions_total"] == 2
        assert summary["leader_approvals_total"] == 2

    @pytest.mark.asyncio
    async def test_decision_flow_411_to_412(self, constellation_5_agent):
        """Test complete flow from SwarmDecisionLoop (#411) to ResponseOrchestrator (#412)."""
        constellation = constellation_5_agent

        # Simulate decision from SwarmDecisionLoop (#411)
        # with ActionScope tag (new in Issue #412)
        decision = Decision(
            decision_type=DecisionType.ANOMALY_RESPONSE,
            action="anomaly_response_safe_mode",
            confidence=0.98,
            reasoning="Anomaly detected by ML model",
            scope=ActionScope.CONSTELLATION,  # Issue #412: ActionScope tag
            params={"anomaly_score": 0.87, "duration_minutes": 30},
            decision_id="decision-2024-001",
        )

        # Execute on constellation
        results = await constellation.execute_on_all(decision, decision.scope)

        # All should succeed
        assert all(results)

        # Verify metrics
        summary = constellation.get_metrics_summary()
        assert summary["constellation_actions_total"] == 5

    @pytest.mark.asyncio
    async def test_feature_flag_swarm_mode(self, constellation_5_agent):
        """Test SWARM_MODE_ENABLED feature flag."""
        constellation = constellation_5_agent

        # Disable swarm mode
        for orchestrator in constellation.orchestrators:
            orchestrator.swarm_mode_enabled = False

        swarm_decision = Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="requires_swarm",
            confidence=0.95,
            reasoning="Needs swarm coordination",
            scope=ActionScope.SWARM,
            params={},
        )

        results = await constellation.execute_on_all(swarm_decision, ActionScope.SWARM)

        # All should fail (swarm mode disabled)
        assert all(r is False for r in results)

        # LOCAL should still work
        local_decision = Decision(
            decision_type=DecisionType.NORMAL,
            action="local_only",
            confidence=0.95,
            reasoning="Local execution",
            scope=ActionScope.LOCAL,
            params={},
        )

        results = await constellation.execute_on_all(local_decision, ActionScope.LOCAL)

        # All should succeed (LOCAL doesn't need swarm mode)
        assert all(results)

    @pytest.mark.asyncio
    async def test_action_params_propagation(self, constellation_5_agent):
        """Test action parameters propagate correctly."""
        constellation = constellation_5_agent

        decision = Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="battery_management",
            confidence=0.95,
            reasoning="Manage battery resource",
            scope=ActionScope.SWARM,
            params={
                "max_discharge_rate": 0.8,
                "min_voltage": 3.2,
                "target_temperature": 25,
                "timeout_minutes": 10,
            },
        )

        # Leader executes
        result = await constellation.execute_on_leader(decision, ActionScope.SWARM)

        assert result is True

        # Verify propagator was called with correct params
        leader_orchestrator = constellation.orchestrators[constellation.leader_index]
        assert leader_orchestrator.propagator.propagate_action.called

        # Check propagate call included params
        call_kwargs = leader_orchestrator.propagator.propagate_action.call_args.kwargs
        assert call_kwargs.get("scope") == ActionScope.SWARM.value


@pytest.mark.asyncio
async def test_integration_with_real_mocks():
    """Integration test with fully mocked swarm components."""
    # This test validates the integration without actual network/consensus logic

    # Create 3 agents
    agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}-A") for i in range(1, 4)]
    leader = agents[0]

    orchestrators = []
    for agent in agents:
        election = Mock(spec=LeaderElection)
        election.is_leader = Mock(return_value=(agent == leader))
        election.get_leader = Mock(return_value=leader)

        consensus = Mock(spec=ConsensusEngine)
        consensus.propose = AsyncMock(return_value=True)

        registry = Mock(spec=SwarmRegistry)
        registry.get_alive_peers = Mock(return_value=agents)

        propagator = Mock(spec=ActionPropagator)
        propagator.propagate_action = AsyncMock(return_value=True)

        orchestrator = SwarmResponseOrchestrator(
            election=election,
            consensus=consensus,
            registry=registry,
            propagator=propagator,
            swarm_mode_enabled=True,
        )
        orchestrators.append(orchestrator)

    # Execute mixed actions
    decisions = [
        Decision(
            decision_type=DecisionType.NORMAL,
            action="local_check",
            confidence=0.99,
            reasoning="Local health check",
            scope=ActionScope.LOCAL,
            params={},
        ),
        Decision(
            decision_type=DecisionType.RESOURCE_OPTIMIZATION,
            action="role_optimize",
            confidence=0.95,
            reasoning="Optimize constellation roles",
            scope=ActionScope.SWARM,
            params={},
        ),
        Decision(
            decision_type=DecisionType.SAFE_MODE,
            action="safe_transition",
            confidence=0.92,
            reasoning="Transition to safe mode",
            scope=ActionScope.CONSTELLATION,
            params={},
        ),
    ]

    results = {}
    for decision in decisions:
        scope_results = []
        for orchestrator in orchestrators:
            result = await orchestrator.execute(decision, decision.scope)
            scope_results.append(result)
        results[decision.action] = scope_results

    # Verify results
    assert all(results["local_check"])  # All succeed
    assert results["role_optimize"][0] is True  # Leader succeeds
    assert all(r is False for r in results["role_optimize"][1:])  # Followers fail
    assert all(results["safe_transition"])  # All succeed
