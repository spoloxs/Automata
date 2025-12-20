"""
Integration test for solving LA Times Mini Crossword.
This tests the agent's ability to navigate, interact with a crossword puzzle interface,
and solve clues using reasoning and contextual understanding.
"""

import asyncio

import pytest

from web_agent.config.settings import GEMINI_API_KEY
from web_agent.core.master_agent import MasterAgent
from web_agent.util.logger import log_error, log_info


@pytest.mark.asyncio
async def test_latimes_mini_crossword():
    """
    Test the agent solving the LA Times Mini Crossword.

    The task requires:
    1. Navigate to latimes.com
    2. Find and open the mini crossword puzzle
    3. Understand the crossword interface (grid, clues, input)
    4. Read and interpret clues (Across and Down)
    5. Fill in answers logically using reasoning
    6. Complete the entire crossword puzzle
    """

    if not GEMINI_API_KEY:
        log_info("No GEMINI_API_KEY found")
        return

    # Initialize MasterAgent with 1 worker for focused reasoning
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)

    try:
        await master.initialize()

        # Clear, specific goal with tile-by-tile solving strategy
        goal = (
            "Go to https://www.latimes.com and find the Mini Crossword puzzle. "
            "Open the mini crossword and solve it by filling each tile one at a time. "
            "\n"
            "SOLVING STRATEGY:\n"
            "1. Once you reach the crossword grid, click on each individual tile/cell\n"
            "2. For each tile, type ONE letter at a time\n"
            "3. Move to the next tile and fill it with the appropriate letter\n"
            "4. Continue this process systematically (row by row or clue by clue)\n"
            "5. Use the clues (Across and Down) to determine the correct letters\n"
            "6. Keep filling tiles until you see a 'Congratulations' message, success popup, or completion indicator\n"
            "\n"
            "COMPLETION CRITERIA:\n"
            "- The task is ONLY complete when you see a 'Congrats', 'Congratulations', 'You solved it', or similar success message\n"
            "- OR when all tiles are filled and the puzzle validates as complete\n"
            "- Do NOT stop until you see the completion message or all tiles are filled\n"
            "- If you make a mistake, correct it and continue filling\n"
        )

        # Crossword solving with no timeout - relies on 50 iteration limit
        result = await master.execute_goal(
            goal=goal,
            starting_url="https://www.latimes.com",
        )

        # Verification
        assert result is not None

        # Check if successful
        if not result.success:
            log_error(f"\n❌ LA Times Mini Crossword failed with errors: {result.errors}")

        assert result.success, f"Failed to solve LA Times Mini Crossword: {result.errors}"
        assert result.completed_tasks >= 1, "No tasks completed"

        log_info(f"✅ Successfully completed LA Times Mini Crossword!")
        log_info(f"   Tasks completed: {result.completed_tasks}")
        log_info(f"   Total actions: {result.total_actions}")
        log_info(f"   Duration: {result.total_duration:.2f}s")

    finally:
        await master.cleanup()


if __name__ == "__main__":
    asyncio.run(test_latimes_mini_crossword())
