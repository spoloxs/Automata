import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from pydantic import BaseModel

from web_agent.supervision.decision_engine import (
    DecisionEngine,
    DecisionRequest,
    SupervisorAction,
)


# Mock response models to simulate structured LLM output
class FakeDecisionResult(BaseModel):
    action: str
    reasoning: str
    confidence: float
    task_id: Optional[str] = None
    alternative: Optional[str] = None
    simplify_plan: bool = False
    suggested_continuation_attempts: Optional[int] = None


class FakeHealthResult(BaseModel):
    assessment: str
    confidence: float


# Mock LLM that returns pre-configured results
class FakeStructuredLLM:
    def __init__(self, result: BaseModel):
        self._result = result

    async def ainvoke(self, *args, **kwargs):
        # Simulate async LLM call
        await asyncio.sleep(0)
        return self._result


@pytest.mark.asyncio
async def test_normalize_execution_state_and_recent_history_formatting():
    """Test that execution state normalization handles various shapes correctly."""
    engine = DecisionEngine(gemini_agent=None)

    # 1. Test normalization
    raw_state = {
        "completed": 2,
        "failed": ["task_a", "task_b"],  # list should be converted to length
        "remaining": 3,
        "elapsed_time": 12.5,
        "recent_history": [
            {
                "task_id": "t-1",
                "task_desc": "Type 'hello'",
                "success": False,
                "error": "Timeout",
                "action_history": [
                    {"type": "type", "target": 5},
                    {"type": "press_enter"},
                ],
            }
        ],
    }

    norm = engine._normalize_execution_state(raw_state)

    assert norm["completed"] == 2
    assert norm["failed"] == 2  # List length
    assert norm["total"] == 7  # 2 + 2 + 3 (derived)
    assert norm["elapsed_time"] == 12.5
    assert "recent_history" in norm["raw"]

    # 2. Test recent history formatting
    recent_text = engine._format_recent_history(norm["raw"]["recent_history"])

    # Assert key information is present in the formatted string
    assert "t-1" in recent_text
    assert "Timeout" in recent_text or "failed" in recent_text
    assert "type" in recent_text
    assert "press_enter" in recent_text


@pytest.mark.asyncio
async def test_decide_failure_action_structured_path():
    """Test that decision engine uses the structured LLM path correctly."""

    # Prepare a fake structured response
    expected_action = SupervisorAction.RETRY
    fake_result = FakeDecisionResult(
        action="retry",
        reasoning="Transient error detected",
        confidence=0.95,
        task_id="task-123",
        suggested_continuation_attempts=2,
    )

    # Mock GeminiAgent with decision_llm
    fake_gemini = SimpleNamespace()
    fake_gemini.decision_llm = FakeStructuredLLM(fake_result)

    engine = DecisionEngine(gemini_agent=fake_gemini)

    # Inputs
    failed_task = {
        "id": "task-123",
        "description": "Click button",
        "error": "Timeout",
        "duration": 5.0,
        "action_history": [],
    }
    execution_state = {"completed": 1, "failed": 1, "total": 5, "elapsed_time": 10.0}
    dag_state = {"downstream_tasks": []}

    # Execute
    decision = await engine.decide_failure_action(
        goal="Test goal",
        failed_task=failed_task,
        execution_state=execution_state,
        dag_state=dag_state,
    )

    # Verify
    assert decision.action == expected_action
    assert decision.reasoning == "Transient error detected"
    assert decision.confidence == 0.95
    assert decision.task_id == "task-123"


@pytest.mark.asyncio
async def test_health_assessment_structured_path():
    """Test that health assessment uses the structured LLM path correctly."""

    fake_health = FakeHealthResult(
        assessment="Execution is proceeding normally", confidence=0.88
    )

    fake_gemini = SimpleNamespace()
    fake_gemini.health_llm = FakeStructuredLLM(fake_health)

    engine = DecisionEngine(gemini_agent=fake_gemini)

    execution_state = {"completed": 5, "total": 10, "failed": 0, "elapsed_time": 50.0}

    result = await engine.health_assessment(execution_state)

    assert result["assessment"] == "Execution is proceeding normally"
    assert result["confidence"] == 0.88
    # Heuristic calculation check (5 remaining, 0 failed -> ~1 or 2 attempts)
    assert "suggested_continuation_attempts" in result


@pytest.mark.asyncio
async def test_format_downstream_tasks_robustness():
    """Test _format_downstream_tasks with various inputs."""
    engine = DecisionEngine(gemini_agent=None)

    # Case 1: List of dicts
    tasks_list = [
        {"id": "t1", "description": "Task 1"},
        {"id": "t2", "description": "Task 2"},
    ]
    fmt_list = engine._format_downstream_tasks(tasks_list)
    assert "- 2 tasks blocked" in fmt_list
    assert "Task 1" in fmt_list

    # Case 2: Integer count
    tasks_int = 5
    fmt_int = engine._format_downstream_tasks(tasks_int)
    assert "- 5 tasks blocked" in fmt_int

    # Case 3: None/Empty
    assert "No downstream tasks affected" in engine._format_downstream_tasks([])
    assert "No downstream tasks affected" in engine._format_downstream_tasks(None)
