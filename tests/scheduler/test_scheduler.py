#!/usr/bin/env python3
"""Test CPU Scheduler Integration"""

import pytest
from web_agent.core.task import Task, TaskDAG
from web_agent.scheduling.scheduler import WorkerScheduler


@pytest.mark.unit
def test_scheduler_creation():
    """Test scheduler can be created"""
    scheduler = WorkerScheduler(max_parallel_workers=4)
    assert scheduler.max_workers == 4
