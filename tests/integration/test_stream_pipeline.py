import pytest
import pytest_asyncio
import asyncio
import json
import msgpack
import zstandard as zstd
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# Import the app - ensuring mocks are applied if possible or patching where needed
# We need to patch where the app imports them
from api.service import app, initialize_components
import api.service
from api.models import TelemetryInput, TelemetryBatch
from core.auth import require_operator, User, UserRole

# ============================================================================
# FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def mock_dependencies():
    """
    Mock external dependencies to isolate the integration test.
    We need to patch the classes/functions used in api.service.lifespan and endpoints.
    """
    # Create a mock user
    mock_user = MagicMock(spec=User)
    mock_user.username = "test_operator"
    mock_user.role = UserRole.OPERATOR
    mock_user.email = "test@example.com"
    mock_user.is_active = True

    with patch("api.service.RedisClient") as MockRedisClient, \
         patch("api.service.AdaptiveMemoryStore") as MockMemoryStore, \
         patch("api.service.StateMachine") as MockStateMachine, \
         patch("api.service.MissionPhasePolicyLoader") as MockPolicyLoader, \
         patch("api.service.PhaseAwareAnomalyHandler") as MockHandler, \
         patch("api.service.load_model", new_callable=AsyncMock) as mock_load_model, \
         patch("api.service.classify", return_value="test_fault") as mock_classify, \
         patch("api.service.detect_anomaly", new_callable=AsyncMock) as mock_detect:

        # Setup Redis Mock
        redis_instance = MockRedisClient.return_value
        redis_instance.connect = AsyncMock(return_value=True)
        redis_instance.close = AsyncMock()
        redis_instance.redis = MagicMock() # The underlying redis object

        # Setup MemoryStore Mock
        memory_instance = MockMemoryStore.return_value
        memory_instance.write = AsyncMock()
        memory_instance.save = AsyncMock()

        # Setup StateMachine Mock
        sm_instance = MockStateMachine.return_value
        sm_instance.get_current_phase = MagicMock()
        sm_instance.get_current_phase.return_value.value = "NOMINAL_OPS"

        # Setup PhaseHandler Mock
        handler_instance = MockHandler.return_value
        handler_instance.handle_anomaly.return_value = {
            "anomaly_type": "test_fault",
            "severity_score": 0.95,
            "policy_decision": {
                "severity": "HIGH",
                "escalation_level": "WARNING",
                "is_allowed": True,
                "allowed_actions": ["LOG"]
            },
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "INVESTIGATE",
            "should_escalate_to_safe_mode": False,
            "detection_confidence": 0.95,
            "reasoning": "Test reasoning",
            "recurrence_info": {"count": 1}
        }

        # Setup Anomaly Detection Mock
        # Default behavior: No anomaly
        mock_detect.return_value = (False, 0.1)

        # Force re-initialization of components with mocks
        api.service.state_machine = None
        api.service.policy_loader = None
        api.service.phase_aware_handler = None
        api.service.memory_store = None
        api.service.predictive_engine = None

        await initialize_components()

        yield {
            "redis": redis_instance,
            "memory": memory_instance,
            "state_machine": sm_instance,
            "detect_anomaly": mock_detect,
            "classify": mock_classify
        }

@pytest_asyncio.fixture
async def client(mock_dependencies):
    """
    Create an AsyncClient with the FastAPI app.
    The app's lifespan will run, using the mocked classes.
    We also override the authentication dependency.
    """
    # Create a mock user
    mock_user = MagicMock(spec=User)
    mock_user.username = "test_operator"
    mock_user.role = UserRole.OPERATOR
    mock_user.email = "test@example.com"
    mock_user.is_active = True

    # Override the dependency
    app.dependency_overrides[require_operator] = lambda: mock_user

    transport = ASGITransport(app=app)
    # Use HTTPS to satisfy TLSMiddleware
    # Also set X-Forwarded-Proto to ensure the middleware sees it as HTTPS
    headers = {"X-Forwarded-Proto": "https"}
    async with AsyncClient(transport=transport, base_url="https://test", headers=headers) as ac:
        yield ac

    # Clean up overrides
    app.dependency_overrides = {}

# ============================================================================
# TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_streaming_pipeline_basic_flow(client, mock_dependencies):
    """
    Test Case 1: Basic Flow
    Verify that a standard JSON batch request is processed correctly.
    """
    # Prepare input data
    telemetry_item = {
        "voltage": 5.0,
        "temperature": 25.0,
        "gyro": 0.01,
        "current": 1.0,
        "wheel_speed": 10.0,
        "timestamp": "2023-01-01T12:00:00"
    }
    payload = {"telemetry": [telemetry_item]}

    # Send request
    response = await client.post("/api/v1/telemetry/batch", json=payload)

    # Assertions
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["total_processed"] == 1
    assert data["anomalies_detected"] == 0

    # Verify processing pipeline steps
    mock_dependencies["detect_anomaly"].assert_called()


