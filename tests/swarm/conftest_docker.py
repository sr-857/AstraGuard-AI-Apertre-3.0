
try:
    import docker
except ImportError:
    docker = None

import pytest

@pytest.fixture
def docker_client():
    if not docker:
        pytest.skip("Docker python client not installed")
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        pytest.skip("Docker daemon not reachable")
