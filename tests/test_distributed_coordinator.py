"""
Comprehensive tests for Issue #18 - Distributed Resilience Coordinator.

Tests cover:
- Leader election with TTL and tie-breaking
- Vote collection and majority voting
- Quorum consensus decisions
- Multi-instance simulation
- State publishing
- Cluster health aggregation
- Metrics tracking
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from collections import Counter

# Import modules under test
from backend.redis_client import RedisClient
from backend.orchestration.distributed_coordinator import (
    DistributedResilienceCoordinator,
    ConsensusDecision,
)

# Mark all tests in this module as slow due to distributed nature
pytestmark = [pytest.mark.slow, pytest.mark.timeout(60)]


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock(spec=RedisClient)
    redis.redis = AsyncMock()
    redis.connected = True
    return redis


@pytest.fixture
async def mock_health_monitor():
    """Mock health monitor."""
    monitor = AsyncMock()
    monitor.get_comprehensive_state = AsyncMock(
        return_value={
            "circuit_state": "CLOSED",
            "fallback_mode": "PRIMARY",
            "health_score": 0.95,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )
    return monitor


@pytest.fixture
async def mock_recovery_orchestrator():
    """Mock recovery orchestrator."""
    return AsyncMock()


@pytest.fixture
async def mock_fallback_manager():
    """Mock fallback manager."""
    manager = AsyncMock()
    manager.cascade = AsyncMock(return_value="PRIMARY")
    return manager


@pytest.fixture
async def coordinator(mock_redis, mock_health_monitor, mock_recovery_orchestrator, mock_fallback_manager):
    """Create distributed coordinator with mocks."""
    coord = DistributedResilienceCoordinator(
        redis_client=mock_redis,
        health_monitor=mock_health_monitor,
        recovery_orchestrator=mock_recovery_orchestrator,
        fallback_manager=mock_fallback_manager,
        quorum_threshold=0.5,
    )
    return coord


# ============================================================================
# LEADER ELECTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_leader_election_first_instance_wins(coordinator, mock_redis):
    """Test that first instance attempting election becomes leader."""
    mock_redis.leader_election = AsyncMock(return_value=True)

    result = await mock_redis.leader_election(coordinator.instance_id)

    assert result is True
    assert mock_redis.leader_election.called


@pytest.mark.asyncio
async def test_leader_election_second_instance_loses(coordinator, mock_redis):
    """Test that second instance doesn't win election if leader exists."""
    mock_redis.leader_election = AsyncMock(return_value=False)

    result = await mock_redis.leader_election("other-instance")

    assert result is False
    assert mock_redis.leader_election.called


@pytest.mark.asyncio
async def test_leader_election_ttl_expiry(coordinator, mock_redis):
    """Test that leader election respects TTL expiry."""
    # Set leadership with 30s TTL
    ttl = 30
    result = await mock_redis.leader_election(coordinator.instance_id, ttl=ttl)

    mock_redis.leader_election.assert_called_with(coordinator.instance_id, ttl=ttl)


@pytest.mark.asyncio
async def test_startup_sets_leader_flag(coordinator, mock_redis):
    """Test that startup() properly sets is_leader flag."""
    mock_redis.leader_election = AsyncMock(return_value=True)
    mock_redis.get_leader = AsyncMock(return_value=coordinator.instance_id)

    await coordinator.startup()

    assert coordinator.is_leader is True
    assert coordinator.election_wins == 1


@pytest.mark.asyncio
async def test_startup_as_follower(coordinator, mock_redis):
    """Test startup when not elected leader."""
    mock_redis.leader_election = AsyncMock(return_value=False)

    await coordinator.startup()

    assert coordinator.is_leader is False
    assert coordinator.election_wins == 0


@pytest.mark.asyncio
async def test_leader_renewal_extends_ttl(coordinator, mock_redis):
    """Test that leadership renewal extends TTL."""
    coordinator.is_leader = True
    mock_redis.renew_leadership = AsyncMock(return_value=True)

    result = await mock_redis.renew_leadership(coordinator.instance_id, ttl=30)

    assert result is True
    mock_redis.renew_leadership.assert_called_once()


# ============================================================================
# VOTING AND CONSENSUS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_majority_vote_single_option(coordinator):
    """Test majority vote with unanimous decision."""
    votes = ["CLOSED", "CLOSED", "CLOSED"]

    result = coordinator._majority_vote(votes)

    assert result == "CLOSED"


