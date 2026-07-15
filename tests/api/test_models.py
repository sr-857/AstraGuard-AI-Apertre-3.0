import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from typing import List
from api.models import (
    UserRole,
    MissionPhaseEnum,
    TelemetryInput,
    TelemetryBatch,
    PhaseUpdateRequest,
    AnomalyHistoryQuery,
    UserCreateRequest,
    APIKeyCreateRequest,
    LoginRequest,
    AnomalyResponse,
    BatchAnomalyResponse,
    SystemStatus,
    PhaseUpdateResponse,
    MemoryStats,
    AnomalyHistoryResponse,
    HealthCheckResponse,
    UserResponse,
    APIKeyResponse,
    APIKeyCreateResponse,
    TokenResponse,
    ModelValidationError,
)
class TestEnums:
    """Test enum classes."""
    
    def test_user_role_values(self):
        """Test UserRole enum has all expected values."""
        assert UserRole.ADMIN == "admin"
        assert UserRole.OPERATOR == "operator"
        assert UserRole.ANALYST == "analyst"
    
    def test_user_role_membership(self):
        """Test UserRole enum membership."""
        assert "admin" in [role.value for role in UserRole]
        assert "operator" in [role.value for role in UserRole]
        assert "analyst" in [role.value for role in UserRole]
        assert "invalid_role" not in [role.value for role in UserRole]
    
    def test_mission_phase_enum_values(self):
        """Test MissionPhaseEnum has all expected values."""
        assert MissionPhaseEnum.LAUNCH == "LAUNCH"
        assert MissionPhaseEnum.DEPLOYMENT == "DEPLOYMENT"
        assert MissionPhaseEnum.NOMINAL_OPS == "NOMINAL_OPS"
        assert MissionPhaseEnum.PAYLOAD_OPS == "PAYLOAD_OPS"
        assert MissionPhaseEnum.SAFE_MODE == "SAFE_MODE"
    
    def test_mission_phase_enum_membership(self):
        """Test MissionPhaseEnum membership."""
        phases = [phase.value for phase in MissionPhaseEnum]
        assert "LAUNCH" in phases
        assert "DEPLOYMENT" in phases
        assert "NOMINAL_OPS" in phases
        assert "PAYLOAD_OPS" in phases
        assert "SAFE_MODE" in phases
        assert "INVALID_PHASE" not in phases
