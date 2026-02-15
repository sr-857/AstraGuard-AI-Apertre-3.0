"""Integration tests for orchestration and coordination."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock
from backend.orchestration.recovery_orchestrator import RecoveryOrchestrator
from backend.orchestration.coordinator import LocalCoordinator, ConsensusDecision
from backend.orchestration.distributed_coordinator import DistributedResilienceCoordinator

# Mark orchestration integration tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(60)]


class IntegrationMockHealthMonitor:
    """Health monitor mock for integration testing."""
    
    def __init__(self):
        self.state = {
            "system": {"status": "HEALTHY", "failed_components": 0},
            "circuit_breaker": {"state": "CLOSED", "open_duration_seconds": 0},
            "retry": {"failures_1h": 0, "state": "STABLE"},
            "fallback": {"mode": "PRIMARY"},
        }
        self.calls = []
    
    async def get_comprehensive_state(self):
        self.calls.append(("get_comprehensive_state", datetime.utcnow()))
        return self.state.copy()
    
    def set_unhealthy(self):
        """Simulate unhealthy state."""
        self.state["system"]["status"] = "DEGRADED"
        self.state["circuit_breaker"]["state"] = "OPEN"
        self.state["circuit_breaker"]["open_duration_seconds"] = 400
        self.state["retry"]["failures_1h"] = 60
    
    def set_healthy(self):
        """Restore healthy state."""
        self.state["system"]["status"] = "HEALTHY"
        self.state["circuit_breaker"]["state"] = "CLOSED"
        self.state["circuit_breaker"]["open_duration_seconds"] = 0
        self.state["retry"]["failures_1h"] = 0


class IntegrationMockFallbackManager:
    """Fallback manager mock for integration testing."""
    
    def __init__(self):
        self.current_mode = "PRIMARY"
        self.mode_changes = []
    
    async def cascade(self, state):
        self.mode_changes.append(("cascade", "SAFE", datetime.utcnow()))
        self.current_mode = "SAFE"
        return True
    
    async def set_mode(self, mode):
        self.mode_changes.append(("set_mode", mode, datetime.utcnow()))
        self.current_mode = mode
        return True


class IntegrationMockRedisClient:
    """Redis client mock for integration testing."""
    
    def __init__(self):
        self.connected = True
        self.leader = None
        self.votes = {}
        self.states = {}
        self.leadership_ttl = {}
    
    async def leader_election(self, instance_id, ttl=30):
        if self.leader is None or self.leader == instance_id:
            self.leader = instance_id
            self.leadership_ttl[instance_id] = ttl
            return True
        return False
    
    async def renew_leadership(self, instance_id, ttl=30):
        if self.leader == instance_id:
            self.leadership_ttl[instance_id] = ttl
            return True
        return False
    
    async def get_leader(self):
        return self.leader
    
    async def register_vote(self, instance_id, vote, ttl=30):
        self.votes[instance_id] = vote
    
    async def get_cluster_votes(self):
        return self.votes.copy()
    
    async def publish_state(self, channel, state):
        self.states[channel] = state
    
    async def get_all_instance_health(self):
        return {
            instance_id: {"health_score": vote.get("health_score", 0.5)}
            for instance_id, vote in self.votes.items()
        }
    
    def simulate_leader_failure(self):
        """Simulate current leader failure."""
        self.leader = None
        self.leadership_ttl.clear()


class TestOrchestratorIntegration:
    """Integration tests for orchestrator with dependencies."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_recovery_cycle_integration(self):
        """Test full recovery cycle with real dependencies."""
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
        )
        
        # Simulate unhealthy state
        health_monitor.set_unhealthy()
        
        # Run single recovery cycle
        await orchestrator._recovery_cycle()
        
        # Should have triggered recovery actions
        assert orchestrator.metrics.total_actions_executed > 0
        assert len(health_monitor.calls) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_event_handling_integration(self):
        """Test orchestrator handles various events."""
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
        )
        
        # Send health check event
        health_monitor.set_unhealthy()
        await orchestrator.handle_event({
            "type": "health_check",
            "state": health_monitor.state,
        })
        
        assert orchestrator.metrics.total_actions_executed > 0
        
        # Send manual trigger event
        await orchestrator.handle_event({
            "type": "manual_trigger",
            "action_type": "safe_mode",
            "reason": "Integration test",
        })
        
        # Should have executed safe mode
        assert orchestrator.metrics.actions_by_type["safe_mode"] > 0
        assert len(fallback_manager.mode_changes) > 0
    
    @pytest.mark.asyncio
    async def test_orchestrator_respects_cooldowns(self):
        """Test orchestrator respects cooldown periods."""
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
        )
        
        # Trigger circuit recovery
        health_monitor.state["circuit_breaker"]["state"] = "OPEN"
        health_monitor.state["circuit_breaker"]["open_duration_seconds"] = 400
        
        await orchestrator._recovery_cycle()
        first_action_count = orchestrator.metrics.total_actions_executed
        
        # Try again immediately (should be in cooldown)
        await orchestrator._recovery_cycle()
        second_action_count = orchestrator.metrics.total_actions_executed
        
        # Should not have executed another action
        assert second_action_count == first_action_count