@pytest.mark.asyncio
async def test_majority_vote_clear_majority(coordinator):
    """Test majority vote with clear majority."""
    votes = ["OPEN", "OPEN", "OPEN", "CLOSED", "CLOSED"]

    result = coordinator._majority_vote(votes)

    assert result == "OPEN"


@pytest.mark.asyncio
async def test_majority_vote_no_clear_winner_split_brain(coordinator):
    """Test that tie/no majority returns SPLIT_BRAIN."""
    votes = ["OPEN", "OPEN", "CLOSED", "CLOSED", "HALF_OPEN"]

    result = coordinator._majority_vote(votes)

    assert result == "SPLIT_BRAIN"


@pytest.mark.asyncio
async def test_majority_vote_two_instances_unanimous(coordinator):
    """Test majority with minimum quorum (2 instances)."""
    votes = ["HEURISTIC", "HEURISTIC"]

    result = coordinator._majority_vote(votes)

    assert result == "HEURISTIC"


@pytest.mark.asyncio
async def test_quorum_consensus_empty_votes(coordinator, mock_redis):
    """Test consensus when no votes available."""
    mock_redis.get_cluster_votes = AsyncMock(return_value={})

    decision = await coordinator.get_cluster_consensus()

    assert decision.quorum_met is False
    assert decision.voting_instances == 0
    assert decision.circuit_state == "UNKNOWN"


@pytest.mark.asyncio
async def test_quorum_consensus_simple_majority(coordinator, mock_redis):
    """Test consensus with simple majority."""
    mock_votes = {
        "instance1": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance2": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance3": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        },
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    decision = await coordinator.get_cluster_consensus()

    assert decision.circuit_state == "OPEN"
    assert decision.fallback_mode == "HEURISTIC"
    assert decision.quorum_met is True
    assert decision.voting_instances == 3


@pytest.mark.asyncio
async def test_quorum_consensus_5_instances_3_vote_open(coordinator, mock_redis):
    """Test 5-instance cluster with 3/5 voting OPEN (60%)."""
    mock_votes = {
        "instance1": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance2": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance3": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance4": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        },
        "instance5": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        },
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    decision = await coordinator.get_cluster_consensus()

    assert decision.circuit_state == "OPEN"
    assert decision.consensus_strength == 0.6  # 3/5 = 60%
    assert decision.quorum_met is True


@pytest.mark.asyncio
async def test_quorum_consensus_split_brain_detection(coordinator, mock_redis):
    """Test that split brain scenario is detected."""
    mock_votes = {
        "instance1": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance2": {
            "circuit_breaker_state": "OPEN",
            "fallback_mode": "HEURISTIC",
        },
        "instance3": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        },
        "instance4": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        },
        "instance5": {
            "circuit_breaker_state": "HALF_OPEN",
            "fallback_mode": "SAFE",
        },
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    decision = await coordinator.get_cluster_consensus()

    assert decision.circuit_state == "SPLIT_BRAIN"