class TestTelemetryInput:
    """Test TelemetryInput model validation."""
    
    def test_valid_telemetry_minimal(self):
        """Test valid telemetry with only required fields."""
        data = {
            "voltage": 12.5,
            "temperature": 25.0,
            "gyro": 0.05
        }
        telemetry = TelemetryInput(**data)
        assert telemetry.voltage == 12.5
        assert telemetry.temperature == 25.0
        assert telemetry.gyro == 0.05
        assert telemetry.timestamp is None
    
    def test_valid_telemetry_all_fields(self):
        """Test valid telemetry with all fields."""
        now = datetime.now()
        data = {
            "voltage": 12.5,
            "temperature": 25.0,
            "gyro": 0.05,
            "current": 1.5,
            "wheel_speed": 5000.0,
            "cpu_usage": 45.5,
            "memory_usage": 60.2,
            "network_latency": 15.3,
            "disk_io": 120.5,
            "error_rate": 0.5,
            "response_time": 25.0,
            "active_connections": 10,
            "timestamp": now
        }
        telemetry = TelemetryInput(**data)
        assert telemetry.voltage == 12.5
        assert telemetry.current == 1.5
        assert telemetry.cpu_usage == 45.5
        assert telemetry.timestamp == now
    
    def test_voltage_boundary_values(self):
        """Test voltage field boundary constraints (0-50V)."""
        telemetry = TelemetryInput(voltage=0, temperature=25.0, gyro=0.05)
        assert telemetry.voltage == 0
        
        telemetry = TelemetryInput(voltage=50, temperature=25.0, gyro=0.05)
        assert telemetry.voltage == 50
        
        with pytest.raises(ValidationError) as exc_info:
            TelemetryInput(voltage=-0.1, temperature=25.0, gyro=0.05)
        assert "voltage" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError) as exc_info:
            TelemetryInput(voltage=50.1, temperature=25.0, gyro=0.05)
        assert "voltage" in str(exc_info.value).lower()
    
    def test_temperature_boundary_values(self):
        """Test temperature field boundary constraints (-100 to 150°C)."""
        telemetry = TelemetryInput(voltage=12.5, temperature=-100, gyro=0.05)
        assert telemetry.temperature == -100
        
        telemetry = TelemetryInput(voltage=12.5, temperature=150, gyro=0.05)
        assert telemetry.temperature == 150
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=-100.1, gyro=0.05)
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=150.1, gyro=0.05)
    
    def test_cpu_usage_boundary_values(self):
        """Test CPU usage percentage constraints (0-100%)."""
        telemetry = TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, cpu_usage=0)
        assert telemetry.cpu_usage == 0
        
        telemetry = TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, cpu_usage=100)
        assert telemetry.cpu_usage == 100
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, cpu_usage=-0.1)
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, cpu_usage=100.1)
    
    def test_memory_usage_boundary_values(self):
        """Test memory usage percentage constraints (0-100%)."""
        telemetry = TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, memory_usage=0)
        assert telemetry.memory_usage == 0
        
        telemetry = TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, memory_usage=100)
        assert telemetry.memory_usage == 100
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, memory_usage=-1)
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, memory_usage=101)
    
    def test_non_negative_optional_fields(self):
        """Test non-negative constraints on optional fields."""
        telemetry = TelemetryInput(
            voltage=12.5, temperature=25.0, gyro=0.05,
            current=0, wheel_speed=0, network_latency=0,
            disk_io=0, error_rate=0, response_time=0,
            active_connections=0
        )
        assert telemetry.current == 0
        assert telemetry.wheel_speed == 0
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, current=-0.1)
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, wheel_speed=-1)
        
        with pytest.raises(ValidationError):
            TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, network_latency=-1)
    
    def test_timestamp_auto_generation_when_none(self):
        """Test timestamp validator generates timestamp when explicitly set to None."""
        before = datetime.now()
        telemetry = TelemetryInput(voltage=12.5, temperature=25.0, gyro=0.05, timestamp=None)
        after = datetime.now()
        
        assert telemetry.timestamp is not None
        assert before <= telemetry.timestamp <= after
    
    def test_timestamp_custom_value(self):
        """Test custom timestamp is preserved."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        telemetry = TelemetryInput(
            voltage=12.5, temperature=25.0, gyro=0.05,
            timestamp=custom_time
        )
        assert telemetry.timestamp == custom_time
    
    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryInput(temperature=25.0, gyro=0.05)
        assert "voltage" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError) as exc_info:
            TelemetryInput(voltage=12.5, gyro=0.05)
        assert "temperature" in str(exc_info.value).lower()
        
        with pytest.raises(ValidationError) as exc_info:
            TelemetryInput(voltage=12.5, temperature=25.0)
        assert "gyro" in str(exc_info.value).lower()
    
    def test_type_validation(self):
        """Test type validation for fields."""
        with pytest.raises(ValidationError):
            TelemetryInput(voltage="invalid", temperature=25.0, gyro=0.05)
        
        with pytest.raises(ValidationError):
            TelemetryInput(
                voltage=12.5, temperature=25.0, gyro=0.05,
                active_connections="invalid"
            )
class TestTelemetryBatch:
    """Test TelemetryBatch model validation."""
    
    def test_valid_batch_single_item(self):
        """Test valid batch with single telemetry point."""
        telemetry_data = {
            "voltage": 12.5,
            "temperature": 25.0,
            "gyro": 0.05
        }
        batch = TelemetryBatch(telemetry=[telemetry_data])
        assert len(batch.telemetry) == 1
        assert batch.telemetry[0].voltage == 12.5
    
    def test_valid_batch_multiple_items(self):
        """Test valid batch with multiple telemetry points."""
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05},
            {"voltage": 13.0, "temperature": 26.0, "gyro": 0.06},
            {"voltage": 12.8, "temperature": 25.5, "gyro": 0.055}
        ]
        batch = TelemetryBatch(telemetry=telemetry_list)
        assert len(batch.telemetry) == 3
        assert batch.telemetry[1].voltage == 13.0
    
    def test_batch_minimum_size(self):
        """Test batch requires at least 1 item."""
        with pytest.raises(ValidationError) as exc_info:
            TelemetryBatch(telemetry=[])
        assert "telemetry" in str(exc_info.value).lower()
    
    def test_batch_maximum_size(self):
        """Test batch maximum size constraint (1000 items)."""
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05}
            for _ in range(1000)
        ]
        batch = TelemetryBatch(telemetry=telemetry_list)
        assert len(batch.telemetry) == 1000
        
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05}
            for _ in range(1001)
        ]
        with pytest.raises(ValidationError) as exc_info:
            TelemetryBatch(telemetry=telemetry_list)
        assert "telemetry" in str(exc_info.value).lower()
class TestAnomalyResponse:
    """Test AnomalyResponse model validation."""
    
    def test_valid_anomaly_response(self):
        """Test valid anomaly response with all fields."""
        data = {
            "is_anomaly": True,
            "anomaly_score": 0.85,
            "anomaly_type": "thermal_fault",
            "severity_score": 0.75,
            "severity_level": "HIGH",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "THERMAL_REGULATION",
            "escalation_level": "LEVEL_2",
            "is_allowed": False,
            "allowed_actions": ["monitor", "log"],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.92,
            "reasoning": "Temperature exceeds normal operating range",
            "recurrence_count": 3,
            "timestamp": datetime.now()
        }
        response = AnomalyResponse(**data)
        assert response.is_anomaly is True
        assert response.anomaly_score == 0.85
        assert response.recurrence_count == 3
    
    def test_anomaly_score_boundary_values(self):
        """Test anomaly_score constraints (0-1)."""
        base_data = {
            "is_anomaly": True,
            "anomaly_type": "test",
            "severity_score": 0.5,
            "severity_level": "MEDIUM",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "monitor",
            "escalation_level": "LEVEL_1",
            "is_allowed": True,
            "allowed_actions": [],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.8,
            "reasoning": "test",
            "recurrence_count": 0,
            "timestamp": datetime.now()
        }
        
        response = AnomalyResponse(**{**base_data, "anomaly_score": 0})
        assert response.anomaly_score == 0
        
        response = AnomalyResponse(**{**base_data, "anomaly_score": 1})
        assert response.anomaly_score == 1
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "anomaly_score": -0.1})
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "anomaly_score": 1.1})
    
    def test_severity_score_boundary_values(self):
        """Test severity_score constraints (0-1)."""
        base_data = {
            "is_anomaly": True,
            "anomaly_score": 0.5,
            "anomaly_type": "test",
            "severity_level": "MEDIUM",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "monitor",
            "escalation_level": "LEVEL_1",
            "is_allowed": True,
            "allowed_actions": [],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.8,
            "reasoning": "test",
            "recurrence_count": 0,
            "timestamp": datetime.now()
        }
        
        response = AnomalyResponse(**{**base_data, "severity_score": 0})
        assert response.severity_score == 0
        
        response = AnomalyResponse(**{**base_data, "severity_score": 1})
        assert response.severity_score == 1
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "severity_score": -0.01})
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "severity_score": 1.01})
    
    def test_confidence_boundary_values(self):
        """Test confidence constraints (0-1)."""
        base_data = {
            "is_anomaly": True,
            "anomaly_score": 0.5,
            "anomaly_type": "test",
            "severity_score": 0.5,
            "severity_level": "MEDIUM",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "monitor",
            "escalation_level": "LEVEL_1",
            "is_allowed": True,
            "allowed_actions": [],
            "should_escalate_to_safe_mode": False,
            "reasoning": "test",
            "recurrence_count": 0,
            "timestamp": datetime.now()
        }
        
        response = AnomalyResponse(**{**base_data, "confidence": 0})
        assert response.confidence == 0
        
        response = AnomalyResponse(**{**base_data, "confidence": 1})
        assert response.confidence == 1
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "confidence": -0.1})
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "confidence": 1.1})
    
    def test_recurrence_count_non_negative(self):
        """Test recurrence_count must be non-negative."""
        base_data = {
            "is_anomaly": True,
            "anomaly_score": 0.5,
            "anomaly_type": "test",
            "severity_score": 0.5,
            "severity_level": "MEDIUM",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "monitor",
            "escalation_level": "LEVEL_1",
            "is_allowed": True,
            "allowed_actions": [],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.8,
            "reasoning": "test",
            "timestamp": datetime.now()
        }
        
        response = AnomalyResponse(**{**base_data, "recurrence_count": 0})
        assert response.recurrence_count == 0
        
        response = AnomalyResponse(**{**base_data, "recurrence_count": 100})
        assert response.recurrence_count == 100
        
        with pytest.raises(ValidationError):
            AnomalyResponse(**{**base_data, "recurrence_count": -1})
class TestBatchAnomalyResponse:
    """Test BatchAnomalyResponse model validation."""
    
    def test_valid_batch_response(self):
        """Test valid batch anomaly response."""
        anomaly_data = {
            "is_anomaly": True,
            "anomaly_score": 0.85,
            "anomaly_type": "thermal_fault",
            "severity_score": 0.75,
            "severity_level": "HIGH",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "THERMAL_REGULATION",
            "escalation_level": "LEVEL_2",
            "is_allowed": False,
            "allowed_actions": ["monitor"],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.92,
            "reasoning": "Temperature exceeds normal range",
            "recurrence_count": 3,
            "timestamp": datetime.now()
        }
        
        data = {
            "total_processed": 10,
            "anomalies_detected": 2,
            "results": [anomaly_data, anomaly_data]
        }
        
        response = BatchAnomalyResponse(**data)
        assert response.total_processed == 10
        assert response.anomalies_detected == 2
        assert len(response.results) == 2
    
    def test_empty_results_list(self):
        """Test batch response with no anomalies detected."""
        data = {
            "total_processed": 10,
            "anomalies_detected": 0,
            "results": []
        }
        
        response = BatchAnomalyResponse(**data)
        assert response.total_processed == 10
        assert response.anomalies_detected == 0
        assert len(response.results) == 0
class TestSystemStatus:
    """Test SystemStatus model validation."""
    
    def test_valid_system_status(self):
        """Test valid system status."""
        data = {
            "status": "healthy",
            "mission_phase": "NOMINAL_OPS",
            "components": {
                "anomaly_detector": {"status": "healthy"},
                "policy_engine": {"status": "healthy"}
            },
            "uptime_seconds": 3600.5,
            "timestamp": datetime.now()
        }
        
        status = SystemStatus(**data)
        assert status.status == "healthy"
        assert status.mission_phase == "NOMINAL_OPS"
        assert status.uptime_seconds == 3600.5
        assert "anomaly_detector" in status.components
    
    def test_empty_components_dict(self):
        """Test system status with empty components."""
        data = {
            "status": "degraded",
            "mission_phase": "SAFE_MODE",
            "components": {},
            "uptime_seconds": 100.0,
            "timestamp": datetime.now()
        }
        
        status = SystemStatus(**data)
        assert status.components == {}
class TestPhaseUpdateRequest:
    """Test PhaseUpdateRequest model validation."""
    
    def test_valid_phase_update_all_phases(self):
        """Test valid phase update for each phase."""
        for phase in MissionPhaseEnum:
            request = PhaseUpdateRequest(phase=phase)
            assert request.phase == phase
            assert request.force is False  # Default value
    
    def test_phase_update_with_force(self):
        """Test phase update with force flag."""
        request = PhaseUpdateRequest(
            phase=MissionPhaseEnum.SAFE_MODE,
            force=True
        )
        assert request.phase == MissionPhaseEnum.SAFE_MODE
        assert request.force is True
    
    def test_invalid_phase_value(self):
        """Test invalid phase value is rejected."""
        with pytest.raises(ValidationError):
            PhaseUpdateRequest(phase="INVALID_PHASE")
class TestPhaseUpdateResponse:
    """Test PhaseUpdateResponse model validation."""
    
    def test_valid_phase_update_response(self):
        """Test valid phase update response."""
        data = {
            "success": True,
            "previous_phase": "NOMINAL_OPS",
            "new_phase": "SAFE_MODE",
            "message": "Phase transition successful",
            "timestamp": datetime.now()
        }
        
        response = PhaseUpdateResponse(**data)
        assert response.success is True
        assert response.previous_phase == "NOMINAL_OPS"
        assert response.new_phase == "SAFE_MODE"
    
    def test_failed_phase_update_response(self):
        """Test failed phase update response."""
        data = {
            "success": False,
            "previous_phase": "NOMINAL_OPS",
            "new_phase": "NOMINAL_OPS",
            "message": "Invalid phase transition",
            "timestamp": datetime.now()
        }
        
        response = PhaseUpdateResponse(**data)
        assert response.success is False
class TestMemoryStats:
    """Test MemoryStats model validation."""
    
    def test_valid_memory_stats(self):
        """Test valid memory statistics."""
        data = {
            "total_events": 1000,
            "critical_events": 25,
            "avg_age_hours": 12.5,
            "max_recurrence": 5,
            "timestamp": datetime.now()
        }
        
        stats = MemoryStats(**data)
        assert stats.total_events == 1000
        assert stats.critical_events == 25
        assert stats.avg_age_hours == 12.5
        assert stats.max_recurrence == 5
    
    def test_zero_values(self):
        """Test memory stats with zero values."""
        data = {
            "total_events": 0,
            "critical_events": 0,
            "avg_age_hours": 0.0,
            "max_recurrence": 0,
            "timestamp": datetime.now()
        }
        
        stats = MemoryStats(**data)
        assert stats.total_events == 0
        assert stats.critical_events == 0
class TestAnomalyHistoryQuery:
    """Test AnomalyHistoryQuery model validation."""
    
    def test_valid_query_with_defaults(self):
        """Test query with default values."""
        query = AnomalyHistoryQuery()
        assert query.start_time is None
        assert query.end_time is None
        assert query.limit == 100  # Default
        assert query.severity_min is None
    
    def test_valid_query_with_all_parameters(self):
        """Test query with all parameters."""
        start = datetime.now() - timedelta(days=7)
        end = datetime.now()
        
        query = AnomalyHistoryQuery(
            start_time=start,
            end_time=end,
            limit=500,
            severity_min=0.7
        )
        
        assert query.start_time == start
        assert query.end_time == end
        assert query.limit == 500
        assert query.severity_min == 0.7
    
    def test_limit_boundary_values(self):
        """Test limit constraints (1-1000)."""
        query = AnomalyHistoryQuery(limit=1)
        assert query.limit == 1
        
        query = AnomalyHistoryQuery(limit=1000)
        assert query.limit == 1000
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(limit=0)
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(limit=1001)
    
    def test_severity_min_boundary_values(self):
        """Test severity_min constraints (0-1)."""
        query = AnomalyHistoryQuery(severity_min=0)
        assert query.severity_min == 0
        
        query = AnomalyHistoryQuery(severity_min=1)
        assert query.severity_min == 1
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(severity_min=-0.1)
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(severity_min=1.1)
class TestAnomalyHistoryResponse:
    """Test AnomalyHistoryResponse model validation."""
    
    def test_valid_history_response(self):
        """Test valid anomaly history response."""
        anomaly_data = {
            "is_anomaly": True,
            "anomaly_score": 0.85,
            "anomaly_type": "thermal_fault",
            "severity_score": 0.75,
            "severity_level": "HIGH",
            "mission_phase": "NOMINAL_OPS",
            "recommended_action": "THERMAL_REGULATION",
            "escalation_level": "LEVEL_2",
            "is_allowed": False,
            "allowed_actions": ["monitor"],
            "should_escalate_to_safe_mode": False,
            "confidence": 0.92,
            "reasoning": "Temperature exceeds normal range",
            "recurrence_count": 3,
            "timestamp": datetime.now()
        }
        
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()
        
        data = {
            "count": 2,
            "anomalies": [anomaly_data, anomaly_data],
            "start_time": start,
            "end_time": end
        }
        
        response = AnomalyHistoryResponse(**data)
        assert response.count == 2
        assert len(response.anomalies) == 2
        assert response.start_time == start
        assert response.end_time == end
    
    def test_empty_history_response(self):
        """Test history response with no anomalies."""
        data = {
            "count": 0,
            "anomalies": [],
            "start_time": None,
            "end_time": None
        }
        
        response = AnomalyHistoryResponse(**data)
        assert response.count == 0
        assert len(response.anomalies) == 0
class TestHealthCheckResponse:
    """Test HealthCheckResponse model validation."""
    
    def test_valid_health_check_minimal(self):
        """Test health check with minimal required fields."""
        data = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now()
        }
        
        response = HealthCheckResponse(**data)
        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.uptime_seconds is None
        assert response.mission_phase is None
        assert response.components_status is None
        assert response.error is None
    
    def test_valid_health_check_all_fields(self):
        """Test health check with all fields."""
        data = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now(),
            "uptime_seconds": 3600.5,
            "mission_phase": "NOMINAL_OPS",
            "components_status": {
                "anomaly_detector": {"status": "healthy", "latency_ms": 10.5},
                "policy_engine": {"status": "healthy", "latency_ms": 5.2}
            },
            "error": None
        }
        
        response = HealthCheckResponse(**data)
        assert response.uptime_seconds == 3600.5
        assert response.mission_phase == "NOMINAL_OPS"
        assert "anomaly_detector" in response.components_status
    
    def test_health_check_with_error(self):
        """Test health check with error status."""
        data = {
            "status": "unhealthy",
            "version": "1.0.0",
            "timestamp": datetime.now(),
            "error": "Database connection failed"
        }
        
        response = HealthCheckResponse(**data)
        assert response.status == "unhealthy"
        assert response.error == "Database connection failed"
class TestUserCreateRequest:
    """Test UserCreateRequest model validation."""
    
    def test_valid_user_create_minimal(self):
        """Test user creation with minimal fields."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "role": UserRole.ANALYST
        }
        
        request = UserCreateRequest(**data)
        assert request.username == "testuser"
        assert request.email == "test@example.com"
        assert request.role == UserRole.ANALYST
        assert request.password is None
    
    def test_valid_user_create_all_fields(self):
        """Test user creation with all fields."""
        data = {
            "username": "adminuser",
            "email": "admin@example.com",
            "role": UserRole.ADMIN,
            "password": "securepassword123"
        }
        
        request = UserCreateRequest(**data)
        assert request.username == "adminuser"
        assert request.role == UserRole.ADMIN
        assert request.email == "admin@example.com"
        assert request.password == "securepassword123"
    
    def test_username_length_constraints(self):
        """Test username length validation (min: 3, max: 50)."""
        request = UserCreateRequest(username="abc", email="test@example.com", role=UserRole.ANALYST)
        assert request.username == "abc"
        
        request = UserCreateRequest(username="a" * 50, email="test@example.com", role=UserRole.ANALYST)
        assert len(request.username) == 50
        
        with pytest.raises(ValidationError):
            UserCreateRequest(username="ab", email="test@example.com", role=UserRole.ANALYST)
        
        with pytest.raises(ValidationError):
            UserCreateRequest(username="a" * 51, email="test@example.com", role=UserRole.ANALYST)
    
    def test_password_length_constraint(self):
        """Test password minimum length (min: 8)."""
        request = UserCreateRequest(username="testuser", email="test@example.com", role=UserRole.ANALYST, password="12345678")
        assert len(request.password) == 8
        
        with pytest.raises(ValidationError):
            UserCreateRequest(username="testuser", email="test@example.com", role=UserRole.ANALYST, password="1234567")
