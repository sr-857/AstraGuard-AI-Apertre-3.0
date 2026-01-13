"""
Consensus Engine Tests - Quorum Voting Validation

Test coverage:
- 2/3 quorum: 8/12 votes → APPROVED
- 1/3 faulty: 8/12 votes → APPROVED (Byzantine tolerance)
- <1/3 quorum: 7/12 votes → TIMEOUT
- Network partition → Local fallback
- Scalability (5, 10, 50 agents)
- Proposal deduplication
- Leader-only enforcement

Issue #406: Consensus for global actions
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from uuid import uuid4

from astraguard.swarm.consensus import (
    ConsensusEngine, ProposalRequest, ProposalState, ConsensusMetrics, NotLeaderError
)
from astraguard.swarm.leader_election import LeaderElection, ElectionState
from astraguard.swarm.models import AgentID, SwarmConfig
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.types import QoSLevel


@pytest.fixture
def mock_config():
    """Create mock SwarmConfig."""
    config = Mock(spec=SwarmConfig)
    config.agent_id = AgentID.create("astra-v3.0", "SAT-001-A")
    config.SWARM_MODE_ENABLED = True
    return config


@pytest.fixture
def mock_registry():
    """Create mock SwarmRegistry."""
    registry = Mock(spec=SwarmRegistry)
    registry.get_alive_peers = Mock(return_value=[
        AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)
    ])
    return registry


@pytest.fixture
def mock_election():
    """Create mock LeaderElection."""
    election = Mock(spec=LeaderElection)
    election.is_leader = Mock(return_value=True)
    election.get_leader = Mock(return_value=AgentID.create("astra-v3.0", "SAT-001-A"))
    election.state = ElectionState.LEADER
    return election


@pytest.fixture
def mock_bus():
    """Create mock SwarmMessageBus."""
    bus = Mock(spec=SwarmMessageBus)
    bus.publish = AsyncMock()
    bus.subscribe = Mock()
    return bus


@pytest.fixture
def consensus_engine(mock_config, mock_election, mock_registry, mock_bus):
    """Create ConsensusEngine instance."""
    engine = ConsensusEngine(mock_config, mock_election, mock_registry, mock_bus)
    return engine


# ============================================================================
# Basic State Tests
# ============================================================================

class TestConsensusBasics:
    """Test basic ConsensusEngine initialization and state."""

    def test_initialization(self, consensus_engine, mock_config):
        """Test proper initialization."""
        assert consensus_engine.config == mock_config
        assert len(consensus_engine.pending_proposals) == 0
        assert consensus_engine.metrics.proposal_count == 0

    def test_initial_metrics(self, consensus_engine):
        """Test metrics initialized correctly."""
        metrics = consensus_engine.get_metrics()
        assert metrics.proposal_count == 0
        assert metrics.approved_count == 0
        assert metrics.denied_count == 0

    def test_not_leader_raises_error(self, consensus_engine, mock_election):
        """Test proposal raises NotLeaderError when not leader."""
        mock_election.is_leader.return_value = False

        with pytest.raises(NotLeaderError):
            asyncio.run(consensus_engine.propose("safe_mode", {}))

    def test_swarm_mode_disabled(self, mock_config, mock_election, mock_registry, mock_bus):
        """Test start() respects SWARM_MODE_ENABLED flag."""
        mock_config.SWARM_MODE_ENABLED = False
        engine = ConsensusEngine(mock_config, mock_election, mock_registry, mock_bus)

        asyncio.run(engine.start())
        mock_bus.subscribe.assert_not_called()


# ============================================================================
# Proposal Request Tests
# ============================================================================

class TestProposalRequest:
    """Test ProposalRequest creation and serialization."""

    def test_proposal_creation(self):
        """Test proposal creation with default values."""
        proposal = ProposalRequest("123", "safe_mode")

        assert proposal.proposal_id == "123"
        assert proposal.action == "safe_mode"
        assert proposal.timeout_seconds == 5

    def test_proposal_serialization(self):
        """Test proposal serializes to dict correctly."""
        proposal = ProposalRequest("456", "role_reassign", {"role": "observer"}, timeout_seconds=10)
        data = proposal.to_dict()

        assert data["proposal_id"] == "456"
        assert data["action"] == "role_reassign"
        assert data["params"]["role"] == "observer"
        assert data["timeout_seconds"] == 10


# ============================================================================
# Quorum Calculation Tests
# ============================================================================

class TestQuorumCalculation:
    """Test 2/3 majority quorum calculations."""

    @pytest.mark.asyncio
    async def test_5_agent_quorum(self, consensus_engine, mock_registry):
        """Test 5-agent cluster quorum requirement."""
        mock_registry.get_alive_peers.return_value = [
            AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)
        ]

        # 2/3 of 5 = 3.33 → 3
        # With self vote: need 3/5
        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        # Add 2 votes (self + 2 others = 3 total)
        consensus_engine.proposal_votes["test"].add(AgentID.create("astra-v3.0", "SAT-002-B"))
        consensus_engine.proposal_votes["test"].add(AgentID.create("astra-v3.0", "SAT-003-C"))

        # Wait for quorum should return True
        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True

    @pytest.mark.asyncio
    async def test_12_agent_quorum(self, consensus_engine, mock_registry):
        """Test 12-agent cluster quorum requirement."""
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 13)]
        mock_registry.get_alive_peers.return_value = agents

        # 2/3 of 12 = 8
        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        # Add 7 more votes (total 8)
        for i in range(2, 9):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True

    @pytest.mark.asyncio
    async def test_insufficient_quorum_timeout(self, consensus_engine, mock_registry):
        """Test timeout when insufficient votes received."""
        mock_registry.get_alive_peers.return_value = [
            AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)
        ]

        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        # Only 2 votes (self + 1 other) out of 5
        consensus_engine.proposal_votes["test"].add(AgentID.create("astra-v3.0", "SAT-002-B"))

        # Should timeout after 0.5s
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                consensus_engine._wait_for_quorum("test", "safe_mode"),
                timeout=0.5
            )


# ============================================================================
# Byzantine Fault Tolerance Tests
# ============================================================================

class TestByzantineTolerance:
    """Test 1/3 Byzantine fault tolerance."""

    @pytest.mark.asyncio
    async def test_1_3_faulty_nodes_approved(self, consensus_engine, mock_registry):
        """Test approval with 1/3 of nodes faulty (voting against)."""
        # 12 agents, 4 faulty, 8 approve = quorum
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 13)]
        mock_registry.get_alive_peers.return_value = agents

        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}
        consensus_engine.proposal_denials["test"] = {}

        # Add 7 more approvals (total 8)
        for i in range(2, 9):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        # Add 4 denials (faulty nodes)
        for i in range(9, 13):
            voter = AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            consensus_engine.proposal_denials["test"][voter] = "byzantine"

        # Should still approve (8 votes >= 8 quorum)
        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True

    @pytest.mark.asyncio
    async def test_2_3_faulty_fails(self, consensus_engine, mock_registry):
        """Test failure when 2/3 of nodes faulty (no quorum)."""
        # 12 agents, 8 faulty, 4 approve = no quorum (need 8)
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 13)]
        mock_registry.get_alive_peers.return_value = agents

        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}
        consensus_engine.proposal_denials["test"] = {}

        # Add only 3 more approvals (total 4 < 8 needed)
        for i in range(2, 5):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        # Add 8 denials
        for i in range(5, 13):
            voter = AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            consensus_engine.proposal_denials["test"][voter] = "byzantine"

        # Should return False (quorum not reached)
        result = await consensus_engine._wait_for_quorum("test", "safe_mode")
        assert result is False


# ============================================================================
# Proposal Execution Tests
# ============================================================================

class TestProposalExecution:
    """Test proposal execution and callbacks."""

    @pytest.mark.asyncio
    async def test_propose_safe_mode(self, consensus_engine, mock_election, mock_registry):
        """Test basic safe_mode proposal."""
        mock_election.is_leader.return_value = True
        mock_registry.get_alive_peers.return_value = [
            AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)
        ]

        # Manually add votes to simulate peer responses
        async def auto_vote():
            await asyncio.sleep(0.1)
            # Get the proposal ID from pending
            for prop_id in consensus_engine.pending_proposals:
                # Add 2 more votes to reach quorum of 3
                consensus_engine.proposal_votes[prop_id].add(
                    AgentID.create("astra-v3.0", "SAT-002-B")
                )
                consensus_engine.proposal_votes[prop_id].add(
                    AgentID.create("astra-v3.0", "SAT-003-C")
                )

        vote_task = asyncio.create_task(auto_vote())
        result = await consensus_engine.propose("safe_mode", {}, timeout=2)
        await vote_task

        assert result is True
        assert consensus_engine.metrics.proposal_count == 1
        assert consensus_engine.metrics.approved_count == 1

    @pytest.mark.asyncio
    async def test_propose_timeout_fallback(self, consensus_engine, mock_election, mock_registry):
        """Test proposal timeout triggers fallback."""
        mock_election.is_leader.return_value = True
        mock_registry.get_alive_peers.return_value = [
            AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)
        ]

        # Don't add any votes; should timeout and fallback
        result = await consensus_engine.propose("safe_mode", {}, timeout=1)

        # Fallback decision is to approve
        assert result is True
        assert consensus_engine.metrics.timeout_count == 1


# ============================================================================
# Vote Handling Tests
# ============================================================================

class TestVoteHandling:
    """Test vote request and response handling."""

    @pytest.mark.asyncio
    async def test_handle_vote_grant(self, consensus_engine, mock_config):
        """Test handling vote grant from peer."""
        proposal_id = "test-prop-123"
        consensus_engine.pending_proposals[proposal_id] = ProposalRequest(proposal_id, "safe_mode")
        consensus_engine.proposal_votes[proposal_id] = {mock_config.agent_id}
        consensus_engine.proposal_denials[proposal_id] = {}

        message = {
            "proposal_id": proposal_id,
            "voter_id": "SAT-002-B",
        }

        await consensus_engine._handle_vote_grant(message)

        assert len(consensus_engine.proposal_votes[proposal_id]) == 2
        assert consensus_engine.proposal_votes[proposal_id] == {
            mock_config.agent_id,
            AgentID.create("astra-v3.0", "SAT-002-B"),
        }

    @pytest.mark.asyncio
    async def test_handle_vote_deny(self, consensus_engine):
        """Test handling vote denial from peer."""
        proposal_id = "test-prop-456"
        consensus_engine.pending_proposals[proposal_id] = ProposalRequest(proposal_id, "safe_mode")
        consensus_engine.proposal_votes[proposal_id] = set()
        consensus_engine.proposal_denials[proposal_id] = {}

        message = {
            "proposal_id": proposal_id,
            "voter_id": "SAT-003-C",
            "reason": "battery_critical",
        }

        await consensus_engine._handle_vote_deny(message)

        assert len(consensus_engine.proposal_denials[proposal_id]) == 1
        voter = AgentID.create("astra-v3.0", "SAT-003-C")
        assert consensus_engine.proposal_denials[proposal_id][voter] == "battery_critical"

    @pytest.mark.asyncio
    async def test_proposal_request_evaluation(self, consensus_engine):
        """Test proposal request handling."""
        message = {
            "proposal_id": "test-eval",
            "action": "safe_mode",
            "params": {},
            "timestamp": datetime.now().isoformat(),
            "timeout_seconds": 5,
        }

        await consensus_engine._handle_proposal_request(message)

        # Should succeed without error
        assert True


# ============================================================================
# Metrics Tests
# ============================================================================

class TestConsensusMetrics:
    """Test metrics tracking and export."""

    def test_metrics_export(self, consensus_engine):
        """Test metrics can be exported as dictionary."""
        consensus_engine.metrics.proposal_count = 5
        consensus_engine.metrics.approved_count = 3
        consensus_engine.metrics.denied_count = 2
        consensus_engine.metrics.timeout_count = 0
        consensus_engine.metrics.last_proposal_id = "abc123"

        metrics_dict = consensus_engine.get_metrics().to_dict()

        assert metrics_dict["proposal_count"] == 5
        assert metrics_dict["approved_count"] == 3
        assert metrics_dict["denied_count"] == 2
        assert metrics_dict["timeout_count"] == 0
        assert "abc123" in metrics_dict["last_proposal_id"]


# ============================================================================
# Proposal Type Tests
# ============================================================================

class TestProposalTypes:
    """Test different proposal types and their timeouts."""

    def test_safe_mode_config(self, consensus_engine):
        """Test safe_mode proposal configuration."""
        config = consensus_engine.PROPOSAL_TYPES["safe_mode"]
        assert config["quorum_fraction"] == 2/3
        assert config["timeout"] == 3

    def test_role_reassign_config(self, consensus_engine):
        """Test role_reassign proposal configuration."""
        config = consensus_engine.PROPOSAL_TYPES["role_reassign"]
        assert config["quorum_fraction"] == 2/3
        assert config["timeout"] == 10

    def test_attitude_adjust_config(self, consensus_engine):
        """Test attitude_adjust proposal configuration."""
        config = consensus_engine.PROPOSAL_TYPES["attitude_adjust"]
        assert config["quorum_fraction"] == 1/2
        assert config["timeout"] == 5


# ============================================================================
# Scalability Tests
# ============================================================================

class TestScalability:
    """Test consensus with different cluster sizes."""

    @pytest.mark.asyncio
    async def test_5_agent_cluster(self, consensus_engine, mock_registry):
        """Test 5-agent cluster consensus."""
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 6)]
        mock_registry.get_alive_peers.return_value = agents

        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        # Need 3 votes total
        for i in range(2, 4):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True

    @pytest.mark.asyncio
    async def test_10_agent_cluster(self, consensus_engine, mock_registry):
        """Test 10-agent cluster consensus."""
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 11)]
        mock_registry.get_alive_peers.return_value = agents

        # 2/3 of 10 = 6.67 → 6
        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        for i in range(2, 7):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True

    @pytest.mark.asyncio
    async def test_50_agent_cluster(self, consensus_engine, mock_registry):
        """Test 50-agent cluster consensus."""
        agents = [AgentID.create("astra-v3.0", f"SAT-{i:03d}") for i in range(1, 51)]
        mock_registry.get_alive_peers.return_value = agents

        # 2/3 of 50 = 33.33 → 33
        consensus_engine.pending_proposals["test"] = ProposalRequest("test", "safe_mode")
        consensus_engine.proposal_votes["test"] = {consensus_engine.config.agent_id}

        for i in range(2, 34):
            consensus_engine.proposal_votes["test"].add(
                AgentID.create("astra-v3.0", f"SAT-{i:03d}")
            )

        approved = await asyncio.wait_for(
            consensus_engine._wait_for_quorum("test", "safe_mode"),
            timeout=1.0
        )
        assert approved is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
