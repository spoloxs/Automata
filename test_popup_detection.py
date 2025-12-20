"""
Test to verify if the agent can detect a popup/modal on a webpage.
Uses the enhanced element formatter with bbox coordinates and hierarchy.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_agent.core.master_agent import MasterAgent


async def test_popup_detection():
    """Test if agent can detect popup from element structure"""
    
    # Get absolute path to test HTML
    html_path = Path(__file__).parent / "test_popup_page.html"
    file_url = f"file://{html_path.absolute()}"
    
    print("\n" + "="*80)
    print("🧪 POPUP DETECTION TEST")
    print("="*80)
    print(f"\nLoading page: {file_url}")
    print("\nThis page has a centered modal popup overlay")
    print("The agent should detect it from bbox coordinates and hierarchy")
    print("\n" + "="*80 + "\n")
    
    # Create master agent
    agent = MasterAgent()
    await agent.initialize()
    
    # Task: Analyze the page and identify if there's a popup
    goal = """
    Analyze this webpage and answer the following question:
    
    "Is there a popup, modal, or overlay visible on this screen that is blocking the main content?"
    
    If yes, describe:
    1. What type of element it is (modal, overlay, popup, etc.)
    2. What text/content is shown in it
    3. What buttons or actions are available to dismiss it
    4. Approximately what percentage of the screen it covers
    
    If no, explain what you see instead.
    
    Base your answer on the element structure, bbox coordinates, and hierarchy information provided.
    """
    
    try:
        print("🤖 Asking agent to analyze the page...\n")
        result = await agent.execute_goal(
            goal=goal,
            starting_url=file_url
        )
        
        print("\n" + "="*80)
        print("📊 AGENT'S RESPONSE:")
        print("="*80)
        print(result)
        print("="*80)
        
    finally:
        # Cleanup
        await agent.cleanup()
    
    print("\n✅ Test complete!\n")


if __name__ == "__main__":
    asyncio.run(test_popup_detection())
