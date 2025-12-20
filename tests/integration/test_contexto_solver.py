"""
Integration test for solving Contexto (contexto.me).
This tests the agent's ability to engage in a multi-step semantic reasoning task.
"""

import asyncio

import pytest

from web_agent.config.settings import GEMINI_API_KEY
from web_agent.core.master_agent import MasterAgent
from web_agent.util.logger import log_error, log_info


@pytest.mark.asyncio
async def test_contexto_solver():
    """
    Test the agent playing and solving the Contexto game.

    The game requires:
    1. Visual perception of the game state (previous guesses, proximity colors).
    2. Semantic reasoning to generate better guesses based on feedback.
    3. Persistent interaction until the target word is found.
    """

    if not GEMINI_API_KEY:
        log_info("No GEMINI_API_KEY found")
        return

    # Initialize MasterAgent with 1 worker for sequential reasoning
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)

    try:
        await master.initialize()

        # The goal is specific and includes strategy hints for the LLM
        goal = (
            "Go to https://contexto.me and play the game to find the secret word. "
            "Type guesses into the input field and press Enter. "
            "Analyze the position/color of your guesses: green/low number means close, red/high number means far. "
            "Use semantic similarity to converge on the secret word. "
            "Keep guessing until you find the word (number 1)."
        )

        # High timeout because this game can take many turns
        result = await master.execute_goal(
            goal=goal,
            starting_url="https://contexto.me",
            timeout=9000,
        )

        # Verification
        assert result is not None

        # Check if successful
        if not result.success:
            log_error(f"\n❌ Contexto run failed with errors: {result.errors}")

        assert result.success, f"Failed to solve Contexto: {result.errors}"
        assert result.completed_tasks >= 1

    finally:
        await master.cleanup()


if __name__ == "__main__":
    asyncio.run(test_contexto_solver())
