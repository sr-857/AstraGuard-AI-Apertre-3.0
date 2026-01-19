"""
Intent Broadcaster - Exchange and conflict detection for coordinated actions.

Issue #402: Communication protocols - intent signal exchange
- Publishes IntentMessages with conflict detection
- QoS=2 reliable delivery (prep for Issue #403)
- Conflict scoring: geometric overlap + temporal overlap + priority
- Integration: Registry (#400), Bus (#398), Compressor (#399)
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import math

from astraguard.swarm.types import IntentMessage, PriorityEnum, SwarmTopic
from astraguard.swarm.models import AgentID
from astraguard.swarm.registry import SwarmRegistry
from astraguard.swarm.bus import SwarmMessageBus
from astraguard.swarm.compressor import StateCompressor

logger = logging.getLogger(__name__)

# Configuration
INTENT_HISTORY_SIZE = 100  # Keep last N intents per agent
INTENT_TIMEOUT = 300  # Intent expires after 5 minutes
CONFLICT_THRESHOLD = 0.6  # 0.0-1.0, flag if >= this value


@dataclass
class IntentStats:
    """Statistics for intent broadcasting."""
    
    total_published: int = 0
    successful_broadcasts: int = 0
    failed_broadcasts: int = 0
    conflicts_detected: int = 0
    average_conflict_score: float = 0.0


class IntentBroadcaster:
    """Broadcasts intents and detects conflicts across constellation."""
    
    def __init__(
        self,
        registry: SwarmRegistry,
        bus: SwarmMessageBus,
        compressor: StateCompressor,
    ):
        """Initialize intent broadcaster.
        
        Args:
            registry: SwarmRegistry for peer management
            bus: SwarmMessageBus for pub/sub
            compressor: StateCompressor for data efficiency
        """
        self.registry = registry
        self.bus = bus
        self.compressor = compressor
        
        # Track known intents per agent
        self.intent_history: Dict[AgentID, List[IntentMessage]] = {}
        self.stats = IntentStats()
        self.sequence_counter = 0
        
        logger.info("IntentBroadcaster initialized")
    
    async def publish_intent(self, intent: IntentMessage) -> bool:
        """Publish intent with conflict detection.
        
        Args:
            intent: IntentMessage to publish
            
        Returns:
            True if published successfully
        """
        try:
            # Compute conflict score vs known intents
            intent.conflict_score = self._compute_conflict_score(intent)
            intent.sequence = self.sequence_counter
            self.sequence_counter += 1
            
            # Create signed payload
            payload = {
                "action_type": intent.action_type,
                "parameters": intent.parameters,
                "priority": intent.priority.value,
                "sender": intent.sender.uuid.hex,
                "conflict_score": intent.conflict_score,
                "sequence": intent.sequence,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Publish to bus with QoS=2 (reliable)
            topic = f"{SwarmTopic.INTENT.value}/{intent.sender.constellation}"
            success = await self.bus.publish(
                topic=topic,
                payload=json.dumps(payload),
                qos=2,  # RELIABLE
                receiver=None  # Broadcast to all
            )
            
            if success:
                self.stats.successful_broadcasts += 1
                # Store in local history
                self._store_intent(intent)
                
                if intent.conflict_score >= CONFLICT_THRESHOLD:
                    self.stats.conflicts_detected += 1
                    logger.warning(
                        f"Intent conflict detected: {intent.action_type} "
                        f"(score: {intent.conflict_score:.2f})"
                    )
            else:
                self.stats.failed_broadcasts += 1
            
            self.stats.total_published += 1
            self._update_average_conflict(intent.conflict_score)
            
            return success
            
        except Exception as e:
            logger.error(f"Error publishing intent: {e}", exc_info=True)
            self.stats.failed_broadcasts += 1
            return False
    
    def _compute_conflict_score(self, new_intent: IntentMessage) -> float:
        """Compute conflict score vs known intents.
        
        Considers:
        - Geometric overlap (e.g., attitude angles)
        - Temporal overlap (duration overlap)
        - Priority override (SAFETY beats others)
        
        Returns:
            Float 0.0-1.0 where 1.0 = complete conflict
        """
        if not self.intent_history:
            return 0.0
        
        # Collect all non-expired intents
        known_intents = self._get_active_intents()
        
        if not known_intents:
            return 0.0
        
        # Compute scores against each known intent
        scores = []
        for known in known_intents:
            score = self._compute_pairwise_conflict(new_intent, known)
            scores.append(score)
        
        # Return max conflict (worst case)
        return max(scores) if scores else 0.0
    
    def _compute_pairwise_conflict(
        self, intent_a: IntentMessage, intent_b: IntentMessage
    ) -> float:
        """Compute conflict between two intents.
        
        Algorithm:
        1. Check if same action type
        2. Geometric overlap (angle/parameter distance)
        3. Temporal overlap (duration overlap)
        4. Priority resolution
        """
        # Different action types: low conflict (0.2)
        if intent_a.action_type != intent_b.action_type:
            return 0.2
        
        # Geometric overlap for attitude adjustments
        geometric_score = self._compute_geometric_overlap(intent_a, intent_b)
        
        # Temporal overlap (duration overlap multiplier)
        temporal_multiplier = self._compute_temporal_overlap(intent_a, intent_b)
        
        # Base conflict
        base_conflict = geometric_score * temporal_multiplier
        
        # Priority resolution: SAFETY always wins
        if intent_a.priority == PriorityEnum.SAFETY:
            base_conflict *= 0.5  # SAFETY intent reduces conflict
        if intent_b.priority == PriorityEnum.SAFETY:
            base_conflict *= 0.5
        
        return min(1.0, base_conflict)
    
    def _compute_geometric_overlap(
        self, intent_a: IntentMessage, intent_b: IntentMessage
    ) -> float:
        """Compute geometric overlap for attitude adjustments.
        
        For attitude_adjust actions:
        - Extract target_angle from parameters
        - Compute angular distance
        - Normalize to 0.0-1.0 conflict
        """
        if intent_a.action_type != "attitude_adjust":
            return 0.5  # Default for other types
        
        try:
            angle_a = intent_a.parameters.get("target_angle", 0)
            angle_b = intent_b.parameters.get("target_angle", 0)
            
            if not isinstance(angle_a, (int, float)) or not isinstance(angle_b, (int, float)):
                return 0.3
            
            # Angular distance (0-180 degrees max)
            angle_diff = abs(angle_a - angle_b)
            angle_diff = min(angle_diff, 360 - angle_diff)  # Wrap around
            
            # Normalize to 0.0-1.0: 0° = 1.0 conflict, 180° = 0.0 conflict
            conflict = 1.0 - (angle_diff / 180.0)
            return max(0.0, conflict)
            
        except (KeyError, TypeError):
            return 0.3
    
    def _compute_temporal_overlap(
        self, intent_a: IntentMessage, intent_b: IntentMessage
    ) -> float:
        """Compute temporal overlap multiplier.
        
        If durations overlap in time:
        - Full overlap = 1.0x multiplier
        - Partial overlap = 0.5-1.0x
        - No overlap = 0.1x (minimal conflict)
        """
        try:
            duration_a = intent_a.parameters.get("duration", 0)
            duration_b = intent_b.parameters.get("duration", 0)
            
            if not isinstance(duration_a, (int, float)) or not isinstance(duration_b, (int, float)):
                return 0.5
            
            time_a_start = intent_a.timestamp
            time_a_end = time_a_start + timedelta(seconds=duration_a)
            
            time_b_start = intent_b.timestamp
            time_b_end = time_b_start + timedelta(seconds=duration_b)
            
            # Check for overlap
            overlap_start = max(time_a_start, time_b_start)
            overlap_end = min(time_a_end, time_b_end)
            
            if overlap_start >= overlap_end:
                # No overlap
                return 0.1
            
            # Compute overlap fraction
            overlap_duration = (overlap_end - overlap_start).total_seconds()
            total_duration = max(duration_a, duration_b)
            
            if total_duration == 0:
                return 0.5
            
            overlap_fraction = overlap_duration / total_duration
            
            # Return multiplier: 0.1-1.0
            return 0.1 + (overlap_fraction * 0.9)
            
        except (KeyError, TypeError):
            return 0.5
    
    def _store_intent(self, intent: IntentMessage):
        """Store intent in local history."""
        if intent.sender not in self.intent_history:
            self.intent_history[intent.sender] = []
        
        history = self.intent_history[intent.sender]
        history.append(intent)
        
        # Trim to size limit
        if len(history) > INTENT_HISTORY_SIZE:
            self.intent_history[intent.sender] = history[-INTENT_HISTORY_SIZE:]
    
    def _get_active_intents(self) -> List[IntentMessage]:
        """Get all non-expired intents from history."""
        now = datetime.utcnow()
        active = []
        
        for agent_id, intents in self.intent_history.items():
            for intent in intents:
                age = (now - intent.timestamp).total_seconds()
                if age < INTENT_TIMEOUT:
                    active.append(intent)
        
        return active
    
    def _update_average_conflict(self, new_score: float):
        """Update running average conflict score."""
        if self.stats.total_published == 0:
            self.stats.average_conflict_score = new_score
        else:
            count = self.stats.total_published
            prev_avg = self.stats.average_conflict_score
            self.stats.average_conflict_score = (
                (prev_avg * (count - 1) + new_score) / count
            )
    
    def get_stats(self) -> IntentStats:
        """Get current statistics."""
        return self.stats
    
    def get_delivery_rate(self) -> float:
        """Get intent delivery success rate."""
        if self.stats.total_published == 0:
            return 0.0
        return self.stats.successful_broadcasts / self.stats.total_published
    
    def get_conflict_rate(self) -> float:
        """Get fraction of intents with high conflict."""
        if self.stats.total_published == 0:
            return 0.0
        return self.stats.conflicts_detected / self.stats.total_published
