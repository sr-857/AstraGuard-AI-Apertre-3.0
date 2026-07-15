"""
Unit tests for src/api/service.py

Tests cover FastAPI endpoints, helper functions, and core functionality
with mocking for external dependencies.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
import json
import secrets
from fastapi.testclient import TestClient
from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials
import sys
from pathlib import Path
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from api.service import (
    app,
    check_chaos_injection,
    inject_chaos_fault,
    create_response,
    process_telemetry_batch,
    cleanup_expired_faults,
    _check_credential_security,
    initialize_components,
    _process_telemetry,
    get_current_username,
    active_faults,
    telemetry_lock,
    anomaly_lock,
    faults_lock,
    anomaly_history,
    MAX_ANOMALY_HISTORY_SIZE
)
from api.models import (
    TelemetryInput, 
    TelemetryBatch,
    AnomalyResponse,
    HealthCheckResponse,
    SystemStatus,
    PhaseUpdateRequest
)
from state_machine.state_engine import MissionPhase
from typing import Optional


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
async def reset_global_state():
    """Reset global state before each test."""
    # Clear active faults
    active_faults.clear()
    # Clear anomaly history
    anomaly_history.clear()
    yield
    # Cleanup after test
    active_faults.clear()
    anomaly_history.clear()


@pytest.fixture
def mock_dependencies():
    """Mock external dependencies."""
    with patch('api.service.state_machine') as mock_state_machine, \
         patch('api.service.policy_loader') as mock_policy_loader, \
         patch('api.service.phase_aware_handler') as mock_handler, \
         patch('api.service.memory_store') as mock_memory_store, \
         patch('api.service.predictive_engine') as mock_predictive, \
         patch('api.service.get_health_monitor') as mock_health_monitor, \
         patch('api.service.get_auth_manager') as mock_auth_manager, \
         patch('api.service.get_api_key') as mock_get_api_key, \
         patch('api.service.require_operator') as mock_require_operator, \
         patch('api.service.require_admin') as mock_require_admin, \
         patch('api.service.require_phase_update') as mock_require_phase_update, \
         patch('api.service.require_analyst') as mock_require_analyst, \
         patch('api.service.get_current_user') as mock_get_current_user:

        # Configure mocks
        mock_phase = Mock()
        mock_phase.value = "NOMINAL_OPS"
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_memory_store.get_stats.return_value = {
            'total_events': 100,
            'critical_events': 5,
            'avg_age_hours': 24.5,
            'max_recurrence': 3
        }
        mock_health_monitor.return_value.get_all_health.return_value = {
            'anomaly_detector': {'status': 'HEALTHY', 'timestamp': datetime.now()},
            'memory_store': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }

        yield {
            'state_machine': mock_state_machine,
            'policy_loader': mock_policy_loader,
            'handler': mock_handler,
            'memory_store': mock_memory_store,
            'predictive': mock_predictive,
            'health_monitor': mock_health_monitor,
            'auth_manager': mock_auth_manager,
            'get_api_key': mock_get_api_key,
            'require_operator': mock_require_operator,
            'require_admin': mock_require_admin,
            'require_phase_update': mock_require_phase_update,
            'require_analyst': mock_require_analyst,
            'get_current_user': mock_get_current_user
        }


@pytest.fixture
def sample_telemetry():
    """Sample telemetry data."""
    return TelemetryInput(
        voltage=8.0,
        temperature=25.0,
        gyro=0.02,
        current=1.1,
        wheel_speed=5000,
        timestamp=datetime.now()
    )


@pytest.fixture
def anomalous_telemetry():
    """Anomalous telemetry data."""
    return TelemetryInput(
        voltage=8.0,
        temperature=95.0,  # High temperature
        gyro=0.02,
        current=1.1,
        wheel_speed=5000,
        timestamp=datetime.now()
    )


class TestHelperFunctions:
    """Test helper functions."""

    @pytest.mark.asyncio
    async def test_check_chaos_injection_active(self):
        """Test chaos injection check when fault is active."""
        # Set up active fault that expires in the future
        active_faults['test_fault'] = time.time() + 60  # Active for 60 seconds

        result = await check_chaos_injection('test_fault')
        assert result is True

    @pytest.mark.asyncio
    async def test_check_chaos_injection_expired(self):
        """Test chaos injection check when fault has expired."""
        # Set up expired fault
        active_faults['test_fault'] = time.time() - 60  # Expired 60 seconds ago

        result = await check_chaos_injection('test_fault')
        assert result is False
        # Should be cleaned up
        assert 'test_fault' not in active_faults

    @pytest.mark.asyncio
    async def test_check_chaos_injection_inactive(self):
        """Test chaos injection check when fault is not active."""
        result = await check_chaos_injection('nonexistent_fault')
        assert result is False

    @pytest.mark.asyncio
    async def test_check_chaos_injection_concurrent_access(self):
        """Test chaos injection with concurrent access."""
        active_faults['test_fault'] = time.time() + 60
        
        # Simulate concurrent access
        results = await asyncio.gather(
            check_chaos_injection('test_fault'),
            check_chaos_injection('test_fault'),
            check_chaos_injection('test_fault')
        )
        
        assert all(r is True for r in results)

    @pytest.mark.asyncio
    async def test_inject_chaos_fault(self):
        """Test injecting a chaos fault."""
        result = await inject_chaos_fault('test_fault', 30)

        assert result['status'] == 'injected'
        assert result['fault'] == 'test_fault'
        assert 'expires_at' in result
        assert 'test_fault' in active_faults
        assert active_faults['test_fault'] > time.time()

    @pytest.mark.asyncio
    async def test_inject_chaos_fault_overwrite(self):
        """Test overwriting an existing chaos fault."""
        # Inject first fault
        result1 = await inject_chaos_fault('test_fault', 30)
        expiration1 = result1['expires_at']
        
        # Wait a bit
        await asyncio.sleep(0.1)
        
        # Inject again with different duration
        result2 = await inject_chaos_fault('test_fault', 60)
        expiration2 = result2['expires_at']
        
        # Second expiration should be later
        assert expiration2 > expiration1

    @pytest.mark.asyncio
    async def test_inject_chaos_fault_multiple_types(self):
        """Test injecting multiple different chaos faults."""
        await inject_chaos_fault('fault1', 30)
        await inject_chaos_fault('fault2', 40)
        await inject_chaos_fault('fault3', 50)
        
        assert len(active_faults) == 3
        assert 'fault1' in active_faults
        assert 'fault2' in active_faults
        assert 'fault3' in active_faults

    def test_create_response(self):
        """Test creating standardized API response."""
        response = create_response("success", {"data": "test"}, custom_field="value")

        assert response['status'] == 'success'
        assert 'timestamp' in response
        assert isinstance(response['timestamp'], datetime)
        assert response['data'] == 'test'
        assert response['custom_field'] == 'value'

    def test_create_response_no_data(self):
        """Test creating response without data."""
        response = create_response("error")

        assert response['status'] == 'error'
        assert 'timestamp' in response
        assert 'data' not in response

    def test_create_response_with_kwargs(self):
        """Test creating response with various kwargs."""
        response = create_response("success", None, 
                                  error_code=404, 
                                  message="Not found",
                                  details={"reason": "test"})

        assert response['status'] == 'success'
        assert response['error_code'] == 404
        assert response['message'] == "Not found"
        assert response['details'] == {"reason": "test"}

    @pytest.mark.asyncio
    async def test_cleanup_expired_faults(self):
        """Test cleanup of expired chaos faults."""
        current_time = time.time()
        active_faults['expired1'] = current_time - 10
        active_faults['expired2'] = current_time - 5
        active_faults['active'] = current_time + 60

        await cleanup_expired_faults()

        assert 'expired1' not in active_faults
        assert 'expired2' not in active_faults
        assert 'active' in active_faults

    @pytest.mark.asyncio
    async def test_cleanup_expired_faults_empty(self):
        """Test cleanup with no faults."""
        await cleanup_expired_faults()
        assert len(active_faults) == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_faults_boundary(self):
        """Test cleanup with fault expiring exactly now."""
        current_time = time.time()
        active_faults['boundary_fault'] = current_time
        
        await asyncio.sleep(0.01)  # Small delay to ensure time passes
        await cleanup_expired_faults()
        
        # Should be cleaned up
        assert 'boundary_fault' not in active_faults


class TestCredentialSecurity:
    """Test credential security checks."""

    @patch('api.service.get_secret')
    def test_check_credential_security_configured(self, mock_get_secret):
        """Test credential security check when properly configured."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'secure_user',
            'METRICS_PASSWORD': 'very_strong_password_with_lots_of_chars_12345678',
            'metrics_user': 'secure_user',
            'metrics_password': 'very_strong_password_with_lots_of_chars_12345678'
        }.get(key)

        # Should not raise any exceptions
        _check_credential_security()

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_missing(self, mock_print, mock_get_secret):
        """Test credential security check when credentials are missing."""
        mock_get_secret.return_value = None

        _check_credential_security()

        # Should print warning messages
        assert mock_print.call_count > 0
        # Check that warning appears in print calls
        print_args = str(mock_print.call_args_list)
        assert "WARNING" in print_args or "METRICS_USER" in print_args

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_weak_admin_admin(self, mock_print, mock_get_secret):
        """Test credential security check with weak admin/admin credentials."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'admin',
            'METRICS_PASSWORD': 'admin',
            'metrics_user': 'admin',
            'metrics_password': 'admin'
        }.get(key)

        _check_credential_security()

        # Should print security warnings
        assert mock_print.call_count > 0
        print_args = str(mock_print.call_args_list)
        assert "WARNING" in print_args or "CRITICAL" in print_args

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_weak_root_root(self, mock_print, mock_get_secret):
        """Test credential security check with weak root/root credentials."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'root',
            'METRICS_PASSWORD': 'root',
            'metrics_user': 'root',
            'metrics_password': 'root'
        }.get(key)

        _check_credential_security()

        assert mock_print.call_count > 0

    @patch('api.service.get_secret')
    @patch('builtins.print')
    def test_check_credential_security_short_password(self, mock_print, mock_get_secret):
        """Test credential security check with short password."""
        mock_get_secret.side_effect = lambda key: {
            'METRICS_USER': 'myuser',
            'METRICS_PASSWORD': 'short',  # Only 5 characters
            'metrics_user': 'myuser',
            'metrics_password': 'short'
        }.get(key)

        _check_credential_security()

        # Should warn about short password
        assert mock_print.call_count > 0
        print_args = str(mock_print.call_args_list)
        assert "password" in print_args.lower() or "WARNING" in print_args

    def test_get_current_username_valid_credentials(self):
        """Test username validation with correct credentials."""
        with patch('api.service.get_secret') as mock_get_secret:
            mock_get_secret.side_effect = lambda key: {
                'METRICS_USER': 'testuser',
                'METRICS_PASSWORD': 'testpass',
                'metrics_user': 'testuser',
                'metrics_password': 'testpass'
            }.get(key)

            credentials = HTTPBasicCredentials(username='testuser', password='testpass')
            username = get_current_username(credentials)

            assert username == 'testuser'

    def test_get_current_username_invalid_credentials(self):
        """Test username validation with incorrect credentials."""
        with patch('api.service.get_secret') as mock_get_secret:
            mock_get_secret.side_effect = lambda key: {
                'METRICS_USER': 'testuser',
                'METRICS_PASSWORD': 'testpass',
                'metrics_user': 'testuser',
                'metrics_password': 'testpass'
            }.get(key)

            credentials = HTTPBasicCredentials(username='wronguser', password='wrongpass')

            with pytest.raises(HTTPException) as exc_info:
                get_current_username(credentials)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_current_username_missing_config(self):
        """Test username validation when credentials are not configured."""
        with patch('api.service.get_secret') as mock_get_secret:
            mock_get_secret.return_value = None

            credentials = HTTPBasicCredentials(username='testuser', password='testpass')

            with pytest.raises(HTTPException) as exc_info:
                get_current_username(credentials)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "not configured" in exc_info.value.detail.lower()

    def test_get_current_username_timing_attack_resistance(self):
        """Test that credential comparison is timing-attack resistant (uses secrets.compare_digest)."""
        with patch('api.service.get_secret') as mock_get_secret, \
             patch('secrets.compare_digest') as mock_compare:
            
            mock_get_secret.side_effect = lambda key: {
                'METRICS_USER': 'testuser',
                'METRICS_PASSWORD': 'testpass',
                'metrics_user': 'testuser',
                'metrics_password': 'testpass'
            }.get(key)
            mock_compare.return_value = True

            credentials = HTTPBasicCredentials(username='testuser', password='testpass')
            get_current_username(credentials)

            # Should use secrets.compare_digest for timing-attack resistance
            assert mock_compare.call_count >= 2  # Called for both username and password


