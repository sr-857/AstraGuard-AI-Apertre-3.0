"""
Pytest configuration for chaos engineering tests.

Issue #415: Swarm chaos engineering suite
Provides shared fixtures and configuration for chaos scenarios.
"""

import pytest
import asyncio
import logging
from pathlib import Path

# Configure logging for chaos tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test."""
    yield
    # Tests clean up via finally blocks


@pytest.mark.asyncio
async def test_chaos_infrastructure_available():
    """Verify chaos testing infrastructure is available."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        assert True, "Docker available"
    except Exception as e:
        pytest.skip(f"Docker not available: {e}")