class TestUserResponse:
    """Test UserResponse model validation."""
    
    def test_valid_user_response(self):
        """Test valid user response."""
        data = {
            "id": "user_123",
            "username": "testuser",
            "role": UserRole.OPERATOR,
            "email": "test@example.com",
            "created_at": datetime.now(),
            "is_active": True
        }
        
        response = UserResponse(**data)
        assert response.id == "user_123"
        assert response.username == "testuser"
        assert response.role == UserRole.OPERATOR
        assert response.is_active is True
    
    def test_user_response_without_email(self):
        """Test user response - email is required."""
        data = {
            "id": "user_123",
            "username": "testuser",
            "email": "test@example.com",
            "role": UserRole.ANALYST,
            "created_at": datetime.now(),
            "is_active": True
        }
        
        response = UserResponse(**data)
        assert response.email == "test@example.com"
class TestAPIKeyCreateRequest:
    """Test APIKeyCreateRequest model validation."""
    
    def test_valid_api_key_create_minimal(self):
        """Test API key creation with minimal fields."""
        data = {
            "name": "My API Key",
            "permissions": ["read"]
        }
        
        request = APIKeyCreateRequest(**data)
        assert request.name == "My API Key"
        assert request.permissions == ["read"]
    
    def test_valid_api_key_create_all_fields(self):
        """Test API key creation with all fields."""
        data = {
            "name": "Production Key",
            "permissions": ["read", "write", "admin"]
        }
        
        request = APIKeyCreateRequest(**data)
        assert request.name == "Production Key"
        assert request.permissions == ["read", "write", "admin"]
    
    def test_name_length_constraints(self):
        """Test name length validation (min: 1, max: 100)."""
        request = APIKeyCreateRequest(name="A", permissions=["read"])
        assert request.name == "A"
        
        request = APIKeyCreateRequest(name="A" * 100, permissions=["read"])
        assert len(request.name) == 100
        
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="", permissions=["read"])
        
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="A" * 101, permissions=["read"])
    
    def test_permissions_min_length(self):
        """Test permissions field requires at least 1 item."""
        request = APIKeyCreateRequest(name="Key", permissions=["read"])
        assert len(request.permissions) == 1
        
        request = APIKeyCreateRequest(name="Key", permissions=["read", "write"])
        assert len(request.permissions) == 2
        
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="Key", permissions=[])
class TestAPIKeyResponse:
    """Test APIKeyResponse model validation."""
    
    def test_valid_api_key_response(self):
        """Test valid API key response."""
        data = {
            "id": "key_123",
            "name": "My API Key",
            "permissions": ["read", "write"],
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=90),
            "last_used": datetime.now()
        }
        
        response = APIKeyResponse(**data)
        assert response.id == "key_123"
        assert response.name == "My API Key"
        assert response.permissions == ["read", "write"]
    
    def test_api_key_response_optional_fields(self):
        """Test API key response with optional fields as None."""
        data = {
            "id": "key_123",
            "name": "My API Key",
            "permissions": [],
            "created_at": datetime.now(),
            "expires_at": None,
            "last_used": None
        }
        
        response = APIKeyResponse(**data)
        assert response.expires_at is None
        assert response.last_used is None
