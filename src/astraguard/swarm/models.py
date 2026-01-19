"""
SwarmConfig Data Models for AstraGuard v3.0 Multi-Agent Intelligence

Defines immutable data structures for agent identification, configuration,
and health telemetry with strict bandwidth constraints (10KB/s ISL limit).

Issue #397: Foundation layer for multi-agent swarm intelligence
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List
from datetime import datetime
from uuid import UUID, uuid5, NAMESPACE_DNS


@dataclass(frozen=True)
class AgentID:
    """
    Unique identifier for satellite agents in the constellation.
    
    Attributes:
        constellation: Constellation identifier (e.g., "astra-v3.0")
        satellite_serial: Physical satellite serial number (e.g., "SAT-001-A")
        uuid: UUIDv5 derived from constellation + serial for deterministic ID
    
    Example:
        >>> agent = AgentID(
        ...     constellation="astra-v3.0",
        ...     satellite_serial="SAT-001-A",
        ...     uuid=uuid5(NAMESPACE_DNS, "astra-v3.0:SAT-001-A")
        ... )
    """
    constellation: str
    satellite_serial: str
    uuid: UUID

    def __post_init__(self):
        """Validate agent ID components."""
        if not self.constellation or not self.satellite_serial:
            raise ValueError(
                "constellation and satellite_serial must not be empty"
            )
        if self.constellation != "astra-v3.0":
            raise ValueError(
                f"Only 'astra-v3.0' constellation supported, got {self.constellation}"
            )

    @classmethod
    def create(cls, constellation: str, satellite_serial: str) -> "AgentID":
        """
        Factory method to create AgentID with deterministic UUIDv5.
        
        Args:
            constellation: Constellation identifier
            satellite_serial: Satellite serial number
            
        Returns:
            AgentID instance with derived UUIDv5
        """
        uuid = uuid5(NAMESPACE_DNS, f"{constellation}:{satellite_serial}")
        return cls(
            constellation=constellation,
            satellite_serial=satellite_serial,
            uuid=uuid,
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "constellation": self.constellation,
            "satellite_serial": self.satellite_serial,
            "uuid": str(self.uuid),
        }


class SatelliteRole(str, Enum):
    """
    Operational roles for satellite agents in the constellation.
    
    PRIMARY: Main operational agent
    BACKUP: Standby replacement for primary
    STANDBY: Idle, available for rapid activation
    SAFE_MODE: Degraded operation state (limited functionality)
    """
    PRIMARY = "primary"
    BACKUP = "backup"
    STANDBY = "standby"
    SAFE_MODE = "safe_mode"


@dataclass
class HealthSummary:
    """
    Compressed health telemetry for bandwidth-constrained ISL links.
    
    Target: <1KB compressed payload (Issue #399 prep)
    Compression: LZ4 algorithm (80%+ compression ratio expected)
    
    Attributes:
        anomaly_signature: 32-dimensional PCA vector for anomaly detection
        risk_score: Normalized risk metric (0.0-1.0)
        recurrence_score: Weighted decay score (0-10 scale)
        timestamp: ISO 8601 timestamp of health snapshot
        compressed_size: Size after LZ4 compression (bytes)
    """
    anomaly_signature: List[float]
    risk_score: float
    recurrence_score: float
    timestamp: datetime
    compressed_size: int = 0

    def __post_init__(self):
        """Validate health summary constraints."""
        if len(self.anomaly_signature) != 32:
            raise ValueError(
                f"anomaly_signature must be 32-dimensional, "
                f"got {len(self.anomaly_signature)}"
            )
        if not (0.0 <= self.risk_score <= 1.0):
            raise ValueError(
                f"risk_score must be in [0.0, 1.0], got {self.risk_score}"
            )
        if not (0 <= self.recurrence_score <= 10):
            raise ValueError(
                f"recurrence_score must be in [0, 10], got {self.recurrence_score}"
            )
        if self.compressed_size < 0:
            raise ValueError(
                f"compressed_size must be non-negative, got {self.compressed_size}"
            )
        if self.compressed_size > 1024:
            raise ValueError(
                f"compressed_size exceeds 1KB limit: {self.compressed_size} bytes"
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "anomaly_signature": self.anomaly_signature,
            "risk_score": self.risk_score,
            "recurrence_score": self.recurrence_score,
            "timestamp": self.timestamp.isoformat(),
            "compressed_size": self.compressed_size,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HealthSummary":
        """Deserialize from dictionary."""
        return cls(
            anomaly_signature=data["anomaly_signature"],
            risk_score=data["risk_score"],
            recurrence_score=data["recurrence_score"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            compressed_size=data.get("compressed_size", 0),
        )


@dataclass
class SwarmConfig:
    """
    Configuration for multi-agent satellite constellation operations.
    
    Attributes:
        agent_id: Unique identifier for this agent
        role: Operational role in constellation
        constellation_id: Constellation identifier
        peers: List of peer agent IDs for ISL communication
        bandwidth_limit_kbps: ISL bandwidth limit (default 10 KB/s)
    """
    agent_id: AgentID
    role: SatelliteRole
    constellation_id: str
    peers: List[AgentID] = field(default_factory=list)
    bandwidth_limit_kbps: int = 10

    def __post_init__(self):
        """Validate swarm configuration constraints."""
        if self.bandwidth_limit_kbps <= 0:
            raise ValueError(
                f"bandwidth_limit_kbps must be positive, "
                f"got {self.bandwidth_limit_kbps}"
            )
        if self.constellation_id != self.agent_id.constellation:
            raise ValueError(
                "constellation_id must match agent_id.constellation"
            )
        if not isinstance(self.role, SatelliteRole):
            raise ValueError(
                f"role must be SatelliteRole instance, got {type(self.role)}"
            )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "agent_id": self.agent_id.to_dict(),
            "role": self.role.value,
            "constellation_id": self.constellation_id,
            "peers": [peer.to_dict() for peer in self.peers],
            "bandwidth_limit_kbps": self.bandwidth_limit_kbps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SwarmConfig":
        """Deserialize from dictionary."""
        agent_id_data = data["agent_id"]
        agent_id = AgentID(
            constellation=agent_id_data["constellation"],
            satellite_serial=agent_id_data["satellite_serial"],
            uuid=UUID(agent_id_data["uuid"]),
        )
        peers = [
            AgentID(
                constellation=peer_data["constellation"],
                satellite_serial=peer_data["satellite_serial"],
                uuid=UUID(peer_data["uuid"]),
            )
            for peer_data in data.get("peers", [])
        ]
        return cls(
            agent_id=agent_id,
            role=SatelliteRole(data["role"]),
            constellation_id=data["constellation_id"],
            peers=peers,
            bandwidth_limit_kbps=data.get("bandwidth_limit_kbps", 10),
        )