class TestCoordinatorIntegration:
    """Integration tests for coordinator with dependencies."""
    
    @pytest.mark.asyncio
    async def test_local_coordinator_full_lifecycle(self):
        """Test local coordinator full startup/shutdown lifecycle."""
        health_monitor = IntegrationMockHealthMonitor()
        coordinator = LocalCoordinator(health_monitor=health_monitor)
        
        # Startup
        await coordinator.startup()
        assert coordinator._running is True
        assert coordinator.is_leader is True
        
        # Heartbeat
        await coordinator.heartbeat()
        nodes = await coordinator.get_nodes()
        assert len(nodes) == 1
        
        # Get consensus
        consensus = await coordinator.get_consensus()
        assert consensus.quorum_met is True
        assert consensus.circuit_state == "CLOSED"
        
        # Shutdown
        await coordinator.shutdown()
        assert coordinator._running is False
    
    @pytest.mark.asyncio
    async def test_distributed_coordinator_with_single_instance(self):
        """Test distributed coordinator works with single instance."""
        redis_client = IntegrationMockRedisClient()
        health_monitor = IntegrationMockHealthMonitor()
        
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            instance_id="test-1",
        )
        
        # Startup
        await coordinator.startup()
        assert coordinator.is_leader is True
        
        # Heartbeat registers vote
        await coordinator.heartbeat()
        assert "test-1" in redis_client.votes
        
        # Get consensus
        consensus = await coordinator.get_consensus()
        assert consensus.leader_instance == "test-1"
        assert consensus.quorum_met is True
        
        # Shutdown
        await coordinator.shutdown()
        assert coordinator._running is False


class TestCoordinatorFailoverIntegration:
    """Integration tests for coordinator failover scenarios."""
    
    @pytest.mark.asyncio
    async def test_two_coordinators_leader_election(self):
        """Test two coordinators elect a single leader."""
        redis_client = IntegrationMockRedisClient()
        health_monitor1 = IntegrationMockHealthMonitor()
        health_monitor2 = IntegrationMockHealthMonitor()
        
        coordinator1 = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor1,
            instance_id="instance-1",
        )
        
        coordinator2 = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor2,
            instance_id="instance-2",
        )
        
        # Start first coordinator (becomes leader)
        await coordinator1.startup()
        assert coordinator1.is_leader is True
        
        # Start second coordinator (should be follower)
        await coordinator2.startup()
        assert coordinator2.is_leader is False
        
        # Verify only one leader
        assert redis_client.leader == "instance-1"
        
        # Clean up
        await coordinator1.shutdown()
        await coordinator2.shutdown()
    
    @pytest.mark.asyncio
    async def test_coordinator_failover_scenario(self):
        """Test coordinator failover when leader fails."""
        redis_client = IntegrationMockRedisClient()
        health_monitor1 = IntegrationMockHealthMonitor()
        health_monitor2 = IntegrationMockHealthMonitor()
        
        coordinator1 = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor1,
            instance_id="leader-instance",
        )
        
        coordinator2 = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor2,
            instance_id="follower-instance",
        )
        
        # Start both coordinators
        await coordinator1.startup()
        await coordinator2.startup()
        
        assert coordinator1.is_leader is True
        assert coordinator2.is_leader is False
        
        # Simulate leader failure
        redis_client.simulate_leader_failure()
        
        # Follower should be able to become leader
        result = await coordinator2.elect_leader()
        assert result is True
        assert coordinator2.is_leader is True
        assert redis_client.leader == "follower-instance"
        
        # Clean up
        await coordinator1.shutdown()
        await coordinator2.shutdown()
    
    @pytest.mark.asyncio
    async def test_consensus_with_multiple_instances(self):
        """Test consensus decision with multiple voting instances."""
        redis_client = IntegrationMockRedisClient()
        
        # Create 3 coordinators
        coordinators = []
        for i in range(3):
            health_monitor = IntegrationMockHealthMonitor()
            if i == 2:
                # Make one instance unhealthy
                health_monitor.set_unhealthy()
            
            coordinator = DistributedResilienceCoordinator(
                redis_client=redis_client,
                health_monitor=health_monitor,
                instance_id=f"instance-{i}",
            )
            coordinators.append(coordinator)
        
        # Start all coordinators
        for coordinator in coordinators:
            await coordinator.startup()
        
        # All should send heartbeats/votes
        for coordinator in coordinators:
            await coordinator.heartbeat()
        
        # Get consensus from leader
        leader = coordinators[0]
        consensus = await leader.get_consensus()
        
        # Should have 3 votes
        assert consensus.voting_instances == 3
        assert consensus.quorum_met is True
        
        # Majority should be CLOSED (2 out of 3)
        assert consensus.circuit_state == "CLOSED"
        assert consensus.consensus_strength > 0.5
        
        # Clean up
        for coordinator in coordinators:
            await coordinator.shutdown()


