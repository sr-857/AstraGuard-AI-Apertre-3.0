"""Tests for Job Failure Handling (#681)"""

import pytest
import asyncio
from src.core.job_failure_handler import (
    JobFailureHandler,
    FailureReason,
    get_failure_handler
)


class TestJobFailureHandler:
    @pytest.fixture
    def handler(self):
        return JobFailureHandler(
            max_retries=2,
            initial_retry_delay_seconds=0.1,
            backoff_multiplier=2.0
        )
    
    @pytest.mark.asyncio
    async def test_successful_retry(self, handler):
        attempts = []
        
        async def flaky_job():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("First attempt fails")
        
        result = await handler.handle_failure(
            "job1", "flaky_job", flaky_job,
            ValueError("First attempt fails")
        )
        
        assert result is True
        assert len(attempts) == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, handler):
        async def always_fails():
            raise ValueError("Always fails")
        
        result = await handler.handle_failure(
            "job2", "failing_job", always_fails,
            ValueError("Always fails")
        )
        
        assert result is False
        dlq = handler.get_dead_letter_queue()
        assert len(dlq) > 0
    
    def test_get_failure_statistics(self, handler):
        stats = handler.get_failure_statistics()
        assert "active_failures" in stats
        assert "dead_letter_queue_size" in stats
        assert stats["max_retries"] == 2
    
    def test_singleton(self):
        h1 = get_failure_handler()
        h2 = get_failure_handler()
        assert h1 is h2
