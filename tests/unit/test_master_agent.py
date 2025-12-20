"""
Unit tests for MasterAgent.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from web_agent.core.master_agent import MasterAgent


@pytest.mark.asyncio
async def test_master_agent_initialization():
    """Test master agent initialization"""
    with (
        patch("web_agent.core.master_agent.BrowserController"),
        patch("web_agent.core.master_agent.ScreenParser"),
        patch("web_agent.core.master_agent.GeminiAgent"),
        patch("web_agent.core.master_agent.TaskVerifier"),
        patch("web_agent.core.master_agent.Planner"),
        patch("web_agent.core.master_agent.WorkerScheduler"),
    ):
        master = MasterAgent(api_key="test_key", max_parallel_workers=2)

        assert master.master_id is not None
        assert master.max_workers == 2
        assert master.current_goal is None


@pytest.mark.asyncio
async def test_minimal_context():
    """Test that master provides minimal context to workers"""
    with (
        patch("web_agent.core.master_agent.BrowserController"),
        patch("web_agent.core.master_agent.ScreenParser"),
        patch("web_agent.core.master_agent.GeminiAgent"),
        patch("web_agent.core.master_agent.TaskVerifier"),
        patch("web_agent.core.master_agent.Planner"),
        patch("web_agent.core.master_agent.WorkerScheduler"),
    ):
        master = MasterAgent(api_key="test_key")
        master.current_goal = "Test goal"

        context = master._get_minimal_context()

        assert "goal" in context
        assert "master_id" in context
        assert context["goal"] == "Test goal"
        # Should NOT contain history or other polluting data
        assert "action_history" not in context
        assert "previous_results" not in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