class TestInitialization:
    """Test initialization functions."""

    @pytest.mark.asyncio
    async def test_initialize_components(self):
        """Test that components are initialized correctly."""
        import api.service
        
        # Reset global state
        api.service.state_machine = None
        api.service.policy_loader = None
        api.service.phase_aware_handler = None
        api.service.memory_store = None
        api.service.predictive_engine = None

        with patch('api.service.StateMachine') as mock_sm, \
             patch('api.service.MissionPhasePolicyLoader') as mock_loader, \
             patch('api.service.PhaseAwareAnomalyHandler') as mock_handler, \
             patch('api.service.AdaptiveMemoryStore') as mock_store, \
             patch('api.service.get_predictive_maintenance_engine') as mock_engine:
            
            mock_engine.return_value = AsyncMock()
            
            await initialize_components()

            assert api.service.state_machine is not None
            assert api.service.policy_loader is not None
            assert api.service.phase_aware_handler is not None
            assert api.service.memory_store is not None
            assert api.service.predictive_engine is not None

    @pytest.mark.asyncio
    async def test_initialize_components_idempotent(self):
        """Test that calling initialize_components multiple times is safe."""
        import api.service
        
        with patch('api.service.StateMachine') as mock_sm, \
             patch('api.service.MissionPhasePolicyLoader') as mock_loader, \
             patch('api.service.PhaseAwareAnomalyHandler') as mock_handler, \
             patch('api.service.AdaptiveMemoryStore') as mock_store, \
             patch('api.service.get_predictive_maintenance_engine') as mock_engine:
            
            mock_engine.return_value = AsyncMock()
            
            # Initialize once
            await initialize_components()
            first_state_machine = api.service.state_machine
            
            # Initialize again
            await initialize_components()
            second_state_machine = api.service.state_machine
            
            # Should reuse existing instances (idempotent)
            assert first_state_machine is second_state_machine