class TestAPIKeyCreateResponse:
    """Test APIKeyCreateResponse model validation."""
    
    def test_valid_api_key_create_response(self):
        """Test valid API key creation response with secret."""
        data = {
            "id": "key_123",
            "name": "My API Key",
            "key": "sk_test_1234567890abcdef",
            "permissions": ["read"],
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=90)
        }
        
        response = APIKeyCreateResponse(**data)
        assert response.key == "sk_test_1234567890abcdef"
        assert response.id == "key_123"
class TestLoginRequest:
    """Test LoginRequest model validation."""
    
    def test_valid_login_request(self):
        """Test valid login request."""
        data = {
            "username": "testuser",
            "password": "securepassword123"
        }
        
        request = LoginRequest(**data)
        assert request.username == "testuser"
        assert request.password == "securepassword123"
    
    def test_missing_credentials(self):
        """Test login request with missing credentials."""
        with pytest.raises(ValidationError):
            LoginRequest(password="password123")
        
        with pytest.raises(ValidationError):
            LoginRequest(username="testuser")
class TestTokenResponse:
    """Test TokenResponse model validation."""
    
    def test_valid_token_response(self):
        """Test valid token response."""
        data = {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        
        response = TokenResponse(**data)
        assert response.access_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        assert response.token_type == "bearer"
    
    def test_custom_token_type(self):
        """Test token response with custom token type."""
        data = {
            "access_token": "token123",
            "token_type": "custom"
        }
        
        response = TokenResponse(**data)
        assert response.token_type == "custom"
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_nested_model_validation(self):
        """Test validation of nested models in lists."""
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05},
            {"voltage": 13.0, "temperature": 26.0, "gyro": 0.06}
        ]
        batch = TelemetryBatch(telemetry=telemetry_list)
        assert len(batch.telemetry) == 2
        
        invalid_telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05},
            {"voltage": -1, "temperature": 26.0, "gyro": 0.06}  # Invalid voltage
        ]
        with pytest.raises(ValidationError):
            TelemetryBatch(telemetry=invalid_telemetry_list)
    
    def test_datetime_serialization(self):
        """Test datetime fields can be serialized and deserialized."""
        now = datetime.now()
        telemetry = TelemetryInput(
            voltage=12.5,
            temperature=25.0,
            gyro=0.05,
            timestamp=now
        )
        
        data_dict = telemetry.model_dump()
        assert data_dict["timestamp"] == now
        
        telemetry2 = TelemetryInput(**data_dict)
        assert telemetry2.timestamp == now
    
    def test_enum_string_conversion(self):
        """Test enum fields accept string values."""
        phase_request = PhaseUpdateRequest(phase="SAFE_MODE")
        assert phase_request.phase == MissionPhaseEnum.SAFE_MODE
    
    def test_optional_fields_none_vs_missing(self):
        """Test optional fields can be None or omitted."""
        telemetry1 = TelemetryInput(
            voltage=12.5,
            temperature=25.0,
            gyro=0.05,
            current=None
        )
        assert telemetry1.current is None
        
        telemetry2 = TelemetryInput(
            voltage=12.5,
            temperature=25.0,
            gyro=0.05
        )
        assert telemetry2.current is None
    
    def test_float_to_int_coercion(self):
        """Test numeric type coercion."""
        telemetry = TelemetryInput(
            voltage=12.5,
            temperature=25.0,
            gyro=0.05,
            active_connections=10.0  # Float instead of int
        )
        assert telemetry.active_connections == 10
        assert isinstance(telemetry.active_connections, int)
    
    def test_list_field_validation(self):
        """Test list field validation."""
        response = AnomalyResponse(
            is_anomaly=True,
            anomaly_score=0.5,
            anomaly_type="test",
            severity_score=0.5,
            severity_level="MEDIUM",
            mission_phase="NOMINAL_OPS",
            recommended_action="monitor",
            escalation_level="LEVEL_1",
            is_allowed=True,
            allowed_actions=["action1", "action2", "action3"],
            should_escalate_to_safe_mode=False,
            confidence=0.8,
            reasoning="test",
            recurrence_count=0,
            timestamp=datetime.now()
        )
        assert len(response.allowed_actions) == 3
        
        response2 = AnomalyResponse(
            is_anomaly=True,
            anomaly_score=0.5,
            anomaly_type="test",
            severity_score=0.5,
            severity_level="MEDIUM",
            mission_phase="NOMINAL_OPS",
            recommended_action="monitor",
            escalation_level="LEVEL_1",
            is_allowed=True,
            allowed_actions=[],
            should_escalate_to_safe_mode=False,
            confidence=0.8,
            reasoning="test",
            recurrence_count=0,
            timestamp=datetime.now()
        )
        assert len(response2.allowed_actions) == 0


