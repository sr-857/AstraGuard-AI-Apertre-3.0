"""
SwarmMessage types and schema for inter-satellite communication.

Issue #398: Message bus abstraction for distributed satellite operations
- Topic-based pub/sub messaging
- QoS levels (0: fire-forget, 1: ACK, 2: reliable)
- ISL bandwidth and latency constraints
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime
from uuid import UUID, uuid4

from astraguard.swarm.models import AgentID


class SwarmTopic(str, Enum):
    """Topic categories for satellite messaging.
    
    health/     → Periodic health summaries and status (30s intervals)
    intent/     → Action plans and mission intent (variable)
    coord/      → Coordination and synchronization messages
    control/    → Control commands and mode changes
    """
    HEALTH = "health"
    INTENT = "intent"
    COORD = "coord"
    CONTROL = "control"

    @classmethod
    def is_valid_topic(cls, topic: str) -> bool:
        """Check if topic string is valid."""
        for member in cls:
            if topic.startswith(f"{member.value}/"):
                return True
        return False


class QoSLevel(int, Enum):
    """Quality of Service levels for message delivery.
    
    FIRE_FORGET (0): Best effort, no guarantees
    ACK (1): Sender waits for acknowledgment
    RELIABLE (2): Retry + deduplication guarantee
    """
    FIRE_FORGET = 0
    ACK = 1
    RELIABLE = 2


@dataclass(frozen=True)
class SwarmMessage:
    """Immutable inter-satellite message.
    
    Attributes:
        topic: Message topic (e.g., "health/summary", "control/safe_mode")
        payload: Serialized message content (bytes, typically LZ4 compressed)
        sender: Agent ID of message sender
        qos: Quality of Service level (0, 1, 2)
        timestamp: UTC timestamp of message creation
        sequence: Sequence number for ordering (Issue #403 prep)
        message_id: Unique message identifier (UUID4)
        receiver: Optional specific receiver (None = broadcast)
    """
    topic: str
    payload: bytes
    sender: AgentID
    qos: int = 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence: int = 0
    message_id: UUID = field(default_factory=uuid4)
    receiver: Optional[AgentID] = None

    def __post_init__(self):
        """Validate message constraints."""
        # Validate topic
        if not SwarmTopic.is_valid_topic(self.topic):
            raise ValueError(
                f"Invalid topic: {self.topic}. Must start with "
                f"'health/', 'intent/', 'coord/', or 'control/'"
            )
        
        # Validate QoS
        if self.qos not in (0, 1, 2):
            raise ValueError(f"QoS must be 0, 1, or 2, got {self.qos}")
        
        # Validate payload
        if not isinstance(self.payload, bytes):
            raise ValueError(f"Payload must be bytes, got {type(self.payload)}")
        
        if len(self.payload) == 0:
            raise ValueError("Payload cannot be empty")
        
        if len(self.payload) > 10240:  # 10KB ISL limit
            raise ValueError(
                f"Payload size {len(self.payload)} exceeds 10KB ISL limit"
            )
        
        # Validate sequence
        if self.sequence < 0:
            raise ValueError(f"Sequence must be non-negative, got {self.sequence}")

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "topic": self.topic,
            "payload": self.payload.hex(),  # Hex encode bytes
            "sender": self.sender.to_dict(),
            "qos": self.qos,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "message_id": str(self.message_id),
            "receiver": self.receiver.to_dict() if self.receiver else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SwarmMessage":
        """Deserialize from dictionary."""
        from uuid import UUID
        
        sender_data = data["sender"]
        sender = AgentID(
            constellation=sender_data["constellation"],
            satellite_serial=sender_data["satellite_serial"],
            uuid=UUID(sender_data["uuid"]),
        )
        
        receiver = None
        if data.get("receiver"):
            receiver_data = data["receiver"]
            receiver = AgentID(
                constellation=receiver_data["constellation"],
                satellite_serial=receiver_data["satellite_serial"],
                uuid=UUID(receiver_data["uuid"]),
            )
        
        return cls(
            topic=data["topic"],
            payload=bytes.fromhex(data["payload"]),
            sender=sender,
            qos=data.get("qos", 1),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence=data.get("sequence", 0),
            message_id=UUID(data.get("message_id", str(uuid4()))),
            receiver=receiver,
        )


@dataclass
class MessageAck:
    """Acknowledgment for QoS 1 messages.
    
    Attributes:
        message_id: ID of acknowledged message
        sender: Agent sending the ACK
        timestamp: ACK timestamp
        success: Whether delivery was successful
    """
    message_id: UUID
    sender: AgentID
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "message_id": str(self.message_id),
            "sender": self.sender.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
        }


@dataclass
class TopicFilter:
    """Filter for topic subscriptions.
    
    Supports wildcard subscriptions:
    - "health/*" → all health topics
    - "health/summary" → specific topic
    - "*" → all topics (use with caution)
    """
    pattern: str

    def __post_init__(self):
        """Validate filter pattern."""
        if not self.pattern:
            raise ValueError("Filter pattern cannot be empty")

    def matches(self, topic: str) -> bool:
        """Check if topic matches this filter."""
        if self.pattern == "*":
            return True
        
        if self.pattern.endswith("/*"):
            prefix = self.pattern[:-2]
            return topic.startswith(f"{prefix}/")
        
        return self.pattern == topic


@dataclass
class SubscriptionID:
    """Subscription identifier for message bus operations.
    
    Attributes:
        id: Unique subscription identifier
        topic_filter: Topic filter for this subscription
        subscriber: Subscribing agent
    """
    id: UUID = field(default_factory=uuid4)
    topic_filter: str = ""
    subscriber: Optional[AgentID] = None

    def __hash__(self):
        """Make subscription hashable."""
        return hash(self.id)

    def __eq__(self, other):
        """Compare subscriptions by ID."""
        if not isinstance(other, SubscriptionID):
            return False
        return self.id == other.id

class ActionScope(str, Enum):
    """Scope of policy action.
    
    LOCAL: Only affects this satellite
    SWARM: Affects constellation (requires global consensus)
    """
    LOCAL = "LOCAL"
    SWARM = "SWARM"


class PriorityEnum(int, Enum):
    """Priority levels for intent messages.
    
    AVAILABILITY (1): Lowest - role changes, load balancing
    PERFORMANCE (2): Medium - thrust optimization, attitude control
    SAFETY (3): Highest - emergency stop, safe mode transitions
    """
    AVAILABILITY = 1
    PERFORMANCE = 2
    SAFETY = 3


@dataclass
class IntentMessage:
    """Intent message for coordinating planned actions across constellation.
    
    Issue #402: Intent signal exchange protocol
    - Communicates planned actions (attitude adjust, load shed, role change)
    - Includes conflict scoring for collision detection
    - Prioritized delivery with QoS=2 (reliable)
    
    Attributes:
        action_type: Type of action (e.g., "attitude_adjust", "load_shed", "role_change")
        parameters: Action parameters as dict (e.g., {"target_angle": 45.2, "duration": 30})
        priority: Priority level (SAFETY > PERFORMANCE > AVAILABILITY)
        sender: AgentID of intent originator
        conflict_score: 0.0-1.0 estimated conflict vs known intents
        sequence: Sequence number for ordering (Issue #403 prep)
        timestamp: When intent was created
    """
    action_type: str
    parameters: dict[str, Any]
    priority: PriorityEnum
    sender: AgentID
    conflict_score: float = 0.0
    sequence: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate intent message fields."""
        if not self.action_type:
            raise ValueError("action_type must not be empty")
        if not isinstance(self.priority, PriorityEnum):
            raise ValueError("priority must be PriorityEnum instance")
        if not (0.0 <= self.conflict_score <= 1.0):
            raise ValueError("conflict_score must be 0.0-1.0")
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "action_type": self.action_type,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "sender": self.sender.uuid.hex,
            "conflict_score": self.conflict_score,
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Policy:
    """Policy for local or global swarm action.
    
    Issue #407: Local vs global policy arbitration
    - Represents a proposed action (safe_mode, attitude_adjust, role_reassign)
    - Can originate locally (device agent) or globally (consensus engine)
    - Weighted scoring enables intelligent conflict resolution
    
    Attributes:
        action: Action name (e.g., "safe_mode", "attitude_adjust", "role_reassign")
        parameters: Action parameters as dict
        priority: Priority level (SAFETY > PERFORMANCE > AVAILABILITY)
        scope: LOCAL (satellite-only) or SWARM (constellation-wide)
        score: Confidence score 0.0-1.0 (higher = more important)
        agent_id: Originating agent ID
        timestamp: When policy was created
    """
    action: str
    parameters: dict[str, Any]
    priority: PriorityEnum
    scope: ActionScope
    score: float
    agent_id: AgentID
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate policy fields."""
        if not self.action:
            raise ValueError("action must not be empty")
        if not isinstance(self.priority, PriorityEnum):
            raise ValueError("priority must be PriorityEnum instance")
        if not isinstance(self.scope, ActionScope):
            raise ValueError("scope must be ActionScope instance")
        if not (0.0 <= self.score <= 1.0):
            raise ValueError("score must be 0.0-1.0")

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "action": self.action,
            "parameters": self.parameters,
            "priority": self.priority.value,
            "scope": self.scope.value,
            "score": self.score,
            "agent_id": self.agent_id.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Policy":
        """Deserialize from dictionary."""
        agent_data = data["agent_id"]
        agent_id = AgentID(
            constellation=agent_data["constellation"],
            satellite_serial=agent_data["satellite_serial"],
            uuid=UUID(agent_data["uuid"]),
        )
        
        return cls(
            action=data["action"],
            parameters=data["parameters"],
            priority=PriorityEnum(data["priority"]),
            scope=ActionScope(data["scope"]),
            score=data["score"],
            agent_id=agent_id,
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class ActionCommand:
    """Command to execute action across constellation.
    
    Issue #408: Action propagation and compliance tracking
    - Broadcast by leader to target agents
    - Includes deadline for execution
    - Tracked via unique action_id
    
    Attributes:
        action_id: Unique identifier for this action
        action: Action type (e.g., "safe_mode", "attitude_adjust")
        parameters: Action-specific parameters
        target_agents: List of agents that must execute
        deadline: Seconds until deadline
        priority: Priority level (SAFETY > PERFORMANCE > AVAILABILITY)
        originator: Leader agent ID
        timestamp: When action was issued
    """
    action_id: str
    action: str
    parameters: dict[str, Any]
    target_agents: list[AgentID]
    deadline: int  # Seconds
    priority: PriorityEnum
    originator: AgentID
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate command fields."""
        if not self.action_id:
            raise ValueError("action_id must not be empty")
        if not self.action:
            raise ValueError("action must not be empty")
        if self.deadline <= 0:
            raise ValueError("deadline must be positive")
        if not self.target_agents:
            raise ValueError("target_agents must not be empty")

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "action_id": self.action_id,
            "action": self.action,
            "parameters": self.parameters,
            "target_agents": [agent.to_dict() for agent in self.target_agents],
            "deadline": self.deadline,
            "priority": self.priority.value,
            "originator": self.originator.to_dict(),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionCommand":
        """Deserialize from dictionary."""
        originator_data = data["originator"]
        originator = AgentID(
            constellation=originator_data["constellation"],
            satellite_serial=originator_data["satellite_serial"],
            uuid=UUID(originator_data["uuid"]),
        )
        
        target_agents = []
        for agent_data in data["target_agents"]:
            target_agents.append(AgentID(
                constellation=agent_data["constellation"],
                satellite_serial=agent_data["satellite_serial"],
                uuid=UUID(agent_data["uuid"]),
            ))
        
        return cls(
            action_id=data["action_id"],
            action=data["action"],
            parameters=data["parameters"],
            target_agents=target_agents,
            deadline=data["deadline"],
            priority=PriorityEnum(data["priority"]),
            originator=originator,
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class ActionCompleted:
    """Agent completion report for executed action.
    
    Issue #408: Action propagation and compliance tracking
    - Sent by agents to leader after executing action
    - Includes execution status and optional error
    - Used to track compliance percentage
    
    Attributes:
        action_id: ID of the action that was executed
        agent_id: Agent that executed the action
        status: "success", "partial", or "failed"
        timestamp: When action was completed
        error: Optional error message if failed
    """
    action_id: str
    agent_id: AgentID
    status: str  # "success", "partial", "failed"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None

    def __post_init__(self):
        """Validate completion fields."""
        if not self.action_id:
            raise ValueError("action_id must not be empty")
        if self.status not in ("success", "partial", "failed"):
            raise ValueError(f"status must be success/partial/failed, got {self.status}")

    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id.to_dict(),
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionCompleted":
        """Deserialize from dictionary."""
        agent_data = data["agent_id"]
        agent_id = AgentID(
            constellation=agent_data["constellation"],
            satellite_serial=agent_data["satellite_serial"],
            uuid=UUID(agent_data["uuid"]),
        )
        
        return cls(
            action_id=data["action_id"],
            agent_id=agent_id,
            status=data["status"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            error=data.get("error"),
        )