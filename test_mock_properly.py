"""
Properly test with mock - patch BEFORE any imports
"""
import sys
from pathlib import Path

# Add to path FIRST
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

# Patch BEFORE importing anything from web_agent
from unittest.mock import patch
from mock_screen_parser import MockScreenParser

# Now patch and import
with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
    # NOW import web_agent modules (they will use MockScreenParser)
    import asyncio
    import gc
    import psutil
    from web_agent.core.master_agent import MasterAgent
    from web_agent.config.settings import GEMINI_API_KEY
    
    def get_ram():
        return psutil.Process().memory_info().rss / 1024 / 1024
    
    async def test():
        print("\n" + "="*70)
        print("PROPERLY MOCKED TEST")
        print("="*70)
        
        baseline = get_ram()
        print(f"Baseline: {baseline:.1f} MB")
        
        master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
        await master.initialize()
        after_init = get_ram()
        print(f"After init: {after_init:.1f} MB (+{after_init - baseline:.1f} MB)")
        
        await master.execute_goal(
            goal="Navigate to google.com",
            starting_url="https://www.google.com",
            timeout=60
        )
        after_task = get_ram()
        print(f"After task: {after_task:.1f} MB (+{after_task - after_init:.1f} MB)")
        
        await master.cleanup()
        del master
        gc.collect()
        gc.collect()
        after_cleanup = get_ram()
        
        leaked = after_cleanup - after_init
        freed = after_task - after_cleanup
        
        print(f"After cleanup: {after_cleanup:.1f} MB ({freed:+.1f} MB)")
        print(f"\n📊 LEAKED: {leaked:.1f} MB")
        
        if leaked > 100:
            print("❌ LEAK FOUND: Agent workflow leaks!")
        else:
            print("✅ NO LEAK: Parsing was the culprit!")
    
    asyncio.run(test())