class TestModelValidationError:
    """Test ModelValidationError exception."""

    def test_model_validation_error_creation(self):
        """Test ModelValidationError can be created with context."""
        error = ModelValidationError(
            message="Validation failed",
            field_name="voltage",
            provided_value=-5.0,
            constraints={"ge": 0, "le": 50}
        )
        assert error.message == "Validation failed"
        assert error.field_name == "voltage"
        assert error.provided_value == -5.0
        assert error.constraints["ge"] == 0

    def test_model_validation_error_to_dict(self):
        """Test ModelValidationError can be serialized to dict."""
        error = ModelValidationError(
            message="Test error",
            field_name="test_field",
            provided_value="invalid",
            constraints={"max_length": 10}
        )
        error_dict = error.to_dict()
        assert error_dict["error_type"] == "ModelValidationError"
        assert error_dict["message"] == "Test error"
        assert error_dict["field_name"] == "test_field"


class TestTelemetryInputEdgeCases:
    """Test TelemetryInput edge cases with new validators."""

    def test_timestamp_iso_format_with_z(self):
        """Test timestamp parsing with Z suffix."""
        telemetry = TelemetryInput(
            voltage=12.5, temperature=25.0, gyro=0.05,
            timestamp="2024-01-15T10:30:00Z"
        )
        assert telemetry.timestamp is not None
        assert telemetry.timestamp.year == 2024
        assert telemetry.timestamp.month == 1

    def test_timestamp_invalid_string_uses_current(self, caplog):
        """Test invalid timestamp string falls back to current time."""
        import logging
        with caplog.at_level(logging.WARNING):
            telemetry = TelemetryInput(
                voltage=12.5, temperature=25.0, gyro=0.05,
                timestamp="invalid-timestamp"
            )
            assert telemetry.timestamp is not None
            assert "timestamp_parsing_failed" in caplog.text

    def test_timestamp_type_unknown_logs_warning(self, caplog):
        """Test unknown timestamp type logs warning and uses current time."""
        import logging
        with caplog.at_level(logging.WARNING):
            telemetry = TelemetryInput(
                voltage=12.5, temperature=25.0, gyro=0.05,
                timestamp=12345
            )
            assert telemetry.timestamp is not None
            assert "timestamp_type_invalid" in caplog.text


