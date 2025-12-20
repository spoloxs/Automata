#!/usr/bin/env python3
"""
Test Rtree Spatial Indexing Performance
"""

import asyncio
import os
import sys
import time
from pathlib import Path


from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🎯 SPATIAL INDEX PERFORMANCE TEST")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1280, 720),
        thread_id="spatial_test",
        enable_parser_cache=True,
        enable_image_diff=True,
    )
    
    try:
        await agent._async_init()
        
        # Visit a complex page
        print("\n📄 Loading Google homepage...")
        await agent.page.goto("https://www.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        # Parse
        print("\n🔍 Parsing screen...")
        screenshot = await agent.capture_screenshot()
        result = await agent.parser.parse_screen(screenshot, url=agent.page.url)
        
        # Extract results
        if len(result) == 4:
            annotated, elements, all_text, spatial_index = result
        else:
            annotated, elements, all_text = result
            spatial_index = None
        
        print(f"✅ Found {len(elements)} elements")
        
        if not spatial_index:
            print("❌ Spatial index not available")
            return
        
        # Test 1: Query region (top-right)
        print("\n" + "=" * 60)
        print("TEST 1: Query top-right region")
        print("=" * 60)
        
        region = spatial_index.get_region_bounds('top-right', 1280, 720)
        print(f"Region: {region}")
        
        # Linear search (slow)
        start = time.time()
        linear_results = [
            e for e in elements
            if (e['bbox'][0] >= region[0] and e['bbox'][1] >= region[1] and
                e['bbox'][2] <= region[2] and e['bbox'][3] <= region[3])
        ]
        linear_time = time.time() - start
        
        # Rtree search (fast)
        start = time.time()
        rtree_results = spatial_index.query_region(region)
        rtree_time = time.time() - start
        
        print(f"Linear search: {len(linear_results)} elements in {linear_time*1000:.3f}ms")
        print(f"Rtree search:  {len(rtree_results)} elements in {rtree_time*1000:.3f}ms")
        
        if rtree_time > 0:
            speedup = linear_time / rtree_time
            print(f"🚀 Speedup: {speedup:.1f}x faster!")
        
        # Test 2: Find nearest to point
        print("\n" + "=" * 60)
        print("TEST 2: Find nearest element to center")
        print("=" * 60)
        
        center_x, center_y = 640, 360
        
        # Linear search
        start = time.time()
        nearest_linear = min(
            elements,
            key=lambda e: ((e['center'][0] - center_x)**2 + (e['center'][1] - center_y)**2)**0.5
        )
        linear_time = time.time() - start
        
        # Rtree search
        start = time.time()
        nearest_rtree = spatial_index.find_nearest(center_x, center_y, k=1)[0]
        rtree_time = time.time() - start
        
        print(f"Linear search: {linear_time*1000:.3f}ms")
        print(f"Rtree search:  {rtree_time*1000:.3f}ms")
        
        if rtree_time > 0:
            speedup = linear_time / rtree_time
            print(f"🚀 Speedup: {speedup:.1f}x faster!")
        
        # Test 3: Query by type in region
        print("\n" + "=" * 60)
        print("TEST 3: Find all buttons in left region")
        print("=" * 60)
        
        left_region = spatial_index.get_region_bounds('left', 1280, 720)
        
        start = time.time()
        buttons = spatial_index.query_by_type('button', region=left_region)
        query_time = time.time() - start
        
        print(f"Found {len(buttons)} buttons in {query_time*1000:.3f}ms")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 SPATIAL INDEX STATS")
        print("=" * 60)
        print(spatial_index.get_stats())
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
