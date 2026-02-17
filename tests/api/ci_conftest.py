"""
CI/CD Integration Configuration for API Testing

Pytest configuration for CI/CD environments including:
- Test discovery and selection
- Coverage reporting
- Performance testing
- Test result formatting
"""

import pytest
import os
from datetime import datetime


def pytest_configure(config):
    """Configure pytest for CI/CD."""
    # Add custom markers
    config.addinivalue_line(
        "markers",
        "api: mark test as an API test"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow-running"
    )
    config.addinivalue_line(
        "markers",
        "contract: mark test as an API contract test"
    )

    # Store test results directory
    config.test_results_dir = os.environ.get(
        "TEST_RESULTS_DIR",
        "test-results"
    )
    if not os.path.exists(config.test_results_dir):
        os.makedirs(config.test_results_dir)


def pytest_collection_modifyitems(config, items):
    """Modify test collection for CI/CD."""
    for item in items:
        # Auto-mark API tests
        if "api" in item.nodeid:
            item.add_marker(pytest.mark.api)
        
        # Auto-mark integration tests
        if "integration" in item.nodeid or "contract" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Auto-mark benchmark tests
        if "benchmark" in item.nodeid or "performance" in item.nodeid:
            item.add_marker(pytest.mark.benchmark)


@pytest.fixture(scope="session")
def test_session_info():
    """Provide test session information."""
    return {
        "start_time": datetime.now().isoformat(),
        "environment": os.environ.get("ENV", "test"),
        "ci_provider": os.environ.get("CI_PROVIDER", "unknown"),
    }


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    import json
    
    # Generate test summary
    summary = {
        "total": session.config.hook.pytest_collection_modifyitems,
        "passed": session.testsfailed == 0,
        "exit_code": exitstatus,
        "timestamp": datetime.now().isoformat(),
    }
    
    results_dir = getattr(session.config, "test_results_dir", "test-results")
    summary_file = os.path.join(results_dir, "summary.json")
    
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
