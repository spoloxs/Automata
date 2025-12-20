#!/usr/bin/env python3
"""
OmniParser Cache Test - Fixed for 3-tuple return
"""

import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

print(f"📂 Project root: {PROJECT_ROOT}")

from web_agent.agents.web_agent import WebAgent


async def main():
    print("\n" + "=" * 60)
    print("🧪 OMNIPARSER CACHE TEST")
    print("=" * 60)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY not set")
        return
    
    print("✅ GEMINI_API_KEY found")
    
    # Find test HTML
    test_dir = Path(__file__).parent
    test_html = test_dir / "test_omniparser_cache.html"
    
    if not test_html.exists():
        print(f"Creating test HTML...")
        create_test_html(test_html)
    
    test_url = f"file://{test_html.absolute()}"
    print(f"📄 Test URL: {test_url}\n")
    
    agent = WebAgent(
        gemini_api_key=gemini_api_key,
        headless=False,
        window_size=(1280, 720),
        thread_id="cache_test",
        enable_parser_cache=True,  # Enable caching
        enable_image_diff=True,
    )
    
    try:
        print("🔧 Initializing agent...")
        await agent._async_init()
        
        parser = agent.parser
        print(f"✅ Parser type: {type(parser).__name__}")
        
        # Check if optimized
        is_optimized = hasattr(parser, 'get_stats')
        if is_optimized:
            print("   🎉 OptimizedOmniParser active!")
        else:
            print("   ⚠️  Original parser (no caching)")
        
        print()
        
        # Helper function to parse (handles 3-tuple return)
        async def parse_screenshot(screenshot, url=None):
            if is_optimized:
                # OptimizedOmniParser: returns 3 values
                result = await parser.parse_screen(screenshot, url=url)
            else:
                # Original OmniParser: returns 3 values
                result = await parser.parse_screen(screenshot)
            
            # Handle 3-tuple return: (labeled_image, elements, all_text)
            if isinstance(result, tuple):
                if len(result) >= 3:
                    return result[0], result[1], result[2]  # labeled, elements, all_text
                elif len(result) == 2:
                    return result[0], result[1], []  # labeled, elements, empty all_text
                else:
                    return screenshot, [], []
            return screenshot, [], []
        
        import time
        
        # Visit 1: Initial load
        print("="*60)
        print("VISIT 1: Initial page load")
        print("="*60)
        await agent.page.goto(test_url, wait_until="domcontentloaded")
        await asyncio.sleep(1)
        
        start = time.time()
        screenshot = await agent.capture_screenshot()
        labeled, elements, all_text = await parse_screenshot(screenshot, url=agent.page.url)
        elapsed1 = time.time() - start
        
        print(f"⏱️  Parse time: {elapsed1:.3f}s")
        print(f"✅ Found {len(elements)} elements, {len(all_text)} text items")
        
        # Visit 2: Reload (should be cached)
        print("\n" + "="*60)
        print("VISIT 2: Page reload (cache expected)")
        print("="*60)
        
        await agent.page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(1)
        
        start = time.time()
        screenshot = await agent.capture_screenshot()
        labeled, elements, all_text = await parse_screenshot(screenshot, url=agent.page.url)
        elapsed2 = time.time() - start
        
        print(f"⏱️  Parse time: {elapsed2:.3f}s")
        print(f"✅ Found {len(elements)} elements, {len(all_text)} text items")
        
        if elapsed2 < elapsed1 * 0.5:
            speedup = elapsed1 / elapsed2 if elapsed2 > 0 else 999
            print(f"🚀 Speedup: {speedup:.1f}x faster!")
        
        # Visit 3: Click button
        print("\n" + "="*60)
        print("VISIT 3: After button click")
        print("="*60)
        
        try:
            await agent.page.click('button:has-text("Increment")', timeout=5000)
            await asyncio.sleep(0.5)
            
            start = time.time()
            screenshot = await agent.capture_screenshot()
            labeled, elements, all_text = await parse_screenshot(screenshot, url=agent.page.url)
            elapsed3 = time.time() - start
            
            print(f"⏱️  Parse time: {elapsed3:.3f}s")
            print(f"✅ Found {len(elements)} elements")
        except Exception as e:
            print(f"⚠️  Button click failed: {e}")
        
        # Visit 4: Another reload
        print("\n" + "="*60)
        print("VISIT 4: Another reload")
        print("="*60)
        
        await agent.page.reload(wait_until="domcontentloaded")
        await asyncio.sleep(0.5)
        
        start = time.time()
        screenshot = await agent.capture_screenshot()
        labeled, elements, all_text = await parse_screenshot(screenshot, url=agent.page.url)
        elapsed4 = time.time() - start
        
        print(f"⏱️  Parse time: {elapsed4:.3f}s")
        print(f"✅ Found {len(elements)} elements")
        
        # Summary
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        
        print(f"\nParse times:")
        print(f"  Visit 1 (initial): {elapsed1:.3f}s")
        print(f"  Visit 2 (reload):  {elapsed2:.3f}s")
        print(f"  Visit 4 (reload):  {elapsed4:.3f}s")
        
        if is_optimized:
            print(f"\n📈 Cache Statistics:")
            stats = parser.get_stats()
            for key, value in stats.items():
                print(f"  {key}: {value}")
            
            total_hits = stats.get('l1_hits', 0) + stats.get('image_diff_skips', 0)
            if total_hits > 0:
                print("\n✅ CACHE IS WORKING! 🎉")
            else:
                print("\n⚠️  No cache hits detected")
        else:
            print("\n⚠️  Caching not available")
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🔒 Closing agent...")
        await agent.close()


def create_test_html(path: Path):
    """Create test HTML file"""
    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OmniParser Test</title>
    <style>
        body { 
            font-family: Arial; 
            padding: 50px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
        }
        .container { 
            background: white; 
            padding: 40px; 
            border-radius: 15px; 
            max-width: 600px; 
            margin: 0 auto; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }
        h1 { color: #667eea; text-align: center; }
        .counter { 
            font-size: 48px; 
            text-align: center; 
            color: #667eea; 
            margin: 20px 0; 
            font-weight: bold;
        }
        button { 
            padding: 15px 25px; 
            margin: 10px; 
            font-size: 16px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            background: #667eea; 
            color: white; 
        }
        button:hover { background: #5568d3; transform: translateY(-2px); }
        .btn-group { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 OmniParser Cache Test</h1>
        <div class="counter" id="counter">0</div>
        <div class="btn-group">
            <button onclick="increment()">➕ Increment</button>
            <button onclick="decrement()">➖ Decrement</button>
            <button onclick="reset()">🔄 Reset</button>
        </div>
    </div>
    <script>
        let count = 0;
        function increment() { 
            count++; 
            document.getElementById('counter').textContent = count; 
        }
        function decrement() { 
            count--; 
            document.getElementById('counter').textContent = count; 
        }
        function reset() { 
            count = 0; 
            document.getElementById('counter').textContent = count; 
        }
    </script>
</body>
</html>'''
    path.write_text(html)
    print(f"✅ Created test HTML at {path}")


if __name__ == "__main__":
    asyncio.run(main())
