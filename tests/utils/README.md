# Mock Server and Testing Utilities

Reusable mock servers, fixtures, and data generators for testing AstraGuard components.

## Overview

This package provides:

- **Mock Servers**: FastAPI and HTTP servers for testing
- **Pytest Fixtures**: Reusable test fixtures for common components
- **Data Generators**: Realistic test data generation
- **Request Recording**: Track and validate HTTP requests

## Quick Start

```python
# Import utilities
from tests.utils import MockAPIServer, quick_telemetry, mock_telemetry_data

# Use in tests
def test_api_endpoint(mock_api_client):
    """Use pytest fixture for quick testing."""
    response = mock_api_client.get("/health")
    assert response.status_code == 200

# Generate test data
data = quick_telemetry(count=10)
```

## Mock Servers

### MockAPIServer

FastAPI-based mock server for testing API interactions.

```python
from tests.utils import MockAPIServer
from fastapi import FastAPI

# Create mock API
app = FastAPI()

@app.get("/status")
def status():
    return {"status": "ok"}

# Use in tests
with MockAPIServer(app) as server:
    response = server.get("/status")
    assert response.json()["status"] == "ok"
```

**Features:**
- Automatic client creation with `TestClient`
- Context manager support
- Dependency override support
- Route mocking capabilities

**Advanced Usage:**

```python
# Override dependencies
def mock_auth():
    return {"user": "test_user"}

with MockAPIServer(app, overrides={original_auth: mock_auth}) as server:
    response = server.get("/protected")
    assert response.status_code == 200

# Mock specific routes
server = MockAPIServer(app)
server.mock_route("/api/data", {"data": "mocked"}, status_code=200)
response = server.get("/api/data")
```

### MockHTTPServer

Simple HTTP server for mocking external services.

```python
from tests.utils import MockHTTPServer

# Define mock responses
def handler(request):
    if request.path == "/data":
        return 200, {"Content-Type": "application/json"}, '{"result": "ok"}'
    return 404, {}, "Not Found"

# Start server
server = MockHTTPServer(handler, port=8888)
server.start()

# Make requests
import requests
response = requests.get("http://localhost:8888/data")

# Clean up
server.stop()
```

**Context Manager:**

```python
with MockHTTPServer(handler, port=8888) as server:
    response = requests.get(f"http://localhost:{server.port}/data")
    assert response.status_code == 200
```

### RequestRecorder

Track and validate HTTP requests.

```python
from tests.utils.mock_server import RequestRecorder

# Record requests
recorder = RequestRecorder()

with MockHTTPServer(recorder.handler, port=8888) as server:
    requests.get("http://localhost:8888/api/test")
    requests.post("http://localhost:8888/data", json={"key": "value"})

# Validate
assert recorder.count() == 2
assert recorder.received_path("/api/test")
assert recorder.received_method("POST")

req = recorder.last_request()
assert req["method"] == "POST"
```

## Pytest Fixtures

Import fixtures in your conftest.py or use directly:

```python
# In tests/conftest.py
from tests.utils.fixtures import *
```

### Available Fixtures

#### mock_api_client
FastAPI TestClient for testing API endpoints.

```python
def test_health(mock_api_client):
    response = mock_api_client.get("/health")
    assert response.status_code == 200
```

#### mock_telemetry_data
Pre-generated telemetry data for testing.

```python
def test_telemetry_processing(mock_telemetry_data):
    assert len(mock_telemetry_data) == 10
    assert all("voltage" in d for d in mock_telemetry_data)
```

#### mock_auth_context
Mock authentication context with test user.

```python
def test_authenticated_endpoint(mock_auth_context):
    assert mock_auth_context["user_id"] == "test-user-12345"
    assert mock_auth_context["role"] == "ADMIN"
```

#### mock_health_monitor
Mock component health monitor.

```python
async def test_health_check(mock_health_monitor):
    status = await mock_health_monitor.check_health()
    assert status["status"] == "healthy"
```

