#!/usr/bin/env python3
"""
Test Full Task Execution with LLM Caching
Shows both caching AND actual browser interactions
"""

import asyncio
import os
import sys
import time
from pathlib import Path

from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🚀 FULL TASK EXECUTION WITH CACHE TEST")
    print("=" * 60)

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return

    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,  # Keep visible to see execution
        window_size=(1280, 720),
        thread_id="full_task_test",
        enable_llm_cache=True,
        enable_parser_cache=True,
    )

    try:
        await agent._async_init()

        # Test Task 1: Search on Google
        print("\n" + "=" * 60)
        print("📋 TASK 1: Search 'OpenAI' on Google")
        print("=" * 60)

        task1 = "Go to Google, search for 'OpenAI', and press Enter"
        start_url = "https://www.google.com"

        start = time.time()
        result1 = await agent.run_task(task1, start_url)
        elapsed1 = time.time() - start

        print(f"\n✅ Task 1 completed in {elapsed1:.1f}s")
        print(f"   Success: {result1.get('success', False)}")

        # Wait a bit to see the result
        await asyncio.sleep(3)

        # Test Task 2: Repeat Similar Task (Should use cache!)
        print("\n" + "=" * 60)
        print("📋 TASK 2: Search 'Anthropic' on Google (Similar Task)")
        print("=" * 60)
        print("⚡ Watch for cache hits - should be much faster!")

        task2 = "Go to Google, search for 'Anthropic', and press Enter"

        start = time.time()
        result2 = await agent.run_task(task2, start_url)
        elapsed2 = time.time() - start

        print(f"\n✅ Task 2 completed in {elapsed2:.1f}s")
        print(f"   Success: {result2.get('success', False)}")

        # Compare performance
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE COMPARISON")
        print("=" * 60)
        print(f"Task 1 (uncached): {elapsed1:.1f}s")
        print(f"Task 2 (cached):   {elapsed2:.1f}s")

        if elapsed2 < elapsed1 * 0.7:
            speedup = elapsed1 / elapsed2 if elapsed2 > 0 else 1
            print(f"🚀 Speedup: {speedup:.1f}x faster with cache!")
        else:
            print(f"ℹ️  Similar speed (cache effect minimal for this task)")

        # Print cache statistics
        print("\n" + "=" * 60)
        print("📊 CACHE STATISTICS")
        print("=" * 60)

        # LLM Cache
        if hasattr(agent.agent, "llm_cache") and agent.agent.llm_cache:
            print("\n🧠 LLM Cache (GeminiAgent):")
            llm_stats = agent.agent.llm_cache.get_stats()
            for key, value in llm_stats.items():
                print(f"   {key}: {value}")

        # Parser Cache
        if hasattr(agent.parser, "get_stats"):
            print("\n📦 Parser Cache (OmniParser):")
            parser_stats = agent.parser.get_stats()
            for key, value in parser_stats.items():
                print(f"   {key}: {value}")

        # Planner Cache
        if hasattr(agent.planner, "get_cache_stats"):
            print("\n🧠 Planner Cache:")
            planner_stats = agent.planner.get_cache_stats()
            for key, value in planner_stats.items():
                print(f"   {key}: {value}")

        print("\n✅ Full test completed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        print("\n🔒 Closing agent in 5 seconds...")
        await asyncio.sleep(5)
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