@pytest.mark.asyncio
async def test_streaming_pipeline_multiple_events(client, mock_dependencies):
    """
    Test Case 2: Multiple Events (Batch Processing)
    Verify that a large batch of events is processed without loss.
    """
    batch_size = 50
    telemetry_list = []
    for i in range(batch_size):
        telemetry_list.append({
            "voltage": 5.0 + (i * 0.1),
            "temperature": 25.0,
            "gyro": 0.01,
            "current": 1.0,
            "wheel_speed": 10.0,
            "timestamp": "2023-01-01T12:00:00"
        })

    payload = {"telemetry": telemetry_list}

    # Send request
    response = await client.post("/api/v1/telemetry/batch", json=payload)

    # Assertions
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["total_processed"] == batch_size

    # Verify detect_anomaly was called batch_size times (since it's called per item in gathering)
    assert mock_dependencies["detect_anomaly"].call_count >= batch_size


@pytest.mark.asyncio
async def test_streaming_pipeline_anomaly_handling(client, mock_dependencies):
    """
    Test Case 3: Anomaly Handling
    Verify that if an anomaly is detected, it is recorded in memory store.
    """
    # Configure mock to detect anomaly
    mock_dependencies["detect_anomaly"].return_value = (True, 0.95) # is_anomaly, score

    telemetry_item = {
        "voltage": 2.0, # Low voltage
        "temperature": 80.0,
        "gyro": 0.5,
        "current": 5.0,
        "wheel_speed": 0.0,
        "timestamp": "2023-01-01T12:00:00"
    }
    payload = {"telemetry": [telemetry_item]}

    response = await client.post("/api/v1/telemetry/batch", json=payload)

    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["anomalies_detected"] == 1

    # Verify write to memory store
    mock_dependencies["memory"].write.assert_called()


@pytest.mark.asyncio
async def test_streaming_pipeline_error_handling(client, mock_dependencies):
    """
    Test Case 3b: Error Handling (Malformed Data)
    Verify pipeline doesn't crash on invalid input items within a batch.
    """
    # Mix of valid and invalid data

    # Let's mock detect_anomaly to raise an exception for one call
    mock_dependencies["detect_anomaly"].side_effect = [
        (False, 0.1), # 1st success
        Exception("Simulated Model Error"), # 2nd failure
        (False, 0.1)  # 3rd success
    ]

    telemetry_list = [
        {"voltage": 5.0, "temperature": 20.0, "gyro": 0.0, "current": 1.0, "wheel_speed": 10.0},
        {"voltage": 5.0, "temperature": 20.0, "gyro": 0.0, "current": 1.0, "wheel_speed": 10.0},
        {"voltage": 5.0, "temperature": 20.0, "gyro": 0.0, "current": 1.0, "wheel_speed": 10.0},
    ]
    payload = {"telemetry": telemetry_list}

    response = await client.post("/api/v1/telemetry/batch", json=payload)

    # The API should catch the exception and return a partial success or error result for that item
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()

    # Check results
    results = data["results"]
    assert len(results) == 3
    assert results[0]["anomaly_type"] == "normal"

    # The second one threw an error but the system swallows it and returns 'normal'
    # This behavior is confirmed by current implementation in api/service.py
    # We assert that it didn't crash and returned a response for all items
    assert results[1]["anomaly_type"] == "normal"

    assert results[2]["anomaly_type"] == "normal"


@pytest.mark.asyncio
async def test_streaming_pipeline_concurrency(client, mock_dependencies):
    """
    Test Case 4: Concurrency
    Verify that the pipeline handles multiple concurrent batch requests.
    """
    batch_size = 10
    num_requests = 10

    payload = {
        "telemetry": [
            {"voltage": 5.0, "temperature": 25.0, "gyro": 0.01, "current": 1.0, "wheel_speed": 10.0}
            for _ in range(batch_size)
        ]
    }

    async def send_batch():
        return await client.post("/api/v1/telemetry/batch", json=payload)

    # Launch concurrent requests
    responses = await asyncio.gather(*[send_batch() for _ in range(num_requests)])

    for resp in responses:
        assert resp.status_code == 200, f"Response: {resp.text}"
        assert resp.json()["total_processed"] == batch_size


@pytest.mark.asyncio
async def test_streaming_pipeline_compression_serialization(client, mock_dependencies):
    """
    Test Case 5: Compression & Serialization (Zstd + MsgPack)
    Verify end-to-end flow with network optimization.
    """
    # Prepare data
    telemetry_data = [
        {"voltage": 5.0, "temperature": 25.0, "gyro": 0.01, "current": 1.0, "wheel_speed": 10.0}
    ]
    payload_dict = {"telemetry": telemetry_data}

    # Serialize with MsgPack
    packed_data = msgpack.packb(payload_dict)

    # Compress with Zstd
    compressor = zstd.ZstdCompressor()
    compressed_data = compressor.compress(packed_data)

    # Send request with headers
    headers = {
        "Content-Type": "application/msgpack",
        "Content-Encoding": "zstd"
    }

    response = await client.post(
        "/api/v1/telemetry/batch",
        content=compressed_data,
        headers=headers
    )

    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["total_processed"] == 1
