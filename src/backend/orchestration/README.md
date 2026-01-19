# Orchestration Package - Issue #444 Implementation

This document describes the Recovery Orchestrators & Distributed Coordinator Refactor implementation.

## Overview

The orchestration and coordination logic has been refactored to improve testability, maintainability, and architectural clarity by:

1. **Creating a dedicated `backend/orchestration` package**
2. **Defining clear interfaces** (`Orchestrator`, `Coordinator`)
3. **Implementing dependency injection** for all external dependencies
4. **Separating decision logic from side-effects**
5. **Adding comprehensive test coverage**
6. **Providing backward compatibility shims**

## Package Structure

```
backend/orchestration/
├── __init__.py                         # Package exports
├── orchestrator_base.py                # Orchestrator interface and base class
├── coordinator.py                      # Coordinator interface and LocalCoordinator
├── recovery_orchestrator.py            # Basic recovery orchestrator (refactored)
├── recovery_orchestrator_enhanced.py   # Enhanced recovery orchestrator (refactored)
└── distributed_coordinator.py          # Distributed coordinator (refactored)

tests/backend/orchestration/
├── test_orchestrator.py                # Unit tests for orchestrators
├── test_coordinator.py                 # Unit tests for coordinators
└── test_integration.py                 # Integration tests
```

## Interfaces

### Orchestrator Interface

All orchestrators implement the `Orchestrator` protocol:

```python
class Orchestrator(Protocol):
    async def run(self) -> None:
        """Start the orchestrator's main loop."""
    
    def stop(self) -> None:
        """Stop the orchestrator gracefully."""
    
    async def handle_event(self, event: Dict[str, Any]) -> None:
        """Handle an external event that may trigger recovery."""
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the orchestrator."""
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get recovery metrics."""
```

### Coordinator Interface

All coordinators implement the `Coordinator` protocol:

```python
class Coordinator(Protocol):
    async def startup(self) -> None:
        """Initialize coordination and attempt leader election."""
    
    async def shutdown(self) -> None:
        """Gracefully shutdown coordination."""
    
    async def elect_leader(self) -> bool:
        """Attempt to become cluster leader."""
    
    async def assign_work(self, work_item: Dict[str, Any]) -> str:
        """Assign work to a cluster node."""
    
    async def heartbeat(self) -> None:
        """Send heartbeat to indicate this instance is alive."""
    
    async def get_nodes(self) -> List[NodeInfo]:
        """Get list of all active nodes in cluster."""
    
    async def get_consensus(self) -> ConsensusDecision:
        """Get consensus decision from cluster quorum."""
```

## Dependency Injection

### RecoveryOrchestrator

```python
orchestrator = RecoveryOrchestrator(
    health_monitor=health_monitor,          # HealthMonitor instance
    fallback_manager=fallback_manager,      # FallbackManager instance
    metrics_collector=metrics_collector,    # Optional metrics collector
    storage=storage,                        # Optional persistent storage
    config_path="config/recovery.yaml",
)
```

### EnhancedRecoveryOrchestrator

```python
orchestrator = EnhancedRecoveryOrchestrator(
    health_monitor=health_monitor,
    fallback_manager=fallback_manager,
    phase_aware_handler=phase_aware_handler,  # PhaseAwareAnomalyHandler
    state_machine=state_machine,              # StateMachine for phase awareness
    metrics_collector=metrics_collector,
    storage=storage,
    config_path="config/recovery_policies.yaml",
)
```

### DistributedResilienceCoordinator

```python
coordinator = DistributedResilienceCoordinator(
    redis_client=redis_client,              # RedisClient instance
    health_monitor=health_monitor,
    recovery_orchestrator=orchestrator,      # Optional recovery orchestrator
    fallback_manager=fallback_manager,       # Optional fallback manager
    instance_id="astra-instance-1",         # Unique instance ID
    quorum_threshold=0.5,                   # Majority quorum (>50%)
)
```

### LocalCoordinator

For local development and testing without Redis:

```python
coordinator = LocalCoordinator(
    health_monitor=health_monitor,
    instance_id="local-instance",
    quorum_threshold=0.5,
)
```

## Migration Guide

### Import Migration

**Old imports (deprecated):**
```python
from backend.recovery_orchestrator import RecoveryOrchestrator
from backend.recovery_orchestrator_enhanced import EnhancedRecoveryOrchestrator
from backend.distributed_coordinator import DistributedResilienceCoordinator
```

**New imports:**
```python
from backend.orchestration import (
    RecoveryOrchestrator,
    EnhancedRecoveryOrchestrator,
    DistributedResilienceCoordinator,
    LocalCoordinator,
)

# Or import specific components:
from backend.orchestration.recovery_orchestrator import RecoveryOrchestrator
from backend.orchestration.coordinator import LocalCoordinator, ConsensusDecision
```

### Compatibility Shims

Compatibility shims are provided at the original file locations to ease migration:

- `backend/recovery_orchestrator.py` → shim to `backend/orchestration/recovery_orchestrator.py`
- `backend/recovery_orchestrator_enhanced.py` → shim to `backend/orchestration/recovery_orchestrator_enhanced.py`
- `backend/distributed_coordinator.py` → shim to `backend/orchestration/distributed_coordinator.py`

