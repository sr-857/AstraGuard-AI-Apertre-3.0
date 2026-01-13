# Quick Reference: ActionScope System (Issue #412)

## Quick Start

```python
from astraguard.swarm.response_orchestrator import (
    ActionScope,
    SwarmResponseOrchestrator,
)
from astraguard.swarm.swarm_decision_loop import Decision

# Initialize orchestrator
orchestrator = SwarmResponseOrchestrator(
    election=election,        # LeaderElection
    consensus=consensus,      # ConsensusEngine
    registry=registry,        # SwarmRegistry
    propagator=propagator,    # ActionPropagator
    swarm_mode_enabled=True,
)

# From SwarmDecisionLoop, get decision with scope tag
decision = await swarm_loop.step(telemetry)

# Execute with scope-based routing
result = await orchestrator.execute(decision, decision.scope)
```

## Choosing Your Scope

### LOCAL: For Local-Only Actions

**When**: Action has no swarm impact

**Example**:
```python
decision = Decision(
    action="battery_reboot",
    confidence=0.99,
    reasoning="Battery voltage critical",
    scope=ActionScope.LOCAL,
    params={"timeout_ms": 5000},
)

# Executes immediately - no coordination
result = await orchestrator.execute(decision, ActionScope.LOCAL)
```

**Use Cases**:
- Battery reboot
- Thermal throttling
- Sensor recalibration
- Local health check

**Latency**: <10ms  
**Bandwidth**: 0 KB

---

### SWARM: For Leader-Approved Actions

**When**: Action needs leader approval and constellation notification

**Example**:
```python
decision = Decision(
    action="role_reassignment",
    confidence=0.95,
    reasoning="Optimize constellation roles",
    scope=ActionScope.SWARM,
    params={"new_role": "BACKUP"},
)

# Executes only on leader; propagates to all
result = await orchestrator.execute(decision, ActionScope.SWARM)
```

**Use Cases**:
- Role reassignment (PRIMARY ↔ BACKUP)
- Attitude adjustment
- Orbit correction
- Consensual power management

**Latency**: 100-500ms  
**Bandwidth**: ~2.5 KB  
**Quorum**: 2/3 majority required  
**Leader-Only**: Yes - non-leaders always denied

---

### CONSTELLATION: For Safe-Mode Actions

**When**: Action needs full quorum and safety validation

**Example**:
```python
decision = Decision(
    action="safe_mode_transition",
    confidence=0.92,
    reasoning="Anomaly detected: thermal spike",
    scope=ActionScope.CONSTELLATION,
    params={"duration_minutes": 30},
)

# Executes with safety gates; blocks if unsafe
result = await orchestrator.execute(decision, ActionScope.CONSTELLATION)
```

**Use Cases**:
- Safe mode transition
- Emergency power reduction
- Coordinated failover
- Constellation-wide emergency actions

