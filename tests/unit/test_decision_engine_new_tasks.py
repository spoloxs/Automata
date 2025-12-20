import asyncio
import pytest
from types import SimpleNamespace

from web_agent.supervision.decision_engine import DecisionEngine, SupervisorAction


class FakeResult:
    def __init__(self):
        self.action = "replan"
        self.reasoning = "Add recovery tasks"
        self.confidence = 0.92
        self.task_id = None
        self.alternative = "Create backup step"
        self.simplify_plan = False
        self.suggested_continuation_attempts = 1
        self.new_tasks = [{"description": "Probe environment"}]


class FakeStructuredLLM:
    async def ainvoke(self, *args, **kwargs):
        await asyncio.sleep(0)
        return FakeResult()


@pytest.mark.asyncio
async def test_decision_engine_structured_new_tasks_pass_through():
    fake = SimpleNamespace()
    fake.decision_llm = FakeStructuredLLM()

    engine = DecisionEngine(gemini_agent=fake)

    decision = await engine.decide_failure_action(
        goal="Test goal",
        failed_task={"id": "t1", "description": "x", "error": "e", "duration": 1.0},
        execution_state={"completed": 0, "failed": 1, "total": 2, "elapsed_time": 1.0},
        dag_state={"downstream_tasks": [], "failure_pattern": "unknown", "current_url": ""},
    )

    assert decision.action == SupervisorAction.REPLAN
    assert decision.alternative == "Create backup step"
    # Pass-through for new_tasks
    assert getattr(decision, "new_tasks", None) is not None
    assert decision.new_tasks[0]["description"] == "Probe environment"
