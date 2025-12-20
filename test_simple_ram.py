"""
Simpler RAM test - Just test if cleanup works AT ALL
"""
import asyncio
import gc
import psutil
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


def get_ram_mb():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


async def test():
    print("\n" + "="*70)
    print("SIMPLE RAM TEST - Does cleanup work?")
    print("="*70)
    
    # Baseline
    gc.collect()
    baseline = get_ram_mb()
    print(f"\n1. Baseline: {baseline:.1f} MB")
    
    # Create MasterAgent
    print(f"\n2. Creating MasterAgent...")
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
    await master.initialize()
    gc.collect()
    after_init = get_ram_mb()
    print(f"   After init: {after_init:.1f} MB (+{after_init - baseline:.1f} MB)")
    
    # Run ONE simple task
    print(f"\n3. Running task...")
    result = await master.execute_goal(
        goal="Navigate to google.com",
        starting_url="https://www.google.com",
        timeout=60
    )
    gc.collect()
    after_task = get_ram_mb()
    print(f"   After task: {after_task:.1f} MB (+{after_task - after_init:.1f} MB)")
    
    # Cleanup
    print(f"\n4. Cleanup...")
    await master.cleanup()
    del master
    gc.collect()
    gc.collect()
    after_cleanup = get_ram_mb()
    print(f"   After cleanup: {after_cleanup:.1f} MB ({after_cleanup - after_task:+.1f} MB)")
    
    # Verdict
    print("\n" + "="*70)
    freed = after_task - after_cleanup
    if freed > 100:
        print(f"✅ CLEANUP WORKS! Freed {freed:.1f} MB")
    elif freed > 0:
        print(f"⚠️  PARTIAL: Freed {freed:.1f} MB (should be more)")
    else:
        print(f"❌ CLEANUP BROKEN! Freed {freed:.1f} MB (nothing!)")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test())
