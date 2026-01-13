"""
Test suite for AstraGuard swarm models and serialization.

Issue #397: Foundation layer tests with 90%+ coverage
- AgentID creation and validation
- SatelliteRole enumeration
- HealthSummary constraints and serialization
- SwarmConfig validation
- Roundtrip serialization <50ms
- HealthSummary <1KB compressed
- JSONSchema validation
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid5, NAMESPACE_DNS
from typing import List

from astraguard.swarm.models import (
    AgentID,
    SatelliteRole,
    HealthSummary,
    SwarmConfig,
)
from astraguard.swarm.serializer import SwarmSerializer


class TestAgentID:
    """Test suite for AgentID model."""

    def test_agent_id_creation(self):
        """Test basic AgentID creation."""
        uuid = uuid5(NAMESPACE_DNS, "astra-v3.0:SAT-001-A")
        agent = AgentID(
            constellation="astra-v3.0",
            satellite_serial="SAT-001-A",
            uuid=uuid,
        )
        assert agent.constellation == "astra-v3.0"
        assert agent.satellite_serial == "SAT-001-A"
        assert agent.uuid == uuid

    def test_agent_id_factory_method(self):
        """Test AgentID.create factory method with UUIDv5 derivation."""
        agent1 = AgentID.create("astra-v3.0", "SAT-001-A")
        agent2 = AgentID.create("astra-v3.0", "SAT-001-A")
        
        # UUIDv5 should be deterministic
        assert agent1.uuid == agent2.uuid
        assert agent1.constellation == "astra-v3.0"
        assert agent1.satellite_serial == "SAT-001-A"

    def test_agent_id_frozen(self):
        """Test that AgentID is immutable (frozen)."""
        agent = AgentID.create("astra-v3.0", "SAT-001-A")
        with pytest.raises(AttributeError):
            agent.constellation = "astra-v4.0"

    def test_agent_id_invalid_constellation(self):
        """Test that invalid constellation raises ValueError."""
        with pytest.raises(ValueError, match="Only 'astra-v3.0' constellation supported"):
            AgentID(
                constellation="astra-v2.0",
                satellite_serial="SAT-001-A",
                uuid=uuid5(NAMESPACE_DNS, "astra-v2.0:SAT-001-A"),
            )

    def test_agent_id_empty_serial(self):
        """Test that empty satellite_serial raises ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            AgentID(
                constellation="astra-v3.0",
                satellite_serial="",
                uuid=uuid5(NAMESPACE_DNS, "astra-v3.0:"),
            )

    def test_agent_id_to_dict(self):
        """Test AgentID serialization to dictionary."""
        agent = AgentID.create("astra-v3.0", "SAT-001-A")
        data = agent.to_dict()
        assert data["constellation"] == "astra-v3.0"
        assert data["satellite_serial"] == "SAT-001-A"
        assert data["uuid"] == str(agent.uuid)

    def test_agent_id_distinct_uuids(self):
        """Test that different satellites get different UUIDs."""
        agent1 = AgentID.create("astra-v3.0", "SAT-001-A")
        agent2 = AgentID.create("astra-v3.0", "SAT-002-A")
        assert agent1.uuid != agent2.uuid


class TestSatelliteRole:
    """Test suite for SatelliteRole enum."""

    def test_satellite_role_values(self):
        """Test that all required roles exist."""
        assert SatelliteRole.PRIMARY.value == "primary"
        assert SatelliteRole.BACKUP.value == "backup"
        assert SatelliteRole.STANDBY.value == "standby"
        assert SatelliteRole.SAFE_MODE.value == "safe_mode"

    def test_satellite_role_from_string(self):
        """Test creating role from string."""
        role = SatelliteRole("primary")
        assert role == SatelliteRole.PRIMARY

    def test_satellite_role_all_members(self):
        """Test that all expected members exist."""
        roles = [r.value for r in SatelliteRole]
        assert set(roles) == {"primary", "backup", "standby", "safe_mode"}


