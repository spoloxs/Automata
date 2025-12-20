"""
Unit tests for WorkerAgent.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from web_agent.core.task import Task
from web_agent.core.worker_agent import WorkerAgent


@pytest.mark.asyncio
@patch("web_agent.core.worker_agent.ScreenParser")
async def test_worker_agent_initialization(mock_parser):
    """Test worker agent initialization"""
    task = Task(description="Test task")
    mock_page = Mock()
    mock_gemini = Mock()
    mock_verifier = Mock()

    worker = WorkerAgent(
        worker_id="test_worker",
        task=task,
        browser_page=mock_page,
        gemini_agent=mock_gemini,
        verifier=mock_verifier,
        parent_context={"goal": "Test goal"},
    )

    assert worker.worker_id == "test_worker"
    assert worker.task == task
    assert worker.thread_id is not None
    assert "worker_test_worker" in worker.thread_id


@pytest.mark.asyncio
@patch("web_agent.core.worker_agent.ScreenParser")
async def test_worker_unique_thread_id(mock_parser):
    """Test that each worker gets unique thread_id"""
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2")
    mock_page = Mock()
    mock_gemini = Mock()
    mock_verifier = Mock()

    worker1 = WorkerAgent(
        worker_id="worker_1",
        task=task1,
        browser_page=mock_page,
        gemini_agent=mock_gemini,
        verifier=mock_verifier,
    )

    worker2 = WorkerAgent(
        worker_id="worker_2",
        task=task2,
        browser_page=mock_page,
        gemini_agent=mock_gemini,
        verifier=mock_verifier,
    )

    assert worker1.thread_id != worker2.thread_id
    print(f"Worker 1 thread: {worker1.thread_id}")
    print(f"Worker 2 thread: {worker2.thread_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
