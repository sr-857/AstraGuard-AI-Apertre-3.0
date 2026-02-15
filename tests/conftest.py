"""Pytest configuration and fixtures for AstraGuard-AI test suite."""
import pytest
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Register pytest-asyncio plugin (required for @pytest.mark.asyncio tests)
# Only register if pytest-asyncio is available (installed via requirements-test.txt)
try:
    import pytest_asyncio
    pytest_plugins = ('pytest_asyncio',)
except ImportError:
    pytest_plugins = ()

# Ensure project modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


# ============================================================================
# PYTEST ASYNCIO CONFIGURATION
# ============================================================================

@pytest.fixture(scope="function")
def event_loop():
    """Create event loop for async tests (function scope for isolation)"""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    policy.set_event_loop(loop)
    yield loop
    loop.close()
    policy.set_event_loop(None)


# ============================================================================
# TELEMETRY DATA FIXTURES
# ============================================================================

@pytest.fixture
def valid_telemetry_data():
    """Valid satellite telemetry data within normal operating ranges."""
    return {
        'timestamp': datetime.now().isoformat(),
        'voltage': 8.0,
        'temperature': 25.0,
        'gyro': 0.02,
        'current': 1.1,
        'wheel_speed': 5000,
        'state_of_charge': 85.0
    }


@pytest.fixture
def anomalous_telemetry_data():
    """Anomalous telemetry data indicating fault conditions."""
    return {
        'timestamp': datetime.now().isoformat(),
        'voltage': 3.5,  # Low voltage
        'temperature': 85.0,  # High temperature
        'gyro': 0.5,  # High angular velocity
        'current': 2.5,  # High current draw
        'wheel_speed': 8000,  # High wheel speed
        'state_of_charge': 15.0  # Low battery
    }


@pytest.fixture
def edge_case_telemetry():
    """Edge case telemetry data at boundaries."""
    return {
        'timestamp': datetime.now().isoformat(),
        'voltage': 7.8,  # Near lower boundary
        'temperature': 30.0,  # Near upper boundary
        'gyro': 0.45,  # High but not extreme
        'current': 2.0,  # Near boundary
        'wheel_speed': 7500,
        'state_of_charge': 20.0
    }


# ============================================================================
# POLICY DECISION FIXTURES
# ============================================================================

@pytest.fixture
def valid_policy_decision():
    """Valid policy decision output."""
    return {
        'mission_phase': 'NOMINAL_OPS',
        'anomaly_type': 'thermal_fault',
        'severity': 'HIGH',
        'recommended_action': 'THERMAL_REGULATION',
        'detection_confidence': 0.87,
        'timestamp': datetime.now().isoformat()
    }


@pytest.fixture
def critical_policy_decision():
    """Critical priority policy decision."""
    return {
        'mission_phase': 'SAFEGUARD_MODE',
        'anomaly_type': 'power_loss',
        'severity': 'CRITICAL',
        'recommended_action': 'EMERGENCY_SHUTDOWN',
        'detection_confidence': 0.99,
        'timestamp': datetime.now().isoformat()
    }


@pytest.fixture
def low_priority_decision():
    """Low priority policy decision."""
    return {
        'mission_phase': 'NOMINAL_OPS',
        'anomaly_type': 'minor_drift',
        'severity': 'LOW',
        'recommended_action': 'CALIBRATION_CHECK',
        'detection_confidence': 0.62,
        'timestamp': datetime.now().isoformat()
    }


# ============================================================================
# MISSION PHASE FIXTURES
# ============================================================================

@pytest.fixture
def mission_phases():
    """All valid mission phases."""
    return [
        'STARTUP',
        'NOMINAL_OPS',
        'SAFEGUARD_MODE',
        'SAFE_MODE',
        'SHUTDOWN'
    ]


@pytest.fixture
def phase_transitions():
    """Valid phase transitions."""
    return {
        'STARTUP': ['NOMINAL_OPS', 'SAFEGUARD_MODE'],
        'NOMINAL_OPS': ['SAFEGUARD_MODE', 'SHUTDOWN'],
        'SAFEGUARD_MODE': ['NOMINAL_OPS', 'SAFE_MODE'],
        'SAFE_MODE': ['NOMINAL_OPS', 'SHUTDOWN'],
        'SHUTDOWN': []
    }


# ============================================================================
# HEALTH MONITOR FIXTURES
# ============================================================================

@pytest.fixture
def health_monitor():
    """Get and reset health monitor instance."""
    from core.component_health import SystemHealthMonitor
    monitor = SystemHealthMonitor.get_instance()
    # Reset state for testing
    monitor._components = {}
    monitor._health_status = {}
    return monitor


