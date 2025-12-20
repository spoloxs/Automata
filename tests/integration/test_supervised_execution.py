"""
Integration Test for Supervised Execution

This test verifies the end-to-end functionality of the AISupervisorAgent
by using real implementations of its dependencies, including:
- GeminiAgent (requires GEMINI_API_KEY)
- BrowserController (uses a real browser instance)
- Planner, ScreenParser, Verifier, and WorkerScheduler

The test executes a simple, real-world task to ensure all components
integrate and function correctly under the supervisor's control.
"""

import asyncio
import os

import pytest

from web_agent.core.task import Task, TaskDAG
from web_agent.execution.browser_controller import BrowserController
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.perception.screen_parser import ScreenParser
from web_agent.planning.planner import Planner
from web_agent.scheduling.scheduler import WorkerScheduler
from web_agent.core.supervisor_agent import AISupervisorAgent
from web_agent.verification.task_verifier import TaskVerifier as Verifier

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_supervised_execution_simple_goal():
    """
    Tests the full execution pipeline for a simple navigation and extraction task.
    It ensures that the supervisor can successfully manage a plan from creation
    to completion using real components.
    """
    # Pre-test check for API key
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip(
            "GEMINI_API_KEY environment variable not set. Skipping integration test."
        )

    # 1. --- Arrange: Initialize all components ---
    browser_controller = BrowserController()
    await browser_controller.initialize()

    gemini_agent = GeminiAgent()
    screen_parser = ScreenParser()
    planner = Planner(gemini_agent, browser_controller, screen_parser)
    scheduler = WorkerScheduler()
    verifier = Verifier(gemini_agent)
    supervisor = AISupervisorAgent(gemini_agent, planner, scheduler)

    goal = "navigate to google.com and search for 'hello world'"
    dag = None

    try:
        # 2. --- Act: Create a plan and execute it under supervision ---
        print(f"--- Starting integration test for goal: '{goal}' ---")

        # Create a plan for the goal
        plan = await planner.create_plan(goal, explore=False)
        assert plan is not None, "Planner failed to create a plan."
        assert len(plan.steps) > 0, "Plan should have at least one step."
        print(f"Plan created with {len(plan.steps)} steps.")

        # Convert the structured plan into a TaskDAG
        dag = TaskDAG()
        task_map = {}
        for step in plan.steps:
            task = Task(id=f"task_{step.number}", description=step.description)
            dag.add_task(task)
            task_map[step.number] = task.id
        for step in plan.steps:
            if step.dependencies:
                for dep_num in step.dependencies:
                    dag.add_dependency(task_map[dep_num], task_map[step.number])

        assert dag.get_task_count() > 0, "DAG should not be empty."
        print(f"TaskDAG created with {dag.get_task_count()} tasks.")

        # Supervise the execution of the DAG
        result = await supervisor.supervise_execution(
            goal=goal,
            dag=dag,
            browser_page=browser_controller.get_page(),
            verifier=verifier,
        )
        print("--- Supervision complete ---")

        # 3. --- Assert: Verify the outcome ---
        assert result is not None, "Supervisor did not return a result."
        assert result.success is True, "Supervised execution should succeed."
        assert (
            result.completed_tasks == dag.get_task_count()
        ), "All tasks should be completed."
        assert result.failed_tasks == 0, "No tasks should have failed."
        print("--- Assertions passed ---")

    finally:
        # 4. --- Cleanup: Ensure browser is closed ---
        if browser_controller:
            await browser_controller.cleanup()
            print("--- Browser cleaned up ---")