class TestFastAPIEndpoints:
    """Test FastAPI endpoints."""

    def test_root_endpoint(self, client):
        """Test root health check endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['version'] == '1.0.0'
        assert 'timestamp' in data

    @patch('api.service.get_health_monitor')
    @patch('api.service.state_machine')
    @patch('api.service.start_time')
    def test_health_check_endpoint_healthy(self, mock_start_time, mock_state_machine, 
                                          mock_health_monitor, client):
        """Test health check endpoint when all components are healthy."""
        mock_start_time.__float__ = Mock(return_value=1000000000.0)
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        
        mock_health_monitor.return_value.get_all_health.return_value = {
            'component1': {'status': 'HEALTHY', 'timestamp': datetime.now()},
            'component2': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'uptime_seconds' in data
        assert data['mission_phase'] == 'NOMINAL_OPS'
        assert 'components_status' in data
        assert len(data['components_status']) == 2

    @patch('api.service.get_health_monitor')
    @patch('api.service.state_machine')
    def test_health_check_endpoint_degraded(self, mock_state_machine, 
                                            mock_health_monitor, client):
        """Test health check endpoint when some components are degraded."""
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        
        mock_health_monitor.return_value.get_all_health.return_value = {
            'component1': {'status': 'HEALTHY', 'timestamp': datetime.now()},
            'component2': {'status': 'DEGRADED', 'timestamp': datetime.now()}
        }

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'degraded'

    @patch('api.service.get_health_monitor')
    def test_health_check_endpoint_error(self, mock_health_monitor, client):
        """Test health check endpoint when an error occurs."""
        mock_health_monitor.return_value.get_all_health.side_effect = Exception("Health check failed")

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'unhealthy'
        assert 'error' in data

    @patch('api.service.OBSERVABILITY_ENABLED', True)
    @patch('api.service.get_metrics_text')
    @patch('api.service.get_metrics_content_type')
    @patch('api.service.get_current_username')
    def test_metrics_endpoint_with_auth(self, mock_auth, mock_content_type, mock_text, client):
        """Test metrics endpoint with authentication."""
        mock_auth.return_value = 'testuser'
        mock_text.return_value = '# HELP test_metric Test metric\n# TYPE test_metric counter\ntest_metric 42'
        mock_content_type.return_value = 'text/plain; version=0.0.4'

        response = client.get("/metrics", auth=('testuser', 'testpass'))

        assert response.status_code == 200
        assert 'test_metric 42' in response.text

    @patch('api.service.get_api_key')
    @patch('api.service.latest_telemetry_data', None)
    def test_get_latest_telemetry_no_data(self, mock_api_key, client):
        """Test getting latest telemetry when no data exists."""
        mock_api_key.return_value = Mock()

        response = client.get("/api/v1/telemetry/latest")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'no_data'

    @patch('api.service.get_api_key')
    def test_get_latest_telemetry_with_data(self, mock_api_key, client):
        """Test getting latest telemetry when data exists."""
        import api.service
        
        mock_api_key.return_value = Mock()
        api.service.latest_telemetry_data = {
            'data': {'voltage': 8.0, 'temperature': 25.0},
            'timestamp': datetime.now()
        }

        response = client.get("/api/v1/telemetry/latest")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'data' in data

    @patch('api.service.get_api_key')
    @patch('api.service.memory_store')
    def test_get_memory_stats(self, mock_memory_store, mock_api_key, client):
        """Test memory stats endpoint."""
        mock_api_key.return_value = Mock()
        mock_memory_store.get_stats.return_value = {
            'total_events': 50,
            'critical_events': 2,
            'avg_age_hours': 12.5,
            'max_recurrence': 1
        }

        response = client.get("/api/v1/memory/stats")

        assert response.status_code == 200
        data = response.json()
        assert data['total_events'] == 50
        assert data['critical_events'] == 2

    @patch('api.service.get_api_key')
    @patch('api.service.state_machine')
    @patch('api.service.phase_aware_handler')
    def test_get_phase(self, mock_handler, mock_state_machine, mock_api_key, client):
        """Test get phase endpoint."""
        mock_api_key.return_value = Mock()
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_state_machine.get_phase_description.return_value = 'Normal operations'
        mock_state_machine.get_phase_history.return_value = []
        mock_handler.get_phase_constraints.return_value = {'max_power': 100}

        response = client.get("/api/v1/phase")

        assert response.status_code == 200
        data = response.json()
        assert data['phase'] == 'NOMINAL_OPS'
        assert 'constraints' in data
        assert 'history' in data
        assert 'description' in data

    @patch('api.service.get_api_key')
    @patch('api.service.state_machine')
    @patch('api.service.get_health_monitor')
    def test_get_status_healthy(self, mock_health_monitor, mock_state_machine, mock_api_key, client):
        """Test system status endpoint when healthy."""
        mock_api_key.return_value = Mock()
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        
        mock_health_monitor.return_value.get_all_health.return_value = {
            'component1': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }

        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['mission_phase'] == 'NOMINAL_OPS'
        assert 'components' in data
        assert 'uptime_seconds' in data

    @patch('api.service.get_api_key')
    @patch('api.service.state_machine')
    @patch('api.service.get_health_monitor')
    @patch('api.service.check_chaos_injection')
    async def test_get_status_with_redis_failure_chaos(self, mock_chaos, mock_health_monitor, 
                                                       mock_state_machine, mock_api_key, client):
        """Test system status endpoint with Redis failure chaos injection."""
        mock_api_key.return_value = Mock()
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_chaos.return_value = True  # Chaos injection active
        
        mock_health_monitor.return_value.get_all_health.return_value = {
            'memory_store': {'status': 'HEALTHY', 'timestamp': datetime.now()}
        }

        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        # Chaos injection should degrade memory_store
        assert data['components']['memory_store']['status'] == 'DEGRADED'


class TestTelemetryProcessing:
    """Test telemetry processing functions."""

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_normal(self, mock_state_machine, mock_memory_store,
                                          mock_handler, mock_classify, mock_detect, sample_telemetry):
        """Test processing normal telemetry (no anomaly)."""
        # Setup mocks
        mock_detect.return_value = (False, 0.1)  # No anomaly
        mock_classify.return_value = 'normal'
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase

        result = await _process_telemetry(sample_telemetry, 0.0)

        assert result.is_anomaly is False
        assert result.anomaly_type == 'normal'
        assert result.mission_phase == 'NOMINAL_OPS'
        assert result.severity_level == 'LOW'
        assert result.recommended_action == 'NO_ACTION'
        mock_memory_store.write.assert_not_called()  # No anomaly, so no write

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_anomaly(self, mock_state_machine, mock_memory_store,
                                           mock_handler, mock_classify, mock_detect, anomalous_telemetry):
        """Test processing anomalous telemetry."""
        # Setup mocks
        mock_detect.return_value = (True, 0.9)  # Anomaly detected
        mock_classify.return_value = 'thermal_fault'

        decision = {
            'anomaly_type': 'thermal_fault',
            'severity_score': 0.9,
            'policy_decision': {
                'severity': 'HIGH',
                'escalation_level': 'MONITOR',
                'is_allowed': True,
                'allowed_actions': ['LOG', 'NOTIFY']
            },
            'mission_phase': 'NOMINAL_OPS',
            'recommended_action': 'THERMAL_REGULATION',
            'should_escalate_to_safe_mode': False,
            'detection_confidence': 0.85,
            'reasoning': 'High temperature detected',
            'recurrence_info': {'count': 1}
        }
        mock_handler.handle_anomaly.return_value = decision
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_memory_store.write = AsyncMock()

        result = await _process_telemetry(anomalous_telemetry, 0.0)

        assert result.is_anomaly is True
        assert result.anomaly_type == 'thermal_fault'
        assert result.severity_level == 'HIGH'
        assert result.recommended_action == 'THERMAL_REGULATION'
        assert result.recurrence_count == 1
        mock_memory_store.write.assert_called_once()
        
        # Verify anomaly was added to history
        assert len(anomaly_history) > 0

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_with_timestamp(self, mock_state_machine, mock_memory_store,
                                                   mock_handler, mock_classify, mock_detect):
        """Test processing telemetry with explicit timestamp."""
        mock_detect.return_value = (False, 0.1)
        mock_classify.return_value = 'normal'
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase

        custom_timestamp = datetime(2026, 1, 15, 10, 30, 0)
        telemetry = TelemetryInput(
            voltage=8.0,
            temperature=25.0,
            gyro=0.02,
            timestamp=custom_timestamp
        )

        result = await _process_telemetry(telemetry, 0.0)

        assert result.timestamp == custom_timestamp

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_safe_mode_escalation(self, mock_state_machine, mock_memory_store,
                                                         mock_handler, mock_classify, mock_detect, 
                                                         anomalous_telemetry):
        """Test processing telemetry that should escalate to safe mode."""
        mock_detect.return_value = (True, 0.99)  # Critical anomaly
        mock_classify.return_value = 'critical_fault'

        decision = {
            'anomaly_type': 'critical_fault',
            'severity_score': 0.99,
            'policy_decision': {
                'severity': 'CRITICAL',
                'escalation_level': 'SAFE_MODE',
                'is_allowed': False,
                'allowed_actions': []
            },
            'mission_phase': 'NOMINAL_OPS',
            'recommended_action': 'EMERGENCY_SAFE_MODE',
            'should_escalate_to_safe_mode': True,
            'detection_confidence': 0.95,
            'reasoning': 'Critical fault detected',
            'recurrence_info': {'count': 1}
        }
        mock_handler.handle_anomaly.return_value = decision
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_memory_store.write = AsyncMock()

        result = await _process_telemetry(anomalous_telemetry, 0.0)

        assert result.should_escalate_to_safe_mode is True
        assert result.severity_level == 'CRITICAL'

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine')
    async def test_process_telemetry_with_predictive_engine(self, mock_predictive, mock_state_machine, 
                                                           mock_memory_store, mock_handler, 
                                                           mock_classify, mock_detect, sample_telemetry):
        """Test processing telemetry with predictive maintenance engine."""
        mock_detect.return_value = (False, 0.1)
        mock_classify.return_value = 'normal'
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        
        # Mock predictive engine
        mock_predictive.add_training_data = AsyncMock()
        mock_predictive.predict_failures = AsyncMock(return_value=[])
        
        result = await _process_telemetry(sample_telemetry, 0.0)

        # Should call predictive engine methods
        mock_predictive.add_training_data.assert_called_once()
        mock_predictive.predict_failures.assert_called_once()

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine')
    async def test_process_telemetry_predictive_engine_error(self, mock_predictive, mock_state_machine, 
                                                            mock_memory_store, mock_handler, 
                                                            mock_classify, mock_detect, sample_telemetry):
        """Test that predictive engine errors don't break telemetry processing."""
        mock_detect.return_value = (False, 0.1)
        mock_classify.return_value = 'normal'
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        
        # Mock predictive engine to raise error
        mock_predictive.add_training_data = AsyncMock(side_effect=Exception("Predictive engine failed"))
        
        # Should not raise exception
        result = await _process_telemetry(sample_telemetry, 0.0)
        
        assert result.is_anomaly is False

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_updates_global_state(self, mock_state_machine, mock_memory_store,
                                                         mock_handler, mock_classify, mock_detect, sample_telemetry):
        """Test that processing updates global latest_telemetry_data."""
        import api.service
        
        mock_detect.return_value = (False, 0.1)
        mock_classify.return_value = 'normal'
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase

        api.service.latest_telemetry_data = None
        await _process_telemetry(sample_telemetry, 0.0)

        # Should update global state
        assert api.service.latest_telemetry_data is not None
        assert 'data' in api.service.latest_telemetry_data
        assert 'timestamp' in api.service.latest_telemetry_data


