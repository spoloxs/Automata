"""
RAM Diagnostic Test - Monitor memory at each agent step
"""
import asyncio
import gc
import psutil
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


def get_ram_mb():
    """Get current process RAM in MB"""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


async def test_ram_step_by_step():
    """Test RAM usage at each step"""
    print("\n" + "="*70)
    print("RAM DIAGNOSTIC TEST")
    print("="*70)
    
    # Step 1: Baseline
    gc.collect()
    baseline_ram = get_ram_mb()
    print(f"\n1️⃣  Baseline (before anything): {baseline_ram:.1f} MB")
    
    # Step 2: Create MasterAgent
    print(f"\n2️⃣  Creating MasterAgent...")
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
    gc.collect()
    after_master_ram = get_ram_mb()
    print(f"    RAM after MasterAgent: {after_master_ram:.1f} MB (+{after_master_ram - baseline_ram:.1f} MB)")
    
    # Step 3: Initialize (loads OmniParser models)
    print(f"\n3️⃣  Initializing (loading ML models)...")
    await master.initialize()
    gc.collect()
    after_init_ram = get_ram_mb()
    print(f"    RAM after initialize: {after_init_ram:.1f} MB (+{after_init_ram - after_master_ram:.1f} MB)")
    
    # Step 4: Simple navigation task
    print(f"\n4️⃣  Executing simple task...")
    goal = "Navigate to google.com"
    starting_url = "https://www.google.com"
    
    result = await master.execute_goal(
        goal=goal,
        starting_url=starting_url,
        timeout=60
    )
    gc.collect()
    after_task_ram = get_ram_mb()
    print(f"    RAM after task 1: {after_task_ram:.1f} MB (+{after_task_ram - after_init_ram:.1f} MB)")
    print(f"    Task success: {result.success}")
    
    # Step 5: Check Gemini sessions
    active_sessions = master.gemini.get_active_sessions()
    print(f"    Active Gemini sessions: {active_sessions}")
    
    # Step 6: Cleanup
    print(f"\n5️⃣  Cleaning up...")
    await master.cleanup()
    
    # CRITICAL: Delete the master object to release ALL references
    del master
    gc.collect()
    gc.collect()  # Call twice for cyclic references
    
    after_cleanup_ram = get_ram_mb()
    print(f"    RAM after cleanup: {after_cleanup_ram:.1f} MB ({after_cleanup_ram - after_task_ram:+.1f} MB)")
    
    # Step 7: Run ANOTHER task to verify RAM doesn't keep growing
    print(f"\n6️⃣  Creating NEW MasterAgent for second task...")
    master2 = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
    await master2.initialize()
    gc.collect()
    after_init2_ram = get_ram_mb()
    print(f"    RAM after second init: {after_init2_ram:.1f} MB")
    
    print(f"\n7️⃣  Executing second task...")
    result2 = await master2.execute_goal(
        goal="Navigate to bing.com",
        starting_url="https://www.bing.com",
        timeout=60
    )
    gc.collect()
    after_task2_ram = get_ram_mb()
    print(f"    RAM after task 2: {after_task2_ram:.1f} MB (+{after_task2_ram - after_init2_ram:.1f} MB)")
    print(f"    Task success: {result2.success}")
    
    active_sessions2 = master2.gemini.get_active_sessions()
    print(f"    Active Gemini sessions: {active_sessions2}")
    
    await master2.cleanup()
    gc.collect()
    final_ram = get_ram_mb()
    print(f"    RAM after cleanup 2: {final_ram:.1f} MB")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Baseline:              {baseline_ram:.1f} MB")
    print(f"After MasterAgent:     {after_master_ram:.1f} MB (+{after_master_ram - baseline_ram:.1f} MB)")
    print(f"After Init (models):   {after_init_ram:.1f} MB (+{after_init_ram - baseline_ram:.1f} MB)")
    print(f"After Task 1:          {after_task_ram:.1f} MB (+{after_task_ram - after_init_ram:.1f} MB)")
    print(f"After Cleanup 1:       {after_cleanup_ram:.1f} MB")
    print(f"After Task 2:          {after_task2_ram:.1f} MB (+{after_task2_ram - after_init2_ram:.1f} MB)")
    print(f"After Cleanup 2:       {final_ram:.1f} MB")
    print("="*70)
    
    # Verdict
    task1_growth = after_task_ram - after_init_ram
    task2_growth = after_task2_ram - after_init2_ram
    
    print("\nVERDICT:")
    if abs(task2_growth - task1_growth) < 100:  # Within 100 MB difference
        print(f"✅ MEMORY LEAK FIXED! Task growth is consistent:")
        print(f"   Task 1: +{task1_growth:.1f} MB")
        print(f"   Task 2: +{task2_growth:.1f} MB")
        print(f"   Difference: {abs(task2_growth - task1_growth):.1f} MB (acceptable)")
    else:
        print(f"❌ POTENTIAL LEAK: Task 2 used significantly more RAM:")
        print(f"   Task 1: +{task1_growth:.1f} MB")
        print(f"   Task 2: +{task2_growth:.1f} MB")
        print(f"   Difference: {abs(task2_growth - task1_growth):.1f} MB (concerning)")
    
    if active_sessions2 > 5:
        print(f"⚠️  WARNING: {active_sessions2} Gemini sessions still active (should be 0-2)")
    else:
        print(f"✅ Gemini sessions: {active_sessions2} (healthy)")


if __name__ == "__main__":
    asyncio.run(test_ram_step_by_step())
