"""
Test GeminiAgent memory leak - chat_histories accumulation
"""
import asyncio
import gc
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.util.memory_monitor import get_memory_monitor
import os

async def test_gemini_memory():
    print("="*60)
    print("MEMORY TEST: GeminiAgent chat_histories")
    print("="*60)
    
    # Skip if no API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("⚠️  No GEMINI_API_KEY found - skipping test")
        return
    
    mem_monitor = get_memory_monitor()
    mem_monitor.set_baseline()
    mem_monitor.log_ram("Baseline")
    
    # Initialize Gemini agent
    gemini = GeminiAgent(api_key=api_key)
    mem_monitor.log_ram("After GeminiAgent init")
    
    # Simulate 20 workers, each creating a unique thread
    print("\n--- Simulating 20 workers ---")
    for i in range(20):
        thread_id = f"worker_test_{i}"
        
        # Simulate a decision call (adds to chat_histories)
        try:
            actions = await gemini.decide_action(
                task=f"Test task {i}",
                elements=[],
                url="https://example.com",
                thread_id=thread_id,
                storage_data={},
                viewport_size=(1280, 720),
            )
        except Exception as e:
            print(f"   Error in decision {i}: {e}")
        
        if i % 5 == 0:
            active = gemini.get_active_sessions()
            mem_monitor.log_ram(f"After {i+1} workers ({active} active sessions)")
    
    final_sessions = gemini.get_active_sessions()
    print(f"\n📊 Final active sessions: {final_sessions}")
    mem_monitor.log_ram(f"Before cleanup ({final_sessions} sessions)")
    
    # Test 1: Clear all histories manually
    print("\n--- Clearing all chat histories ---")
    gemini.chat_histories.clear()
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After clearing chat_histories")
    
    print(f"📊 Active sessions after clear: {gemini.get_active_sessions()}")
    
    # Test 2: Create more workers and test incremental cleanup
    print("\n--- Testing incremental cleanup ---")
    for i in range(10):
        thread_id = f"worker_cleanup_test_{i}"
        try:
            await gemini.decide_action(
                task=f"Cleanup test {i}",
                elements=[],
                url="https://example.com",
                thread_id=thread_id,
                storage_data={},
                viewport_size=(1280, 720),
            )
        except:
            pass
        
        # Clear immediately after each worker
        gemini.clear_context(thread_id)
    
    final_after_incremental = gemini.get_active_sessions()
    print(f"\n📊 Sessions after incremental cleanup: {final_after_incremental}")
    mem_monitor.log_ram("After incremental cleanup test")
    
    # Final cleanup
    del gemini
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("Final cleanup")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_gemini_memory())
