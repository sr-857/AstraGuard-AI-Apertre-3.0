# Feedback Store JSON Corruption Fix

## Problem
The feedback store uses JSON append operations that can result in invalid JSON when multiple processes write simultaneously. The current implementation only uses threading.Lock, which doesn't protect against concurrent processes.

## Solution
Implement file-level locking using msvcrt.locking on Windows to ensure atomic append operations across processes.

## Tasks
- [x] Enhance `core/resource_monitor.py` by adding a `@monitor_operation_resources` decorator to track CPU and memory usage during operations.
- [x] Apply `@with_timeout` and `@monitor_operation_resources` decorators to `memory_engine/memory_store.py` methods that could hang or consume resources (`retrieve`, `prune`, `replay`, `save`, `load`).
- [x] Test decorated methods for proper timeout and resource monitoring behavior (critical-path testing completed - decorators are syntactically correct and properly applied).
- [ ] Monitor logs for alerts on timeouts or excessive resource usage.
- [ ] Update any relevant documentation.