class TestTelemetryBatchEdgeCases:
    """Test TelemetryBatch edge cases with new validators."""

    def test_batch_maximum_size_enforced(self):
        """Test batch maximum size constraint is enforced."""
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05}
            for _ in range(1000)
        ]
        batch = TelemetryBatch(telemetry=telemetry_list)
        assert len(batch.telemetry) == 1000
        
        telemetry_list = [
            {"voltage": 12.5, "temperature": 25.0, "gyro": 0.05}
            for _ in range(1001)
        ]
        with pytest.raises(ValidationError):
            TelemetryBatch(telemetry=telemetry_list)


class TestAnomalyHistoryQueryEdgeCases:
    """Test AnomalyHistoryQuery edge cases with new validators."""

    def test_limit_boundary_values_enforced(self):
        """Test limit constraints are enforced."""
        query = AnomalyHistoryQuery(limit=1)
        assert query.limit == 1
        
        query = AnomalyHistoryQuery(limit=1000)
        assert query.limit == 1000
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(limit=0)
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(limit=1001)

    def test_severity_min_boundary_values_enforced(self):
        """Test severity_min constraints are enforced."""
        query = AnomalyHistoryQuery(severity_min=0)
        assert query.severity_min == 0
        
        query = AnomalyHistoryQuery(severity_min=1)
        assert query.severity_min == 1
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(severity_min=-0.1)
        
        with pytest.raises(ValidationError):
            AnomalyHistoryQuery(severity_min=1.1)

    def test_datetime_invalid_parsed_as_none(self, caplog):
        """Test invalid datetime string is parsed as None with warning."""
        import logging
        with caplog.at_level(logging.WARNING):
            query = AnomalyHistoryQuery(start_time="invalid-date")
            assert query.start_time is None
            assert "datetime_parse_failed" in caplog.text

    def test_datetime_iso_format_with_z(self):
        """Test datetime parsing with Z suffix."""
        query = AnomalyHistoryQuery(start_time="2024-01-15T10:30:00Z")
        assert query.start_time is not None
        assert query.start_time.year == 2024


