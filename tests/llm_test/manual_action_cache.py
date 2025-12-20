#!/usr/bin/env python3
"""
Test LLM Action Decision Caching (More Realistic)
"""

import asyncio
import os
import sys
import time
from pathlib import Path


from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🎯 ACTION DECISION CACHE TEST")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1280, 720),
        thread_id="action_cache_test",
        enable_llm_cache=True,
    )
    
    try:
        await agent._async_init()
        
        # Navigate to test page
        print("\n📄 Loading Google homepage...")
        await agent.page.goto("https://www.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Parse screen once
        print("\n🔍 Parsing screen...")
        screenshot = await agent.capture_screenshot()
        result = await agent.parser.parse_screen(screenshot, url=agent.page.url)
        
        # Handle 4-tuple or 3-tuple
        if len(result) >= 2:
            elements = result[1]
        else:
            elements = []
        
        print(f"✅ Found {len(elements)} elements\n")
        
        # Test repeated action decisions
        test_tasks = [
            "Find and click the search button",
            "Type 'hello world' in the search box",
            "Find and click the search button",  # Repeat
            "Type 'hello world' in the search box",  # Repeat
            "Scroll down the page",
            "Find and click the search button",  # Repeat again
        ]
        
        print("🎯 Testing 6 action decisions (3 unique, 3 repeated)...")
        
        for i, task in enumerate(test_tasks, 1):
            print(f"\n[Decision {i}] {task}")
            
            start = time.time()
            
            # Call decide_action (this is what actually runs during tasks)
            action = await agent.agent.decide_action(
                task=task,
                elements=elements,
                url=agent.page.url,
                cursor_position=(640, 360),
                viewport_size=(1280, 720),
                thread_id="test",
                plan=None,
                storage_data=None,
                element_hierarchy_text=None,
                previous_actions=None,
            )
            
            elapsed = time.time() - start
            
            print(f"   ⏱️  Decision time: {elapsed:.3f}s")
            print(f"   🎬 Action: {action.action_type}")
            
            if elapsed < 0.1:
                print(f"   ✅ CACHED! (saved ~2s)")
        
        # Print statistics
        print("\n" + "=" * 60)
        print("📊 CACHE STATISTICS")
        print("=" * 60)
        
        if hasattr(agent.agent, 'llm_cache') and agent.agent.llm_cache:
            stats = agent.agent.llm_cache.get_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
            
            hit_rate = stats.get('cache_hit_rate', '0%')
            print(f"\n🎯 Cache Hit Rate: {hit_rate}")
            
            if float(hit_rate.rstrip('%')) > 40:
                print("✅ EXCELLENT! Cache is working perfectly!")
            elif float(hit_rate.rstrip('%')) > 20:
                print("✅ GOOD! Cache is helping!")
            else:
                print("⚠️  Low hit rate - cache needs more repeated queries")
        else:
            print("   ⚠️  Cache not available")
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
