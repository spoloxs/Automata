"""
Complete test: Dismiss popup, then fill out registration form
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_agent.core.master_agent import MasterAgent


async def test_popup_and_form():
    """Test dismissing popup and filling form"""
    
    # Get absolute path to test HTML
    html_path = Path(__file__).parent / "test_popup_with_form.html"
    file_url = f"file://{html_path.absolute()}"
    
    print("\n" + "="*80)
    print("🧪 POPUP + FORM FILLING TEST")
    print("="*80)
    print(f"\nPage: {file_url}")
    print("\nObjective:")
    print("1. Dismiss cookie popup")
    print("2. Fill out registration form")
    print("3. Submit form")
    print("\n" + "="*80 + "\n")
    
    # Create master agent
    agent = MasterAgent()
    await agent.initialize()
    
    # Task: Complete registration form
    goal = """
    Complete the user registration on this page:
    
    1. First, dismiss any popups or cookie notices that are blocking the form
    2. Then fill out the registration form with the following information:
       - Full Name: John Smith
       - Email: john.smith@example.com  
       - Phone: +1 (555) 123-4567
    3. Submit the form by clicking the "Complete Registration" button
    4. Verify that the success message appears
    
    Return a summary of what you accomplished.
    """
    
    try:
        print("🤖 Agent starting task...\n")
        result = await agent.execute_goal(
            goal=goal,
            starting_url=file_url
        )
        
        print("\n" + "="*80)
        print("📊 AGENT'S RESULT:")
        print("="*80)
        print(result)
        print("="*80)
        
    finally:
        # Cleanup
        await agent.cleanup()
    
    print("\n✅ Test complete!\n")


if __name__ == "__main__":
    asyncio.run(test_popup_and_form())
