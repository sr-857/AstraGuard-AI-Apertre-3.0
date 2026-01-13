# Developer Notes — Storage Abstraction

This note explains how to instantiate and pass `Storage` instances to higher-level components.

## Creating storage

Production (Redis):

```py
from backend.storage import RedisAdapter

config = {
    'redis_url': 'redis://localhost:6379',
    'timeout': 5.0,
    'max_retries': 3,
    'retry_delay': 0.5
}
storage = RedisAdapter.from_config(config)
await storage.connect()
```

Local / tests (in-memory):

```py
from backend.storage import MemoryStorage

storage = MemoryStorage()
await storage.connect()
```

## Passing `Storage` into components (DI)

Prefer constructor injection instead of importing Redis directly inside modules. Example:

```py
from backend.storage import Storage

class MyService:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def get_user(self, user_id: str):
        return await self.storage.get(f'user:{user_id}')

    async def save_user(self, user_id: str, data: dict):
        return await self.storage.set(f'user:{user_id}', data, expire=3600)
```

When wiring up the app, create one storage instance and pass it to services:

```py
storage = RedisAdapter.from_config(app_config)
await storage.connect()
service = MyService(storage)
```

## Tests

Use `MemoryStorage` in unit tests to avoid external dependencies:

```py
import pytest
from backend.storage import MemoryStorage

@pytest.fixture
async def storage():
    s = MemoryStorage()
    await s.connect()
    yield s
    await s.close()
```

## Notes

- Use key prefixes (e.g., `user:`, `cache:`, `resilience:`) for namespacing and easier scanning/cleanup.
- Use `expire` for temporary values to avoid stale data accumulation.
- For legacy code, `backend.redis_client` still exports the compatibility shim; prefer `backend.storage` for new code.


## Fallback Manager Usage

The `FallbackManager` orchestrates progressive fallback modes (PRIMARY → HEURISTIC → SAFE) based on system health. It now uses dependency injection with the `Storage` interface for better testability.

### Quick Start

```py
from backend.fallback import FallbackManager, FallbackMode
from backend.storage import MemoryStorage  # or RedisAdapter for production

# Create storage instance
storage = MemoryStorage()

# Initialize manager with DI
manager = FallbackManager(
    storage=storage,
    circuit_breaker=my_circuit_breaker,
    anomaly_detector=my_ml_detector,
    heuristic_detector=my_rule_based_detector,
)

# Evaluate health and cascade
health_state = health_monitor.get_comprehensive_state()
mode = await manager.cascade(health_state)

# Check current mode
if manager.is_degraded():
    logger.warning(f"System in degraded mode: {manager.get_mode_string()}")
```

### Mode Transition Rules

- **PRIMARY**: Full ML-based anomaly detection (default)
- **HEURISTIC**: Rule-based fallback (when circuit open OR high retry failures)
- **SAFE**: Conservative mode, no actions (when 2+ component failures)

### Registering Mode Callbacks

```py
async def on_safe_mode():
    logger.critical("Entered SAFE mode - notifying ops team")
    await send_alert("system_degraded", severity="critical")

manager.register_mode_callback(FallbackMode.SAFE, on_safe_mode)
```

### Manual Mode Control

```py
# Distributed coordinator can override mode
await manager.set_mode("heuristic")

# Check mode status
assert manager.get_current_mode() == FallbackMode.HEURISTIC
assert manager.is_degraded() == True
```

### Using with Storage Interface

The manager persists transition history to storage for observability:

```py
# Transitions are stored with keys like:
# fallback:transition:<timestamp>

# Query recent transitions
transitions = manager.get_transitions_log(limit=10)
for t in transitions:
    print(f"{t['timestamp']}: {t['from']} → {t['to']} (reason: {t['reason']})")

# Get metrics
metrics = await manager.get_metrics()
# {
#   "current_mode": "heuristic",
#   "is_degraded": True,
#   "total_transitions": 5,
#   "recent_transitions": [...]
# }
```

### Testing with In-Memory Storage

```py
import pytest
from backend.fallback import FallbackManager
from backend.storage import MemoryStorage

@pytest.fixture
def manager():
    storage = MemoryStorage()
    return FallbackManager(storage=storage)

@pytest.mark.asyncio
async def test_cascade_to_safe_mode(manager):
    health_state = {
        "circuit_breaker": {"state": "CLOSED"},
        "retry": {"failures_1h": 0},
        "system": {"failed_components": 2},
    }
    
    mode = await manager.cascade(health_state)
    assert mode == FallbackMode.SAFE
```