class TestPhaseUpdateRequestEdgeCases:
    """Test PhaseUpdateRequest edge cases with new validators."""

    def test_phase_string_normalized(self, caplog):
        """Test lowercase phase string is normalized to enum."""
        import logging
        with caplog.at_level(logging.INFO):
            request = PhaseUpdateRequest(phase="safe_mode")
            assert request.phase == MissionPhaseEnum.SAFE_MODE
            assert "phase_normalized" in caplog.text

    def test_invalid_phase_logged_with_valid_values(self, caplog):
        """Test invalid phase logs valid options."""
        import logging
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError):
                PhaseUpdateRequest(phase="INVALID_PHASE")
            assert "invalid_phase_value" in caplog.text

    def test_phase_wrong_type_raises_type_error(self):
        """Test wrong type for phase raises TypeError."""
        with pytest.raises(TypeError):
            PhaseUpdateRequest(phase=123)


class TestUserCreateRequestEdgeCases:
    """Test UserCreateRequest edge cases with new validators."""

    def test_username_whitespace_only_rejected(self):
        """Test username that is only whitespace is rejected."""
        with pytest.raises(ValidationError):
            UserCreateRequest(
                username="   ",
                email="test@example.com",
                role=UserRole.ANALYST
            )

    def test_username_special_prefix_logged(self, caplog):
        """Test username starting with special char is logged."""
        import logging
        with caplog.at_level(logging.WARNING):
            request = UserCreateRequest(
                username="_specialuser",
                email="test@example.com",
                role=UserRole.ANALYST
            )
            assert request.username == "_specialuser"
            assert "username_starts_with_special" in caplog.text

    def test_username_normalized_to_lowercase(self):
        """Test username is normalized to lowercase."""
        request = UserCreateRequest(
            username="TestUser",
            email="test@example.com",
            role=UserRole.ANALYST
        )
        assert request.username == "testuser"

    def test_password_minimum_length_enforced(self):
        """Test password minimum length is enforced."""
        with pytest.raises(ValidationError):
            UserCreateRequest(
                username="testuser",
                email="test@example.com",
                role=UserRole.ANALYST,
                password="short"
            )