class TestOrchestratorCoordinatorIntegration:
    """Integration tests combining orchestrator and coordinator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_with_local_coordinator(self):
        """Test orchestrator works with local coordinator."""
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        coordinator = LocalCoordinator(health_monitor=health_monitor)
        orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
        )
        
        # Start coordinator
        await coordinator.startup()
        
        # Simulate unhealthy state
        health_monitor.set_unhealthy()
        
        # Run orchestrator cycle
        await orchestrator._recovery_cycle()
        
        # Get coordinator consensus
        consensus = await coordinator.get_consensus()
        
        # Should reflect unhealthy state
        assert consensus.circuit_state == "OPEN"
        assert orchestrator.metrics.total_actions_executed > 0
        
        # Clean up
        await coordinator.shutdown()
    
    @pytest.mark.asyncio
    async def test_distributed_coordinator_applies_consensus(self):
        """Test distributed coordinator can apply consensus to orchestrator."""
        redis_client = IntegrationMockRedisClient()
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
            instance_id="test-instance",
        )
        
        await coordinator.startup()
        
        # Create consensus decision
        consensus = ConsensusDecision(
            circuit_state="OPEN",
            fallback_mode="SAFE",
            leader_instance=coordinator.instance_id,
            quorum_met=True,
            voting_instances=3,
            consensus_strength=0.8,
        )
        
        # Apply consensus
        result = await coordinator.apply_consensus_decision(consensus)
        
        assert result is True
        assert fallback_manager.current_mode == "SAFE"
        
        # Clean up
        await coordinator.shutdown()


class TestOrchestratorStressTest:
    """Stress tests for orchestrator under load."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_handles_rapid_events(self):
        """Test orchestrator handles rapid event stream."""
        health_monitor = IntegrationMockHealthMonitor()
        fallback_manager = IntegrationMockFallbackManager()
        
        orchestrator = RecoveryOrchestrator(
            health_monitor=health_monitor,
            fallback_manager=fallback_manager,
        )
        
        # Send 50 events rapidly
        for i in range(50):
            event = {
                "type": "health_check",
                "state": health_monitor.state,
            }
            await orchestrator.handle_event(event)
        
        # Orchestrator should have processed events - check that actions are throttled
        # (Cooldowns should prevent excessive actions)
        assert orchestrator.metrics.total_actions_executed < 50
    
    @pytest.mark.asyncio
    async def test_coordinator_handles_many_nodes(self):
        """Test coordinator can handle many voting nodes."""
        redis_client = IntegrationMockRedisClient()
        
        # Register 20 votes
        for i in range(20):
            await redis_client.register_vote(
                f"instance-{i}",
                {
                    "circuit_breaker_state": "CLOSED" if i < 15 else "OPEN",
                    "fallback_mode": "PRIMARY",
                    "health_score": 0.9 if i < 15 else 0.2,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        
        health_monitor = IntegrationMockHealthMonitor()
        coordinator = DistributedResilienceCoordinator(
            redis_client=redis_client,
            health_monitor=health_monitor,
            instance_id="test-coordinator",
        )
        
        # Get consensus
        consensus = await coordinator.get_consensus()
        
        # Should handle all votes
        assert consensus.voting_instances == 20
        assert consensus.quorum_met is True
        
        # Majority should be CLOSED (15 out of 20)
        assert consensus.circuit_state == "CLOSED"
        assert consensus.consensus_strength == 0.75
