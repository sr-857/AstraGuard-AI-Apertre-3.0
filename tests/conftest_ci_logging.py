"""Pytest configuration with enhanced CI logging integration.

This module extends conftest.py to integrate comprehensive logging
for CI test failures. It should be imported in the main conftest.py.
"""

import pytest
import os
import sys
from conftest_logging import CITestLogger, LoggingFixture


# Initialize the global CI logger
ci_logger = CITestLogger()


@pytest.fixture(scope='session', autouse=True)
def setup_ci_logging():
    """Setup CI logging at the start of test session."""
    ci_logger.logger.info("\n" + "="*70)
    ci_logger.logger.info("CI TEST SESSION STARTED")
    ci_logger.logger.info(f"Python Version: {sys.version}")
    ci_logger.logger.info(f"Working Directory: {os.getcwd()}")
    ci_logger.logger.info("="*70 + "\n")
    
    yield
    
    ci_logger.logger.info("\n" + "="*70)
    ci_logger.logger.info("CI TEST SESSION ENDED")
    ci_logger.logger.info("="*70 + "\n")


@pytest.fixture(autouse=True)
def log_test_start(request):
    """Log information at the start of each test."""
    LoggingFixture.log_test_info(request)


def pytest_runtest_logreport(report):
    """Hook to log test report information."""
    if report.when == 'setup':
        if report.outcome == 'failed':
            ci_logger.logger.error(f"Test setup failed: {report.nodeid}")
            ci_logger.logger.error(report.longrepr)
    elif report.when == 'call':
        if report.outcome == 'failed':
            ci_logger.logger.error(f"Test failed: {report.nodeid}")
            ci_logger.logger.error(report.longrepr)
    elif report.when == 'teardown':
        if report.outcome == 'failed':
            ci_logger.logger.error(f"Test teardown failed: {report.nodeid}")
            ci_logger.logger.error(report.longrepr)


def pytest_configure(config):
    """Hook to configure pytest with CI logging."""
    ci_logger.logger.debug(f"Pytest configuration initiated")


def pytest_collection_finish(session):
    """Hook to log test collection results."""
    ci_logger.logger.info(f"Test collection complete: {len(session.items)} tests collected")


@pytest.fixture(scope='function')
def ci_logged_test(request):
    """Fixture that provides CI logging context for individual tests."""
    test_name = request.node.name
    metadata = {
        'module': request.module.__name__,
        'class': request.cls.__name__ if request.cls else None,
        'function': test_name
    }
    
    with ci_logger.test_context_manager(test_name, metadata=metadata) as logger:
        yield logger
