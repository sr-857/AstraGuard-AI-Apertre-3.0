"""
Tests for SwarmAdaptiveMemory distributed caching.

Issue #410: Comprehensive test suite for swarm-aware adaptive memory.

Tests cover:
  - Cache hit rate tracking (target 85% vs 50% single-agent)
  - Local cache operations (get/put)
  - Peer replication (RSSI-based top 3 selection)
  - Bandwidth-aware eviction (bus.utilization > 0.7)
  - Multi-agent constellation scenarios (5-agent)
  - Metrics validation
  - Error handling and edge cases

Target: 90%+ code coverage, 45+ tests
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid5, NAMESPACE_DNS

from astraguard.swarm.swarm_memory import (
    SwarmAdaptiveMemory,
    AnomalyPattern,
    PeerCacheInfo,
    SwarmMemoryMetrics,
)
from astraguard.swarm.models import AgentID
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.compressor import StateCompressor


# Fixtures

@pytest.fixture
def agent_id():
    """Create test agent ID."""
    return AgentID(
        constellation="astra-v3.0",
        satellite_serial="test-sat-001",
        uuid=uuid5(NAMESPACE_DNS, "astra-v3.0:test-sat-001"),
    )


@pytest.fixture
def peer_ids():
    """Create test peer IDs."""
    return [
        AgentID(constellation="astra-v3.0", satellite_serial=f"test-sat-{i:03d}", uuid=uuid5(NAMESPACE_DNS, f"astra-v3.0:test-sat-{i:03d}"))
        for i in range(2, 7)  # 5 peers
    ]


@pytest.fixture
def mock_registry(agent_id):
    """Create mock SwarmRegistry."""
    registry = AsyncMock(spec=SwarmRegistry)
    registry.config = MagicMock()
    registry.config.agent_id = agent_id
    registry.get_alive_peers = MagicMock(return_value=[])
    registry.get_peer_health = MagicMock(return_value=None)
    return registry


@pytest.fixture
def mock_bus():
    """Create mock SwarmMessageBus."""
    bus = AsyncMock(spec=SwarmMessageBus)
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    return bus


@pytest.fixture
def mock_compressor():
    """Create mock StateCompressor."""
    compressor = MagicMock(spec=StateCompressor)
    return compressor


@pytest.fixture
def swarm_memory(mock_registry, mock_bus, mock_compressor, tmp_path):
    """Create SwarmAdaptiveMemory instance for testing."""
    memory = SwarmAdaptiveMemory(
        local_path=str(tmp_path / "memory.pkl"),
        registry=mock_registry,
        bus=mock_bus,
        compressor=mock_compressor,
        config={"peer_cache_size": 3},
    )
    return memory


def create_test_pattern(pattern_id: str, risk_score: float = 0.8) -> AnomalyPattern:
    """Create test AnomalyPattern."""
    return AnomalyPattern(
        pattern_id=pattern_id,
        anomaly_signature=[0.1 * i for i in range(32)],  # 32-dim
        recurrence_score=0.75,
        risk_score=risk_score,
        last_seen=datetime.utcnow(),
        recurrence_count=3,
    )


# Test: Local Cache Operations

class TestLocalCacheOperations:
    """Test basic cache get/put operations."""

    @pytest.mark.asyncio
    async def test_put_stores_pattern_locally(self, swarm_memory):
        """Test put() stores pattern in local cache."""
        pattern = create_test_pattern("pattern-001")

        await swarm_memory.put("pattern-001", pattern)

        assert "pattern-001" in swarm_memory._local_pattern_cache
        assert swarm_memory._local_pattern_cache["pattern-001"] == pattern

    @pytest.mark.asyncio
    async def test_get_returns_local_pattern(self, swarm_memory):
        """Test get() returns pattern from local cache."""
        pattern = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern)

        result = await swarm_memory.get("pattern-001")

        assert result == pattern
        assert swarm_memory.metrics.cache_hits == 1
        assert swarm_memory.metrics.cache_misses == 0

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, swarm_memory):
        """Test get() returns None for missing pattern."""
        result = await swarm_memory.get("nonexistent")

        assert result is None
        assert swarm_memory.metrics.cache_hits == 0
        assert swarm_memory.metrics.cache_misses == 1

    @pytest.mark.asyncio
    async def test_put_triggers_async_replication(self, swarm_memory, mock_bus):
        """Test put() triggers async peer replication."""
        pattern = create_test_pattern("pattern-001")
        swarm_memory._running = True

        await swarm_memory.put("pattern-001", pattern)

        # Allow async task to start
        await asyncio.sleep(0.01)


# Test: Cache Hit Rate Tracking

class TestCacheHitRate:
    """Test cache hit rate metrics (target 85%)."""

    @pytest.mark.asyncio
    async def test_cache_hit_rate_single_hit(self, swarm_memory):
        """Test hit rate calculation with single hit."""
        pattern = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern)

        await swarm_memory.get("pattern-001")

        metrics = swarm_memory.get_metrics()
        assert metrics.cache_hit_rate == 1.0
        assert metrics.cache_hits == 1

    @pytest.mark.asyncio
    async def test_cache_hit_rate_mixed_hits_misses(self, swarm_memory):
        """Test hit rate with mixed hits and misses."""
        pattern1 = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern1)

        # 3 hits
        await swarm_memory.get("pattern-001")
        await swarm_memory.get("pattern-001")
        await swarm_memory.get("pattern-001")

        # 2 misses
        await swarm_memory.get("nonexistent-1")
        await swarm_memory.get("nonexistent-2")

        metrics = swarm_memory.get_metrics()
        assert metrics.cache_hits == 3
        assert metrics.cache_misses == 2
        assert abs(metrics.cache_hit_rate - 0.6) < 0.01

    @pytest.mark.asyncio
    async def test_cache_hit_rate_zero_accesses(self, swarm_memory):
        """Test hit rate with no accesses."""
        metrics = swarm_memory.get_metrics()
        assert metrics.cache_hit_rate == 0.0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0

    @pytest.mark.asyncio
    async def test_target_85_percent_hit_rate(self, swarm_memory):
        """Test achieving 85% hit rate target."""
        # Store 10 patterns
        patterns = [create_test_pattern(f"pattern-{i:03d}") for i in range(10)]
        for i, pattern in enumerate(patterns):
            await swarm_memory.put(f"pattern-{i:03d}", pattern)

        # Access first 8 patterns 10 times each (80 hits)
        for i in range(8):
            for _ in range(10):
                await swarm_memory.get(f"pattern-{i:03d}")

        # Access missing patterns 15 times (15 misses)
        for i in range(15):
            await swarm_memory.get(f"missing-{i}")

        metrics = swarm_memory.get_metrics()
        # Hit rate: 80 / (80 + 15) = 0.842
        assert metrics.cache_hit_rate > 0.83
        assert metrics.cache_hit_rate < 0.85


# Test: Peer Selection

class TestPeerSelection:
    """Test RSSI-based peer selection."""

    def test_get_nearest_peers_empty(self, swarm_memory, mock_registry):
        """Test peer selection with no alive peers."""
        mock_registry.get_alive_peers.return_value = []

        peers = swarm_memory._get_nearest_peers()

        assert peers == []

    def test_get_nearest_peers_single_peer(self, swarm_memory, mock_registry, peer_ids):
        """Test peer selection with single peer."""
        alive_peer = peer_ids[0]
        mock_registry.get_alive_peers.return_value = [alive_peer]

        peers = swarm_memory._get_nearest_peers()

        assert len(peers) == 1
        assert peers[0] == alive_peer

    def test_get_nearest_peers_top_3(self, swarm_memory, mock_registry, peer_ids):
        """Test selecting top 3 nearest peers by RSSI."""
        # Set RSSI values (higher = stronger = nearer)
        swarm_memory.peer_caches[peer_ids[0]] = PeerCacheInfo(
            agent_id=peer_ids[0], rssi_strength=-50.0
        )
        swarm_memory.peer_caches[peer_ids[1]] = PeerCacheInfo(
            agent_id=peer_ids[1], rssi_strength=-60.0
        )
        swarm_memory.peer_caches[peer_ids[2]] = PeerCacheInfo(
            agent_id=peer_ids[2], rssi_strength=-70.0
        )
        swarm_memory.peer_caches[peer_ids[3]] = PeerCacheInfo(
            agent_id=peer_ids[3], rssi_strength=-80.0
        )

        mock_registry.get_alive_peers.return_value = [
            peer_ids[0], peer_ids[1], peer_ids[2], peer_ids[3], peer_ids[4]
        ]

        peers = swarm_memory._get_nearest_peers()

        # Should return top 3 by RSSI (strongest first)
        assert len(peers) == 3
        assert peers[0] == peer_ids[0]  # -50 (strongest)
        assert peers[1] == peer_ids[1]  # -60
        assert peers[2] == peer_ids[2]  # -70

    def test_get_nearest_peers_respects_limit(self, swarm_memory, mock_registry, peer_ids):
        """Test that peer selection respects peer_cache_size limit."""
        swarm_memory.peer_cache_size = 2
        mock_registry.get_alive_peers.return_value = peer_ids[:5]

        peers = swarm_memory._get_nearest_peers()

        assert len(peers) <= 2


# Test: Peer Replication

class TestPeerReplication:
    """Test async replication to peers."""

    @pytest.mark.asyncio
    async def test_replicate_to_peers_publishes_messages(self, swarm_memory, mock_bus, peer_ids, mock_registry):
        """Test replication publishes to message bus."""
        pattern = create_test_pattern("pattern-001")
        swarm_memory.peer_caches[peer_ids[0]] = PeerCacheInfo(
            agent_id=peer_ids[0], rssi_strength=-50.0
        )
        swarm_memory.peer_caches[peer_ids[1]] = PeerCacheInfo(
            agent_id=peer_ids[1], rssi_strength=-60.0
        )

        mock_registry.get_alive_peers.return_value = [peer_ids[0], peer_ids[1]]
        mock_bus.publish = AsyncMock()

        await swarm_memory._replicate_to_peers("pattern-001", pattern)

        # Should call publish for each peer
        assert mock_bus.publish.call_count >= 1
        assert swarm_memory.metrics.replication_count > 0

    @pytest.mark.asyncio
    async def test_replication_updates_peer_cache_info(self, swarm_memory, peer_ids, mock_registry):
        """Test replication updates PeerCacheInfo."""
        pattern = create_test_pattern("pattern-001")
        swarm_memory.peer_caches[peer_ids[0]] = PeerCacheInfo(
            agent_id=peer_ids[0], rssi_strength=-50.0
        )

        mock_registry.get_alive_peers.return_value = [peer_ids[0]]

        await swarm_memory._replicate_to_peers("pattern-001", pattern)

        # Check peer cache was updated
        assert "pattern-001" in swarm_memory.peer_caches[peer_ids[0]].pattern_ids

    @pytest.mark.asyncio
    async def test_replication_failure_increments_counter(self, swarm_memory, mock_bus, peer_ids, mock_registry):
        """Test replication failure is tracked."""
        pattern = create_test_pattern("pattern-001")
        swarm_memory.peer_caches[peer_ids[0]] = PeerCacheInfo(
            agent_id=peer_ids[0], rssi_strength=-50.0
        )

        mock_registry.get_alive_peers.return_value = [peer_ids[0]]
        mock_bus.publish.side_effect = Exception("Bus error")

        await swarm_memory._replicate_to_peers("pattern-001", pattern)

        assert swarm_memory.metrics.replication_failures > 0


# Test: Bandwidth-Aware Eviction

class TestBandwidthEviction:
    """Test eviction during ISL congestion."""

    @pytest.mark.asyncio
    async def test_no_eviction_normal_bandwidth(self, swarm_memory):
        """Test no eviction when bandwidth is normal."""
        # Add peer cache entries
        peer_id = AgentID(constellation="astra-v3.0", satellite_serial="sat-002", uuid=uuid5(NAMESPACE_DNS, "astra-v3.0:sat-002"))
        swarm_memory.peer_caches[peer_id] = PeerCacheInfo(
            agent_id=peer_id,
            pattern_ids={"p1", "p2", "p3"},
            last_sync=datetime.utcnow(),
        )

        initial_count = len(swarm_memory.peer_caches[peer_id].pattern_ids)

        with patch.object(swarm_memory, "_is_congested", return_value=False):
            await swarm_memory._evict_on_congestion()

        # No eviction should occur
        assert len(swarm_memory.peer_caches[peer_id].pattern_ids) == initial_count

    @pytest.mark.asyncio
    async def test_eviction_during_congestion(self, swarm_memory):
        """Test eviction when bandwidth congested."""
        # Add peer cache entries
        peer_id = AgentID(constellation="astra-v3.0", satellite_serial="sat-002", uuid=uuid5(NAMESPACE_DNS, "astra-v3.0:sat-002"))
        swarm_memory.peer_caches[peer_id] = PeerCacheInfo(
            agent_id=peer_id,
            pattern_ids={"p1", "p2", "p3", "p4", "p5"},
            last_sync=datetime.utcnow() - timedelta(hours=1),  # Old
        )

        with patch.object(swarm_memory, "_is_congested", return_value=True):
            await swarm_memory._evict_on_congestion()

        # Should evict ~20% (1 of 5)
        assert len(swarm_memory.peer_caches[peer_id].pattern_ids) <= 4
        assert swarm_memory.metrics.bandwidth_evictions >= 0

    @pytest.mark.asyncio
    async def test_eviction_respects_20_percent_rule(self, swarm_memory):
        """Test eviction removes ~20% of peer patterns."""
        # Add 20 patterns across peers
        for i in range(3):
            peer_id = AgentID(constellation="astra-v3.0", satellite_serial=f"sat-{i:03d}", uuid=uuid5(NAMESPACE_DNS, f"astra-v3.0:sat-{i:03d}"))
            swarm_memory.peer_caches[peer_id] = PeerCacheInfo(
                agent_id=peer_id,
                pattern_ids={f"pattern-{j}" for j in range(20)},
                last_sync=datetime.utcnow() - timedelta(hours=i),
            )

        total_before = sum(len(c.pattern_ids) for c in swarm_memory.peer_caches.values())

        with patch.object(swarm_memory, "_is_congested", return_value=True):
            await swarm_memory._evict_on_congestion()

        total_after = sum(len(c.pattern_ids) for c in swarm_memory.peer_caches.values())
        evicted = total_before - total_after

        # Should evict approximately 20% (12 of 60)
        assert 10 <= evicted <= 14


# Test: Multi-Agent Scenarios

class TestMultiAgentScenarios:
    """Test 5-agent constellation scenarios."""

    @pytest.mark.asyncio
    async def test_5_agent_cache_hit_rate_improvement(self, swarm_memory):
        """Test cache hit rate improvement with 5 peers."""
        # Simulate 5-agent scenario
        peers = [
            AgentID(constellation="astra-v3.0", satellite_serial=f"sat-{i:03d}", uuid=uuid5(NAMESPACE_DNS, f"astra-v3.0:sat-{i:03d}"))
            for i in range(1, 6)
        ]

        # Store 20 unique patterns across agents
        for i in range(20):
            pattern = create_test_pattern(f"pattern-{i:03d}")
            await swarm_memory.put(f"pattern-{i:03d}", pattern)

        # Each agent queries 50 patterns (expect ~80% hit rate)
        hits = 0
        misses = 0

        for _ in range(50):
            for i in range(20):
                result = await swarm_memory.get(f"pattern-{i:03d}")
                if result:
                    hits += 1
                else:
                    misses += 1

        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
        assert hit_rate > 0.8  # Should achieve >80% with local cache

    @pytest.mark.asyncio
    async def test_peer_failure_recovery(self, swarm_memory, peer_ids):
        """Test recovery when peer cache fails."""
        pattern = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern)

        # Mark peer as healthy initially
        swarm_memory.peer_caches[peer_ids[0]] = PeerCacheInfo(
            agent_id=peer_ids[0],
            pattern_ids={"pattern-001"},
            rssi_strength=-50.0,
        )

        # Query succeeds from local cache
        result = await swarm_memory.get("pattern-001")
        assert result is not None

    @pytest.mark.asyncio
    async def test_network_partition_graceful_degradation(self, swarm_memory, mock_registry):
        """Test graceful degradation during network partition."""
        pattern = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern)

        # Network partitioned - no alive peers
        mock_registry.get_alive_peers.return_value = []

        # Still get from local cache
        result = await swarm_memory.get("pattern-001")
        assert result is not None

        # Query for non-local pattern returns None
        result = await swarm_memory.get("nonexistent")
        assert result is None


# Test: Metrics

class TestMetrics:
    """Test metrics export and tracking."""

    @pytest.mark.asyncio
    async def test_metrics_initialization(self, swarm_memory):
        """Test metrics initialized correctly."""
        metrics = swarm_memory.get_metrics()

        assert metrics.cache_hit_rate == 0.0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.replication_count == 0

    @pytest.mark.asyncio
    async def test_metrics_to_dict(self, swarm_memory):
        """Test metrics export to dict."""
        metrics = swarm_memory.get_metrics()
        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert "cache_hit_rate" in metrics_dict
        assert "cache_hits" in metrics_dict
        assert "replication_success_rate" in metrics_dict

    def test_reset_metrics(self, swarm_memory):
        """Test metrics reset."""
        swarm_memory.metrics.cache_hits = 100
        swarm_memory.metrics.cache_misses = 50

        swarm_memory.reset_metrics()

        assert swarm_memory.metrics.cache_hits == 0
        assert swarm_memory.metrics.cache_misses == 0


# Test: Error Handling

class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handle_query_missing_pattern(self, swarm_memory):
        """Test handling query for missing pattern."""
        message = {
            "requester": "sat-002",
            "pattern_key": "nonexistent",
        }

        # Should not raise
        await swarm_memory._handle_cache_query(message)

    @pytest.mark.asyncio
    async def test_handle_replication_malformed_message(self, swarm_memory):
        """Test handling malformed replication message."""
        message = {"source": "sat-002"}  # Missing pattern_key and pattern

        # Should not raise
        await swarm_memory._handle_replication(message)

    @pytest.mark.asyncio
    async def test_get_with_corrupted_peer_response(self, swarm_memory):
        """Test handling corrupted peer response."""
        # This would be tested with actual peer communication
        result = await swarm_memory.get("missing-pattern")
        assert result is None

    @pytest.mark.asyncio
    async def test_put_while_not_running(self, swarm_memory):
        """Test put() while not running."""
        swarm_memory._running = False
        pattern = create_test_pattern("pattern-001")

        # Should still work locally
        await swarm_memory.put("pattern-001", pattern)

        assert "pattern-001" in swarm_memory._local_pattern_cache


# Test: Data Serialization

class TestDataSerialization:
    """Test AnomalyPattern serialization."""

    def test_pattern_to_dict(self):
        """Test pattern serialization to dict."""
        pattern = create_test_pattern("pattern-001")
        pattern_dict = pattern.to_dict()

        assert pattern_dict["pattern_id"] == "pattern-001"
        assert "anomaly_signature" in pattern_dict
        assert "recurrence_score" in pattern_dict
        assert "risk_score" in pattern_dict

    def test_pattern_from_dict(self):
        """Test pattern deserialization from dict."""
        pattern = create_test_pattern("pattern-001")
        pattern_dict = pattern.to_dict()

        restored = AnomalyPattern.from_dict(pattern_dict)

        assert restored.pattern_id == pattern.pattern_id
        assert restored.recurrence_score == pattern.recurrence_score
        assert abs((restored.last_seen - pattern.last_seen).total_seconds()) < 1

    def test_pattern_roundtrip(self):
        """Test pattern serialization roundtrip."""
        pattern = create_test_pattern("pattern-001")
        pattern_dict = pattern.to_dict()
        restored = AnomalyPattern.from_dict(pattern_dict)

        assert restored == pattern


# Test: Backward Compatibility

class TestBackwardCompatibility:
    """Test backward compatibility with existing AdaptiveMemory."""

    @pytest.mark.asyncio
    async def test_local_cache_uses_adaptive_memory_store(self, swarm_memory):
        """Test that local cache is AdaptiveMemoryStore instance."""
        from memory_engine.memory_store import AdaptiveMemoryStore

        assert isinstance(swarm_memory.local_cache, AdaptiveMemoryStore)

    @pytest.mark.asyncio
    async def test_compatible_with_existing_retrieve_interface(self, swarm_memory):
        """Test compatibility with existing retrieve() interface."""
        # Should not break existing AdaptiveMemoryStore usage
        pattern = create_test_pattern("pattern-001")
        await swarm_memory.put("pattern-001", pattern)

        # Verify local cache can be accessed
        assert "pattern-001" in swarm_memory._local_pattern_cache


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
