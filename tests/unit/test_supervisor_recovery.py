import pytest
from unittest.mock import AsyncMock, Mock

from web_agent.core.supervisor_agent import AISupervisorAgent
from web_agent.supervision.decision_engine import SupervisorDecision, SupervisorAction
from web_agent.core.task import TaskDAG, Task


@pytest.mark.asyncio
async def test_replan_adds_recovery_tasks_when_dag_incomplete():
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()
    mock_scheduler.max_workers = 1

    sup = AISupervisorAgent(mock_gemini, mock_planner, mock_scheduler)

    # Use a real DAG to verify tasks are added without side effects
    dag = TaskDAG()
    # Seed with a task to make DAG non-empty and incomplete
    dag.add_task(Task(description="Seed task"))

    decision = SupervisorDecision(
        action=SupervisorAction.REPLAN,
        reasoning="Add recovery tasks",
        confidence=0.9,
        alternative="Try a different path",
        new_tasks=[{"description": "Collect additional context"}],
    )

    before = dag.get_task_count()
    await sup._execute_decision(decision, dag, Mock(), Mock())
    after = dag.get_task_count()

    # We expect at least two tasks to be added (alternative + one new task)
    assert after >= before + 2


def test_retry_adds_retry_task_with_dependencies():
    mock_gemini = AsyncMock()
    mock_planner = Mock()
    mock_scheduler = Mock()
    sup = AISupervisorAgent(mock_gemini, mock_planner, mock_scheduler)

    dag = TaskDAG()
    a = Task(description="Step A")
    b = Task(description="Step B", dependencies=[a.id])
    dag.add_task(a)
    dag.add_task(b)
    dag.add_dependency(b.id, a.id)

    dec = SupervisorDecision(
        action=SupervisorAction.RETRY,
        reasoning="Retry B",
        confidence=0.8,
        task_id=b.id,
    )

    added = sup._add_recovery_tasks(dec, dag)
    assert added >= 1
    # Find retry task
    retry_tasks = [t for t in dag.get_all_tasks() if t.description.startswith("Retry:")]
    assert len(retry_tasks) >= 1
    # The retry task should carry original dependencies (on A)
    assert a.id in retry_tasks[0].dependencies