#### mock_redis_client
Mock Redis client with in-memory operations.

```python
async def test_cache(mock_redis_client):
    await mock_redis_client.set("key", "value")
    result = await mock_redis_client.get("key")
    assert result == "value"
```

#### mock_circuit_breaker
Mock circuit breaker for testing failure scenarios.

```python
def test_circuit_breaker(mock_circuit_breaker):
    assert mock_circuit_breaker.state == "closed"
    mock_circuit_breaker.record_failure()
```

#### mock_state_machine
Mock state machine for testing state transitions.

```python
def test_state_machine(mock_state_machine):
    assert mock_state_machine.current_state == "idle"
    mock_state_machine.transition("active")
```

#### mock_anomaly_detector
Mock anomaly detector with configurable responses.

```python
async def test_anomaly_detection(mock_anomaly_detector):
    result = await mock_anomaly_detector.detect({"voltage": 5.0})
    assert result["is_anomaly"] is True
```

### Utility Functions

#### create_mock_api_key()
Generate mock API key for testing.

```python
from tests.utils.fixtures import create_mock_api_key

key = create_mock_api_key(permissions={"read", "write"})
assert key["key"].startswith("test_key_")
```

#### create_mock_user()
Generate mock user for testing.

```python
from tests.utils.fixtures import create_mock_user

user = create_mock_user(role="OPERATOR")
assert user["role"] == "OPERATOR"
```

## Data Generators

### TelemetryGenerator

Generate realistic telemetry data.

```python
from tests.utils import TelemetryGenerator

gen = TelemetryGenerator()

# Single reading
data = gen.generate()
# Output: {"voltage": 8.2, "temperature": 35.4, ...}

# Batch generation
batch = gen.generate_batch(count=100, anomalous_ratio=0.1)
# 100 readings, 10% anomalous

# Time series with drift
series = gen.generate_time_series(
    duration_seconds=60,
    sample_rate=1.0,
    drift=True,
    noise=0.2
)
```

**Custom Ranges:**

```python
gen = TelemetryGenerator(
    voltage_range=(6.0, 10.0),
    temp_range=(15.0, 60.0)
)
```

### UserGenerator

Generate user data for testing.

```python
from tests.utils import UserGenerator

gen = UserGenerator()

# Single user
user = gen.generate(role="ADMIN")
# Output: {"id": "user-12345", "username": "user_1234", ...}

# Batch
users = gen.generate_batch(count=20)
```

### APIKeyGenerator

Generate API keys for testing.

```python
from tests.utils import APIKeyGenerator

gen = APIKeyGenerator()

# Single key
key = gen.generate(
    name="test_key",
    permissions={"read", "write"},
    expires_in_days=30
)

# Batch
keys = gen.generate_batch(count=5)
```

### AnomalyGenerator

Generate anomalous patterns for testing.

```python
from tests.utils import AnomalyGenerator

gen = AnomalyGenerator()

# Spike pattern
spike_data = gen.generate_spike_pattern(duration=20, spike_at=10)

# Drift pattern
drift_data = gen.generate_drift_pattern(duration=30, drift_start=10)

# Oscillation pattern
oscillation = gen.generate_oscillation_pattern(duration=30, frequency=0.5)
```

### Quick Functions

For rapid test data generation:

```python
from tests.utils import quick_telemetry, quick_user, quick_api_key

# Quick telemetry
data = quick_telemetry(count=10, anomalous=False)

# Quick user
user = quick_user(role="OPERATOR")

# Quick API key
key = quick_api_key(permissions={"read"})
```

## Example Tests

### Testing API Endpoints

```python
import pytest
from tests.utils import MockAPIServer, quick_telemetry

def test_telemetry_ingestion(mock_api_client):
    """Test telemetry endpoint with mock client."""
    data = quick_telemetry(count=1)
    
    response = mock_api_client.post("/api/telemetry", json=data)
    
    assert response.status_code == 201
    assert "id" in response.json()
```