class TestAnomalyHistory:
    """Test anomaly history functionality."""

    @pytest.mark.asyncio
    async def test_anomaly_history_bounded(self):
        """Test that anomaly history respects max size."""
        # Fill history beyond max
        for i in range(MAX_ANOMALY_HISTORY_SIZE + 100):
            anomaly = Mock()
            anomaly.timestamp = datetime.now()
            anomaly.severity_score = 0.8
            async with anomaly_lock:
                anomaly_history.append(anomaly)

        # Should be bounded to max size
        assert len(anomaly_history) == MAX_ANOMALY_HISTORY_SIZE

    @pytest.mark.asyncio
    async def test_get_anomaly_history_endpoint_filtering(self, client):
        """Test anomaly history endpoint with filtering."""
        # Populate some anomaly history
        for i in range(5):
            anomaly = Mock(spec=AnomalyResponse)
            anomaly.timestamp = datetime.now() - timedelta(hours=i)
            anomaly.severity_score = 0.5 + (i * 0.1)
            anomaly.is_anomaly = True
            anomaly.anomaly_type = 'test'
            anomaly.severity_level = 'MEDIUM'
            anomaly.mission_phase = 'NOMINAL_OPS'
            anomaly.recommended_action = 'MONITOR'
            anomaly.escalation_level = 'MONITOR'
            anomaly.is_allowed = True
            anomaly.allowed_actions = []
            anomaly.should_escalate_to_safe_mode = False
            anomaly.confidence = 0.85
            anomaly.reasoning = 'Test'
            anomaly.recurrence_count = 0
            async with anomaly_lock:
                anomaly_history.append(anomaly)

        with patch('api.service.get_api_key', return_value=Mock()):
            response = client.get("/api/v1/history/anomalies?limit=3&severity_min=0.6")

            assert response.status_code == 200
            data = response.json()
            assert data['count'] <= 3
            # All returned anomalies should meet severity threshold
            for anomaly in data['anomalies']:
                assert anomaly['severity_score'] >= 0.6


