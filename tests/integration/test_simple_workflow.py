"""
Integration test for simple workflow.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from web_agent.config.settings import GEMINI_API_KEY
from web_agent.core.master_agent import MasterAgent


@pytest.mark.asyncio
async def test_simple_search_workflow():
    """Test simple search workflow"""

    # Skip if no API key
    if not GEMINI_API_KEY:
        pytest.skip("No GEMINI_API_KEY found")

    # Mock get_omniparser to avoid loading heavy ML models in ScreenParser
    with patch("web_agent.perception.screen_parser.get_omniparser") as mock_get_omni:
        # Configure mock
        mock_omni_instance = mock_get_omni.return_value
        mock_omni_instance.parse_screen_simple.return_value = [
            {
                "id": 0,
                "type": "text",
                "bbox": [0, 0, 0.1, 0.1],
                "center": [0.05, 0.05],
                "content": "Google",
                "interactivity": False,
                "source": "omniparser",
            }
        ]
        mock_omni_instance.parse.return_value = {
            "label_coordinates": [[0, 0, 0.1, 0.1]],
            "parsed_content_list": ["Google"],
            "labeled_image": "base64_image_data",
        }
        mock_omni_instance.parse_screen.return_value = (
            "base64_image",
            [[0, 0, 0.1, 0.1]],
            ["Google"],
        )

        master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=2)

        try:
            # Initialize
            await master.initialize()

            # Execute simple goal
            result = await master.execute_goal(
                goal="Navigate to google.com",
                starting_url="https://www.google.com",
                timeout=60,
            )

            # Assertions
            assert result is not None
            assert result.goal == "Navigate to google.com"
            assert result.total_tasks >= 1

            # Should complete successfully (simple navigation)
            assert result.completed_tasks >= 1

        finally:
            await master.cleanup()


@pytest.mark.asyncio
async def test_planning_phase():
    """Test that planning creates valid plan"""

    if not GEMINI_API_KEY:
        pytest.skip("No GEMINI_API_KEY found")

    with patch("web_agent.perception.screen_parser.get_omniparser") as mock_get_omni:
        master = MasterAgent(api_key=GEMINI_API_KEY)

        try:
            await master.initialize()
            await master.browser.navigate("https://www.bing.com")

            # Create plan
            plan = await master.planner.create_plan(
                goal="Search for Python",
                explore=False,  # Skip exploration for speed
            )

            # Assertions
            assert plan is not None
            assert plan.goal == "Search for Python"
            assert len(plan.steps) >= 1
            assert plan.complexity in ["simple", "moderate", "complex"]

        finally:
            await master.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
