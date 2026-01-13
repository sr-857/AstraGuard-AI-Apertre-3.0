"""
Unit Tests for Fallback Manager

Tests manager orchestration, mode transitions, storage integration, and callbacks.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from backend.fallback.manager import FallbackManager, FallbackMode
from backend.storage import MemoryStorage


@pytest.fixture
def storage():
    """Provide clean in-memory storage for each test."""
    return MemoryStorage()


@pytest.fixture
def mock_circuit_breaker():
    """Provide mock circuit breaker."""
    return Mock()


@pytest.fixture
def mock_anomaly_detector():
    """Provide mock ML anomaly detector."""
    detector = Mock()
    detector.detect_anomaly = AsyncMock(return_value={
        "anomaly": True,
        "confidence": 0.9,
        "mode": "primary"
    })
    return detector


@pytest.fixture
def mock_heuristic_detector():
    """Provide mock heuristic detector."""
    detector = Mock()
    detector.detect_anomaly = AsyncMock(return_value={
        "anomaly": True,
        "confidence": 0.7,
        "mode": "heuristic"
    })
    return detector


@pytest.fixture
def manager(storage, mock_circuit_breaker, mock_anomaly_detector, mock_heuristic_detector):
    """Provide configured fallback manager."""
    return FallbackManager(
        storage=storage,
        circuit_breaker=mock_circuit_breaker,
        anomaly_detector=mock_anomaly_detector,
        heuristic_detector=mock_heuristic_detector,
    )


class TestManagerInitialization:
    """Test manager initialization."""

    @pytest.mark.asyncio
    async def test_init_default_mode(self, manager):
        """Test manager starts in PRIMARY mode."""
        assert manager.get_current_mode() == FallbackMode.PRIMARY
        assert manager.get_mode_string() == "primary"

    @pytest.mark.asyncio
    async def test_init_with_custom_config(self, storage):
        """Test initialization with custom config."""
        config = {"custom_setting": "value"}
        manager = FallbackManager(storage=storage, config=config)
        assert manager.config["custom_setting"] == "value"

    @pytest.mark.asyncio
    async def test_init_without_detectors(self, storage):
        """Test initialization without detectors."""
        manager = FallbackManager(storage=storage)
        assert manager.anomaly_detector is None
        assert manager.heuristic_detector is None


class TestModeCascade:
    """Test automatic mode cascading based on health state."""

    @pytest.mark.asyncio
    async def test_cascade_stays_primary_when_healthy(self, manager):
        """Test staying in PRIMARY mode when system is healthy."""
        health_state = {
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        mode = await manager.cascade(health_state)
        assert mode == FallbackMode.PRIMARY

    @pytest.mark.asyncio
    async def test_cascade_to_heuristic_on_circuit_open(self, manager):
        """Test cascading to HEURISTIC when circuit breaker opens."""
        health_state = {
            "circuit_breaker": {"state": "OPEN", "open_duration_seconds": 10},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        mode = await manager.cascade(health_state)
        assert mode == FallbackMode.HEURISTIC

    @pytest.mark.asyncio
    async def test_cascade_to_heuristic_on_high_retries(self, manager):
        """Test cascading to HEURISTIC on high retry failures."""
        health_state = {
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"failures_1h": 60},
            "system": {"failed_components": 0},
        }
        
        mode = await manager.cascade(health_state)
        assert mode == FallbackMode.HEURISTIC

    @pytest.mark.asyncio
    async def test_cascade_to_safe_on_multiple_failures(self, manager):
        """Test cascading to SAFE mode on multiple component failures."""
        health_state = {
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 2},
        }
        
        mode = await manager.cascade(health_state)
        assert mode == FallbackMode.SAFE

    @pytest.mark.asyncio
    async def test_cascade_no_transition_if_already_in_mode(self, manager):
        """Test no transition occurs if already in target mode."""
        health_state = {
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        # Already in PRIMARY
        initial_transitions = len(manager.get_transitions_log())
        mode = await manager.cascade(health_state)
        
        assert mode == FallbackMode.PRIMARY
        assert len(manager.get_transitions_log()) == initial_transitions


class TestModeTransitions:
    """Test mode transition tracking and callbacks."""

    @pytest.mark.asyncio
    async def test_transition_recorded_in_log(self, manager):
        """Test that transitions are recorded in log."""
        health_state = {
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        await manager.cascade(health_state)
        
        transitions = manager.get_transitions_log()
        assert len(transitions) == 1
        assert transitions[0]["from"] == "primary"
        assert transitions[0]["to"] == "heuristic"
        assert "timestamp" in transitions[0]
        assert "reason" in transitions[0]

    @pytest.mark.asyncio
    async def test_transition_reason_contains_context(self, manager):
        """Test that transition reason contains health context."""
        health_state = {
            "circuit_breaker": {"state": "OPEN", "open_duration_seconds": 15},
            "retry": {"failures_1h": 60},
            "system": {"failed_components": 0},
        }
        
        await manager.cascade(health_state)
        
        transitions = manager.get_transitions_log()
        reason = transitions[0]["reason"]
        assert "circuit_open" in reason
        assert "high_retry_failures" in reason

    @pytest.mark.asyncio
    async def test_mode_callback_triggered(self, manager):
        """Test that mode callback is triggered on transition."""
        callback_called = False
        
        async def callback():
            nonlocal callback_called
            callback_called = True
        
        manager.register_mode_callback(FallbackMode.HEURISTIC, callback)
        
        health_state = {
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        await manager.cascade(health_state)
        assert callback_called is True

    @pytest.mark.asyncio
    async def test_callback_error_does_not_prevent_transition(self, manager):
        """Test that callback errors don't prevent mode transitions."""
        async def failing_callback():
            raise Exception("Callback failed")
        
        manager.register_mode_callback(FallbackMode.HEURISTIC, failing_callback)
        
        health_state = {
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        # Should not raise exception
        mode = await manager.cascade(health_state)
        assert mode == FallbackMode.HEURISTIC


class TestAnomalyDetection:
    """Test anomaly detection with mode-appropriate detectors."""

    @pytest.mark.asyncio
    async def test_detect_uses_primary_detector_in_primary_mode(
        self, manager, mock_anomaly_detector
    ):
        """Test that PRIMARY mode uses ML detector."""
        data = {"sensor": "value"}
        result = await manager.detect_anomaly(data)
        
        mock_anomaly_detector.detect_anomaly.assert_called_once_with(data)
        assert result["mode"] == "primary"

    @pytest.mark.asyncio
    async def test_detect_uses_heuristic_detector_in_heuristic_mode(
        self, manager, mock_heuristic_detector
    ):
        """Test that HEURISTIC mode uses heuristic detector."""
        # Transition to HEURISTIC
        await manager.set_mode("heuristic")
        
        data = {"sensor": "value"}
        result = await manager.detect_anomaly(data)
        
        mock_heuristic_detector.detect_anomaly.assert_called_once_with(data)
        assert result["mode"] == "heuristic"

    @pytest.mark.asyncio
    async def test_detect_returns_safe_in_safe_mode(self, manager):
        """Test that SAFE mode returns conservative result."""
        await manager.set_mode("safe")
        
        result = await manager.detect_anomaly({"sensor": "value"})
        
        assert result["anomaly"] is False
        assert result["confidence"] == 0.0
        assert result["mode"] == "safe"

    @pytest.mark.asyncio
    async def test_detect_handles_missing_detector(self, storage):
        """Test graceful handling when detector is missing."""
        manager = FallbackManager(storage=storage)  # No detectors
        
        result = await manager.detect_anomaly({"sensor": "value"})
        
        assert result["anomaly"] is False
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_detect_handles_detector_error(self, manager, mock_anomaly_detector):
        """Test error handling in detect_anomaly."""
        mock_anomaly_detector.detect_anomaly.side_effect = Exception("Detector error")
        
        result = await manager.detect_anomaly({"sensor": "value"})
        
        assert result["anomaly"] is False
        assert result["mode"] == "error"
        assert "error" in result


class TestModeManagement:
    """Test manual mode management."""

    @pytest.mark.asyncio
    async def test_set_mode_string(self, manager):
        """Test setting mode via string."""
        success = await manager.set_mode("heuristic")
        
        assert success is True
        assert manager.get_current_mode() == FallbackMode.HEURISTIC

    @pytest.mark.asyncio
    async def test_set_mode_case_insensitive(self, manager):
        """Test that mode strings are case-insensitive."""
        await manager.set_mode("SAFE")
        assert manager.get_current_mode() == FallbackMode.SAFE
        
        await manager.set_mode("Primary")
        assert manager.get_current_mode() == FallbackMode.PRIMARY

    @pytest.mark.asyncio
    async def test_set_mode_invalid_string(self, manager):
        """Test error handling for invalid mode string."""
        success = await manager.set_mode("invalid_mode")
        
        assert success is False
        assert manager.get_current_mode() == FallbackMode.PRIMARY  # Unchanged

    @pytest.mark.asyncio
    async def test_is_degraded(self, manager):
        """Test is_degraded helper."""
        assert manager.is_degraded() is False
        
        await manager.set_mode("heuristic")
        assert manager.is_degraded() is True
        
        await manager.set_mode("safe")
        assert manager.is_degraded() is True

    @pytest.mark.asyncio
    async def test_is_safe_mode(self, manager):
        """Test is_safe_mode helper."""
        assert manager.is_safe_mode() is False
        
        await manager.set_mode("safe")
        assert manager.is_safe_mode() is True


class TestStorageIntegration:
    """Test integration with Storage interface."""

    @pytest.mark.asyncio
    async def test_transitions_persisted_to_storage(self, manager, storage):
        """Test that transitions are persisted to storage."""
        health_state = {
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        await manager.cascade(health_state)
        
        # Check that transition was written to storage
        keys = await storage.keys("fallback:transition:*")
        assert len(keys) > 0

    @pytest.mark.asyncio
    async def test_register_fallback_stores_definition(self, manager, storage):
        """Test that fallback registration persists to storage."""
        async def test_action():
            pass
        
        success = await manager.register_fallback(
            name="test_fallback",
            condition="severity >= 0.8",
            action=test_action,
            metadata={"description": "Test fallback"}
        )
        
        assert success is True
        
        # Check storage
        definition = await storage.get("fallback:definition:test_fallback")
        assert definition is not None

    @pytest.mark.asyncio
    async def test_storage_errors_handled_gracefully(self, manager):
        """Test graceful handling of storage errors."""
        # Create a storage that always fails
        class FailingStorage(MemoryStorage):
            async def set(self, key, value, ttl=None):
                raise Exception("Storage error")
        
        failing_manager = FallbackManager(storage=FailingStorage())
        
        # Should not raise exception
        health_state = {
            "circuit_breaker": {"state": "OPEN"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        mode = await failing_manager.cascade(health_state)
        assert mode == FallbackMode.HEURISTIC


class TestMetrics:
    """Test metrics collection."""

    @pytest.mark.asyncio
    async def test_get_metrics(self, manager):
        """Test metrics retrieval."""
        metrics = await manager.get_metrics()
        
        assert "current_mode" in metrics
        assert "is_degraded" in metrics
        assert "is_safe_mode" in metrics
        assert "total_transitions" in metrics
        assert "recent_transitions" in metrics

    @pytest.mark.asyncio
    async def test_metrics_reflect_current_state(self, manager):
        """Test that metrics reflect current manager state."""
        await manager.set_mode("safe")
        
        metrics = await manager.get_metrics()
        
        assert metrics["current_mode"] == "safe"
        assert metrics["is_degraded"] is True
        assert metrics["is_safe_mode"] is True

    @pytest.mark.asyncio
    async def test_metrics_include_recent_transitions(self, manager):
        """Test that metrics include recent transition history."""
        await manager.set_mode("heuristic")
        await manager.set_mode("safe")
        
        metrics = await manager.get_metrics()
        
        assert len(metrics["recent_transitions"]) == 2
        assert metrics["total_transitions"] == 2


class TestFallbackRegistration:
    """Test fallback registration and management."""

    @pytest.mark.asyncio
    async def test_register_fallback_success(self, manager):
        """Test successful fallback registration."""
        action_called = False
        
        async def test_action():
            nonlocal action_called
            action_called = True
        
        success = await manager.register_fallback(
            name="test_fallback",
            condition="severity >= 0.8",
            action=test_action
        )
        
        assert success is True

    @pytest.mark.asyncio
    async def test_register_fallback_with_metadata(self, manager, storage):
        """Test fallback registration with metadata."""
        async def test_action():
            pass
        
        metadata = {
            "description": "High severity fallback",
            "priority": 1
        }
        
        await manager.register_fallback(
            name="test_fallback",
            condition="severity >= 0.8",
            action=test_action,
            metadata=metadata
        )
        
        # Verify metadata was stored
        import json
        definition = await storage.get("fallback:definition:test_fallback")
        data = json.loads(definition)
        assert data["metadata"]["description"] == "High severity fallback"


class TestConcurrency:
    """Test thread safety and concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_cascades(self, manager):
        """Test concurrent cascade operations."""
        health_state = {
            "circuit_breaker": {"state": "CLOSED"},
            "retry": {"failures_1h": 0},
            "system": {"failed_components": 0},
        }
        
        # Run multiple cascades concurrently
        results = await asyncio.gather(
            manager.cascade(health_state),
            manager.cascade(health_state),
            manager.cascade(health_state),
        )
        
        # All should return same mode
        assert all(mode == FallbackMode.PRIMARY for mode in results)

    @pytest.mark.asyncio
    async def test_concurrent_mode_changes(self, manager):
        """Test concurrent mode changes."""
        # Run multiple set_mode operations concurrently
        results = await asyncio.gather(
            manager.set_mode("heuristic"),
            manager.set_mode("safe"),
            manager.set_mode("primary"),
        )
        
        # All should succeed
        assert all(result is True for result in results)
        
        # Final mode should be one of the requested modes
        assert manager.get_current_mode() in [
            FallbackMode.HEURISTIC,
            FallbackMode.SAFE,
            FallbackMode.PRIMARY,
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