@pytest.fixture
def healthy_components():
    """Mock healthy component states."""
    return {
        'anomaly_detector': {
            'status': 'HEALTHY',
            'last_check': datetime.now().isoformat(),
            'error_count': 0
        },
        'policy_engine': {
            'status': 'HEALTHY',
            'last_check': datetime.now().isoformat(),
            'error_count': 0
        },
        'memory_engine': {
            'status': 'HEALTHY',
            'last_check': datetime.now().isoformat(),
            'error_count': 0
        }
    }


@pytest.fixture
def degraded_components():
    """Mock degraded component states."""
    return {
        'anomaly_detector': {
            'status': 'DEGRADED',
            'last_check': datetime.now().isoformat(),
            'error_count': 3
        },
        'policy_engine': {
            'status': 'HEALTHY',
            'last_check': datetime.now().isoformat(),
            'error_count': 0
        }
    }


# ============================================================================
# ERROR HANDLING FIXTURES
# ============================================================================

@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        'invalid_input': ValueError("Invalid input data"),
        'timeout': TimeoutError("Operation timed out"),
        'resource': RuntimeError("Resource exhausted"),
        'config': IOError("Configuration error")
    }


# ============================================================================
# MEMORY ENGINE FIXTURES
# ============================================================================

@pytest.fixture
def sample_memory_entries():
    """Sample memory store entries."""
    return [
        {
            'id': 'anomaly_001',
            'timestamp': datetime.now().isoformat(),
            'type': 'thermal_fault',
            'severity': 'HIGH',
            'details': {'temp': 85.0},
            'resolution': 'thermal_regulation_applied',
            'recurrence_count': 2
        },
        {
            'id': 'anomaly_002',
            'timestamp': datetime.now().isoformat(),
            'type': 'power_loss',
            'severity': 'CRITICAL',
            'details': {'voltage': 3.5},
            'resolution': 'emergency_shutdown_initiated',
            'recurrence_count': 0
        }
    ]


# ============================================================================
# PYTEST HOOKS AND CONFIGURATION
# ============================================================================

@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """Initialize test environment."""
    # Suppress debug logs during tests
    import logging
    import sys
    
    logging.getLogger('astraguard').setLevel(logging.WARNING)
    
    # Close stdout/stderr in case they were opened during imports
    
    yield
    
    # Cleanup after tests - ensure all logging handlers are closed EXCEPT pytest's  
    try:
        _cleanup_logging_handlers()
    except Exception as e:
        # Silently ignore cleanup errors to avoid breaking pytest teardown
        pass


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    try:
        from core.component_health import SystemHealthMonitor
        # Save original instances
        yield
        # Reset after each test
        SystemHealthMonitor._instance = None
    except (ImportError, ModuleNotFoundError):
        # Skip if dependencies like redis are not installed
        yield


@pytest.fixture(autouse=True)
def reset_prometheus_metrics():
    """Reset Prometheus metrics cache between tests."""
    try:
        # Clear metric cache before each test
        from astraguard.observability import _metric_cache
        _metric_cache.clear()
        yield
        # Clear cache after test
        _metric_cache.clear()
    except (ImportError, ModuleNotFoundError, AttributeError):
        # Skip if prometheus or observability not available
        yield


# ============================================================================
# LOGGING CLEANUP UTILITIES
# ============================================================================

def _cleanup_logging_handlers():
    """Clean up all logging handlers to prevent I/O errors during pytest teardown."""
    import logging

    # Get all loggers
    root_logger = logging.getLogger()
    loggers = [root_logger] + [logging.getLogger(name) for name in list(logging.root.manager.loggerDict.keys())]

    # Keep track of handlers we've already processed to avoid duplication
    processed_handlers = set()
    
    for logger in loggers:
        # Close and remove all handlers (except StreamHandlers which are used by pytest)
        for handler in list(logger.handlers):  # Create a copy of the list
            try:
                # Skip StreamHandlers as they may be used by pytest
                if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                    continue
                
                handler_id = id(handler)
                if handler_id in processed_handlers:
                    continue
                processed_handlers.add(handler_id)
                
                # Flush any pending output
                try:
                    handler.flush()
                except (OSError, ValueError, AttributeError):
                    pass
                
                # Close the handler
                try:
                    handler.close()
                except (OSError, ValueError, AttributeError):
                    pass
                
                # Remove from logger
                try:
                    logger.removeHandler(handler)
                except (ValueError, AttributeError):
                    pass
            except Exception:
                # Silently ignore any errors during cleanup
                pass


# ============================================================================
# MARK DEFINITIONS
# ============================================================================

def pytest_configure(config):
    """Register custom marks."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "error_handling: marks tests for error handling"
    )
    config.addinivalue_line(
        "markers", "memory: marks tests for memory engine"
    )
