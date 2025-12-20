"""
Simple example: Search and click first result.
"""
import asyncio
from pathlib import Path
import sys
from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY

async def simple_search_example():
    master = MasterAgent(
        api_key=GEMINI_API_KEY,
        max_parallel_workers=2
    )
    try:
        await master.initialize()
        result = await master.execute_goal(
            goal="Search for 'LangChain tutorial' and click the first result",
            starting_url="https://www.bing.com",
            timeout=120
        )
        if result.success:
            print(f"\n✅ Success! Confidence: {result.confidence:.1%}")
            print(f"   Completed in {result.total_duration:.1f}s")
            print(f"   Actions taken: {len(result.all_actions)}")
        else:
            print(f"\n❌ Failed")
            if result.errors:
                print(f"   Errors: {result.errors}")
        return result
    finally:
        await master.cleanup()

if __name__ == "__main__":
    result = asyncio.run(simple_search_example())
    sys.exit(0 if result.success else 1)