**Latency**: 500ms-2s  
**Bandwidth**: ~3.0 KB  
**Quorum**: 2/3 majority required  
**Safety Gates**: Validation before execution (prep for #413)

---

## Metrics

### Track Execution

```python
metrics = orchestrator.get_metrics()

# Scope counts
print(f"LOCAL actions: {metrics.local_actions}")
print(f"SWARM actions: {metrics.swarm_actions}")
print(f"CONSTELLATION actions: {metrics.constellation_actions}")

# Approval rate
print(f"Leader approval rate: {metrics.leader_approval_rate:.1%}")

# Safety blocks
print(f"Safety gate blocks: {metrics.safety_gate_blocks}")

# Latency
print(f"LOCAL latency: {metrics.local_latency_ms}ms")
print(f"SWARM latency: {metrics.swarm_latency_ms}ms")
print(f"CONSTELLATION latency: {metrics.constellation_latency_ms}ms")

# Export for Prometheus
prometheus_dict = metrics.to_dict()
```

---

## Feature Flags

### SWARM_MODE_ENABLED

```python
# Enable swarm coordination (default)
orchestrator = SwarmResponseOrchestrator(
    swarm_mode_enabled=True,  # ✓ Full coordination
)

# Disable swarm coordination (fallback to LOCAL only)
orchestrator = SwarmResponseOrchestrator(
    swarm_mode_enabled=False,  # LOCAL only
)
```

**Environment Variable**:
```bash
export SWARM_MODE_ENABLED=true
```

---

## Backward Compatibility

### Legacy Code

```python
# Old code without scope tag still works
from astraguard.swarm.response_orchestrator import LegacyResponseOrchestrator

legacy = LegacyResponseOrchestrator()

# Defaults to LOCAL scope (safe fallback)
result = await legacy.execute(decision)
```

---

## Integration Points

### With LeaderElection (#405)

```python
# SWARM/CONSTELLATION check leader status
if not orchestrator.election.is_leader():
    # Non-leader denied for SWARM actions
    pass
```

### With ConsensusEngine (#406)

```python
# SWARM/CONSTELLATION propose to consensus
approved = await orchestrator.consensus.propose(
    action=decision.action,
    params=decision.params,
)
```

### With SwarmRegistry (#400)

```python
# CONSTELLATION checks quorum
alive_peers = orchestrator.registry.get_alive_peers()
if len(alive_peers) < 2:
    # Insufficient quorum
    pass
```

### With ActionPropagator (#408)

```python
# SWARM/CONSTELLATION propagate actions
propagated = await orchestrator.propagator.propagate_action(
    action_id=proposal_id,
    action=decision.action,
    scope=scope.value,
)
```

### With SwarmDecisionLoop (#411)

```python
# Decision from SwarmDecisionLoop includes scope tag
decision = await swarm_loop.step(telemetry)
# decision.scope is ActionScope.LOCAL | SWARM | CONSTELLATION
await orchestrator.execute(decision, decision.scope)
```

---

## Error Handling

### Missing Dependencies

```python
# Graceful degradation
orchestrator = SwarmResponseOrchestrator(
    election=None,      # Missing
    consensus=None,     # Missing
    registry=None,      # Missing
    propagator=None,    # Missing
)

# LOCAL still works
result = await orchestrator.execute(decision, ActionScope.LOCAL)
# True

# SWARM/CONSTELLATION fail gracefully
result = await orchestrator.execute(decision, ActionScope.SWARM)
# False (logged)
```

### Timeout Handling

```python
# Custom timeout
result = await orchestrator.execute(
    decision,
    ActionScope.SWARM,
    timeout_seconds=10.0,  # Custom timeout
)
```

### Invalid Scope

```python
# Invalid scope defaults to LOCAL
decision.scope = "invalid"  # String instead of enum
# Automatically converts to ActionScope.LOCAL
result = await orchestrator.execute(decision, decision.scope)
```

---

## Testing

### Unit Tests

```bash
# Run response orchestrator tests
pytest tests/swarm/test_response_orchestrator.py -v

# With coverage
pytest tests/swarm/test_response_orchestrator.py --cov=astraguard.swarm.response_orchestrator
```

### Integration Tests

```bash
# Run 5-agent constellation tests
pytest tests/swarm/test_integration_412.py -v

# Run all swarm tests
pytest tests/swarm/ -v
```

---

## Troubleshooting

### Action Denied for SWARM

```python
# Likely cause: Not leader
if not orchestrator.election.is_leader():
    # Only leaders can execute SWARM actions
    pass

# Check metrics
print(orchestrator.metrics.leader_denials)  # Non-leader attempts
```

### Action Denied for CONSTELLATION

```python
# Likely cause: Insufficient quorum
alive_peers = orchestrator.registry.get_alive_peers()
if len(alive_peers) < 2:
    # Need at least 2 for 2/3 quorum
    pass

# Or: Safety validation failed
print(orchestrator.metrics.safety_gate_blocks)
```

### All Actions Blocked

```python
# Check feature flag
if not orchestrator.swarm_mode_enabled:
    # SWARM_MODE_ENABLED=false
    # Only LOCAL actions work
    pass
```

---

## Decision Scope Tagging

### From SwarmDecisionLoop (#411)

```python
from astraguard.swarm.swarm_decision_loop import Decision, ActionScope

# Decision includes scope tag
decision = Decision(
    decision_type=DecisionType.NORMAL,
    action="battery_reboot",
    confidence=0.99,
    reasoning="Battery voltage critical",
    scope=ActionScope.LOCAL,  # ← Issue #412
    params={"timeout_ms": 5000},
)
```

### Creating Decisions

```python
# LOCAL decision
local_decision = Decision(
    action="thermal_throttle",
    scope=ActionScope.LOCAL,
    confidence=0.95,
    reasoning="Local thermal management",
    params={},
)

# SWARM decision
swarm_decision = Decision(
    action="role_change",
    scope=ActionScope.SWARM,
    confidence=0.90,
    reasoning="Optimize roles",
    params={"new_role": "BACKUP"},
)

# CONSTELLATION decision
constellation_decision = Decision(
    action="safe_mode",
    scope=ActionScope.CONSTELLATION,
    confidence=0.88,
    reasoning="Emergency safe mode",
    params={"duration_minutes": 30},
)
```

---

## Performance Targets

| Metric | LOCAL | SWARM | CONSTELLATION |
|--------|-------|-------|---------------|
| Latency (typical) | 2ms | 250ms | 600ms |
| Latency (P95) | 5ms | 500ms | 1500ms |
| Bandwidth | 0 KB | 2.5 KB | 3.0 KB |
| Quorum needed | N/A | 2/3 | 2/3 |
| Leader required | No | Yes | No |

---

## Next Steps

### Issue #413: Safety Simulator

SafetySimulator will:
- Receive CONSTELLATION actions for validation
- Return safety verdict before execution
- Track safety metrics
- Provide real-time safety analysis

```python
# Future: Safety validation will be active
decision.scope = ActionScope.CONSTELLATION
# → Quorum → Safety check → Propagate (if safe)
```

---

**Ready to use! 🚀**

For more details, see [docs/action-scopes.md](docs/action-scopes.md)
