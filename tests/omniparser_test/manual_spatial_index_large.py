#!/usr/bin/env python3
"""
Test Spatial Index on Complex Pages (200+ elements)
"""

import asyncio
import os
import sys
import time
from pathlib import Path


from web_agent.agents.web_agent import WebAgent


def linear_search_region(elements, region):
    """Simulate linear search"""
    x1, y1, x2, y2 = region
    results = []
    for e in elements:
        bbox = e.get('bbox', [0, 0, 0, 0])
        # Check if bbox overlaps with region
        if (bbox[0] < x2 and bbox[2] > x1 and 
            bbox[1] < y2 and bbox[3] > y1):
            results.append(e)
    return results


async def main():
    print("\n" + "=" * 60)
    print("🎯 SPATIAL INDEX TEST - COMPLEX PAGE")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1920, 1080),  # Larger viewport = more elements
        thread_id="spatial_test",
        enable_parser_cache=True,
        enable_image_diff=True,
    )
    
    try:
        await agent._async_init()
        
        # Test multiple sites
        test_sites = [
            ("https://www.amazon.com", "Amazon (200+ elements)"),
            ("https://www.reddit.com", "Reddit (150+ elements)"),
            ("https://news.ycombinator.com", "Hacker News (100+ elements)"),
        ]
        
        for url, description in test_sites:
            print("\n" + "=" * 60)
            print(f"📄 Testing: {description}")
            print("=" * 60)
            
            try:
                await agent.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)  # Let page render
                
                # Parse
                print("🔍 Parsing screen...")
                screenshot = await agent.capture_screenshot()
                result = await agent.parser.parse_screen(screenshot, url=agent.page.url)
                
                # Extract results
                if len(result) == 4:
                    annotated, elements, all_text, spatial_index = result
                else:
                    annotated, elements, all_text = result
                    spatial_index = None
                
                print(f"✅ Found {len(elements)} elements")
                
                if len(elements) < 50:
                    print("⚠️  Not enough elements - skipping benchmark")
                    continue
                
                # Benchmark: Query 10 random regions
                print("\n📊 Benchmarking 10 region queries...")
                
                import random
                w, h = 1920, 1080
                regions = [
                    (random.randint(0, w//2), random.randint(0, h//2),
                     random.randint(w//2, w), random.randint(h//2, h))
                    for _ in range(10)
                ]
                
                # Linear search benchmark
                start = time.time()
                for region in regions:
                    _ = linear_search_region(elements, region)
                linear_time = time.time() - start
                
                # Rtree search benchmark (if available)
                if spatial_index:
                    start = time.time()
                    for region in regions:
                        _ = spatial_index.query_region(region)
                    rtree_time = time.time() - start
                    
                    print(f"Linear search: {linear_time*1000:.2f}ms")
                    print(f"Rtree search:  {rtree_time*1000:.2f}ms")
                    
                    if rtree_time > 0:
                        speedup = linear_time / rtree_time
                        print(f"🚀 Speedup: {speedup:.1f}x faster")
                else:
                    print(f"Linear search: {linear_time*1000:.2f}ms")
                    print("⚠️  No spatial index (dataset too small)")
                
            except Exception as e:
                print(f"⚠️  Failed to load {url}: {e}")
                continue
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