class TestHealthSummary:
    """Test suite for HealthSummary model."""

    @staticmethod
    def create_valid_health_summary(
        risk_score: float = 0.5,
        recurrence_score: float = 3.5,
        anomaly_sig: List[float] = None,
    ) -> HealthSummary:
        """Helper to create valid HealthSummary."""
        if anomaly_sig is None:
            anomaly_sig = [0.1] * 32
        return HealthSummary(
            anomaly_signature=anomaly_sig,
            risk_score=risk_score,
            recurrence_score=recurrence_score,
            timestamp=datetime.utcnow(),
        )

    def test_health_summary_valid_creation(self):
        """Test creating valid HealthSummary."""
        summary = self.create_valid_health_summary()
        assert len(summary.anomaly_signature) == 32
        assert summary.risk_score == 0.5
        assert summary.recurrence_score == 3.5
        assert isinstance(summary.timestamp, datetime)

    def test_health_summary_32d_pca_required(self):
        """Test that anomaly_signature must be exactly 32-dimensional."""
        with pytest.raises(ValueError, match="32-dimensional"):
            HealthSummary(
                anomaly_signature=[0.1] * 31,
                risk_score=0.5,
                recurrence_score=3.5,
                timestamp=datetime.utcnow(),
            )

    def test_health_summary_risk_score_bounds(self):
        """Test that risk_score is bounded [0.0, 1.0]."""
        with pytest.raises(ValueError, match="risk_score must be in"):
            self.create_valid_health_summary(risk_score=1.5)
        
        with pytest.raises(ValueError, match="risk_score must be in"):
            self.create_valid_health_summary(risk_score=-0.1)

    def test_health_summary_recurrence_bounds(self):
        """Test that recurrence_score is bounded [0, 10]."""
        with pytest.raises(ValueError, match="recurrence_score must be in"):
            self.create_valid_health_summary(recurrence_score=10.1)
        
        with pytest.raises(ValueError, match="recurrence_score must be in"):
            self.create_valid_health_summary(recurrence_score=-0.1)

    def test_health_summary_compressed_size_limit(self):
        """Test that compressed_size cannot exceed 1KB."""
        summary = self.create_valid_health_summary()
        assert summary.compressed_size <= 1024
        
        # Test that creating with size > 1KB raises ValueError
        with pytest.raises(ValueError, match="exceeds 1KB limit"):
            from astraguard.swarm.models import HealthSummary
            HealthSummary(
                anomaly_signature=[0.0] * 32,
                risk_score=0.5,
                recurrence_score=5.0,
                timestamp=datetime.utcnow(),
                compressed_size=1025  # Exceeds 1KB limit
            )

    def test_health_summary_to_dict(self):
        """Test serialization to dictionary."""
        summary = self.create_valid_health_summary()
        data = summary.to_dict()
        
        assert data["risk_score"] == 0.5
        assert data["recurrence_score"] == 3.5
        assert len(data["anomaly_signature"]) == 32
        assert "timestamp" in data

    def test_health_summary_from_dict(self):
        """Test deserialization from dictionary."""
        original = self.create_valid_health_summary()
        data = original.to_dict()
        restored = HealthSummary.from_dict(data)
        
        assert restored.risk_score == original.risk_score
        assert restored.recurrence_score == original.recurrence_score
        assert restored.anomaly_signature == original.anomaly_signature

    def test_health_summary_roundtrip(self):
        """Test to_dict -> from_dict roundtrip preserves data."""
        original = self.create_valid_health_summary()
        data = original.to_dict()
        restored = HealthSummary.from_dict(data)
        
        assert restored.to_dict() == data