class TestAuthentication:
    """Test authentication endpoints."""

    @patch('api.service.get_auth_manager')
    def test_login_success(self, mock_auth_manager, client):
        """Test successful user login."""
        mock_auth_manager.return_value.authenticate_user.return_value = 'fake_jwt_token_12345'

        login_data = {
            'username': 'testuser',
            'password': 'testpass'
        }

        response = client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data
        assert data['access_token'] == 'fake_jwt_token_12345'
        assert data['token_type'] == 'bearer'

    @patch('api.service.get_auth_manager')
    def test_login_invalid_credentials(self, mock_auth_manager, client):
        """Test login with invalid credentials."""
        mock_auth_manager.return_value.authenticate_user.side_effect = HTTPException(
            status_code=401, detail="Invalid credentials"
        )

        login_data = {
            'username': 'baduser',
            'password': 'badpass'
        }

        with pytest.raises(HTTPException):
            client.post("/api/v1/auth/login", json=login_data)

    @patch('api.service.get_auth_manager')
    @patch('api.service.require_admin')
    async def test_create_user(self, mock_require_admin, mock_auth_manager, client):
        """Test creating a new user."""
        mock_admin = Mock()
        mock_admin.id = 1
        mock_admin.username = 'admin'
        mock_require_admin.return_value = mock_admin
        
        mock_user = Mock()
        mock_user.id = 2
        mock_user.username = 'newuser'
        mock_user.role.value = 'operator'
        mock_user.email = 'new@example.com'
        mock_user.created_at = datetime.now()
        mock_user.is_active = True
        
        mock_auth_manager.return_value.create_user = AsyncMock(return_value=mock_user)

        user_data = {
            'username': 'newuser',
            'password': 'securepass',
            'role': 'operator',
            'email': 'new@example.com'
        }

        response = client.post("/api/v1/auth/users", json=user_data)

        assert response.status_code == 200
        data = response.json()
        assert data['username'] == 'newuser'
        assert data['role'] == 'operator'
        assert data['email'] == 'new@example.com'

    @patch('api.service.get_current_user')
    def test_get_current_user_info(self, mock_get_current_user, client):
        """Test getting current user information."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = 'testuser'
        mock_user.role.value = 'analyst'
        mock_user.email = 'test@example.com'
        mock_user.created_at = datetime.now()
        mock_user.is_active = True
        mock_get_current_user.return_value = mock_user

        response = client.get("/api/v1/auth/users/me")

        assert response.status_code == 200
        data = response.json()
        assert data['username'] == 'testuser'
        assert data['role'] == 'analyst'

    @patch('api.service.get_auth_manager')
    @patch('api.service.get_current_user')
    async def test_create_api_key(self, mock_get_current_user, mock_auth_manager, client):
        """Test creating an API key."""
        mock_user = Mock()
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user

        mock_api_key = Mock()
        mock_api_key.id = 'key123'
        mock_api_key.name = 'test-key'
        mock_api_key.key = 'secret_key_12345'
        mock_api_key.permissions = ['read', 'write']
        mock_api_key.created_at = datetime.now()
        mock_api_key.expires_at = datetime.now() + timedelta(days=30)

        mock_auth_manager.return_value.create_api_key = AsyncMock(return_value=mock_api_key)

        key_data = {
            'name': 'test-key',
            'permissions': ['read', 'write']
        }

        response = client.post("/api/v1/auth/apikeys", json=key_data)

        assert response.status_code == 200
        data = response.json()
        assert data['name'] == 'test-key'
        assert 'key' in data
        assert data['permissions'] == ['read', 'write']

    @patch('api.service.get_auth_manager')
    @patch('api.service.get_current_user')
    async def test_list_api_keys(self, mock_get_current_user, mock_auth_manager, client):
        """Test listing API keys."""
        mock_user = Mock()
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user

        mock_keys = [
            Mock(id='key1', name='key-1', permissions=['read'], 
                 created_at=datetime.now(), expires_at=None, last_used=None),
            Mock(id='key2', name='key-2', permissions=['read', 'write'], 
                 created_at=datetime.now(), expires_at=None, last_used=datetime.now())
        ]

        mock_auth_manager.return_value.get_user_api_keys = AsyncMock(return_value=mock_keys)

        response = client.get("/api/v1/auth/apikeys")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]['name'] == 'key-1'
        assert data[1]['name'] == 'key-2'

    @patch('api.service.get_auth_manager')
    @patch('api.service.get_current_user')
    def test_revoke_api_key(self, mock_get_current_user, mock_auth_manager, client):
        """Test revoking an API key."""
        mock_user = Mock()
        mock_user.id = 1
        mock_get_current_user.return_value = mock_user

        mock_auth_manager.return_value.revoke_api_key.return_value = None

        response = client.delete("/api/v1/auth/apikeys/key123")

        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert 'revoked' in data['message'].lower()


class TestPhaseManagement:
    """Test mission phase management endpoints."""

    @patch('api.service.state_machine')
    @patch('api.service.require_phase_update')
    def test_update_phase_normal_transition(self, mock_require_phase_update, 
                                           mock_state_machine, client):
        """Test normal phase transition."""
        mock_user = Mock()
        mock_require_phase_update.return_value = mock_user

        mock_state_machine.set_phase.return_value = {
            'success': True,
            'previous_phase': 'NOMINAL_OPS',
            'new_phase': 'MAINTENANCE',
            'message': 'Phase transition successful'
        }

        phase_data = {
            'phase': {'value': 'MAINTENANCE'},
            'force': False
        }

        response = client.post("/api/v1/phase", json=phase_data)

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['new_phase'] == 'MAINTENANCE'

    @patch('api.service.state_machine')
    @patch('api.service.require_phase_update')
    def test_update_phase_force_safe_mode(self, mock_require_phase_update, 
                                         mock_state_machine, client):
        """Test forcing safe mode."""
        mock_user = Mock()
        mock_require_phase_update.return_value = mock_user

        mock_state_machine.force_safe_mode.return_value = {
            'success': True,
            'previous_phase': 'NOMINAL_OPS',
            'new_phase': 'SAFE_MODE',
            'message': 'Emergency safe mode activated'
        }

        phase_data = {
            'phase': {'value': 'SAFE_MODE'},
            'force': True
        }

        response = client.post("/api/v1/phase", json=phase_data)

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['new_phase'] == 'SAFE_MODE'
        mock_state_machine.force_safe_mode.assert_called_once()

    @patch('api.service.state_machine')
    @patch('api.service.require_phase_update')
    def test_update_phase_invalid_transition(self, mock_require_phase_update, 
                                            mock_state_machine, client):
        """Test invalid phase transition."""
        mock_user = Mock()
        mock_require_phase_update.return_value = mock_user

        mock_state_machine.set_phase.side_effect = ValueError("Invalid phase transition")

        phase_data = {
            'phase': {'value': 'INVALID_PHASE'},
            'force': False
        }

        response = client.post("/api/v1/phase", json=phase_data)

        assert response.status_code == 400
        assert "failed" in response.json()['detail'].lower()


class TestChaosInjection:
    """Test chaos engineering features."""

    @patch('api.service.require_operator')
    @patch('api.service._process_telemetry')
    @patch('api.service.check_chaos_injection')
    @patch('time.sleep')
    def test_telemetry_with_network_latency(self, mock_sleep, mock_chaos, 
                                           mock_process, mock_require_op, 
                                           client, sample_telemetry):
        """Test telemetry submission with network latency chaos injection."""
        mock_require_op.return_value = Mock()
        mock_response = Mock(spec=AnomalyResponse)
        mock_response.is_anomaly = False
        mock_response.anomaly_score = 0.1
        mock_process.return_value = mock_response
        
        # First call returns True (network latency active), subsequent calls False
        mock_chaos.side_effect = [True, False]

        telemetry_data = {
            'voltage': 8.0,
            'temperature': 25.0,
            'gyro': 0.02,
            'current': 1.1,
            'wheel_speed': 5000
        }

        response = client.post("/api/v1/telemetry", json=telemetry_data)

        # Should succeed despite chaos injection
        assert response.status_code == 200
        mock_sleep.assert_called_with(2.0)  # Verify network latency delay

    @patch('api.service.require_operator')
    @patch('api.service.check_chaos_injection')
    def test_telemetry_with_model_loader_failure(self, mock_chaos, mock_require_op, client):
        """Test telemetry submission with model loader failure chaos injection."""
        mock_require_op.return_value = Mock()
        
        # First call False (network_latency), second call True (model_loader)
        mock_chaos.side_effect = [False, True]

        telemetry_data = {
            'voltage': 8.0,
            'temperature': 25.0,
            'gyro': 0.02,
            'current': 1.1,
            'wheel_speed': 5000
        }

        response = client.post("/api/v1/telemetry", json=telemetry_data)

        # Should fail with 503 due to chaos injection
        assert response.status_code == 503
        assert "Chaos Injection" in response.json()['detail']


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch('api.service.require_operator')
    @patch('api.service._process_telemetry')
    def test_telemetry_processing_error(self, mock_process, mock_require_op, client):
        """Test handling of telemetry processing errors."""
        mock_require_op.return_value = Mock()
        mock_process.side_effect = Exception("Processing failed")

        telemetry_data = {
            'voltage': 8.0,
            'temperature': 25.0,
            'gyro': 0.02,
            'current': 1.1,
            'wheel_speed': 5000
        }

        response = client.post("/api/v1/telemetry", json=telemetry_data)

        assert response.status_code == 500
        assert "Anomaly detection failed" in response.json()['detail']

    def test_invalid_telemetry_data(self, client):
        """Test submission of invalid telemetry data."""
        # Missing required fields
        telemetry_data = {
            'voltage': 8.0
            # Missing temperature, gyro, etc.
        }

        with patch('api.service.require_operator', return_value=Mock()):
            response = client.post("/api/v1/telemetry", json=telemetry_data)

            # Should fail validation
            assert response.status_code == 422  # Unprocessable Entity

    @patch('api.service.require_operator')
    @patch('api.service._process_telemetry')
    @patch('api.service.OBSERVABILITY_ENABLED', True)
    @patch('api.service.get_logger')
    def test_telemetry_error_logging(self, mock_logger, mock_process, 
                                    mock_require_op, client):
        """Test that errors are properly logged."""
        mock_require_op.return_value = Mock()
        mock_process.side_effect = Exception("Processing failed")
        mock_log_instance = Mock()
        mock_logger.return_value = mock_log_instance

        telemetry_data = {
            'voltage': 8.0,
            'temperature': 25.0,
            'gyro': 0.02
        }

        with patch('api.service.log_error') as mock_log_error:
            response = client.post("/api/v1/telemetry", json=telemetry_data)

            assert response.status_code == 500

    def test_telemetry_missing_optional_fields(self, client):
        """Test that optional fields can be None."""
        with patch('api.service.require_operator', return_value=Mock()), \
             patch('api.service._process_telemetry') as mock_process:
            
            mock_response = Mock(spec=AnomalyResponse)
            mock_response.is_anomaly = False
            mock_response.anomaly_score = 0.1
            mock_process.return_value = mock_response

            telemetry_data = {
                'voltage': 8.0,
                'temperature': 25.0,
                'gyro': 0.02
                # current, wheel_speed, etc. are optional
            }

            response = client.post("/api/v1/telemetry", json=telemetry_data)

            assert response.status_code == 200


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_fault_injection(self):
        """Test concurrent chaos fault injection."""
        # Inject faults concurrently
        results = await asyncio.gather(
            inject_chaos_fault('fault1', 30),
            inject_chaos_fault('fault2', 30),
            inject_chaos_fault('fault3', 30)
        )

        assert len(results) == 3
        assert all(r['status'] == 'injected' for r in results)
        assert len(active_faults) == 3

    @pytest.mark.asyncio
    async def test_zero_duration_fault(self):
        """Test injecting a fault with zero duration."""
        result = await inject_chaos_fault('instant_fault', 0)

        assert result['status'] == 'injected'
        # Should expire immediately
        await asyncio.sleep(0.01)
        is_active = await check_chaos_injection('instant_fault')
        assert is_active is False

    @pytest.mark.asyncio
    async def test_negative_duration_fault(self):
        """Test injecting a fault with negative duration."""
        result = await inject_chaos_fault('expired_fault', -10)

        # Should be immediately expired
        is_active = await check_chaos_injection('expired_fault')
        assert is_active is False

    def test_create_response_empty_status(self):
        """Test creating response with empty status string."""
        response = create_response("", {"data": "test"})

        assert response['status'] == ""
        assert 'timestamp' in response

    def test_create_response_special_characters(self):
        """Test creating response with special characters."""
        response = create_response("success", None, message="Test <>&\"'")

        assert response['message'] == "Test <>&\"'"

    @pytest.mark.asyncio
    @patch('api.service.detect_anomaly')
    @patch('api.service.classify')
    @patch('api.service.phase_aware_handler')
    @patch('api.service.memory_store')
    @patch('api.service.state_machine')
    @patch('api.service.predictive_engine', None)
    async def test_process_telemetry_extreme_values(self, mock_state_machine, mock_memory_store,
                                                   mock_handler, mock_classify, mock_detect):
        """Test processing telemetry with extreme values."""
        mock_detect.return_value = (True, 1.0)
        mock_classify.return_value = 'extreme_fault'
        
        decision = {
            'anomaly_type': 'extreme_fault',
            'severity_score': 1.0,
            'policy_decision': {
                'severity': 'CRITICAL',
                'escalation_level': 'SAFE_MODE',
                'is_allowed': False,
                'allowed_actions': []
            },
            'mission_phase': 'NOMINAL_OPS',
            'recommended_action': 'EMERGENCY_SAFE_MODE',
            'should_escalate_to_safe_mode': True,
            'detection_confidence': 1.0,
            'reasoning': 'Extreme values detected',
            'recurrence_info': {'count': 1}
        }
        mock_handler.handle_anomaly.return_value = decision
        mock_phase = Mock()
        mock_phase.value = 'NOMINAL_OPS'
        mock_state_machine.get_current_phase.return_value = mock_phase
        mock_memory_store.write = AsyncMock()

        # Extreme telemetry values
        telemetry = TelemetryInput(
            voltage=999.9,
            temperature=999.9,
            gyro=999.9,
            current=999.9,
            wheel_speed=99999
        )

        result = await _process_telemetry(telemetry, 0.0)

        assert result.is_anomaly is True
        assert result.severity_score == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
