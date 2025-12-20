"""
Unit tests for AI Supervisor Agent
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, MagicMock, patch, PropertyMock
from web_agent.core.supervisor_agent import AISupervisorAgent
from web_agent.supervision.decision_engine import SupervisorDecision, SupervisorAction
from web_agent.core.task import Task
from web_agent.core.result import TaskResult
from web_agent.supervision.health_monitor import ExecutionHealth


@pytest.mark.asyncio
async def test_supervisor_initialization():
    """Test supervisor initializes correctly"""
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()

    supervisor = AISupervisorAgent(
        gemini_agent=mock_gemini, planner=mock_planner, scheduler=mock_scheduler
    )

    assert supervisor.decision_engine is not None
    assert supervisor.health_monitor is not None
    assert supervisor.execution_id is not None


@pytest.mark.asyncio
async def test_execute_decision_skip():
    """Test skip decision marks task complete"""
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()

    supervisor = AISupervisorAgent(mock_gemini, mock_planner, mock_scheduler)

    mock_dag = Mock()
    mock_dag.mark_task_skipped = Mock()

    decision = SupervisorDecision(
        action=SupervisorAction.SKIP,
        reasoning="Test skip",
        confidence=0.9,
        task_id="test_task_123",
    )

    # Core supervisor expects browser_page and verifier params
    await supervisor._execute_decision(decision, mock_dag, Mock(), Mock())

    mock_dag.mark_task_skipped.assert_called_once_with("test_task_123")


@pytest.mark.asyncio
async def test_health_monitoring():
    """Test health monitoring with proper DAG mock"""
    from web_agent.supervision.health_monitor import HealthMonitor

    monitor = HealthMonitor()
    monitor.start_monitoring()

    monitor.record_task_result("task1", True, 2.1)
    monitor.record_task_result("task2", True, 1.8)
    monitor.record_task_result("task3", False, 10.5)

    # Proper DAG mock (align with HealthMonitor expectations)
    mock_dag = Mock()
    mock_dag.get_completed_count.return_value = 2
    mock_dag.get_failed_count.return_value = 1
    mock_dag.get_task_count.return_value = 3
    mock_dag.get_incomplete_tasks.return_value = []
    mock_dag.get_ready_tasks.return_value = []
    mock_dag.get_all_tasks.return_value = []
    mock_dag.tasks = {}  # Empty dict for fallback path

    health = monitor.get_health(mock_dag)

    assert isinstance(health, ExecutionHealth)
    assert health.success_rate == 2 / 3


@pytest.mark.asyncio
@patch("web_agent.core.supervisor_agent.WorkerAgent")
async def test_task_execution_failure_handling(mock_worker_class):
    """Test task execution handles worker failures"""
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()

    # Mock worker that fails immediately
    mock_worker = Mock()
    mock_worker.execute_task = AsyncMock(
        return_value=TaskResult(task_id="test", success=False, error="test failure")
    )
    mock_worker.cleanup = AsyncMock()
    mock_worker_class.return_value = mock_worker

    supervisor = AISupervisorAgent(mock_gemini, mock_planner, mock_scheduler)

    mock_task = Mock()
    mock_task.id = "test_task"

    result = await supervisor._execute_task_with_recovery(mock_task, Mock(), Mock())

    assert not result.success
    mock_worker.cleanup.assert_called()


@pytest.mark.unit
def test_failure_pattern_detection():
    """Test failure pattern detection"""
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()
    supervisor = AISupervisorAgent(mock_gemini, mock_planner, mock_scheduler)

    mock_task_verify = Mock()
    mock_task_verify.description = "verify task completion"
    pattern = supervisor._detect_failure_pattern(mock_task_verify)
    assert pattern == "verification_failure"

    mock_task_action = Mock()
    mock_task_action.description = "Press the Enter key"
    pattern = supervisor._detect_failure_pattern(mock_task_action)
    assert pattern == "action_redundancy"
