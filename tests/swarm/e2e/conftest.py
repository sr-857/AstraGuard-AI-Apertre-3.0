"""pytest configuration for E2E recovery pipeline tests."""

import pytest
import asyncio
import docker
from pathlib import Path


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def docker_client():
    """Get Docker client for container manipulation."""
    return docker.from_env()


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def cleanup_containers(docker_client):
    """Auto-cleanup test containers after each test."""
    yield
    # Cleanup happens in finally
    try:
        # Restart any killed containers
        for container in docker_client.containers.list(all=True):
            if container.name.startswith("astra-agent"):
                if container.status != "running":
                    container.restart()
    except:
        pass
