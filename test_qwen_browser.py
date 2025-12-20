"""
Test Qwen2-VL OCR with browser-rendered HTML
Opens HTML in Playwright, takes screenshot, uses ScreenParser with Qwen OCR
"""

import sys
import os
import asyncio

# Add web-agent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import psutil
import gc
import torch
from playwright.async_api import async_playwright
from PIL import Image

def get_ram_mb():
    """Get current RAM usage in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def create_test_html():
    """Create a simple test HTML page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Page</title>
        <style>
            body { margin: 0; padding: 20px; font-family: Arial; background: white; width: 1440px; height: 900px; }
            .text1 { position: absolute; left: 100px; top: 100px; font-size: 40px; color: black; }
            .text2 { position: absolute; left: 100px; top: 200px; font-size: 40px; color: black; }
            .text3 { position: absolute; left: 100px; top: 300px; font-size: 40px; color: black; }
            .icon1 { position: absolute; left: 500px; top: 100px; width: 100px; height: 100px; border: 3px solid blue; }
            .icon2 { position: absolute; left: 700px; top: 100px; width: 100px; height: 100px; border: 3px solid red; border-radius: 50%; }
        </style>
    </head>
    <body>
        <div class="text1">Hello World</div>
        <div class="text2">Test OCR</div>
        <div class="text3">Games</div>
        <div class="icon1"></div>
        <div class="icon2"></div>
    </body>
    </html>
    """
    
    # Save HTML file
    html_path = "/tmp/test_qwen_browser.html"
    with open(html_path, 'w') as f:
        f.write(html)
    
    return html_path

async def main():
    print("=" * 60)
    print("Testing Qwen2-VL OCR with Browser-Rendered HTML")
    print("=" * 60)
    
    # Initial RAM
    ram_start = get_ram_mb()
    print(f"\n1. Initial RAM: {ram_start:.0f} MB")
    
    # Create test HTML
    print("\n2. Creating test HTML...")
    html_path = create_test_html()
    print(f"   Saved to: {html_path}")
    
    # Open in Playwright and capture screenshot
    print("\n3. Opening HTML in Playwright browser...")
    screenshot_path = "/tmp/test_screenshot.png"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        
        await page.goto(f'file://{html_path}', wait_until='networkidle')
        print(f"   Page loaded: file://{html_path}")
        
        # Wait a bit for rendering
        await page.wait_for_timeout(500)
        
        # Take screenshot
        screenshot_bytes = await page.screenshot(type='png', full_page=False)
        print(f"   Screenshot captured ({len(screenshot_bytes)} bytes)")
        
        # Save screenshot
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_bytes)
        print(f"   Screenshot saved: {screenshot_path}")
        
        await browser.close()
    
    # Load screenshot
    print("\n4. Loading screenshot...")
    screenshot = Image.open(screenshot_path)
    print(f"   Image size: {screenshot.size}")
    
    # Use ScreenParser with Qwen OCR
    print("\n5. Parsing screen with ScreenParser (Qwen OCR)...")
    from web_agent.perception.screen_parser import ScreenParser
    
    ram_before_parse = get_ram_mb()
    print(f"   RAM before parsing: {ram_before_parse:.0f} MB")
    
    parser = ScreenParser()
    elements = parser.parse(screenshot)
    
    ram_after_parse = get_ram_mb()
    ram_spike = ram_after_parse - ram_before_parse
    print(f"   RAM after parsing: {ram_after_parse:.0f} MB (+{ram_spike:.0f} MB)")
    
    # Show results
    print(f"\n6. Parsing Results:")
    print(f"   Found {len(elements)} elements")
    print("\n   Elements detected:")
    for elem in elements[:15]:  # Show first 15
        # Element is an object, not a dict
        elem_type = elem.type if hasattr(elem, 'type') else 'unknown'
        content = elem.content if hasattr(elem, 'content') else ''
        bbox = elem.bbox if hasattr(elem, 'bbox') else []
        print(f"   - [{elem_type}] '{content}' at {bbox}")
    
    # Check RAM spike
    print(f"\n7. Memory Analysis:")
    if ram_spike < 3000:  # Less than 3GB spike
        print(f"   ✅ RAM spike: {ram_spike:.0f} MB (< 3GB - Qwen OCR working efficiently)")
    else:
        print(f"   ❌ RAM spike: {ram_spike:.0f} MB (>= 3GB - may be using PaddleOCR)")
    
    # Clean up
    print(f"\n8. Cleaning up...")
    del screenshot
    del elements
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    ram_final = get_ram_mb()
    print(f"   Final RAM: {ram_final:.0f} MB")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