class TestAPIKeyCreateRequestEdgeCases:
    """Test APIKeyCreateRequest edge cases with new validators."""

    def test_api_key_name_empty_rejected(self):
        """Test empty API key name is rejected."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="", permissions=["read"])

    def test_api_key_name_whitespace_only_rejected(self):
        """Test whitespace-only API key name is rejected."""
        with pytest.raises(ValidationError):
            APIKeyCreateRequest(name="   ", permissions=["read"])

    def test_api_key_name_logged_when_valid(self, caplog):
        """Test valid API key name is logged."""
        import logging
        with caplog.at_level(logging.INFO):
            request = APIKeyCreateRequest(name="My Key", permissions=["read"])
            assert "api_key_name_valid" in caplog.text

    def test_invalid_permissions_logged(self, caplog):
        """Test invalid permissions are logged with warning."""
        import logging
        with caplog.at_level(logging.WARNING):
            request = APIKeyCreateRequest(
                name="Test Key",
                permissions=["read", "invalid_perm"]
            )
            assert "invalid_permissions_provided" in caplog.text
            assert "invalid_perm" in caplog.text
            assert request.permissions == ["read", "invalid_perm"]

    def test_permissions_case_normalized(self):
        """Test permissions are normalized to lowercase."""
        request = APIKeyCreateRequest(
            name="Test Key",
            permissions=["READ", "WRITE"]
        )
        assert request.permissions == ["read", "write"]


class TestLoginRequestEdgeCases:
    """Test LoginRequest edge cases with new validators."""

    def test_username_empty_rejected(self):
        """Test empty username is rejected."""
        with pytest.raises(ValidationError):
            LoginRequest(username="", password="password123")

    def test_username_whitespace_only_rejected(self):
        """Test whitespace-only username is rejected."""
        with pytest.raises(ValidationError):
            LoginRequest(username="   ", password="password123")

    def test_username_normalized_to_lowercase(self):
        """Test username is normalized to lowercase."""
        request = LoginRequest(username="TestUser", password="password123")
        assert request.username == "testuser"