"""
Test to verify action_loop screenshot leak fix.
This simulates multiple action loop iterations to ensure screenshots are properly cleaned up.
"""
import asyncio
import gc
from PIL import Image, ImageDraw
from web_agent.util.memory_monitor import get_memory_monitor

async def test_action_loop_screenshot_cleanup():
    """
    Simulate what happens in action_loop:
    - Create screenshot (like _observe does)
    - Use it for decisions/actions
    - Delete it immediately (the fix)
    - Repeat 100 times (typical task)
    """
    print("="*60)
    print("MEMORY TEST: Action Loop Screenshot Cleanup")
    print("="*60)
    
    mem_monitor = get_memory_monitor()
    mem_monitor.set_baseline()
    mem_monitor.log_ram("Baseline")
    
    print("\n--- Simulating 100 action loop iterations ---")
    print("(Each iteration creates screenshot, uses it, then deletes)")
    
    for i in range(100):
        # Simulate _observe() - creates screenshot
        screenshot = Image.new('RGB', (1280, 720), color=(i % 255, 100, 150))
        draw = ImageDraw.Draw(screenshot)
        draw.text((100, 100), f"Iteration {i}", fill=(255, 255, 255))
        del draw
        
        # Simulate using screenshot (parsing, decisions, etc)
        # In real code, screenshot would be in Observation object
        
        # CRITICAL FIX: Delete screenshot immediately (like our fix in action_loop.py)
        del screenshot
        
        # Force GC every 10 iterations
        if i % 10 == 9:
            gc.collect()
            mem_monitor.log_ram(f"After {i+1} iterations (WITH cleanup)")
    
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After 100 iterations - Final")
    
    print("\n--- Now test WITHOUT cleanup (to show the leak) ---")
    screenshots_list = []
    for i in range(100):
        screenshot = Image.new('RGB', (1280, 720), color=(i % 255, 200, 100))
        draw = ImageDraw.Draw(screenshot)
        draw.text((100, 100), f"Leak {i}", fill=(255, 255, 255))
        del draw
        screenshots_list.append(screenshot)  # Keep reference - simulates leak!
        
        if i % 10 == 9:
            mem_monitor.log_ram(f"After {i+1} iterations (WITHOUT cleanup - LEAK)")
    
    mem_monitor.log_ram("After 100 iterations WITHOUT cleanup - see the leak!")
    
    # Now cleanup the leak
    screenshots_list.clear()
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After cleaning up the leak")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\nExpected results:")
    print("  WITH cleanup: RAM should stay stable (~+10-20MB total)")
    print("  WITHOUT cleanup: RAM should grow ~500-700MB")
    print("  After cleanup: RAM should return to baseline")

if __name__ == "__main__":
    asyncio.run(test_action_loop_screenshot_cleanup())
