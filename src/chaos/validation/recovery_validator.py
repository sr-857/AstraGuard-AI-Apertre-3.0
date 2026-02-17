"""
Recovery Validation for Chaos Testing

Validates that services recover correctly after chaos injection.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class RecoveryValidationResult:
    """Result of recovery validation."""
    recovered: bool
    recovery_time_seconds: float
    health_status: str
    circuit_breaker_state: str
    fallback_mode: str
    errors: List[str]
    timestamp: datetime


class RecoveryValidator:
    """
    Validates service recovery after chaos experiments.
    
    Checks:
    - Health endpoint returns 200
    - System status is HEALTHY or DEGRADED (not FAILED)
    - Circuit breaker is not stuck in OPEN state
    - Fallback mode returns to PRIMARY
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        max_recovery_time: int = 60,
        poll_interval: float = 2.0,
    ):
        """
        Initialize recovery validator.
        
        Args:
            base_url: Base URL of AstraGuard service
            max_recovery_time: Maximum time to wait for recovery (seconds)
            poll_interval: Interval between health checks (seconds)
        """
        self.base_url = base_url
        self.max_recovery_time = max_recovery_time
        self.poll_interval = poll_interval

    async def validate_recovery(
        self,
        timeout: Optional[int] = None,
    ) -> RecoveryValidationResult:
        """
        Validate that service has recovered from chaos.
        
        Args:
            timeout: Override max recovery time
            
        Returns:
            RecoveryValidationResult with recovery status
        """
        timeout = timeout or self.max_recovery_time
        start_time = datetime.utcnow()
        errors = []
        
        logger.info(f"Starting recovery validation (timeout: {timeout}s)")
        
        async with aiohttp.ClientSession() as session:
            elapsed = 0
            
            while elapsed < timeout:
                try:
                    # Check health endpoint
                    async with session.get(
                        f"{self.base_url}/health/state",
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            state = await resp.json()
                            
                            # Validate recovery criteria
                            system_status = state.get("system", {}).get("status", "UNKNOWN")
                            cb_state = state.get("circuit_breaker", {}).get("state", "UNKNOWN")
                            fallback = state.get("fallback", {}).get("mode", "UNKNOWN")
                            
                            # Check if recovered
                            is_recovered = self._is_recovered(
                                system_status, cb_state, fallback
                            )
                            
                            if is_recovered:
                                recovery_time = (datetime.utcnow() - start_time).total_seconds()
                                logger.info(
                                    f"Service recovered in {recovery_time:.1f}s "
                                    f"(status: {system_status}, cb: {cb_state}, "
                                    f"fallback: {fallback})"
                                )
                                
                                return RecoveryValidationResult(
                                    recovered=True,
                                    recovery_time_seconds=recovery_time,
                                    health_status=system_status,
                                    circuit_breaker_state=cb_state,
                                    fallback_mode=fallback,
                                    errors=errors,
                                    timestamp=datetime.utcnow(),
                                )
                            
                            logger.debug(
                                f"Not yet recovered: status={system_status}, "
                                f"cb={cb_state}, fallback={fallback}"
                            )
                        else:
                            errors.append(f"Health endpoint returned {resp.status}")
                            
                except asyncio.TimeoutError:
                    errors.append(f"Health check timeout at {elapsed}s")
                except Exception as e:
                    errors.append(f"Health check error at {elapsed}s: {e}")
                
                # Wait before next check
                await asyncio.sleep(self.poll_interval)
                elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # Timeout - recovery failed
        logger.error(f"Recovery validation failed after {timeout}s")
        
        return RecoveryValidationResult(
            recovered=False,
            recovery_time_seconds=timeout,
            health_status="UNKNOWN",
            circuit_breaker_state="UNKNOWN",
            fallback_mode="UNKNOWN",
            errors=errors,
            timestamp=datetime.utcnow(),
        )

    def _is_recovered(
        self,
        system_status: str,
        cb_state: str,
        fallback_mode: str,
    ) -> bool:
        """
        Check if system has recovered based on health indicators.
        
        Args:
            system_status: System health status
            cb_state: Circuit breaker state
            fallback_mode: Fallback mode
            
        Returns:
            True if system is considered recovered
        """
        # System must not be in FAILED state
        if system_status == "FAILED":
            return False
        
        # System should be HEALTHY or DEGRADED
        if system_status not in ["HEALTHY", "DEGRADED"]:
            return False
        
        # Circuit breaker should not be stuck OPEN
        if cb_state == "OPEN":
            return False
        
        # Circuit breaker should be CLOSED or HALF_OPEN
        if cb_state not in ["CLOSED", "HALF_OPEN", "UNKNOWN"]:
            return False
        
        # Fallback should ideally be PRIMARY, but HEURISTIC is acceptable
        if fallback_mode == "SAFE":
            return False
        
        return True

    async def wait_for_healthy(
        self,
        timeout: int = 60,
    ) -> bool:
        """
        Wait for system to reach HEALTHY state.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if system became healthy
        """
        start_time = datetime.utcnow()
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(
                        f"{self.base_url}/health/state",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            state = await resp.json()
                            system_status = state.get("system", {}).get("status")
                            
                            if system_status == "HEALTHY":
                                elapsed = (datetime.utcnow() - start_time).total_seconds()
                                logger.info(f"System healthy after {elapsed:.1f}s")
                                return True
                            
                except Exception:
                    pass
                
                # Check timeout
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for healthy state")
                    return False
                
                await asyncio.sleep(self.poll_interval)


# Convenience function
async def validate_recovery(
    base_url: str = "http://localhost:8000",
    timeout: int = 60,
) -> RecoveryValidationResult:
    """
    Validate service recovery.
    
    Args:
        base_url: Base URL of service
        timeout: Maximum time to wait for recovery
        
    Returns:
        RecoveryValidationResult
    """
    validator = RecoveryValidator(base_url, timeout)
    return await validator.validate_recovery(timeout)