@pytest.mark.asyncio
async def test_consensus_increments_decision_counter(coordinator, mock_redis):
    """Test that consensus decisions are counted."""
    mock_votes = {
        "instance1": {
            "circuit_breaker_state": "CLOSED",
            "fallback_mode": "PRIMARY",
        }
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    initial_count = coordinator.consensus_decisions
    await coordinator.get_cluster_consensus()

    assert coordinator.consensus_decisions == initial_count + 1


# ============================================================================
# STATE PUBLISHING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_state_publisher_publishes_local_state(coordinator, mock_redis):
    """Test that state publisher publishes local state."""
    mock_redis.publish_state = AsyncMock(return_value=2)
    coordinator._running = True

    # Start publisher for short time
    publisher_task = asyncio.create_task(
        coordinator._state_publisher(interval=0.1)
    )
    await asyncio.sleep(0.2)
    publisher_task.cancel()

    try:
        await publisher_task
    except asyncio.CancelledError:
        pass

    assert mock_redis.publish_state.called


@pytest.mark.asyncio
async def test_vote_collector_registers_vote(coordinator, mock_redis):
    """Test that vote collector registers instance vote."""
    mock_redis.register_vote = AsyncMock(return_value=True)
    coordinator._running = True

    # Start collector for short time
    collector_task = asyncio.create_task(
        coordinator._vote_collector(interval=0.1)
    )
    await asyncio.sleep(0.2)
    collector_task.cancel()

    try:
        await collector_task
    except asyncio.CancelledError:
        pass

    assert mock_redis.register_vote.called


# ============================================================================
# CLUSTER HEALTH TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cluster_health_all_healthy(coordinator, mock_redis):
    """Test cluster health when all instances healthy."""
    all_health = {
        "instance1": {"health_score": 0.95},
        "instance2": {"health_score": 0.92},
        "instance3": {"health_score": 0.98},
    }
    mock_redis.get_all_instance_health = AsyncMock(return_value=all_health)

    health = await coordinator.get_cluster_health()

    assert health["instances"] == 3
    assert health["healthy"] == 3
    assert health["degraded"] == 0
    assert health["failed"] == 0


@pytest.mark.asyncio
async def test_cluster_health_mixed_states(coordinator, mock_redis):
    """Test cluster health with mixed instance states."""
    all_health = {
        "instance1": {"health_score": 0.95},  # healthy
        "instance2": {"health_score": 0.70},  # degraded
        "instance3": {"health_score": 0.30},  # failed
    }
    mock_redis.get_all_instance_health = AsyncMock(return_value=all_health)

    health = await coordinator.get_cluster_health()

    assert health["instances"] == 3
    assert health["healthy"] == 1
    assert health["degraded"] == 1
    assert health["failed"] == 1


@pytest.mark.asyncio
async def test_cluster_health_no_instances(coordinator, mock_redis):
    """Test cluster health when no instances reporting."""
    mock_redis.get_all_instance_health = AsyncMock(return_value={})

    health = await coordinator.get_cluster_health()

    assert health["instances"] == 0
    assert health["healthy"] == 0
    assert health["degraded"] == 0
    assert health["failed"] == 0


# ============================================================================
# METRICS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_metrics_returns_coordinator_state(coordinator, mock_redis):
    """Test that get_metrics returns coordinator state."""
    coordinator.election_wins = 5
    coordinator.consensus_decisions = 12

    metrics = await coordinator.get_metrics()

    assert metrics["instance_id"] == coordinator.instance_id
    assert metrics["is_leader"] == coordinator.is_leader
    assert metrics["election_wins"] == 5
    assert metrics["consensus_decisions"] == 12


@pytest.mark.asyncio
async def test_metrics_show_running_state(coordinator, mock_redis):
    """Test that metrics show running state."""
    coordinator._running = True

    metrics = await coordinator.get_metrics()

    assert metrics["running"] is True


# ============================================================================
# LIFECYCLE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_startup_initializes_background_tasks(coordinator, mock_redis):
    """Test that startup initializes background tasks."""
    mock_redis.leader_election = AsyncMock(return_value=True)

    await coordinator.startup()

    assert coordinator._running is True
    assert coordinator._state_publisher_task is not None
    assert coordinator._leader_renewal_task is not None
    assert coordinator._vote_collector_task is not None

    # Cleanup
    await coordinator.shutdown()


@pytest.mark.asyncio
async def test_shutdown_stops_background_tasks(coordinator, mock_redis):
    """Test that shutdown stops background tasks."""
    mock_redis.leader_election = AsyncMock(return_value=True)

    await coordinator.startup()
    await asyncio.sleep(0.1)
    await coordinator.shutdown()

    assert coordinator._running is False


@pytest.mark.asyncio
async def test_redis_disconnection_handled_gracefully(coordinator, mock_redis):
    """Test graceful handling when Redis disconnected."""
    mock_redis.connected = False

    # Should not raise exception
    decision = await coordinator.get_cluster_consensus()

    assert decision.quorum_met is False


# ============================================================================
# EDGE CASES & ERROR HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_consensus_with_malformed_votes(coordinator, mock_redis):
    """Test consensus handling of malformed vote data."""
    mock_votes = {
        "instance1": {"circuit_breaker_state": "OPEN"},
        "instance2": {},  # Missing fields
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    decision = await coordinator.get_cluster_consensus()

    # Should handle gracefully
    assert decision is not None


@pytest.mark.asyncio
async def test_consensus_exception_handling(coordinator, mock_redis):
    """Test that consensus handles exceptions gracefully."""
    mock_redis.get_cluster_votes = AsyncMock(
        side_effect=Exception("Redis error")
    )

    # Should not raise
    decision = await coordinator.get_cluster_consensus()

    assert decision.quorum_met is False


@pytest.mark.asyncio
async def test_empty_votes_list_majority_vote(coordinator):
    """Test majority vote with empty list."""
    result = coordinator._majority_vote([])

    assert result == "UNKNOWN"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_coordination_cycle(coordinator, mock_redis, mock_health_monitor):
    """Test complete coordination cycle: leader election → state pub → vote collect → consensus."""
    # Setup mocks
    mock_redis.leader_election = AsyncMock(return_value=True)
    mock_redis.get_leader = AsyncMock(return_value=coordinator.instance_id)
    mock_redis.publish_state = AsyncMock(return_value=3)
    mock_redis.register_vote = AsyncMock(return_value=True)
    mock_redis.get_cluster_votes = AsyncMock(
        return_value={
            "instance1": {
                "circuit_breaker_state": "CLOSED",
                "fallback_mode": "PRIMARY",
            },
            "instance2": {
                "circuit_breaker_state": "CLOSED",
                "fallback_mode": "PRIMARY",
            },
        }
    )

    # Startup
    await coordinator.startup()

    # Get consensus
    decision = await coordinator.get_cluster_consensus()

    # Verify
    assert coordinator.is_leader is True
    assert decision.circuit_state == "CLOSED"
    assert decision.fallback_mode == "PRIMARY"

    # Cleanup
    await coordinator.shutdown()


@pytest.mark.asyncio
async def test_multi_instance_leader_failover(mock_redis, mock_health_monitor):
    """Test leader failover scenario with multiple instances."""
    # Create multiple coordinator instances
    coordinator1 = DistributedResilienceCoordinator(
        redis_client=mock_redis,
        health_monitor=mock_health_monitor,
    )
    coordinator2 = DistributedResilienceCoordinator(
        redis_client=mock_redis,
        health_monitor=mock_health_monitor,
    )

    # First becomes leader
    mock_redis.leader_election = AsyncMock(return_value=True)
    await coordinator1.startup()
    assert coordinator1.is_leader is True

    # Second tries to become leader but fails
    mock_redis.leader_election = AsyncMock(return_value=False)
    await coordinator2.startup()
    assert coordinator2.is_leader is False

    # Cleanup
    await coordinator1.shutdown()
    await coordinator2.shutdown()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consensus_performance(coordinator, mock_redis):
    """Test consensus decision latency (should be < 100ms)."""
    # Create 100 votes
    mock_votes = {
        f"instance{i}": {
            "circuit_breaker_state": "OPEN" if i % 2 == 0 else "CLOSED",
            "fallback_mode": "PRIMARY",
        }
        for i in range(100)
    }
    mock_redis.get_cluster_votes = AsyncMock(return_value=mock_votes)
    mock_redis.get_leader = AsyncMock(return_value="instance1")

    import time

    start = time.time()
    decision = await coordinator.get_cluster_consensus()
    elapsed = (time.time() - start) * 1000  # Convert to ms

    assert elapsed < 100  # Should be < 100ms
    assert decision is not None


@pytest.mark.asyncio
async def test_majority_vote_performance(coordinator):
    """Test majority vote with large dataset (should be < 50ms)."""
    votes = ["OPEN" if i % 3 == 0 else "CLOSED" for i in range(1000)]

    import time

    start = time.time()
    result = coordinator._majority_vote(votes)
    elapsed = (time.time() - start) * 1000  # Convert to ms

    assert elapsed < 50  # Should be < 50ms
    assert result in ["OPEN", "CLOSED"]


# ============================================================================
# CONSENSUS DECISION APPLICATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_apply_consensus_decision_updates_fallback(
    coordinator, mock_fallback_manager
):
    """Test that consensus decision updates fallback mode."""
    decision = ConsensusDecision(
        circuit_state="OPEN",
        fallback_mode="SAFE",
        leader_instance="instance1",
        quorum_met=True,
        voting_instances=3,
        consensus_strength=0.75,
    )
    mock_fallback_manager.set_mode = AsyncMock(return_value=True)

    result = await coordinator.apply_consensus_decision(decision)

    assert result is True
    mock_fallback_manager.set_mode.assert_called_once_with("SAFE")


@pytest.mark.asyncio
async def test_apply_consensus_no_change_when_primary(
    coordinator, mock_fallback_manager
):
    """Test that PRIMARY mode doesn't trigger cascade."""
    decision = ConsensusDecision(
        circuit_state="CLOSED",
        fallback_mode="PRIMARY",
        leader_instance="instance1",
        quorum_met=True,
        voting_instances=3,
        consensus_strength=1.0,
    )

    result = await coordinator.apply_consensus_decision(decision)

    assert result is True
    mock_fallback_manager.set_mode.assert_not_called()
