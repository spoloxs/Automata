#!/usr/bin/env python3
"""
Comprehensive OmniParser Cache Performance Test
Tests all caching strategies and measures performance improvements
"""

import asyncio
import os
import time
from pathlib import Path
from io import BytesIO
from PIL import Image

from web_agent.agents.web_agent import WebAgent
from web_agent.agents.modules.execution_modules.optimized_screen_parser import OptimizedScreenParser


class CachePerformanceTest:
    """Test suite for OmniParser caching"""
    
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("❌ GEMINI_API_KEY not set")
        
        # Find test HTML file
        self.test_html = Path.cwd() / "test_omniparser_cache.html"
        if not self.test_html.exists():
            raise FileNotFoundError(f"❌ Test HTML not found at {self.test_html}")
        
        self.test_url = f"file://{self.test_html.absolute()}"
        self.results = []
    
    async def run_all_tests(self):
        """Run complete test suite"""
        print("=" * 80)
        print("🧪 OMNIPARSER CACHE PERFORMANCE TEST SUITE")
        print("=" * 80)
        print(f"📄 Test URL: {self.test_url}")
        print()
        
        # Test 1: Same page multiple visits (L1 cache)
        await self.test_l1_cache_same_page()
        
        # Test 2: Minimal DOM changes
        await self.test_dom_change_detection()
        
        # Test 3: Image diff detection
        await self.test_image_diff_detection()
        
        # Test 4: State changes (cache misses expected)
        await self.test_state_changes()
        
        # Print summary
        self.print_summary()
    
    async def test_l1_cache_same_page(self):
        """Test L1 cache: Visit same page 5 times"""
        print("\n" + "="*80)
        print("TEST 1: L1 Cache - Same Page Multiple Visits")
        print("="*80)
        print("Visiting the same page 5 times - should see cache hits")
        print()
        
        agent = WebAgent(
            gemini_api_key=self.gemini_api_key,
            headless=True,
            window_size=(1280, 720),
            thread_id="cache_test_l1"
        )
        
        try:
            await agent._async_init()
            
            # Get the optimized parser
            parser = agent.task_executor.screen_parser
            
            times = []
            
            for i in range(5):
                print(f"\n--- Visit {i+1}/5 ---")
                await agent.page.goto(self.test_url, wait_until="domcontentloaded")
                await asyncio.sleep(0.5)  # Let page settle
                
                start = time.time()
                screenshot = await agent.capture_screenshot()
                labeled, elements = await parser.parse_screen(
                    screenshot, 
                    url=agent.page.url
                )
                elapsed = time.time() - start
                
                times.append(elapsed)
                print(f"⏱️  Parse time: {elapsed:.3f}s")
                print(f"📊 Found {len(elements)} elements")
            
            # Calculate improvement
            first_time = times[0]
            avg_cached = sum(times[1:]) / len(times[1:])
            speedup = first_time / avg_cached if avg_cached > 0 else 0
            
            self.results.append({
                "test": "L1 Cache - Same Page",
                "first_parse": first_time,
                "avg_cached": avg_cached,
                "speedup": f"{speedup:.1f}x"
            })
            
            print(f"\n✅ L1 Cache Test Complete")
            print(f"   First parse: {first_time:.3f}s")
            print(f"   Avg cached: {avg_cached:.3f}s")
            print(f"   Speedup: {speedup:.1f}x faster")
            
        finally:
            await agent.close()
    
    async def test_dom_change_detection(self):
        """Test DOM change detection by clicking buttons"""
        print("\n" + "="*80)
        print("TEST 2: DOM Change Detection")
        print("="*80)
        print("Testing small DOM changes (button clicks)")
        print()
        
        agent = WebAgent(
            gemini_api_key=self.gemini_api_key,
            headless=False,  # Show browser for this test
            window_size=(1280, 720),
            thread_id="cache_test_dom"
        )
        
        try:
            await agent._async_init()
            parser = agent.task_executor.screen_parser
            
            # Initial load
            print("--- Initial page load ---")
            await agent.page.goto(self.test_url, wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            
            start = time.time()
            screenshot = await agent.capture_screenshot()
            labeled, elements = await parser.parse_screen(screenshot, url=agent.page.url)
            initial_time = time.time() - start
            print(f"⏱️  Initial parse: {initial_time:.3f}s")
            
            # Click counter button (minor DOM change - just number updates)
            print("\n--- After clicking Increment (minor DOM change) ---")
            await agent.page.click('button:has-text("Increment")')
            await asyncio.sleep(0.3)
            
            start = time.time()
            screenshot = await agent.capture_screenshot()
            labeled, elements = await parser.parse_screen(screenshot, url=agent.page.url)
            after_click_time = time.time() - start
            print(f"⏱️  Parse after click: {after_click_time:.3f}s")
            
            # Click again (should detect no structural change)
            print("\n--- Second increment click (DOM structure unchanged) ---")
            await agent.page.click('button:has-text("Increment")')
            await asyncio.sleep(0.3)
            
            start = time.time()
            screenshot = await agent.capture_screenshot()
            labeled, elements = await parser.parse_screen(screenshot, url=agent.page.url)
            second_click_time = time.time() - start
            print(f"⏱️  Parse after 2nd click: {second_click_time:.3f}s")
            
            self.results.append({
                "test": "DOM Change Detection",
                "initial": initial_time,
                "after_minor_change": after_click_time,
                "structure_unchanged": second_click_time
            })
            
        finally:
            await agent.close()
    
    async def test_image_diff_detection(self):
        """Test image diff detection with minimal visual changes"""
        print("\n" + "="*80)
        print("TEST 3: Image Difference Detection")
        print("="*80)
        print("Testing visual similarity detection")
        print()
        
        agent = WebAgent(
            gemini_api_key=self.gemini_api_key,
            headless=True,
            window_size=(1280, 720),
            thread_id="cache_test_diff"
        )
        
        try:
            await agent._async_init()
            parser = agent.task_executor.screen_parser
            
            # Load page
            await agent.page.goto(self.test_url, wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            
            # First parse
            print("--- Initial parse ---")
            start = time.time()
            screenshot1 = await agent.capture_screenshot()
            labeled, elements = await parser.parse_screen(screenshot1, url=agent.page.url)
            time1 = time.time() - start
            print(f"⏱️  Time: {time1:.3f}s")
            
            # Reload same page (should be visually identical)
            print("\n--- After page reload (visually identical) ---")
            await agent.page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            
            start = time.time()
            screenshot2 = await agent.capture_screenshot()
            labeled, elements = await parser.parse_screen(screenshot2, url=agent.page.url)
            time2 = time.time() - start
            print(f"⏱️  Time: {time2:.3f}s")
            
            speedup = time1 / time2 if time2 > 0 else 0
            
            self.results.append({
                "test": "Image Diff Detection",
                "first": time1,
                "after_reload": time2,
                "speedup": f"{speedup:.1f}x"
            })
            
            print(f"\n✅ Image Diff Test Complete")
            print(f"   Speedup: {speedup:.1f}x faster on reload")
            
        finally:
            await agent.close()
    
    async def test_state_changes(self):
        """Test with major state changes (cache misses expected)"""
        print("\n" + "="*80)
        print("TEST 4: Major State Changes (Cache Misses Expected)")
        print("="*80)
        print("Testing cache behavior with significant page changes")
        print()
        
        agent = WebAgent(
            gemini_api_key=self.gemini_api_key,
            headless=False,
            window_size=(1280, 720),
            thread_id="cache_test_states"
        )
        
        try:
            await agent._async_init()
            parser = agent.task_executor.screen_parser
            
            await agent.page.goto(self.test_url, wait_until="domcontentloaded")
            await asyncio.sleep(0.5)
            
            states = ["State 1", "State 2", "State 3"]
            times = []
            
            for state in states:
                print(f"\n--- Switching to {state} ---")
                await agent.page.click(f'button:has-text("Go to {state}")')
                await asyncio.sleep(0.5)
                
                start = time.time()
                screenshot = await agent.capture_screenshot()
                labeled, elements = await parser.parse_screen(screenshot, url=agent.page.url)
                elapsed = time.time() - start
                
                times.append(elapsed)
                print(f"⏱️  Parse time: {elapsed:.3f}s")
                print(f"📊 Found {len(elements)} elements")
            
            avg_time = sum(times) / len(times)
            
            self.results.append({
                "test": "State Changes",
                "avg_parse_time": avg_time,
                "note": "Cache misses expected (different states)"
            })
            
        finally:
            await agent.close()
    
    def print_summary(self):
        """Print test summary with statistics"""
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        for i, result in enumerate(self.results, 1):
            print(f"\nTest {i}: {result['test']}")
            for key, value in result.items():
                if key != 'test':
                    print(f"  {key}: {value}")
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETE")
        print("="*80)


async def main():
    """Run all cache tests"""
    tester = CachePerformanceTest()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
