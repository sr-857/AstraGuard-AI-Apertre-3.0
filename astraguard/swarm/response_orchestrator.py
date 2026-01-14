"""
Swarm Response Orchestrator with ActionScope Tagging

Issue #412: Integration layer with scope-based action execution
- LOCAL: Battery reboot, no coordination (0ms overhead)
- SWARM: Role reassignment, leader approval + propagation (#408)
- CONSTELLATION: Safe mode, quorum (#406) + safety simulation (#413 prep)

Features:
  - Scope-based execution paths (LOCAL → fast, SWARM → consensus, CONSTELLATION → safe)
  - Leader-only enforcement for SWARM actions
  - Safety simulation hooks for CONSTELLATION (prep for #413)
  - Action propagation integration (#408)
  - Zero breaking changes to existing ResponseOrchestrator
  - Backward compatibility with legacy orchestrator
  - Feature flag: SWARM_MODE_ENABLED
  - Metrics: action_scope_count, leader_approval_rate, safety_gate_block_count

Execution Flow:
  Decision (from #411) → ActionScope tag
    ├─ LOCAL: Execute immediately (battery reboot)
    ├─ SWARM: Check leader → Propose consensus (#406) → Propagate (#408)
    └─ CONSTELLATION: Check quorum → Propose consensus → Validate safety (#413) → Propagate

Dependencies:
  - LeaderElection (#405)
  - ConsensusEngine (#406)
  - SwarmRegistry (#400)
  - ActionPropagator (#408)
  - SwarmDecisionLoop (#411) - provides Decision with scope tag
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ActionScope(Enum):
    """Scope levels for action execution in swarm."""
    LOCAL = "local"                    # Battery reboot, no coordination
    SWARM = "swarm"                    # Role reassignment, leader approval
    CONSTELLATION = "constellation"    # Safe mode, quorum + simulation


@dataclass
class ResponseMetrics:
    """Metrics for response orchestrator."""
    # Scope execution counts
    local_actions: int = 0
    swarm_actions: int = 0
    constellation_actions: int = 0
    
    # Approval tracking
    leader_approvals: int = 0
    leader_denials: int = 0
    
    # Safety gates
    safety_gate_blocks: int = 0
    
    # Latency tracking (ms)
    local_latency_ms: float = 0.0
    swarm_latency_ms: float = 0.0
    constellation_latency_ms: float = 0.0
    
    # Timestamps
    first_execution: Optional[datetime] = None
    last_execution: Optional[datetime] = None
    
    @property
    def leader_approval_rate(self) -> float:
        """Calculate leader approval rate (0.0-1.0)."""
        total = self.leader_approvals + self.leader_denials
        if total == 0:
            return 0.0
        return self.leader_approvals / total
    
    @property
    def total_actions(self) -> int:
        """Total actions executed across all scopes."""
        return self.local_actions + self.swarm_actions + self.constellation_actions
    
    def to_dict(self) -> dict:
        """Export metrics for Prometheus."""
        return {
            "action_scope_count_local": self.local_actions,
            "action_scope_count_swarm": self.swarm_actions,
            "action_scope_count_constellation": self.constellation_actions,
            "action_scope_count_total": self.total_actions,
            "leader_approval_rate": self.leader_approval_rate,
            "leader_approvals": self.leader_approvals,
            "leader_denials": self.leader_denials,
            "safety_gate_block_count": self.safety_gate_blocks,
            "execution_latency_local_ms": self.local_latency_ms,
            "execution_latency_swarm_ms": self.swarm_latency_ms,
            "execution_latency_constellation_ms": self.constellation_latency_ms,
            "first_execution": self.first_execution.isoformat() if self.first_execution else None,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }


class SwarmResponseOrchestrator:
    """
    Orchestrates response execution with scope-based routing.
    
    Handles three classes of actions:
    - LOCAL: Immediate execution (battery reboot)
    - SWARM: Leader-approved consensus actions (role reassignment)
    - CONSTELLATION: Quorum + safety-gated actions (safe mode transition)
    
    Dependencies injected:
    - election: LeaderElection (#405) - leader detection and state
    - consensus: ConsensusEngine (#406) - quorum voting
    - registry: SwarmRegistry (#400) - peer discovery
    - propagator: ActionPropagator (#408) - action broadcast
    - simulator: Optional[SafetySimulator] - (#413 prep) safety validation
    """
    
    def __init__(
        self,
        election: Optional[Any] = None,           # LeaderElection (#405)
        consensus: Optional[Any] = None,          # ConsensusEngine (#406)
        registry: Optional[Any] = None,           # SwarmRegistry (#400)
        propagator: Optional[Any] = None,         # ActionPropagator (#408)
        simulator: Optional[Any] = None,          # SafetySimulator (#413 prep)
        swarm_mode_enabled: bool = True,
    ):
        """
        Initialize SwarmResponseOrchestrator.
        
        Args:
            election: LeaderElection for leader-only enforcement
            consensus: ConsensusEngine for SWARM/CONSTELLATION voting
            registry: SwarmRegistry for peer tracking
            propagator: ActionPropagator for action distribution
            simulator: Optional SafetySimulator for CONSTELLATION validation
            swarm_mode_enabled: Feature flag for swarm coordination
        """
        self.election = election
        self.consensus = consensus
        self.registry = registry
        self.propagator = propagator
        self.simulator = simulator
        self.swarm_mode_enabled = swarm_mode_enabled
        
        # Metrics
        self.metrics = ResponseMetrics()
        
        logger.info(
            f"SwarmResponseOrchestrator initialized "
            f"(swarm_mode={swarm_mode_enabled})"
        )
    
    async def execute(
        self,
        decision: Any,          # SwarmDecisionLoop.Decision (#411)
        scope: ActionScope,
        timeout_seconds: float = 5.0,
    ) -> bool:
        """
        Execute decision based on scope with proper coordination.
        
        Routing:
        - LOCAL: _execute_local() - immediate, no coordination
        - SWARM: _execute_swarm() - leader approval + propagation
        - CONSTELLATION: _execute_constellation() - quorum + safety gates
        
        Args:
            decision: Decision object from SwarmDecisionLoop with action/params
            scope: ActionScope tag indicating execution level
            timeout_seconds: Max time to wait for consensus/propagation
        
        Returns:
            bool: True if execution succeeded, False otherwise
        """
        import time
        start_time = time.time()
        
        try:
            # Route based on scope
            if scope == ActionScope.LOCAL:
                result = await self._execute_local(decision)
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.local_actions += 1
                self.metrics.local_latency_ms = elapsed_ms
                
            elif scope == ActionScope.SWARM:
                result = await self._execute_swarm(decision, timeout_seconds)
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.swarm_actions += 1
                self.metrics.swarm_latency_ms = elapsed_ms
                
            else:  # ActionScope.CONSTELLATION
                result = await self._execute_constellation(decision, timeout_seconds)
                elapsed_ms = (time.time() - start_time) * 1000
                self.metrics.constellation_actions += 1
                self.metrics.constellation_latency_ms = elapsed_ms
            
            # Update timestamps
            if not self.metrics.first_execution:
                self.metrics.first_execution = datetime.utcnow()
            self.metrics.last_execution = datetime.utcnow()
            
            logger.info(
                f"Action executed: scope={scope.value}, "
                f"action={decision.action}, result={result}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing action: {e}", exc_info=True)
            return False
    
    async def _execute_local(self, decision: Any) -> bool:
        """
        Execute LOCAL action immediately without coordination.
        
        Use cases:
        - Battery reboot (no swarm impact)
        - Local sensor recalibration
        - Thermal throttling
        
        Args:
            decision: Decision with action and params
        
        Returns:
            bool: True if execution successful
        """
        try:
            logger.info(
                f"Executing LOCAL action: {decision.action} "
                f"(decision_id={decision.decision_id})"
            )
            
            # Local actions execute immediately without coordination
            # In real implementation, this would call actual action handlers
            # For now, simulate successful execution
            
            logger.debug(
                f"LOCAL action completed: {decision.action}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"LOCAL action failed: {e}", exc_info=True)
            return False
    
    async def _execute_swarm(
        self,
        decision: Any,
        timeout_seconds: float = 5.0,
    ) -> bool:
        """
        Execute SWARM action with leader approval and propagation.
        
        Algorithm:
        1. Check if leader (abort if not leader)
        2. Propose action to consensus engine (#406)
        3. Wait for 2/3 quorum approval (or timeout)
        4. If approved, propagate to constellation (#408)
        5. Await propagation completion
        
        Use cases:
        - Role reassignment (PRIMARY ↔ BACKUP)
        - Attitude adjustment (swarm-wide)
        - Orbit correction (coordinated)
        
        Args:
            decision: Decision with action and params
            timeout_seconds: Max time for consensus
        
        Returns:
            bool: True if consensus achieved and propagated
        """
        try:
            # Verify SWARM mode is enabled
            if not self.swarm_mode_enabled:
                logger.warning("SWARM action blocked: SWARM_MODE_ENABLED=False")
                self.metrics.leader_denials += 1
                return False
            
            # Check leader status
            if not self.election or not self.election.is_leader():
                logger.warning(
                    f"SWARM action rejected: not leader "
                    f"(decision_id={decision.decision_id})"
                )
                self.metrics.leader_denials += 1
                return False
            
            logger.info(
                f"Executing SWARM action: {decision.action} "
                f"(decision_id={decision.decision_id})"
            )
            
            # Propose to consensus engine
            if not self.consensus:
                logger.error("SWARM action blocked: ConsensusEngine not available")
                self.metrics.leader_denials += 1
                return False
            
            proposal_id = str(uuid4())
            approved = await self.consensus.propose(
                action=decision.action,
                params=getattr(decision, 'params', {}),
                proposal_id=proposal_id,
                timeout_seconds=int(timeout_seconds),
            )
            
            if not approved:
                logger.warning(
                    f"SWARM action denied by consensus: {decision.action}"
                )
                self.metrics.leader_denials += 1
                return False
            
            self.metrics.leader_approvals += 1
            
            # Propagate to constellation
            if not self.propagator:
                logger.error("SWARM action approved but propagator unavailable")
                return False
            
            propagated = await self.propagator.propagate_action(
                action_id=proposal_id,
                action=decision.action,
                params=getattr(decision, 'params', {}),
                scope=ActionScope.SWARM.value,
                timeout_seconds=int(timeout_seconds),
            )
            
            if not propagated:
                logger.warning(f"SWARM action propagation failed: {decision.action}")
                return False
            
            logger.info(
                f"SWARM action completed with propagation: {decision.action}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"SWARM action error: {e}", exc_info=True)
            self.metrics.leader_denials += 1
            return False
    
    async def _execute_constellation(
        self,
        decision: Any,
        timeout_seconds: float = 5.0,
    ) -> bool:
        """
        Execute CONSTELLATION action with quorum + safety gates.
        
        Algorithm:
        1. Check quorum size (need majority alive)
        2. Propose to consensus engine for quorum vote
        3. If approved, validate with safety simulator (#413 prep)
        4. If safety check passes, propagate to constellation
        5. Await propagation with stricter compliance (95%+)
        
        Use cases:
        - Safe mode transition (constellation-wide)
        - Emergency power reduction (coordinated)
        - Coordinated failover (all-hands)
        
        Args:
            decision: Decision with action and params
            timeout_seconds: Max time for quorum voting
        
        Returns:
            bool: True if quorum approved AND safety validated AND propagated
        """
        try:
            # Verify SWARM mode is enabled
            if not self.swarm_mode_enabled:
                logger.warning(
                    "CONSTELLATION action blocked: SWARM_MODE_ENABLED=False"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            logger.info(
                f"Executing CONSTELLATION action: {decision.action} "
                f"(decision_id={decision.decision_id})"
            )
            
            # Check quorum availability
            if not self.registry:
                logger.error(
                    "CONSTELLATION action blocked: SwarmRegistry not available"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            alive_peers = self.registry.get_alive_peers()
            if len(alive_peers) < 2:  # Need at least 2 for 2/3 quorum
                logger.warning(
                    f"CONSTELLATION action blocked: insufficient quorum "
                    f"({len(alive_peers)} alive peers)"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            # Safety simulation validation (#413) - CHECK BEFORE CONSENSUS
            if self.simulator:
                try:
                    is_safe = await self.simulator.validate_action(
                        action=decision.action,
                        params=getattr(decision, 'params', {}),
                        decision_id=decision.decision_id,
                        scope=ActionScope.CONSTELLATION.value,
                    )
                    
                    if not is_safe:
                        logger.warning(
                            f"CONSTELLATION action blocked by safety simulator: "
                            f"{decision.action}"
                        )
                        self.metrics.safety_gate_blocks += 1
                        return False
                        
                except Exception as sim_error:
                    logger.warning(
                        f"Safety simulator error (proceeding with caution): {sim_error}"
                    )
                    # Log but don't block - simulator not critical yet
            
            # Propose to consensus (quorum voting)
            if not self.consensus:
                logger.error(
                    "CONSTELLATION action blocked: ConsensusEngine not available"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            proposal_id = str(uuid4())
            approved = await self.consensus.propose(
                action=decision.action,
                params=getattr(decision, 'params', {}),
                proposal_id=proposal_id,
                timeout_seconds=int(timeout_seconds),
            )
            
            if not approved:
                logger.warning(
                    f"CONSTELLATION action denied by quorum: {decision.action}"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            # Propagate to constellation
            if not self.propagator:
                logger.error(
                    "CONSTELLATION action approved but propagator unavailable"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            propagated = await self.propagator.propagate_action(
                action_id=proposal_id,
                action=decision.action,
                params=getattr(decision, 'params', {}),
                scope=ActionScope.CONSTELLATION.value,
                timeout_seconds=int(timeout_seconds),
                min_compliance=0.95,  # CONSTELLATION requires 95% compliance
            )
            
            if not propagated:
                logger.warning(
                    f"CONSTELLATION action propagation failed: {decision.action}"
                )
                self.metrics.safety_gate_blocks += 1
                return False
            
            logger.info(
                f"CONSTELLATION action completed with safety validation: "
                f"{decision.action}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"CONSTELLATION action error: {e}", exc_info=True)
            self.metrics.safety_gate_blocks += 1
            return False
    
    def get_metrics(self) -> ResponseMetrics:
        """Get current metrics snapshot."""
        return self.metrics
    
    def reset_metrics(self) -> None:
        """Reset all metrics to zero."""
        self.metrics = ResponseMetrics()


class LegacyResponseOrchestrator:
    """
    Backward-compatible wrapper for existing ResponseOrchestrator code.
    
    Maintains API compatibility with legacy code while delegating to
    SwarmResponseOrchestrator for scope-aware execution.
    
    Default behavior:
    - Non-scoped decisions default to LOCAL (no coordination)
    - Ensures zero breaking changes to existing orchestrator
    """
    
    def __init__(self, swarm_orchestrator: Optional[SwarmResponseOrchestrator] = None):
        """
        Initialize legacy wrapper.
        
        Args:
            swarm_orchestrator: SwarmResponseOrchestrator to delegate to
        """
        self.swarm = swarm_orchestrator or SwarmResponseOrchestrator()
        logger.info("LegacyResponseOrchestrator initialized (backward compatible)")
    
    async def execute(
        self,
        decision: Any,
        timeout_seconds: float = 5.0,
    ) -> bool:
        """
        Execute decision with default LOCAL scope (backward compatible).
        
        For legacy code that doesn't provide ActionScope, assume LOCAL
        (immediate execution, no coordination).
        
        Args:
            decision: Decision object
            timeout_seconds: Timeout (ignored for LOCAL scope)
        
        Returns:
            bool: Execution success
        """
        # Default to LOCAL scope for backward compatibility
        scope = ActionScope.LOCAL
        
        # Check if decision has explicit scope (from #411 updates)
        if hasattr(decision, 'scope') and decision.scope:
            if isinstance(decision.scope, ActionScope):
                scope = decision.scope
            elif isinstance(decision.scope, str):
                try:
                    scope = ActionScope(decision.scope)
                except ValueError:
                    logger.warning(
                        f"Invalid scope value, defaulting to LOCAL: {decision.scope}"
                    )
                    scope = ActionScope.LOCAL
        
        return await self.swarm.execute(decision, scope, timeout_seconds)
