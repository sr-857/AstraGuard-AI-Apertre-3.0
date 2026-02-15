"""Pytest configuration for CLI tests - isolated to avoid capture system conflicts."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

@pytest.fixture(scope='function', autouse=True)
def reset_logging():
    """Reset logging handlers to prevent I/O errors during pytest teardown."""
    import logging
    yield
    try:
        logging.shutdown()
    except Exception:
        pass
