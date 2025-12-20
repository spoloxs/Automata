"""
Main entry point for the web automation system.
"""
import asyncio
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
from core.master_agent import MasterAgent
from config.settings import GEMINI_API_KEY

async def main():
    goal = "Search for 'Python programming' on Bing and click the first result"
    starting_url = "https://www.bing.com"
    print("🚀 Web Automation System Starting...")
    print(f"Goal: {goal}")
    print(f"Starting URL: {starting_url}\n")
    master = MasterAgent(
        api_key=GEMINI_API_KEY,
        max_parallel_workers=4
    )
    try:
        await master.initialize()
        result = await master.execute_goal(
            goal=goal,
            starting_url=starting_url,
            timeout=300
        )
        print("\n" + "="*70)
        print("FINAL RESULT")
        print("="*70)
        print(result)
        if result.success:
            print("✅ Goal accomplished successfully!")
            return 0
        else:
            print("❌ Goal failed")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await master.cleanup()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
