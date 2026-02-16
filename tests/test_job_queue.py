"""Tests for Job Queue Monitoring (#679)"""

import pytest
import time
from src.core.job_queue import JobQueue, QueueStatus, get_job_queue


class TestJobQueue:
    @pytest.fixture
    def queue(self):
        return JobQueue(warning_depth=5, critical_depth=10)
    
    def test_enqueue_dequeue(self, queue):
        queue.enqueue("job1")
        job = queue.dequeue()
        assert job["id"] == "job1"
    
    def test_queue_depth(self, queue):
        queue.enqueue("job1")
        queue.enqueue("job2")
        metrics = queue.get_metrics()
        assert metrics.queue_depth == 2
    
    def test_status_healthy(self, queue):
        queue.enqueue("job1")
        assert queue.get_status() == QueueStatus.HEALTHY
    
    def test_status_warning(self, queue):
        for i in range(6):
            queue.enqueue(f"job{i}")
        assert queue.get_status() == QueueStatus.WARNING
    
    def test_status_critical(self, queue):
        for i in range(11):
            queue.enqueue(f"job{i}")
        assert queue.get_status() == QueueStatus.CRITICAL
    
    def test_get_statistics(self, queue):
        queue.enqueue("job1")
        stats = queue.get_statistics()
        assert "current_metrics" in stats
        assert "status" in stats
        assert stats["total_processed"] == 0
    
    def test_singleton(self):
        q1 = get_job_queue()
        q2 = get_job_queue()
        assert q1 is q2