### Testing External Service Integration

```python
from tests.utils import MockHTTPServer

def mock_external_service(request):
    """Mock external API responses."""
    if request.path == "/api/data":
        return 200, {"Content-Type": "application/json"}, '{"status": "ok"}'
    return 404, {}, "Not Found"

def test_external_integration():
    """Test integration with external service."""
    with MockHTTPServer(mock_external_service, port=9000) as server:
        # Your code that calls the external service
        result = fetch_from_external("http://localhost:9000/api/data")
        assert result["status"] == "ok"
```

### Testing with Fixtures

```python
import pytest

def test_authentication(mock_auth_context, mock_api_client):
    """Test authenticated endpoint."""
    response = mock_api_client.get(
        "/api/protected",
        headers={"Authorization": f"Bearer {mock_auth_context['token']}"}
    )
    assert response.status_code == 200

async def test_anomaly_detection(mock_anomaly_detector, mock_telemetry_data):
    """Test anomaly detection with mock data."""
    for reading in mock_telemetry_data:
        result = await mock_anomaly_detector.detect(reading)
        assert "is_anomaly" in result
```

### Testing Circuit Breaker Behavior

```python
def test_circuit_breaker_opens(mock_circuit_breaker):
    """Test circuit breaker opens after failures."""
    # Record failures
    for _ in range(5):
        mock_circuit_breaker.record_failure()
    
    assert mock_circuit_breaker.state == "open"
    
    # Should reject calls
    with pytest.raises(Exception):
        mock_circuit_breaker.call(lambda: "test")
```

## Best Practices

### 1. Use Fixtures for Common Setup

```python
@pytest.fixture
def telemetry_service(mock_redis_client, mock_health_monitor):
    """Composed fixture for telemetry service."""
    return TelemetryService(
        cache=mock_redis_client,
        health=mock_health_monitor
    )
```

### 2. Generate Realistic Data

```python
# Bad: Hardcoded data
data = {"voltage": 8.0, "temperature": 30.0}

# Good: Generated data
from tests.utils import quick_telemetry
data = quick_telemetry(count=1)
```

### 3. Record and Validate Requests

```python
from tests.utils.mock_server import RequestRecorder

recorder = RequestRecorder()
with MockHTTPServer(recorder.handler) as server:
    # Test code...
    
    # Validate requests
    assert recorder.received_path("/api/endpoint")
    assert recorder.last_request()["method"] == "POST"
```

### 4. Clean Up Resources

```python
# Use context managers
with MockHTTPServer(handler) as server:
    # Test code...
    pass
# Server automatically stopped

# Or explicit cleanup
server = MockHTTPServer(handler)
try:
    server.start()
    # Test code...
finally:
    server.stop()
```

## Troubleshooting

### Port Already in Use

If you get "Address already in use" errors:

```python
# Use port 0 for auto-assignment
with MockHTTPServer(handler, port=0) as server:
    actual_port = server.port
    # Use actual_port in requests
```

### Async Fixtures Not Working

Ensure pytest-asyncio is installed:

```bash
pip install pytest-asyncio
```

Mark tests as async:

```python
@pytest.mark.asyncio
async def test_async_feature(mock_redis_client):
    result = await mock_redis_client.get("key")
```

### Fixture Not Found

Import fixtures in conftest.py:

```python
# tests/conftest.py
from tests.utils.fixtures import *
```

## Contributing

When adding new utilities:

1. Add to appropriate module (mock_server.py, fixtures.py, generators.py)
2. Include docstrings with examples
3. Update this README
4. Add example tests

## Related Documentation

- [AstraGuard Testing Guide](../../docs/guides/testing.md)
- [Benchmarking Suite](../benchmarks/README_BENCHMARK_SUITE.md)
- [E2E Testing](../e2e/README.md)
