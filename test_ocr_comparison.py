"""
Compare Qwen2-VL OCR vs EasyOCR
Tests both approaches on the same browser-rendered HTML to compare:
- RAM usage
- Detection accuracy
- Speed
"""

import sys
import os
import asyncio
import time

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
    html_path = "/tmp/test_ocr_comparison.html"
    with open(html_path, 'w') as f:
        f.write(html)
    
    return html_path

async def test_with_ocr_method(screenshot, method_name):
    """Test with specific OCR method"""
    print(f"\n{'='*60}")
    print(f"Testing with {method_name}")
    print(f"{'='*60}")
    
    from web_agent.perception.omniparser_wrapper import get_omniparser, check_ocr_box
    
    ram_start = get_ram_mb()
    print(f"  RAM at start: {ram_start:.0f} MB")
    
    # Get parser (reuse instance to save init time)
    parser = get_omniparser()
    
    ram_before = get_ram_mb()
    print(f"  RAM before OCR: {ram_before:.0f} MB")
    
    # Configure OCR method
    if method_name == "Qwen2-VL OCR":
        use_qwen = True
        use_paddle = False
        qwen_model = (parser.caption_model_processor["model"], parser.caption_model_processor["processor"])
    else:  # EasyOCR
        use_qwen = False
        use_paddle = False
        qwen_model = None
    
    # Run OCR
    time_start = time.time()
    ocr_bbox_rslt, _ = check_ocr_box(
        screenshot,
        display_img=False,
        output_bb_format="xyxy",
        goal_filtering=None,
        easyocr_args={"paragraph": False, "text_threshold": 0.9},
        use_paddleocr=use_paddle,
        use_qwen_ocr=use_qwen,
        qwen_model_processor=qwen_model,
    )
    time_end = time.time()
    
    text, ocr_bbox = ocr_bbox_rslt
    
    ram_after = get_ram_mb()
    ram_spike = ram_after - ram_before
    ocr_time = time_end - time_start
    
    # Save results before cleanup
    text_count = len(text) if text else 0
    text_content = text if text else 'None'
    
    print(f"\n  Results:")
    print(f"  - Text detected: {text_count} items")
    print(f"  - Text content: {text_content}")
    print(f"  - RAM spike: {ram_spike:.0f} MB")
    print(f"  - Time: {ocr_time:.2f}s")
    
    # Clean up
    del ocr_bbox_rslt, text, ocr_bbox
    gc.collect()
    
    ram_final = get_ram_mb()
    print(f"  - RAM after cleanup: {ram_final:.0f} MB")
    
    return {
        'method': method_name,
        'text_count': text_count,
        'ram_spike': ram_spike,
        'time': ocr_time,
        'ram_final': ram_final
    }

async def main():
    print("=" * 60)
    print("OCR Method Comparison Test")
    print("=" * 60)
    
    # Create test HTML
    print("\n1. Creating test HTML...")
    html_path = create_test_html()
    print(f"   Saved to: {html_path}")
    
    # Open in Playwright and capture screenshot
    print("\n2. Capturing screenshot...")
    screenshot_path = "/tmp/test_ocr_comparison.png"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        
        await page.goto(f'file://{html_path}', wait_until='networkidle')
        await page.wait_for_timeout(500)
        
        screenshot_bytes = await page.screenshot(type='png', full_page=False)
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_bytes)
        
        await browser.close()
    
    screenshot = Image.open(screenshot_path)
    print(f"   Screenshot size: {screenshot.size}")
    
    # Test both methods
    results = []
    
    # Test 1: Qwen2-VL OCR
    result_qwen = await test_with_ocr_method(screenshot, "Qwen2-VL OCR")
    results.append(result_qwen)
    
    # Clean up before next test
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    await asyncio.sleep(2)
    
    # Test 2: EasyOCR
    result_easy = await test_with_ocr_method(screenshot, "EasyOCR")
    results.append(result_easy)
    
    # Summary
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"\n{'Method':<20} {'Text Count':<12} {'RAM Spike':<12} {'Time (s)':<10}")
    print(f"{'-'*60}")
    for r in results:
        print(f"{r['method']:<20} {r['text_count']:<12} {r['ram_spike']:.0f} MB{'':<5} {r['time']:.2f}")
    
    print(f"\n{'='*60}")
    qwen_spike = results[0]['ram_spike']
    easy_spike = results[1]['ram_spike']
    diff = easy_spike - qwen_spike
    pct = (diff / easy_spike * 100) if easy_spike > 0 else 0
    
    if qwen_spike < easy_spike:
        print(f"✅ Qwen2-VL OCR uses {diff:.0f} MB LESS ({pct:.1f}% reduction)")
    else:
        print(f"❌ Qwen2-VL OCR uses {-diff:.0f} MB MORE")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
