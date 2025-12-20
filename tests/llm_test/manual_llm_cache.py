#!/usr/bin/env python3
"""
Test LLM Response Caching
"""

import asyncio
import os
import sys
import time
from pathlib import Path


from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🧠 LLM CACHE TEST")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1280, 720),
        thread_id="llm_cache_test",
        enable_llm_cache=True,  # Enable caching
        llm_cache_ttl=3600,
    )
    
    try:
        await agent._async_init()
        await agent.page.goto("https://www.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Test repeated queries using generate_response
        test_prompts = [
            "What is the main purpose of this page?",
            "Find the search button",
            "What is the main purpose of this page?",  # Repeat
            "Find the search button",                  # Repeat
            "Describe the layout",
            "What is the main purpose of this page?",  # Repeat again
        ]
        
        print("\n🔍 Running 6 LLM queries (3 unique, 3 repeated)...")
        
        for i, prompt in enumerate(test_prompts, 1):
            print(f"\n[Query {i}] {prompt}")
            
            start = time.time()
            # Use generate_response method (not ask)
            response = await agent.agent.generate_response(
                prompt, 
                thread_id=f"test_{agent.page.url}"
            )
            elapsed = time.time() - start
            
            print(f"   ⏱️  Response time: {elapsed:.3f}s")
            print(f"   📝 Response: {response[:100]}...")  # First 100 chars
            
            if elapsed < 0.1:
                print(f"   ✅ CACHED!")
        
        # Print statistics
        print("\n" + "=" * 60)
        print("📊 LLM CACHE STATISTICS")
        print("=" * 60)
        
        if hasattr(agent.agent, 'llm_cache') and agent.agent.llm_cache:
            stats = agent.agent.llm_cache.get_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
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
