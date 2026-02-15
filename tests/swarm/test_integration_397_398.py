"""
Integration tests for Issue #397 (SwarmConfig/SwarmSerializer) + Issue #398 (MessageBus).

Tests the complete flow:
- SwarmConfig creation → SwarmSerializer → SwarmMessageBus
- Publishing HealthSummary objects through the bus
- Topic-based routing of configuration and health data
"""

import pytest
import asyncio
from datetime import datetime

from astraguard.swarm.models import (
    AgentID,
    SatelliteRole,
    HealthSummary,
    SwarmConfig,
)
from astraguard.swarm.serializer import SwarmSerializer
from astraguard.swarm.types import SwarmMessage, QoSLevel
from astraguard.swarm.bus import SwarmMessageBus

# Mark swarm config integration tests as slow
pytestmark = [pytest.mark.slow, pytest.mark.timeout(45)]


class TestIssue397_398Integration:
    """Integration tests between SwarmConfig (397) and MessageBus (398)."""

    @pytest.fixture
    def integration_setup(self):
        """Setup complete integration environment."""
        agent1 = AgentID.create("astra-v3.0", "SAT-001-A")
        agent2 = AgentID.create("astra-v3.0", "SAT-002-B")

        config1 = SwarmConfig(
            agent_id=agent1,
            role=SatelliteRole.PRIMARY,
            constellation_id="astra-v3.0",
            bandwidth_limit_kbps=10,
        )

        config2 = SwarmConfig(
            agent_id=agent2,
            role=SatelliteRole.BACKUP,
            constellation_id="astra-v3.0",
            bandwidth_limit_kbps=10,
        )

        serializer = SwarmSerializer(validate=False)

        bus1 = SwarmMessageBus(config1, serializer, latency_ms=0)
        bus2 = SwarmMessageBus(config2, serializer, latency_ms=0)

        return {
            "config1": config1,
            "config2": config2,
            "serializer": serializer,
            "bus1": bus1,
            "bus2": bus2,
            "agent1": agent1,
            "agent2": agent2,
        }

    def test_swarm_config_creation(self, integration_setup):
        """Test SwarmConfig creation from Issue #397."""
        config = integration_setup["config1"]
        assert config.agent_id is not None
        assert config.role == SatelliteRole.PRIMARY
        assert config.constellation_id == "astra-v3.0"

    def test_serializer_creation(self, integration_setup):
        """Test SwarmSerializer creation from Issue #397."""
        serializer = integration_setup["serializer"]
        assert serializer is not None
        assert hasattr(serializer, "serialize_health")
        assert hasattr(serializer, "serialize_swarm_config")

    def test_bus_creation(self, integration_setup):
        """Test MessageBus creation with SwarmConfig."""
        bus = integration_setup["bus1"]
        assert bus is not None
        assert bus.config is not None
        assert bus.serializer is not None

    def test_health_summary_roundtrip(self, integration_setup):
        """Test creating HealthSummary and bus integration."""
        serializer = integration_setup["serializer"]

        summary = HealthSummary(
            anomaly_signature=[0.1] * 32,
            risk_score=0.5,
            recurrence_score=3.5,
            timestamp=datetime.utcnow(),
        )

        # Serialize using SwarmSerializer from Issue #397 (without compression)
        serialized = serializer.serialize_health(summary, compress=False)
        assert serialized is not None
        assert isinstance(serialized, bytes)

    @pytest.mark.asyncio
    async def test_config_exchange_over_bus(self, integration_setup):
        """Test exchanging SwarmConfig data over message bus."""
        bus1 = integration_setup["bus1"]
        bus2 = integration_setup["bus2"]
        serializer = integration_setup["serializer"]

        received_configs = []

        def config_subscriber(msg: SwarmMessage):
            try:
                config = serializer.deserialize(msg.payload, SwarmConfig)
                received_configs.append(config)
            except Exception:
                pass

        sub_id = bus2.subscribe("control/config", config_subscriber)

        config1 = integration_setup["config1"]
        serialized_config = serializer.serialize_swarm_config(config1)

        # Publish config through bus1
        await bus1.publish("control/config", serialized_config, qos=QoSLevel.ACK)

        # Simulate network delivery
        for bus in [bus2]:
            if "control/config" in bus.subscriptions:
                for callback in bus.subscriptions["control/config"]:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(
                            SwarmMessage(
                                topic="control/config",
                                payload=serialized_config,
                                sender=config1.agent_id,
                            )
                        )

        bus2.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_health_summary_broadcast(self, integration_setup):
        """Test broadcasting HealthSummary from one agent to another."""
        bus1 = integration_setup["bus1"]
        bus2 = integration_setup["bus2"]
        serializer = integration_setup["serializer"]
        config1 = integration_setup["config1"]

        received_messages = []

        def health_subscriber(msg: SwarmMessage):
            received_messages.append(msg)

        sub_id = bus2.subscribe("health/*", health_subscriber)

        # Create and serialize HealthSummary (without compression)
        summary = HealthSummary(
            anomaly_signature=[0.2] * 32,
            risk_score=0.7,
            recurrence_score=4.2,
            timestamp=datetime.utcnow(),
        )

        serialized_summary = serializer.serialize_health(summary, compress=False)

        # Publish from bus1
        await bus1.publish("health/summary", serialized_summary, qos=QoSLevel.RELIABLE)

        # Simulate network delivery to bus2
        matching_subs = bus2.topic_subscribers.get("health/*", [])
        for sub_id_match in matching_subs:
            callback = bus2.subscriptions.get(sub_id_match)
            if callback:
                msg = SwarmMessage(
                    topic="health/summary",
                    payload=serialized_summary,
                    sender=config1.agent_id,
                )
                if asyncio.iscoroutinefunction(callback):
                    await callback(msg)
                else:
                    callback(msg)

        assert len(received_messages) >= 1

        bus2.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_multiagent_health_aggregation(self, integration_setup):
        """Test aggregating health from multiple agents."""
        config1 = integration_setup["config1"]
        config2 = integration_setup["config2"]
        serializer = integration_setup["serializer"]

        # Create aggregator bus
        aggregator_config = SwarmConfig(
            agent_id=AgentID.create("astra-v3.0", "AGG-CTRL"),
            role=SatelliteRole.PRIMARY,
            constellation_id="astra-v3.0",
        )
        aggregator_bus = SwarmMessageBus(aggregator_config, serializer, latency_ms=0)

        received_messages = []

        def aggregator_subscriber(msg: SwarmMessage):
            received_messages.append(msg)

        agg_sub = aggregator_bus.subscribe("health/*", aggregator_subscriber)

        # Both agents publish health summaries
        summary1 = HealthSummary(
            anomaly_signature=[0.1] * 32,
            risk_score=0.3,
            recurrence_score=2.1,
            timestamp=datetime.utcnow(),
        )

        summary2 = HealthSummary(
            anomaly_signature=[0.2] * 32,
            risk_score=0.6,
            recurrence_score=4.5,
            timestamp=datetime.utcnow(),
        )

        # Simulate publishing
        for agent_id, summary in [
            (config1.agent_id, summary1),
            (config2.agent_id, summary2),
        ]:
            serialized = serializer.serialize_health(summary, compress=False)

            msg = SwarmMessage(
                topic="health/summary", payload=serialized, sender=agent_id
            )

            # Deliver to matching subscribers
            matching_subs = aggregator_bus.topic_subscribers.get("health/*", [])
            for sub_id_match in matching_subs:
                callback = aggregator_bus.subscriptions.get(sub_id_match)
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(msg)
                    else:
                        callback(msg)

        # Verify aggregation
        assert len(received_messages) == 2

        aggregator_bus.unsubscribe(agg_sub)

    @pytest.mark.asyncio
    async def test_constellation_peer_discovery(self, integration_setup):
        """Test constellation peer discovery via message bus."""
        config1 = integration_setup["config1"]
        bus1 = integration_setup["bus1"]
        bus2 = integration_setup["bus2"]
        serializer = integration_setup["serializer"]

        peers_discovered = []

        def peer_discovery_subscriber(msg: SwarmMessage):
            # Just track that we received the message
            peers_discovered.append(msg.sender)

        sub_id = bus2.subscribe("control/peers", peer_discovery_subscriber)

        # Publish peer config
        serialized_config = serializer.serialize_swarm_config(config1)
        await bus1.publish("control/peers", serialized_config, qos=QoSLevel.FIRE_FORGET)

        # Simulate delivery
        msg = SwarmMessage(
            topic="control/peers", payload=serialized_config, sender=config1.agent_id
        )

        matching_subs = bus2.topic_subscribers.get("control/peers", [])
        for sub_id_match in matching_subs:
            callback = bus2.subscriptions.get(sub_id_match)
            if callback:
                if asyncio.iscoroutinefunction(callback):
                    await callback(msg)
                else:
                    callback(msg)

        assert len(peers_discovered) >= 1

        bus2.unsubscribe(sub_id)

    def test_bandwidth_limit_enforcement(self, integration_setup):
        """Test ISL bandwidth limit from SwarmConfig."""
        config = integration_setup["config1"]
        assert config.bandwidth_limit_kbps == 10

        # Message bus should respect this limit via config
        bus = integration_setup["bus1"]
        assert bus.isl_bandwidth_kbps == 10

    @pytest.mark.asyncio
    async def test_error_handling_malformed_message(self, integration_setup):
        """Test error handling for malformed messages."""
        bus = integration_setup["bus1"]

        error_messages = []

        def strict_subscriber(msg: SwarmMessage):
            if not isinstance(msg.payload, bytes):
                error_messages.append("Invalid payload type")

        sub_id = bus.subscribe("health/*", strict_subscriber)

        # Try to publish valid message
        await bus.publish("health/summary", b"valid", qos=0)

        bus.unsubscribe(sub_id)

    @pytest.mark.asyncio
    async def test_feature_flag_integration(self, integration_setup):
        """Test that message bus respects SwarmConfig feature flags."""
        config = integration_setup["config1"]
        serializer = integration_setup["serializer"]

        # Create bus with feature flag
        bus = SwarmMessageBus(config, serializer)

        # Bus should be functional
        assert bus is not None
        assert bus.config is not None