These shims:
- Re-export all classes from the new locations
- Issue `DeprecationWarning` when imported
- Will be removed in a future release after migration is complete

### Updating Bootstrap Code

**Before:**
```python
# Old implicit composition
orchestrator = RecoveryOrchestrator(health_monitor, fallback_manager)
coordinator = DistributedResilienceCoordinator(redis, health_monitor)
```

**After:**
```python
# New explicit dependency injection
orchestrator = RecoveryOrchestrator(
    health_monitor=health_monitor,
    fallback_manager=fallback_manager,
    metrics_collector=metrics_collector,
    storage=storage_backend,
)

coordinator = DistributedResilienceCoordinator(
    redis_client=redis_client,
    health_monitor=health_monitor,
    recovery_orchestrator=orchestrator,
    fallback_manager=fallback_manager,
    instance_id=get_instance_id(),
)
```

## Testing

### Running Tests

```bash
# Run all orchestration tests
pytest tests/backend/orchestration/

# Run specific test suites
pytest tests/backend/orchestration/test_orchestrator.py
pytest tests/backend/orchestration/test_coordinator.py
pytest tests/backend/orchestration/test_integration.py

# Run with coverage
pytest tests/backend/orchestration/ --cov=backend.orchestration --cov-report=html
```

### Test Coverage

- **Unit tests**: Test decision logic, metrics, cooldowns, and state transitions
- **Coordinator tests**: Test voting, consensus, leader election, and failover
- **Integration tests**: Test full lifecycle with real dependencies and multi-instance scenarios

## Key Features

### 1. Separation of Concerns

- **Decision logic**: Pure functions that evaluate conditions and determine actions
- **Side effects**: Isolated to injected dependencies (Redis, storage, metrics)
- **Testability**: Easy to test decision logic without external dependencies

### 2. Local Development Support

The `LocalCoordinator` provides a lightweight, in-process coordinator for:
- Local development without Redis
- Unit testing
- Single-instance deployments

### 3. Explicit Dependencies

All dependencies are injected via constructor, making:
- Dependencies visible and explicit
- Component replacement easy
- Testing straightforward with mocks

### 4. Interface-Based Design

- Components depend on interfaces, not concrete implementations
- Easy to add new orchestrator or coordinator types
- Enables composition and plugin architectures

## Implementation Notes

### Orchestrator Decision Flow

1. **Evaluate conditions**: Check health metrics against thresholds
2. **Check cooldowns**: Ensure sufficient time has passed since last action
3. **Execute actions**: Call injected handlers (not directly modifying state)
4. **Update metrics**: Track action results
5. **Record history**: Maintain action history for inspection

### Coordinator Consensus Flow

1. **Register votes**: Each instance publishes its local state
2. **Collect votes**: Leader gathers votes from all instances
3. **Apply majority voting**: Determine consensus based on >50% agreement
4. **Check quorum**: Ensure sufficient instances voted
5. **Apply decision**: Update local state based on consensus

### Failover Handling

- **Leader election**: First instance to acquire lock becomes leader
- **Leadership renewal**: Leader periodically renews its lock
- **Automatic failover**: Followers attempt election when leader lock expires
- **Split-brain detection**: Consensus requires >50% agreement

## Configuration

Orchestrator and coordinator behavior is controlled by YAML configuration files:

- `config/recovery.yaml` - Basic recovery orchestrator settings
- `config/recovery_policies.yaml` - Enhanced orchestrator policies
- Redis connection settings for distributed coordinator

See existing configuration files for detailed options.

## Future Enhancements

Potential improvements for future PRs:

1. **Bootstrap factory**: Create a DI factory for composing orchestrators/coordinators
2. **Persistence layer**: Add persistent storage for action history and metrics
3. **Metrics integration**: Enhance Prometheus metrics collection
4. **Circuit breaker integration**: Direct integration with circuit breaker component
5. **Admin API**: REST endpoints for orchestrator/coordinator management
6. **Configuration hot-reload**: Dynamic configuration updates without restart

## Cleanup Tasks

After migration is complete:

1. Remove compatibility shims from `backend/` directory
2. Update all imports to use new package
3. Update documentation and examples
4. Remove deprecation warnings
5. Archive old test files if any exist

## Related Issues

- Issue #444: Recovery Orchestrators & Distributed Coordinator Refactor (this implementation)
- Issue #17: Automated Recovery Orchestrator (original implementation)
- Issue #16: Health Monitor and Fallback Manager (dependencies)
- Issue #14: Circuit Breaker Pattern (related component)
- Issue #15: Retry Logic (related component)

## Review Checklist

- [x] Interfaces and base classes are minimal and well-documented
- [x] Orchestrators use injected dependencies for all side-effects
- [x] Tests cover both unit and coordinator failover scenarios
- [x] Compatibility shims included and documented for cleanup in a follow-up PR
- [x] Decision logic separated from I/O operations
- [x] LocalCoordinator provided for local dev/testing
- [x] Integration tests validate multi-instance coordination
- [x] All public methods have clear docstrings
- [x] Type hints used throughout
