"""
Simple memory test - Just parse a screenshot 5 times and monitor RAM.
"""
import asyncio
import gc
from PIL import Image
from web_agent.perception.screen_parser import ScreenParser
from web_agent.util.memory_monitor import get_memory_monitor

async def test_parse_memory():
    print("="*60)
    print("MEMORY TEST: Parse 5 times")
    print("="*60)
    
    mem_monitor = get_memory_monitor()
    mem_monitor.set_baseline()
    mem_monitor.log_ram("Test: Baseline")
    
    # Initialize parser
    parser = ScreenParser()
    mem_monitor.log_ram("Test: After ScreenParser init")
    
    # Create a test image with some text (so OCR doesn't crash on blank image)
    from PIL import ImageDraw, ImageFont
    test_image = Image.new('RGB', (1280, 720), color=(255, 255, 255))
    draw = ImageDraw.Draw(test_image)
    # Add some text so OCR has something to detect
    draw.text((100, 100), "Test Button", fill=(0, 0, 0))
    draw.text((300, 300), "Click Here", fill=(0, 0, 0))
    del draw
    mem_monitor.log_ram("Test: After creating test image")
    
    # Parse 5 times
    for i in range(5):
        print(f"\n--- Parse {i+1} ---")
        elements = parser.parse(test_image)
        print(f"Found {len(elements)} elements")
        mem_monitor.log_ram(f"Test: After parse {i+1}")
        
        # Delete immediately
        del elements
        gc.collect()
        mem_monitor.log_ram(f"Test: After cleanup {i+1}")
    
    # Final cleanup
    del test_image, parser
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("Test: Final cleanup")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_parse_memory())
