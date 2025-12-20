#!/usr/bin/env python3
"""
Test DOM Enrichment Caching
"""

import asyncio
import os
import sys
import time
from pathlib import Path


from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🌳 DOM ENRICHMENT CACHE TEST")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1280, 720),
        thread_id="dom_cache_test",
        enable_parser_cache=True,
        enable_llm_cache=True,
    )
    
    try:
        await agent._async_init()
        
        print("\n📄 Loading Google homepage...")
        await agent.page.goto("https://www.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Parse screen once
        print("\n🔍 Parsing screen...")
        screenshot = await agent.capture_screenshot()
        result = await agent.parser.parse_screen(screenshot, url=agent.page.url)
        
        # Handle 4-tuple (with spatial index) or 3-tuple
        if len(result) >= 2:
            elements = result[1]
        else:
            elements = []
        
        print(f"✅ Found {len(elements)} elements\n")
        
        if len(elements) == 0:
            print("⚠️  No elements found - test may not be accurate")
        
        # Test 1: First enrichment (cold)
        print("=" * 60)
        print("TEST 1: First DOM enrichment (cache miss)")
        print("=" * 60)
        
        start = time.time()
        enriched1 = await agent.dom_enricher.enrich_elements(elements)
        elapsed1 = time.time() - start
        
        print(f"⏱️  Time: {elapsed1:.3f}s")
        print(f"✅ Enriched {len(enriched1)} elements")
        
        # Test 2: Immediate re-enrichment (should be cached)
        print("\n" + "=" * 60)
        print("TEST 2: Re-enrichment (cache hit expected)")
        print("=" * 60)
        
        start = time.time()
        enriched2 = await agent.dom_enricher.enrich_elements(elements)
        elapsed2 = time.time() - start
        
        print(f"⏱️  Time: {elapsed2:.3f}s")
        print(f"✅ Enriched {len(enriched2)} elements")
        
        if elapsed2 < elapsed1 * 0.1:
            speedup = elapsed1 / elapsed2 if elapsed2 > 0.001 else 999
            print(f"🚀 Speedup: {speedup:.0f}x faster with cache!")
        else:
            print(f"ℹ️  Similar speed - cache may not be working or enrichment is already fast")
        
        # Test 3: After simulated action (cache invalidated)
        print("\n" + "=" * 60)
        print("TEST 3: After action (cache invalidated)")
        print("=" * 60)
        
        if hasattr(agent.dom_enricher, 'dom_cache') and agent.dom_enricher.dom_cache:
            agent.dom_enricher.mark_action_occurred()
            print("   ⏳ Waiting 0.2s (past invalidation window)...")
            await asyncio.sleep(0.2)  # Wait past invalidation window
        
        start = time.time()
        enriched3 = await agent.dom_enricher.enrich_elements(elements)
        elapsed3 = time.time() - start
        
        print(f"⏱️  Time: {elapsed3:.3f}s")
        print(f"✅ Enriched {len(enriched3)} elements")
        
        if elapsed3 > elapsed2 * 2:
            print(f"✅ Cache was properly invalidated (slower than cached)")
        
        # Test 4: Multiple quick queries (all should be cached)
        print("\n" + "=" * 60)
        print("TEST 4: 5 rapid queries (cache hits expected)")
        print("=" * 60)
        
        start = time.time()
        for i in range(5):
            await agent.dom_enricher.enrich_elements(elements)
        elapsed_batch = time.time() - start
        
        print(f"⏱️  Total time for 5 queries: {elapsed_batch:.3f}s")
        print(f"⏱️  Average per query: {elapsed_batch/5:.3f}s")
        
        if elapsed_batch < elapsed1:
            print(f"🚀 Batch queries benefited from cache!")
        
        # Test 5: After real action (click)
        print("\n" + "=" * 60)
        print("TEST 5: After real browser action (click)")
        print("=" * 60)
        
        try:
            # Try to click something (Google logo)
            await agent.page.click('a[href="/"]', timeout=2000)
            print("   🖱️  Clicked Google logo")
            await asyncio.sleep(0.5)
            
            # Now enrichment should be slower (cache invalidated by action handler)
            start = time.time()
            enriched5 = await agent.dom_enricher.enrich_elements(elements)
            elapsed5 = time.time() - start
            
            print(f"⏱️  Time: {elapsed5:.3f}s")
            print(f"✅ Enriched {len(enriched5)} elements")
            
            if elapsed5 > elapsed_batch/5 * 2:
                print(f"✅ Cache properly invalidated after action!")
        except Exception as e:
            print(f"⚠️  Click test failed: {e}")
        
        # Print statistics
        print("\n" + "=" * 60)
        print("📊 DOM CACHE STATISTICS")
        print("=" * 60)
        
        if hasattr(agent.dom_enricher, 'dom_cache') and agent.dom_enricher.dom_cache:
            stats = agent.dom_enricher.get_cache_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
            
            hit_rate_str = stats.get('cache_hit_rate', '0%')
            hit_rate = float(hit_rate_str.rstrip('%'))
            
            if hit_rate > 60:
                print("\n✅ EXCELLENT! DOM cache is working perfectly!")
            elif hit_rate > 30:
                print("\n✅ GOOD! DOM cache is helping!")
            else:
                print("\n⚠️  Low hit rate - but this is expected for this test")
        else:
            print("   ⚠️  DOM cache not available")
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n🔒 Closing agent...")
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
