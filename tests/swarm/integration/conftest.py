"""
Integration Tests Configuration

Pytest fixtures and configuration for full-stack integration tests.

Author: SR-MISSIONCONTROL
Date: 2026-01-12
"""

import asyncio
import pytest
from pathlib import Path
from typing import AsyncGenerator


@pytest.fixture(scope="session")
def event_loop():
    """Create asyncio event loop for test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def integration_data_dir() -> Path:
    """Path to integration test data directory"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def metrics_data_dir() -> Path:
    """Path to metrics collection directory"""
    metrics_dir = Path(__file__).parent / "metrics"
    metrics_dir.mkdir(exist_ok=True)
    return metrics_dir


@pytest.fixture(scope="function")
async def docker_client():
    """Docker client for integration tests"""
    try:
        import docker
        client = docker.from_env()
        yield client
        client.close()
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")


@pytest.fixture(scope="function", autouse=True)
async def cleanup_integration_state():
    """Auto-cleanup integration test state"""
    yield
    # Cleanup code here
    await asyncio.sleep(0.1)


@pytest.fixture(scope="session")
def release_report_path() -> Path:
    """Path to release report output"""
    report_dir = Path(__file__).parent.parent.parent / "release_reports"
    report_dir.mkdir(exist_ok=True)
    return report_dir


def pytest_configure(config):
    """Configure pytest for integration tests"""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection"""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        if "slow" in item.nodeid or "stress" in item.nodeid:
            item.add_marker(pytest.mark.slow)
