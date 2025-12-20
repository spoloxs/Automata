"""
Test Image/Screenshot memory leak - PIL Image objects accumulation
"""
import asyncio
import gc
import io
import base64
from PIL import Image, ImageDraw
from web_agent.util.memory_monitor import get_memory_monitor

async def test_image_memory():
    print("="*60)
    print("MEMORY TEST: PIL Image objects")
    print("="*60)
    
    mem_monitor = get_memory_monitor()
    mem_monitor.set_baseline()
    mem_monitor.log_ram("Baseline")
    
    # Test 1: Create and delete images without proper cleanup
    print("\n--- Test 1: Create 50 images WITHOUT explicit del ---")
    images_list = []
    for i in range(50):
        img = Image.new('RGB', (1280, 720), color=(i % 255, (i*2) % 255, (i*3) % 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), f"Screenshot {i}", fill=(255, 255, 255))
        images_list.append(img)
        
        if i % 10 == 0:
            mem_monitor.log_ram(f"After creating {i+1} images")
    
    mem_monitor.log_ram("After creating 50 images (before cleanup)")
    
    # Clear list and force GC
    images_list.clear()
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After clearing list and GC")
    
    # Test 2: Create and immediately delete images
    print("\n--- Test 2: Create 50 images WITH immediate del ---")
    for i in range(50):
        img = Image.new('RGB', (1280, 720), color=(i % 255, (i*2) % 255, (i*3) % 255))
        draw = ImageDraw.Draw(img)
        draw.text((100, 100), f"Screenshot {i}", fill=(255, 255, 255))
        del draw, img  # Immediate cleanup
        
        if i % 10 == 0:
            gc.collect()
            mem_monitor.log_ram(f"After creating+deleting {i+1} images")
    
    mem_monitor.log_ram("After creating+deleting 50 images")
    
    # Test 3: Base64 encoding (used for LLM vision)
    print("\n--- Test 3: Base64 encoding simulation (LLM vision calls) ---")
    for i in range(20):
        img = Image.new('RGB', (1280, 720), color=(100, 150, 200))
        
        # Simulate vision API call
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # WITHOUT proper cleanup (common mistake)
        if i < 10:
            # Bad: only delete img, leave buffered and img_base64
            del img
        else:
            # Good: delete everything
            buffered.close()
            del img, buffered, img_base64
        
        if i % 5 == 0:
            gc.collect()
            mem_monitor.log_ram(f"After {i+1} vision calls")
    
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After all vision call tests")
    
    # Test 4: Verify screenshot lifecycle (browser simulation)
    print("\n--- Test 4: Screenshot lifecycle (10 iterations) ---")
    for i in range(10):
        # Simulate browser screenshot
        screenshot = Image.new('RGB', (1280, 720), color=(255, 255, 255))
        draw = ImageDraw.Draw(screenshot)
        draw.text((200, 200), f"Page content {i}", fill=(0, 0, 0))
        del draw
        
        # Simulate passing to parser (parser makes a copy internally)
        screenshot_copy = screenshot.copy()
        
        # Simulate passing to verifier with base64
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        # Proper cleanup
        buffered.close()
        del screenshot, screenshot_copy, buffered, img_base64
        gc.collect()
        
        if i % 3 == 0:
            mem_monitor.log_ram(f"After screenshot lifecycle {i+1}")
    
    mem_monitor.log_ram("After all screenshot lifecycle tests")
    
    # Final cleanup
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("Final cleanup")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_image_memory())
