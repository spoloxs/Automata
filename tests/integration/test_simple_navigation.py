"""
A simplified integration test focused solely on the navigate action.
"""

import os

import pytest

from web_agent.core.task import Task
from web_agent.core.worker_agent import WorkerAgent
from web_agent.execution.browser_controller import BrowserController
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.verification.task_verifier import TaskVerifier as Verifier

# Mark as an integration test
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_single_navigation_task():
    """
    Tests if the agent can perform a single, simple navigation task.
    This is to isolate and verify the 'navigate' tool call.
    """
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set. Skipping integration test.")

    browser_controller = BrowserController()
    await browser_controller.initialize()

    # Start on a different page to force navigation
    await browser_controller.navigate("https://www.bing.com")

    gemini_agent = GeminiAgent()
    verifier = Verifier(gemini_agent)
    goal_url = "https://www.google.com/"

    # Define a single, very specific task
    navigation_task = Task(
        id="test_nav_task",
        description=f"Navigate the browser to {goal_url}",
    )

    worker = WorkerAgent(
        worker_id="test_nav_worker",
        task=navigation_task,
        browser_page=browser_controller.get_page(),
        gemini_agent=gemini_agent,
        verifier=verifier,
    )

    try:
        print(f"\n--- Starting simple navigation test for URL: {goal_url} ---")

        # Execute the task
        result = await worker.execute_task()

        # Get the final URL from the browser
        final_url = await browser_controller.get_url()
        print(f"--- Final URL: {final_url} ---")

        # Assertions
        assert result.success is True, "The navigation task should succeed."
        assert (
            goal_url in final_url
        ), f"Browser should have navigated to {goal_url}, but is at {final_url}."

        print("--- Assertions passed ---")

    finally:
        await browser_controller.cleanup()
        print("--- Browser cleaned up ---")
