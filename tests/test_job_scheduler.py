"""Tests for Background Job Scheduler (#680)"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.core.job_scheduler import (
    JobScheduler,
    JobStatus,
    ScheduleType,
    get_job_scheduler
)


class TestJobScheduler:
    @pytest.fixture
    def scheduler(self):
        return JobScheduler()
    
    @pytest.mark.asyncio
    async def test_schedule_interval(self, scheduler):
        executed = []
        
        async def handler():
            executed.append(datetime.now())
        
        job_id = scheduler.schedule_interval("test_job", handler, 0.1)
        assert job_id is not None
        
        job = scheduler.get_job(job_id)
        assert job["name"] == "test_job"
        assert job["schedule_type"] == ScheduleType.INTERVAL.value
    
    @pytest.mark.asyncio
    async def test_schedule_one_time(self, scheduler):
        async def handler():
            pass
        
        run_at = datetime.now() + timedelta(seconds=1)
        job_id = scheduler.schedule_one_time("one_time_job", handler, run_at)
        
        job = scheduler.get_job(job_id)
        assert job["schedule_type"] == ScheduleType.ONE_TIME.value
    
    def test_cancel_job(self, scheduler):
        async def handler():
            pass
        
        job_id = scheduler.schedule_interval("cancel_test", handler, 60)
        assert scheduler.cancel_job(job_id) is True
        
        job = scheduler.get_job(job_id)
        assert job["status"] == JobStatus.CANCELLED.value
    
    def test_list_jobs(self, scheduler):
        async def handler():
            pass
        
        scheduler.schedule_interval("job1", handler, 60)
        scheduler.schedule_interval("job2", handler, 60)
        
        jobs = scheduler.list_jobs()
        assert len(jobs) >= 2
    
    def test_singleton(self):
        s1 = get_job_scheduler()
        s2 = get_job_scheduler()
        assert s1 is s2