### Migration from Legacy Code

Old imports still work via compatibility shim:

```py
# OLD (deprecated)
from backend.fallback_manager import FallbackManager

manager = FallbackManager(
    circuit_breaker=cb,
    anomaly_detector=detector,
)

# NEW (recommended)
from backend.fallback import FallbackManager
from backend.storage import MemoryStorage

storage = MemoryStorage()
manager = FallbackManager(
    storage=storage,
    circuit_breaker=cb,
    anomaly_detector=detector,
)
```

The compatibility shim creates an in-memory storage internally, but new code should use explicit DI for better control and testability.

### Condition Parser

The `ConditionParser` provides safe, pure condition evaluation without `eval()`:

```py
from backend.fallback import parse_condition, evaluate

# Parse condition
condition = parse_condition("severity >= 0.8 and recurrence_count >= 2")

# Evaluate with context
context = {"severity": 0.9, "recurrence_count": 3}
result = evaluate(condition, context)  # True

# Allowed variables: severity, recurrence_count, confidence, step, duration
# Allowed operators: >=, <=, >, <, ==, !=
# Logical operators: and, or
# Supports parentheses for grouping
```

Security features:
- No `eval()` or `exec()` usage
- Strict variable whitelist
- Token complexity limit (50 tokens max)
- No function calls or attribute access
- No imports or side effects


## Health Monitor & Monitoring Integrations

The `backend.health` package provides centralized health monitoring with pluggable abstractions for checks and metric emission.

### Quick Start

```py
from backend.health import HealthMonitor, NoOpMetricsSink, PrometheusMetricsSink
from backend.health.checks import DiskSpaceCheck, RedisHealthCheck

# Create monitor with Prometheus sink
from prometheus_client import CollectorRegistry
registry = CollectorRegistry()
sink = PrometheusMetricsSink(registry=registry)

monitor = HealthMonitor(
    circuit_breaker=my_circuit_breaker,
    retry_tracker=my_retry_tracker,
    metrics_sink=sink,
)

# Register health checks
monitor.register_check(DiskSpaceCheck(path="/data"))
monitor.register_check(RedisHealthCheck(redis_client=my_redis))

# Get comprehensive health state
state = await monitor.get_comprehensive_state()
```

### Adding Custom Health Checks

Implement the `HealthCheck` protocol or extend `BaseHealthCheck`:

```py
from backend.health.checks import BaseHealthCheck, HealthCheckResult, HealthCheckStatus

class MyServiceCheck(BaseHealthCheck):
    def __init__(self, service_url: str):
        super().__init__(name="my_service", timeout_seconds=5.0)
        self.service_url = service_url
    
    async def _perform_check(self) -> HealthCheckResult:
        # Implement your check logic
        try:
            response = await check_service(self.service_url)
            if response.ok:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.HEALTHY,
                    message="Service responding",
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthCheckStatus.DEGRADED,
                    message=f"Service returned {response.status}",
                )
        except Exception as e:
            return HealthCheckResult(
                name=self.name,
                status=HealthCheckStatus.UNHEALTHY,
                message=str(e),
            )

# Register the check
monitor.register_check(MyServiceCheck("http://my-service/health"))
```

### Adding Custom Metric Sinks

Implement the `MetricsSink` interface:

```py
from backend.health.sinks import MetricsSink
from typing import Optional, Dict
from datetime import datetime

class DatadogMetricsSink(MetricsSink):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def emit(self, name: str, value: float, 
             tags: Optional[Dict[str, str]] = None,
             timestamp: Optional[datetime] = None) -> None:
        # Send gauge to Datadog
        datadog.api.Metric.send(metric=name, points=[(timestamp or time.time(), value)], tags=tags)
    
    def emit_counter(self, name: str, value: float = 1.0,
                     tags: Optional[Dict[str, str]] = None) -> None:
        # Send counter increment
        datadog.api.Metric.send(metric=name, points=[(time.time(), value)], type="count", tags=tags)
    
    def emit_histogram(self, name: str, value: float,
                       tags: Optional[Dict[str, str]] = None) -> None:
        # Send histogram observation
        datadog.api.Metric.send(metric=name, points=[(time.time(), value)], type="histogram", tags=tags)

# Use custom sink
sink = DatadogMetricsSink(api_key="my-api-key")
monitor = HealthMonitor(metrics_sink=sink)
```

