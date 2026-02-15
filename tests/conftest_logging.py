"""Comprehensive logging utilities for CI test failures.

This module provides enhanced logging capabilities for detecting and documenting
CI test failures with detailed context including:
- Test setup/teardown logs
- Docker container status and logs
- Service health checks
- Environment variables
- Timestamps for all log entries
- Test execution context
"""

import logging
import os
import sys
import time
import subprocess
import socket
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import json


class CITestLogger:
    """Enhanced logger for CI test failures with comprehensive context."""

    def __init__(self, name: str = "CI_Tests"):
        """Initialize CI test logger.

        Args:
            name: Logger name
        """
        self.logger = self._setup_logger(name)
        self.test_context: Dict[str, Any] = {}
        self.start_time = time.time()

    def _setup_logger(self, name: str) -> logging.Logger:
        """Set up comprehensive logging configuration.

        Args:
            name: Logger name

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Console handler with detailed formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # File handler for archiving logs
        log_file = f"ci_test_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        # Detailed formatter with timestamps
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    @contextmanager
    def test_context_manager(self, test_name: str, metadata: Optional[Dict] = None):
        """Context manager for logging test execution.

        Args:
            test_name: Name of the test
            metadata: Optional metadata dictionary

        Yields:
            Logger instance
        """
        self.test_context['test_name'] = test_name
        self.test_context['start_time'] = datetime.now().isoformat()
        self.test_context['metadata'] = metadata or {}

        self.logger.info(f"\n{'='*70}")
        self.logger.info(f"TEST START: {test_name}")
        self.logger.info(f"{'='*70}")
        self._log_environment_info()

        try:
            yield self.logger
        except Exception as e:
            self.logger.error(f"Test failed with exception: {str(e)}", exc_info=True)
            self._log_failure_diagnostics()
            raise
        finally:
            elapsed = time.time() - self.start_time
            self.logger.info(f"TEST END: {test_name} (Duration: {elapsed:.2f}s)")
            self.logger.info(f"{'='*70}\n")

    def _log_environment_info(self) -> None:
        """Log environment variables and system information."""
        self.logger.debug("Environment Variables:")
        env_keys = [
            'PYTHON_VERSION', 'PYTEST_VERSION', 'CI', 'GITHUB_ACTIONS',
            'REDIS_URL', 'DOCKER_BUILDKIT', 'PATH'
        ]
        for key in env_keys:
            value = os.getenv(key, 'NOT_SET')
            self.logger.debug(f"  {key}: {value}")

    def log_service_health(self, service_name: str, check_fn) -> bool:
        """Log service health check result.

        Args:
            service_name: Name of service to check
            check_fn: Function that returns True if healthy

        Returns:
            Health check result
        """
        try:
            is_healthy = check_fn()
            status = "HEALTHY" if is_healthy else "UNHEALTHY"
            self.logger.info(f"Service Health Check [{service_name}]: {status}")
            return is_healthy
        except Exception as e:
            self.logger.error(f"Service Health Check [{service_name}] failed: {str(e)}")
            return False

    def log_docker_status(self) -> None:
        """Log Docker containers and compose services status."""
        self.logger.info("Docker Status Information:")
        try:
            # Log running containers
            result = subprocess.run(
                ['docker', 'ps', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                containers = result.stdout.strip().split('\n')
                self.logger.info(f"  Running containers: {len(containers)}")
                for container in containers[:5]:  # Log first 5
                    self.logger.debug(f"    {container}")
            else:
                self.logger.warning(f"  Failed to list containers: {result.stderr}")
        except Exception as e:
            self.logger.warning(f"  Could not retrieve Docker status: {str(e)}")

    def log_docker_compose_logs(self) -> None:
        """Capture Docker Compose service logs on failure."""
        self.logger.info("Docker Compose Logs:")
        try:
            result = subprocess.run(
                ['docker', 'compose', 'logs', '--tail=50'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.logger.info(result.stdout)
            else:
                self.logger.warning(f"Failed to retrieve compose logs: {result.stderr}")
        except Exception as e:
            self.logger.warning(f"Could not retrieve Docker Compose logs: {str(e)}")

    def log_redis_status(self, host: str = 'localhost', port: int = 6379) -> None:
        """Log Redis connection status.

        Args:
            host: Redis host
            port: Redis port
        """
        self.logger.info(f"Redis Status [{host}:{port}]:")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                self.logger.info(f"  Redis connection: ACTIVE")
            else:
                self.logger.warning(f"  Redis connection: FAILED")
        except Exception as e:
            self.logger.error(f"  Redis connection check failed: {str(e)}")

    def _log_failure_diagnostics(self) -> None:
        """Log comprehensive diagnostics on test failure."""
        self.logger.error("\n" + "="*70)
        self.logger.error("TEST FAILURE DIAGNOSTICS")
        self.logger.error("="*70)

        # Log service status
        self.log_redis_status()
        self.log_docker_status()
        self.log_docker_compose_logs()

        # Log system resources
        self._log_system_resources()

        self.logger.error("="*70 + "\n")

    def _log_system_resources(self) -> None:
        """Log system resource utilization."""
        self.logger.debug("System Resources:")
        try:
            # Disk space
            result = subprocess.run(
                ['df', '-h'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.logger.debug("Disk Space:")
                for line in result.stdout.split('\n')[:3]:  # Header and first 2 rows
                    self.logger.debug(f"  {line}")
        except Exception as e:
            self.logger.debug(f"Could not retrieve disk space: {str(e)}")


class LoggingFixture:
    """Pytest fixture for comprehensive test logging."""

    ci_logger = CITestLogger()

    @staticmethod
    def log_test_info(request) -> None:
        """Log test information at the start of each test.

        Args:
            request: Pytest request fixture
        """
        LoggingFixture.ci_logger.logger.info(
            f"Running test: {request.node.name} from {request.node.parent.name}"
        )

    @staticmethod
    def log_test_failure(request, exc_info) -> None:
        """Log test failure information.

        Args:
            request: Pytest request fixture
            exc_info: Exception info tuple
        """
        LoggingFixture.ci_logger.logger.error(
            f"Test FAILED: {request.node.name}\nError: {str(exc_info[1])}",
            exc_info=exc_info
        )
        LoggingFixture.ci_logger._log_failure_diagnostics()
