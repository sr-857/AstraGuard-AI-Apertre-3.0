"""
Action Propagation and Compliance Tracking for satellite constellation.

Issue #408: Coordination Core - Action propagation and compliance tracking
- Leader broadcasts approved actions to target agents
- Tracks execution status with 30s deadline
- Calculates compliance percentage (target: 90%)
- Escalates non-compliant agents (role demotion prep for #409)
- Metrics: action count, completion rates, escalation tracking

Algorithm:
1. Leader proposes action via consensus (#406) + policy arbitration (#407)
2. ActionPropagator broadcasts ActionCommand to target agents via control/ topic
3. Agents execute and send ActionCompleted status back (success/partial/failed)
4. Leader aggregates completions:
   - Compliance = completed_agents / total_target_agents
   - If compliance < 90% at deadline: mark agents for escalation (#409)
5. Real-time dashboard shows per-agent and constellation-wide compliance

Example:
  Broadcast safe_mode to 10 agents with 30s deadline
  At 25s: 9 agents complete → 90% compliance
  At deadline: 1 agent still pending → escalate for role demotion
  Real-time dashboard: [9/10] 90% green, 1 red (non-compliant)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, List
import asyncio
import uuid

from astraguard.swarm.types import ActionCommand, ActionCompleted, PriorityEnum
from astraguard.swarm.models import AgentID
from astraguard.swarm.leader_election import LeaderElection
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.consensus import NotLeaderError


@dataclass
class ActionState:
    """Tracks state of a propagated action.
    
    Attributes:
        action_id: Unique action identifier
        action: Action type (e.g., "safe_mode", "attitude_adjust")
        target_agents: List of agents that must execute
        deadline: Absolute deadline datetime
        completed_agents: Set of agent IDs that completed successfully
        failed_agents: Set of agent IDs that failed
        escalated_agents: Set of agents marked for escalation
        priority: Action priority level
        timestamp: When action was issued
    """
    action_id: str
    action: str
    target_agents: List[AgentID]
    deadline: datetime
    completed_agents: Set[str] = field(default_factory=set)  # Store as serial strings
    failed_agents: Set[str] = field(default_factory=set)
    escalated_agents: Set[str] = field(default_factory=set)
    priority: PriorityEnum = PriorityEnum.SAFETY
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def compliance_percent(self) -> float:
        """Calculate compliance percentage.
        
        Returns: completed_agents / target_agents * 100 (0.0-100.0)
        """
        if not self.target_agents:
            return 100.0
        return (len(self.completed_agents) / len(self.target_agents)) * 100.0

    @property
    def remaining_agents(self) -> Set[str]:
        """Get agents that haven't completed or failed."""
        target_serials = {agent.satellite_serial for agent in self.target_agents}
        completed_or_failed = self.completed_agents | self.failed_agents
        return target_serials - completed_or_failed

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "action_id": self.action_id,
            "action": self.action,
            "target_agents": len(self.target_agents),
            "deadline": self.deadline.isoformat(),
            "completed_agents": len(self.completed_agents),
            "failed_agents": len(self.failed_agents),
            "escalated_agents": list(self.escalated_agents),
            "compliance_percent": self.compliance_percent,
            "priority": self.priority.name,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ActionPropagatorMetrics:
    """Metrics for action propagation and compliance tracking."""
    action_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    escalation_count: int = 0
    avg_compliance_percent: float = 0.0
    avg_completion_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to dict for Prometheus export."""
        return {
            "action_count": self.action_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "escalation_count": self.escalation_count,
            "avg_compliance_percent": self.avg_compliance_percent,
            "avg_completion_time_ms": self.avg_completion_time_ms,
        }


class ActionPropagator:
    """Propagates actions across constellation with compliance tracking.
    
    Leader-only component that:
    1. Broadcasts ActionCommand to target agents (control/ topic, QoS=2)
    2. Collects ActionCompleted responses with timeout tracking
    3. Calculates compliance (target: 90%)
    4. Escalates non-compliant agents for role demotion (#409)
    5. Exports metrics for dashboard and Prometheus
    
    Attributes:
        election: LeaderElection instance (#405)
        registry: SwarmRegistry instance (#400)
        bus: SwarmMessageBus instance (#398)
        pending_actions: Dict mapping action_id → ActionState
        metrics: ActionPropagatorMetrics for monitoring
    """

    # Message topics
    ACTION_COMMAND_TOPIC = "control/action_command"
    ACTION_COMPLETED_TOPIC = "control/action_completed"

    # Compliance threshold (90%)
    COMPLIANCE_THRESHOLD = 0.90

    def __init__(
        self,
        election: LeaderElection,
        registry: SwarmRegistry,
        bus: SwarmMessageBus,
    ):
        """Initialize ActionPropagator.
        
        Args:
            election: LeaderElection instance for leader verification
            registry: SwarmRegistry for alive peer discovery
            bus: SwarmMessageBus for action/completion messages
        """
        self.election = election
        self.registry = registry
        self.bus = bus
        self.pending_actions: Dict[str, ActionState] = {}
        self.metrics = ActionPropagatorMetrics()
        self._completion_events: Dict[str, asyncio.Event] = {}

    async def start(self):
        """Start listening for action completion messages."""
        if not hasattr(self, '_is_running'):
            self._is_running = True
            # Subscribe to completion messages
            await self.bus.subscribe(
                self.ACTION_COMPLETED_TOPIC,
                self._handle_action_completed,
                qos=2,  # Reliable delivery
            )

    async def stop(self):
        """Stop listening for messages."""
        if hasattr(self, '_is_running'):
            self._is_running = False
            await self.bus.unsubscribe(
                self.ACTION_COMPLETED_TOPIC,
                qos=2,
            )

    async def propagate_action(
        self,
        action: str,
        parameters: dict,
        target_agents: List[AgentID],
        deadline_seconds: int = 30,
        priority: PriorityEnum = PriorityEnum.SAFETY,
    ) -> str:
        """Propagate action to target agents (leader-only).
        
        Algorithm:
        1. Verify leader status
        2. Create unique action_id
        3. Broadcast ActionCommand to all target agents (QoS=2)
        4. Wait for completions or deadline
        5. Calculate compliance
        6. Escalate non-compliant agents
        
        Args:
            action: Action type (e.g., "safe_mode")
            parameters: Action parameters
            target_agents: List of AgentID objects
            deadline_seconds: Execution deadline in seconds (default: 30)
            priority: Action priority level
        
        Returns:
            str: action_id for tracking
        
        Raises:
            NotLeaderError: If not the elected leader
        """
        # Verify leader status
        if not self.election.is_leader():
            raise NotLeaderError("Only leader can propagate actions")
        
        # Create unique action ID
        action_id = f"{action}_{uuid.uuid4().hex[:8]}"
        
        # Calculate deadline
        deadline = datetime.utcnow() + timedelta(seconds=deadline_seconds)
        
        # Create action state
        action_state = ActionState(
            action_id=action_id,
            action=action,
            target_agents=target_agents,
            deadline=deadline,
            priority=priority,
        )
        
        # Store action state
        self.pending_actions[action_id] = action_state
        self.metrics.action_count += 1
        
        # Create action command
        command = ActionCommand(
            action_id=action_id,
            action=action,
            parameters=parameters,
            target_agents=target_agents,
            deadline=deadline_seconds,
            priority=priority,
            originator=self.election.local_agent_id,
        )
        
        # Broadcast to all target agents
        await self.bus.publish(
            self.ACTION_COMMAND_TOPIC,
            command.to_dict(),
            qos=2,  # Reliable delivery via #403
        )
        
        # Create event for completion notification
        self._completion_events[action_id] = asyncio.Event()
        
        # Wait for completions or timeout
        try:
            await asyncio.wait_for(
                self._wait_for_completions(action_id, deadline_seconds),
                timeout=deadline_seconds + 5,  # Small buffer for message delivery
            )
        except asyncio.TimeoutError:
            # Deadline reached, evaluate compliance
            pass
        
        # Check compliance and escalate if needed
        await self._evaluate_compliance(action_id)
        
        return action_id

    async def _wait_for_completions(self, action_id: str, timeout_seconds: int):
        """Wait for agent completions with timeout.
        
        Args:
            action_id: Action to wait for
            timeout_seconds: Seconds to wait
        """
        # Check periodically for completions
        start_time = datetime.utcnow()
        deadline = start_time + timedelta(seconds=timeout_seconds)
        
        while datetime.utcnow() < deadline:
            action_state = self.pending_actions.get(action_id)
            if not action_state:
                break
            
            # Check if all agents completed or failed
            total_responses = len(action_state.completed_agents) + len(action_state.failed_agents)
            if total_responses >= len(action_state.target_agents):
                break
            
            # Wait a bit before checking again
            await asyncio.sleep(0.5)

    async def _handle_action_completed(self, message: dict):
        """Handle ActionCompleted message from agent.
        
        Args:
            message: ActionCompleted message dict
        """
        try:
            completion = ActionCompleted.from_dict(message)
        except Exception:
            return  # Ignore malformed messages
        
        # Find action state
        action_state = self.pending_actions.get(completion.action_id)
        if not action_state:
            return  # Action not found or already processed
        
        # Record completion
        agent_serial = completion.agent_id.satellite_serial
        if completion.status == "success":
            action_state.completed_agents.add(agent_serial)
        else:
            action_state.failed_agents.add(agent_serial)
        
        # Notify waiters
        if completion.action_id in self._completion_events:
            self._completion_events[completion.action_id].set()

    async def _evaluate_compliance(self, action_id: str):
        """Evaluate compliance and escalate if needed.
        
        Algorithm:
        1. Calculate compliance percent
        2. If < 90%: mark agents for escalation
        3. Update metrics
        
        Args:
            action_id: Action to evaluate
        """
        action_state = self.pending_actions.get(action_id)
        if not action_state:
            return
        
        compliance = action_state.compliance_percent
        
        # Check compliance threshold
        if compliance < (self.COMPLIANCE_THRESHOLD * 100):
            # Identify non-compliant agents
            non_compliant = action_state.remaining_agents | action_state.failed_agents
            action_state.escalated_agents = non_compliant
            self.metrics.escalation_count += len(non_compliant)
        
        # Update metrics
        self.metrics.completed_count += len(action_state.completed_agents)
        self.metrics.failed_count += len(action_state.failed_agents)

    def get_compliance_status(self, action_id: str) -> Optional[Dict]:
        """Get compliance status for action.
        
        Returns:
            Dict with: {
                action_id, action, target_count, completed_count,
                failed_count, escalated_count, compliance_percent
            }
        
        Args:
            action_id: Action to query
        
        Returns:
            Dict with compliance info, or None if action not found
        """
        action_state = self.pending_actions.get(action_id)
        if not action_state:
            return None
        
        return action_state.to_dict()

    def get_non_compliant_agents(self, action_id: str) -> Set[str]:
        """Get agents that didn't comply with action.
        
        Args:
            action_id: Action to query
        
        Returns:
            Set of non-compliant agent serials
        """
        action_state = self.pending_actions.get(action_id)
        if not action_state:
            return set()
        
        return action_state.escalated_agents.copy()

    def get_metrics(self) -> Dict:
        """Get propagation metrics.
        
        Returns:
            Dict with action count, completion rates, escalation count
        """
        return self.metrics.to_dict()

    def clear_action(self, action_id: str):
        """Clear action from tracking (for cleanup).
        
        Args:
            action_id: Action to clear
        """
        if action_id in self.pending_actions:
            del self.pending_actions[action_id]
        if action_id in self._completion_events:
            del self._completion_events[action_id]