### Built-in Health Checks

| Check | Description |
|-------|-------------|
| `RedisHealthCheck` | Pings Redis connection |
| `DownstreamServiceCheck` | HTTP ping to downstream services |
| `DiskSpaceCheck` | Checks available disk space |
| `ComponentHealthCheck` | Wraps existing component health |

### Built-in Metric Sinks

| Sink | Description |
|------|-------------|
| `NoOpMetricsSink` | For tests, does nothing |
| `LoggingMetricsSink` | Logs metrics to standard logger |
| `PrometheusMetricsSink` | Uses Prometheus client library |

### Migration from Legacy Code

Old imports still work via compatibility shim:

```py
# OLD (deprecated - emits warning)
from backend.health_monitor import HealthMonitor
from backend.monitoring_integrations import DatadogAdapter

# NEW (recommended)
from backend.health import HealthMonitor
from backend.health.integrations import DatadogAdapter
```


## Profiling & Benchmarks

The `tools/benchmarks/` directory provides scripts for profiling and benchmarking backend hot paths.

### Quick Start

```bash
# Run microbenchmarks
python tools/benchmarks/run_microbench.py

# Profile a module
python tools/benchmarks/run_profile.py --target backend.fallback.manager

# Run E2E load test
python tools/benchmarks/run_e2e_bench.py --url http://localhost:8000
```

### Available Tools

| Script | Purpose |
|--------|---------|
| `run_profile.py` | CPU/memory profiling with pyinstrument, cProfile |
| `run_microbench.py` | pytest-benchmark runner with baseline comparison |
| `run_e2e_bench.py` | HTTP load testing with latency percentiles |

### CI Integration

The `bench-perf.yml` workflow runs benchmarks on every PR and compares against baselines in `benchmarks/baselines/initial.json`.

📖 **Full documentation:** [docs/PROFILING_BENCHMARKS.md](docs/PROFILING_BENCHMARKS.md)


## Types & Linting

The project uses automated code quality tools to maintain consistent style and catch errors early.

### Quick Start

```bash
# Install development dependencies
pip install -r config/requirements-dev.txt

# Install pre-commit hooks (run once)
pip install pre-commit
pre-commit install

# Run all checks locally
pre-commit run --all-files
```

### Tools Overview

| Tool | Purpose | Command |
|------|---------|---------|
| **Ruff** | Fast Python linter | `ruff check backend api` |
| **Black** | Code formatter | `black --check backend api` |
| **isort** | Import sorting | `isort --check-only backend api` |
| **MyPy** | Type checking | `mypy backend api --config-file mypy.ini` |

### Running Checks Manually

```bash
# Lint with auto-fix
ruff check --fix backend api anomaly config core

# Format code
black backend api anomaly config core
isort backend api anomaly config core

# Type check
mypy backend api --config-file mypy.ini
```

### Pre-commit Hooks

Pre-commit runs automatically on `git commit`. To skip temporarily:

```bash
git commit --no-verify -m "WIP: temporary commit"
```

### CI Integration

Two GitHub Actions workflows run on every PR:

- **lint.yml**: Ruff, Black, isort checks
- **type-check.yml**: MyPy and Pyright (non-blocking)

### VS Code Setup

Add these extensions for the best experience:

- `ms-python.python` - Python support
- `ms-python.vscode-pylance` - Pyright language server
- `ms-python.mypy-type-checker` - MyPy integration
- `charliermarsh.ruff` - Ruff linting
- `ms-python.black-formatter` - Black formatting
- `ms-python.isort` - Import sorting

Recommended `settings.json` additions:

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "python.linting.enabled": true,
  "ruff.enable": true
}
```

### Adding Type Hints

When adding new code, include type annotations for public functions:

```python
from typing import Optional, Dict, Any

async def process_data(
    data: Dict[str, Any],
    timeout: float = 5.0
) -> Optional[str]:
    """Process incoming data with timeout."""
    ...
```

For complex types, use `TypedDict` or `Protocol`:

```python
from typing import TypedDict, Protocol

class HealthState(TypedDict):
    status: str
    uptime_seconds: float
    components: Dict[str, bool]

class Storage(Protocol):
    async def get(self, key: str) -> Optional[Any]: ...
    async def set(self, key: str, value: Any) -> bool: ...
```

