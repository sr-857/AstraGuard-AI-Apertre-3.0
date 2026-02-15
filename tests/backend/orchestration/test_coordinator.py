"""Unit tests for coordinator decision logic and behaviors."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from backend.orchestration.coordinator import (
    LocalCoordinator,
    ConsensusDecision,
    NodeInfo,
)
from backend.orchestration.distributed_coordinator import DistributedResilienceCoordinator

# Mark coordinator tests as slow due to distributed operations
pytestmark = [pytest.mark.slow, pytest.mark.timeout(60)]


class MockHealthMonitor:
    """Mock health monitor for testing."""
    
    def __init__(self, status="HEALTHY", circuit_state="CLOSED", fallback_mode="PRIMARY"):
        self.status = status
        self.circuit_state = circuit_state
        self.fallback_mode = fallback_mode
    
    async def get_comprehensive_state(self):
        return {
            "system": {"status": self.status, "failed_components": 0},
            "circuit_breaker": {"state": self.circuit_state},
            "fallback": {"mode": self.fallback_mode},
            "retry": {"state": "STABLE", "failures_1h": 0},
        }


class MockRedisClient:
    """Mock Redis client for testing."""
    
    def __init__(self):
        self.connected = True
        self.leader = None
        self.votes = {}
        self.states = {}
    
    async def leader_election(self, instance_id, ttl=30):
        """Mock leader election."""
        if self.leader is None:
            self.leader = instance_id
            return True
        return self.leader == instance_id
    
    async def renew_leadership(self, instance_id, ttl=30):
        """Mock leadership renewal."""
        if self.leader == instance_id:
            return True
        return False
    
    async def get_leader(self):
        """Get current leader."""
        return self.leader
    
    async def register_vote(self, instance_id, vote, ttl=30):
        """Register a vote."""
        self.votes[instance_id] = vote
    
    async def get_cluster_votes(self):
        """Get all votes."""
        return self.votes.copy()
    
    async def publish_state(self, channel, state):
        """Publish state to channel."""
        self.states[channel] = state
    
    async def get_all_instance_health(self):
        """Get all instance health."""
        return {
            instance_id: {"health_score": vote.get("health_score", 0.5)}
            for instance_id, vote in self.votes.items()
        }


class TestLocalCoordinator:
    """Test LocalCoordinator for single-instance mode."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create mock health monitor."""
        return MockHealthMonitor()
    
    @pytest.fixture
    def coordinator(self, health_monitor):
        """Create local coordinator."""
        return LocalCoordinator(
            health_monitor=health_monitor,
            instance_id="test-local-1",
        )
    
    def test_initialization(self, coordinator):
        """Test coordinator initializes correctly."""
        assert coordinator.instance_id == "test-local-1"
        assert coordinator.is_leader is False
        assert coordinator._running is False
        assert coordinator.quorum_threshold == 0.5
    
    @pytest.mark.asyncio
    async def test_startup(self, coordinator):
        """Test coordinator startup."""
        await coordinator.startup()
        
        assert coordinator._running is True
        assert coordinator.is_leader is True
        assert len(coordinator._nodes) == 1
        assert coordinator.instance_id in coordinator._nodes
    
    @pytest.mark.asyncio
    async def test_shutdown(self, coordinator):
        """Test coordinator shutdown."""
        await coordinator.startup()
        await coordinator.shutdown()
        
        assert coordinator._running is False
        assert len(coordinator._nodes) == 0
    
    @pytest.mark.asyncio
    async def test_elect_leader_always_succeeds(self, coordinator):
        """Test leader election always succeeds in local mode."""
        result = await coordinator.elect_leader()
        
        assert result is True
        assert coordinator.is_leader is True
    
    @pytest.mark.asyncio
    async def test_assign_work_returns_self(self, coordinator):
        """Test work assignment returns self."""
        await coordinator.startup()
        
        work_item = {"task": "test_task"}
        assigned_to = await coordinator.assign_work(work_item)
        
        assert assigned_to == coordinator.instance_id
        assert len(coordinator._work_queue) == 1
    
    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(self, coordinator):
        """Test heartbeat updates node timestamp."""
        await coordinator.startup()
        
        initial_time = coordinator._nodes[coordinator.instance_id].last_heartbeat
        await asyncio.sleep(0.1)
        await coordinator.heartbeat()
        
        updated_time = coordinator._nodes[coordinator.instance_id].last_heartbeat
        assert updated_time > initial_time
    
    @pytest.mark.asyncio
    async def test_heartbeat_updates_health_score(self, coordinator, health_monitor):
        """Test heartbeat updates health score."""
        await coordinator.startup()
        
        # Change health status
        health_monitor.status = "DEGRADED"
        await coordinator.heartbeat()
        
        node = coordinator._nodes[coordinator.instance_id]
        assert node.health_score == 0.6  # DEGRADED = 0.6
    
    @pytest.mark.asyncio
    async def test_get_nodes_returns_self(self, coordinator):
        """Test get_nodes returns only self."""
        await coordinator.startup()
        
        nodes = await coordinator.get_nodes()
        
        assert len(nodes) == 1
        assert nodes[0].instance_id == coordinator.instance_id
        assert nodes[0].is_leader is True
    
    @pytest.mark.asyncio
    async def test_get_consensus_returns_local_state(self, coordinator, health_monitor):
        """Test consensus returns local state in single-instance mode."""
        await coordinator.startup()
        
        consensus = await coordinator.get_consensus()
        
        assert isinstance(consensus, ConsensusDecision)
        assert consensus.circuit_state == "CLOSED"
        assert consensus.fallback_mode == "PRIMARY"
        assert consensus.leader_instance == coordinator.instance_id
        assert consensus.quorum_met is True
        assert consensus.voting_instances == 1
        assert consensus.consensus_strength == 1.0
    
    @pytest.mark.asyncio
    async def test_get_consensus_handles_different_states(self, coordinator, health_monitor):
        """Test consensus reflects different health states."""
        await coordinator.startup()
        
        # Change state
        health_monitor.circuit_state = "OPEN"
        health_monitor.fallback_mode = "SAFE"
        
        consensus = await coordinator.get_consensus()
        
        assert consensus.circuit_state == "OPEN"
        assert consensus.fallback_mode == "SAFE"
    
    def test_get_metrics(self, coordinator):
        """Test metrics retrieval."""
        metrics = coordinator.get_metrics()
        
        assert metrics["instance_id"] == coordinator.instance_id
        assert metrics["is_leader"] is False
        assert metrics["running"] is False
        assert metrics["coordinator_type"] == "local"


