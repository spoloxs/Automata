"""Example: Form filling automation"""
import asyncio
from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


async def form_filling_example():
    """Fill a form on a website"""
    master = MasterAgent(api_key=GEMINI_API_KEY)
    
    try:
        await master.initialize()
        
        result = await master.execute_goal(
            goal="Fill the contact form with name 'John Doe', email 'john@example.com', and submit",
            starting_url="https://example.com/contact",
            timeout=180
        )
        
        return result
    finally:
        await master.cleanup()


if __name__ == "__main__":
    result = asyncio.run(form_filling_example())
    print(result)
