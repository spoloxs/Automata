"""Example: Parallel data extraction"""
import asyncio
from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


async def data_extraction_example():
    """Extract data from multiple sources in parallel"""
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=4)
    
    try:
        await master.initialize()
        
        result = await master.execute_goal(
            goal="Extract the titles of the top 5 news articles from the homepage",
            starting_url="https://news.ycombinator.com",
            timeout=120
        )
        
        if result.success:
            print("Extracted data:", result.extracted_data)
        
        return result
    finally:
        await master.cleanup()


if __name__ == "__main__":
    result = asyncio.run(data_extraction_example())
