"""Tests for Planner"""

import pytest

from web_agent.planning.plan_structures import Step, StepType, StructuredPlan


def test_step_creation():
    """Test step creation"""
    step = Step(
        number=1,
        name="Test Step",
        description="Test description",
        type=StepType.DIRECT,
        dependencies=[],
        estimated_time_seconds=10,
        can_run_parallel=True,
    )

    assert step.number == 1
    assert step.name == "Test Step"
    assert step.type == StepType.DIRECT
    assert step.can_run_parallel == True  # No dependencies


def test_step_with_dependencies():
    """Test step with dependencies"""
    step = Step(
        number=2,
        name="Dependent Step",
        description="Depends on step 1",
        type=StepType.DIRECT,
        dependencies=[1],
    )

    assert len(step.dependencies) == 1
    assert step.dependencies[0] == 1


def test_structured_plan():
    """Test structured plan creation"""
    steps = [
        Step(1, "Step 1", "First step", StepType.DIRECT, []),
        Step(2, "Step 2", "Second step", StepType.DIRECT, [1]),
    ]

    plan = StructuredPlan(
        goal="Test goal", steps=steps, complexity="simple", estimated_total_time=20
    )

    assert plan.goal == "Test goal"
    assert plan.get_total_steps() == 2
    assert len(plan.get_independent_steps()) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
