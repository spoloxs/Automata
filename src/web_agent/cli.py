"""
Main entry point for the web automation system.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
from web_agent.config.settings import GEMINI_API_KEY
from web_agent.core.master_agent import MasterAgent
from web_agent.util.logger import log_error, log_info, log_success, log_warn


async def main():
    goal = "Search for 'Python programming' on Bing and click the first result"
    starting_url = "https://www.bing.com"
    log_info("🚀 Web Automation System Starting...")
    log_info(f"Goal: {goal}")
    log_info(f"Starting URL: {starting_url}\n")
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=4)
    try:
        await master.initialize()
        result = await master.execute_goal(
            goal=goal, starting_url=starting_url, timeout=300
        )
        log_info("\n" + "=" * 70)
        log_info("FINAL RESULT")
        log_info("=" * 70)
        log_info(str(result))
        if result.success:
            log_success("✅ Goal accomplished successfully!")
            return 0
        else:
            log_error("❌ Goal failed")
            return 1
    except KeyboardInterrupt:
        log_warn("\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        log_error(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await master.cleanup()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
