"""
Custom exceptions for database connection pooling.
"""


class PoolError(Exception):
    """Base exception for pool-related errors."""
    pass


class PoolExhaustedError(PoolError):
    """Raised when pool cannot provide a connection within timeout."""
    pass


class PoolClosedError(PoolError):
    """Raised when attempting to use a closed pool."""
    pass


class ConnectionError(PoolError):
    """Raised when a connection fails or becomes invalid."""
    pass