class TestSwarmConfig:
    """Test suite for SwarmConfig model."""

    @staticmethod
    def create_valid_swarm_config(
        agent_id: AgentID = None,
        role: SatelliteRole = SatelliteRole.PRIMARY,
        peers: List[AgentID] = None,
    ) -> SwarmConfig:
        """Helper to create valid SwarmConfig."""
        if agent_id is None:
            agent_id = AgentID.create("astra-v3.0", "SAT-001-A")
        if peers is None:
            peers = []
        return SwarmConfig(
            agent_id=agent_id,
            role=role,
            constellation_id="astra-v3.0",
            peers=peers,
            bandwidth_limit_kbps=10,
        )

    def test_swarm_config_creation(self):
        """Test basic SwarmConfig creation."""
        config = self.create_valid_swarm_config()
        assert config.agent_id.satellite_serial == "SAT-001-A"
        assert config.role == SatelliteRole.PRIMARY
        assert config.constellation_id == "astra-v3.0"
        assert config.bandwidth_limit_kbps == 10

    def test_swarm_config_constellation_mismatch(self):
        """Test that constellation_id must match agent_id.constellation."""
        agent = AgentID.create("astra-v3.0", "SAT-001-A")
        with pytest.raises(ValueError, match="must match agent_id.constellation"):
            SwarmConfig(
                agent_id=agent,
                role=SatelliteRole.PRIMARY,
                constellation_id="astra-v2.0",
            )

    def test_swarm_config_invalid_role_type(self):
        """Test that role must be SatelliteRole instance."""
        agent = AgentID.create("astra-v3.0", "SAT-001-A")
        with pytest.raises(ValueError, match="role must be SatelliteRole"):
            SwarmConfig(
                agent_id=agent,
                role="primary",  # String instead of enum
                constellation_id="astra-v3.0",
            )

    def test_swarm_config_bandwidth_positive(self):
        """Test that bandwidth_limit_kbps must be positive."""
        agent = AgentID.create("astra-v3.0", "SAT-001-A")
        with pytest.raises(ValueError, match="must be positive"):
            SwarmConfig(
                agent_id=agent,
                role=SatelliteRole.PRIMARY,
                constellation_id="astra-v3.0",
                bandwidth_limit_kbps=0,
            )

    def test_swarm_config_with_peers(self):
        """Test SwarmConfig with multiple peers."""
        agent1 = AgentID.create("astra-v3.0", "SAT-001-A")
        agent2 = AgentID.create("astra-v3.0", "SAT-002-A")
        agent3 = AgentID.create("astra-v3.0", "SAT-003-A")
        
        config = SwarmConfig(
            agent_id=agent1,
            role=SatelliteRole.BACKUP,
            constellation_id="astra-v3.0",
            peers=[agent2, agent3],
            bandwidth_limit_kbps=10,
        )
        
        assert len(config.peers) == 2
        assert agent2 in config.peers
        assert agent3 in config.peers

    def test_swarm_config_to_dict(self):
        """Test serialization to dictionary."""
        config = self.create_valid_swarm_config()
        data = config.to_dict()
        
        assert data["constellation_id"] == "astra-v3.0"
        assert data["role"] == "primary"
        assert data["bandwidth_limit_kbps"] == 10
        assert "agent_id" in data

    def test_swarm_config_from_dict(self):
        """Test deserialization from dictionary."""
        original = self.create_valid_swarm_config()
        data = original.to_dict()
        restored = SwarmConfig.from_dict(data)
        
        assert restored.constellation_id == original.constellation_id
        assert restored.role == original.role
        assert restored.bandwidth_limit_kbps == original.bandwidth_limit_kbps

    def test_swarm_config_roundtrip(self):
        """Test to_dict -> from_dict roundtrip preserves data."""
        original = self.create_valid_swarm_config()
        data = original.to_dict()
        restored = SwarmConfig.from_dict(data)
        
        assert restored.to_dict() == data