class TestDistributedCoordinatorVoting:
    """Test distributed coordinator voting logic."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create mock health monitor."""
        return MockHealthMonitor()
    
    @pytest.fixture
    def redis_client(self):
        """Create mock Redis client."""
        return MockRedisClient()
    
    @pytest.fixture
    def coordinator(self, redis_client, health_monitor):
        """Create distributed coordinator."""
        return DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            instance_id="test-dist-1",
        )
    
    def test_initialization(self, coordinator):
        """Test coordinator initializes correctly."""
        assert coordinator.instance_id == "test-dist-1"
        assert coordinator.is_leader is False
        assert coordinator._running is False
        assert coordinator.quorum_threshold == 0.5
    
    def test_compute_health_score_healthy(self, coordinator):
        """Test health score computation for healthy state."""
        state = {
            "system": {"status": "HEALTHY"},
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"state": "STABLE"},
        }
        
        score = coordinator._compute_health_score(state)
        
        # Perfect health: 1.0 * 0.40 + 1.0 * 0.35 + 1.0 * 0.25 = 1.0
        assert score == 1.0
    
    def test_compute_health_score_degraded(self, coordinator):
        """Test health score computation for degraded state."""
        state = {
            "system": {"status": "DEGRADED"},
            "circuit_breaker": {"state": "HALF_OPEN"},
            "retry": {"state": "ELEVATED"},
        }
        
        score = coordinator._compute_health_score(state)
        
        # Degraded: 0.6 * 0.40 + 0.5 * 0.35 + 0.5 * 0.25 = 0.24 + 0.175 + 0.125 = 0.54
        assert abs(score - 0.54) < 0.001
    
    def test_compute_health_score_failed(self, coordinator):
        """Test health score computation for failed state."""
        state = {
            "system": {"status": "FAILED"},
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"state": "CRITICAL"},
        }
        
        score = coordinator._compute_health_score(state)
        
        # Failed: 0.0 * 0.40 + 0.0 * 0.35 + 0.0 * 0.25 = 0.0
        assert score == 0.0
    
    def test_majority_vote_clear_majority(self, coordinator):
        """Test majority voting with clear majority."""
        votes = ["CLOSED", "CLOSED", "CLOSED", "OPEN"]
        
        result = coordinator._majority_vote(votes)
        
        assert result == "CLOSED"
    
    def test_majority_vote_no_majority(self, coordinator):
        """Test majority voting with no clear majority."""
        votes = ["CLOSED", "OPEN", "HALF_OPEN"]
        
        result = coordinator._majority_vote(votes)
        
        assert result == "SPLIT_BRAIN"
    
    def test_majority_vote_exact_split(self, coordinator):
        """Test majority voting with exact 50/50 split."""
        votes = ["CLOSED", "CLOSED", "OPEN", "OPEN"]
        
        result = coordinator._majority_vote(votes)
        
        # No >50% majority
        assert result == "SPLIT_BRAIN"
    
    @pytest.mark.asyncio
    async def test_startup_attempts_leader_election(self, coordinator, redis_client):
        """Test startup attempts leader election."""
        await coordinator.startup()
        
        assert coordinator._running is True
        # First instance should become leader
        assert coordinator.is_leader is True
        assert coordinator.election_wins == 1
    
    @pytest.mark.asyncio
    async def test_elect_leader(self, coordinator, redis_client):
        """Test explicit leader election."""
        result = await coordinator.elect_leader()
        
        assert result is True
        assert coordinator.is_leader is True
        assert redis_client.leader == coordinator.instance_id
    
    @pytest.mark.asyncio
    async def test_heartbeat_registers_vote(self, coordinator, redis_client):
        """Test heartbeat registers vote in Redis."""
        await coordinator.heartbeat()
        
        assert coordinator.instance_id in redis_client.votes
        vote = redis_client.votes[coordinator.instance_id]
        assert "circuit_breaker_state" in vote
        assert "fallback_mode" in vote
        assert "health_score" in vote
        assert "timestamp" in vote
    
    @pytest.mark.asyncio
    async def test_get_nodes_parses_votes(self, coordinator, redis_client):
        """Test get_nodes parses votes into NodeInfo."""
        # Add some votes
        redis_client.votes["instance-1"] = {
            "health_score": 1.0,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client.votes["instance-2"] = {
            "health_score": 0.5,
            "timestamp": datetime.utcnow().isoformat(),
        }
        redis_client.leader = "instance-1"
        
        nodes = await coordinator.get_nodes()
        
        assert len(nodes) == 2
        assert any(n.instance_id == "instance-1" and n.is_leader for n in nodes)
        assert any(n.instance_id == "instance-2" and not n.is_leader for n in nodes)
    
    @pytest.mark.asyncio
    async def test_get_consensus_with_majority(self, coordinator, redis_client):
        """Test consensus with clear majority."""
        # Register votes from multiple instances
        redis_client.votes["instance-1"] = {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
            "health_score": 1.0,
        }
        redis_client.votes["instance-2"] = {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
            "health_score": 1.0,
        }
        redis_client.votes["instance-3"] = {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "SAFE",
            "health_score": 0.2,
        }
        redis_client.leader = "instance-1"
        
        consensus = await coordinator.get_consensus()
        
        assert consensus.circuit_state == "CLOSED"
        assert consensus.fallback_mode == "PRIMARY"
        assert consensus.quorum_met is True
        assert consensus.voting_instances == 3
        assert consensus.consensus_strength > 0.5


class TestCoordinatorFailover:
    """Test coordinator failover scenarios."""
    
    @pytest.mark.asyncio
    async def test_local_coordinator_failover_not_applicable(self):
        """Test local coordinator doesn't need failover."""
        health_monitor = MockHealthMonitor()
        coordinator = LocalCoordinator(health_monitor=health_monitor)
        
        await coordinator.startup()
        
        # Always leader in local mode
        assert coordinator.is_leader is True
        
        # Re-election always succeeds
        result = await coordinator.elect_leader()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_distributed_coordinator_leadership_renewal(self):
        """Test distributed coordinator can renew leadership."""
        redis_client = MockRedisClient()
        health_monitor = MockHealthMonitor()
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            instance_id="leader-1",
        )
        
        # Become leader
        await coordinator.elect_leader()
        assert coordinator.is_leader is True
        
        # Renew leadership
        renewed = await redis_client.renew_leadership(coordinator.instance_id)
        assert renewed is True
    
    @pytest.mark.asyncio
    async def test_distributed_coordinator_loses_leadership(self):
        """Test distributed coordinator handles leadership loss."""
        redis_client = MockRedisClient()
        health_monitor = MockHealthMonitor()
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            instance_id="follower-1",
        )
        
        # Another instance is leader
        redis_client.leader = "leader-1"
        
        # Try to renew (should fail)
        renewed = await redis_client.renew_leadership(coordinator.instance_id)
        assert renewed is False


class TestCoordinatorAssignment:
    """Test work assignment in coordinators."""
    
    @pytest.mark.asyncio
    async def test_local_coordinator_assigns_to_self(self):
        """Test local coordinator assigns all work to self."""
        coordinator = LocalCoordinator(
            health_monitor=MockHealthMonitor(),
        )
        await coordinator.startup()
        
        work1 = {"task": "task1"}
        work2 = {"task": "task2"}
        
        assigned1 = await coordinator.assign_work(work1)
        assigned2 = await coordinator.assign_work(work2)
        
        assert assigned1 == coordinator.instance_id
        assert assigned2 == coordinator.instance_id
        assert len(coordinator._work_queue) == 2
    
    @pytest.mark.asyncio
    async def test_distributed_coordinator_assigns_to_leader(self):
        """Test distributed coordinator assigns work to leader."""
        redis_client = MockRedisClient()
        redis_client.leader = "leader-instance"
        
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=MockHealthMonitor(),
            instance_id="follower-1",
        )
        
        work = {"task": "important_task"}
        assigned_to = await coordinator.assign_work(work)
        
        assert assigned_to == "leader-instance"
