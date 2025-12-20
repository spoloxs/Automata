"""Tests for Scheduler"""
import pytest
import asyncio
from web_agent.scheduling.scheduler import WorkerScheduler
from web_agent.core.task import Task, TaskDAG


@pytest.mark.asyncio
async def test_scheduler_initialization():
    """Test scheduler initialization"""
    scheduler = WorkerScheduler(max_parallel_workers=2)
    assert scheduler.max_workers == 2
    assert len(scheduler.active_workers) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