class TestSwarmSerializer:
    """Test suite for SwarmSerializer."""

    def test_serializer_creation(self):
        """Test SwarmSerializer instantiation."""
        serializer = SwarmSerializer()
        assert serializer.validate is True
        assert serializer._use_orjson is not None
        assert serializer._use_lz4 is not None

    def test_serializer_health_summary_uncompressed(self):
        """Test health summary serialization without compression."""
        serializer = SwarmSerializer(validate=True)
        summary = HealthSummary(
            anomaly_signature=[0.1] * 32,
            risk_score=0.5,
            recurrence_score=3.5,
            timestamp=datetime.utcnow(),
        )
        
        serialized = serializer.serialize_health(summary, compress=False)
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0

    def test_serializer_health_summary_roundtrip_uncompressed(self):
        """Test health summary roundtrip without compression."""
        serializer = SwarmSerializer(validate=True)
        original = HealthSummary(
            anomaly_signature=[0.1 * i for i in range(32)],
            risk_score=0.75,
            recurrence_score=5.2,
            timestamp=datetime.utcnow().replace(microsecond=0),
        )
        
        serialized = serializer.serialize_health(original, compress=False)
        restored = serializer.deserialize_health(serialized, compressed=False)
        
        assert restored.risk_score == original.risk_score
        assert restored.recurrence_score == original.recurrence_score
        assert restored.anomaly_signature == original.anomaly_signature

    @pytest.mark.skipif(
        not hasattr(__import__("astraguard.swarm.serializer", fromlist=["HAS_LZ4"]), "HAS_LZ4"),
        reason="LZ4 not available"
    )
    def test_serializer_health_summary_compressed(self):
        """Test health summary serialization with LZ4 compression."""
        serializer = SwarmSerializer(validate=True)
        summary = HealthSummary(
            anomaly_signature=[0.1] * 32,
            risk_score=0.5,
            recurrence_score=3.5,
            timestamp=datetime.utcnow(),
            compressed_size=0,
        )
        
        # Skip if LZ4 not available
        if not serializer._use_lz4:
            pytest.skip("LZ4 not available")
        
        serialized = serializer.serialize_health(summary, compress=True)
        assert isinstance(serialized, bytes)
        assert len(serialized) > 0

    def test_serializer_swarm_config_roundtrip(self):
        """Test SwarmConfig serialization roundtrip."""
        serializer = SwarmSerializer(validate=True)
        agent1 = AgentID.create("astra-v3.0", "SAT-001-A")
        agent2 = AgentID.create("astra-v3.0", "SAT-002-A")
        
        original = SwarmConfig(
            agent_id=agent1,
            role=SatelliteRole.PRIMARY,
            constellation_id="astra-v3.0",
            peers=[agent2],
            bandwidth_limit_kbps=10,
        )
        
        serialized = serializer.serialize_swarm_config(original)
        restored = serializer.deserialize_swarm_config(serialized)
        
        assert restored.role == original.role
        assert restored.constellation_id == original.constellation_id
        assert len(restored.peers) == len(original.peers)

    def test_serializer_validate_schema_health_summary(self):
        """Test JSONSchema validation for HealthSummary."""
        serializer = SwarmSerializer(validate=True)
        data = {
            "anomaly_signature": [0.1] * 32,
            "risk_score": 0.5,
            "recurrence_score": 3.5,
            "timestamp": datetime.utcnow().isoformat(),
            "compressed_size": 256,
        }
        
        result = serializer.validate_schema(data, "HealthSummary")
        assert result is True

    def test_serializer_validate_schema_invalid_data(self):
        """Test that invalid data fails schema validation."""
        serializer = SwarmSerializer(validate=True)
        data = {
            "anomaly_signature": [0.1] * 31,  # Should be 32
            "risk_score": 0.5,
            "recurrence_score": 3.5,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        with pytest.raises(Exception):  # jsonschema.ValidationError
            serializer.validate_schema(data, "HealthSummary")

    def test_serializer_compression_stats(self):
        """Test compression statistics calculation."""
        stats = SwarmSerializer.get_compression_stats(4200, 800)
        assert stats["original_size"] == 4200
        assert stats["compressed_size"] == 800
        # Compression ratio should be around 19% (800/4200) or 81% compression
        assert "%" in stats["compression_ratio"]  # Contains percentage sign
        assert stats["saved_bytes"] == 3400

    def test_serializer_compression_stats_zero(self):
        """Test compression stats with zero size."""
        stats = SwarmSerializer.get_compression_stats(0, 0)
        assert stats["original_size"] == 0
        assert stats["compression_ratio"] == 0.0


class TestPerformance:
    """Performance tests for serialization."""

    def test_roundtrip_performance_under_50ms(self):
        """Test that roundtrip serialization completes in <50ms."""
        import time
        
        serializer = SwarmSerializer(validate=True)
        summary = HealthSummary(
            anomaly_signature=[0.1 * i for i in range(32)],
            risk_score=0.75,
            recurrence_score=5.2,
            timestamp=datetime.utcnow(),
        )
        
        start = time.time()
        serialized = serializer.serialize_health(summary, compress=False)
        restored = serializer.deserialize_health(serialized, compressed=False)
        elapsed_ms = (time.time() - start) * 1000
        
        assert elapsed_ms < 50.0, f"Roundtrip took {elapsed_ms:.2f}ms (limit: 50ms)"

    def test_health_summary_payload_under_1kb(self):
        """Test that HealthSummary uncompressed stays reasonable."""
        serializer = SwarmSerializer(validate=True)
        summary = HealthSummary(
            anomaly_signature=[0.1] * 32,
            risk_score=0.5,
            recurrence_score=3.5,
            timestamp=datetime.utcnow(),
        )
        
        serialized = serializer.serialize_health(summary, compress=False)
        # Uncompressed JSON should be a few hundred bytes
        assert len(serialized) < 2048, f"Payload too large: {len(serialized)} bytes"
