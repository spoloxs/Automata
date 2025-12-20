"""
Test MasterAgent with MOCK ScreenParser to isolate memory leak source.
If RAM still explodes with mock parser, the leak is in agent workflow, not parsing!
"""
import asyncio
import gc
import psutil
import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY
from mock_screen_parser import MockScreenParser


def get_ram_mb():
    """Get current process RAM in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def test_with_mock_parser():
    print("\n" + "="*70)
    print("RAM TEST WITH MOCK SCREEN PARSER")
    print("="*70)
    print("Goal: See if RAM still leaks when NO parsing happens")
    print("="*70)
    
    # Baseline
    baseline_ram = get_ram_mb()
    print(f"\n1. Baseline: {baseline_ram:.1f} MB")
    
    # Patch ScreenParser with MockScreenParser
    print("\n2. Patching ScreenParser with MockScreenParser...")
    with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
        print("   ✅ ScreenParser patched - NO real parsing will happen!\n")
        
        # Create and initialize master agent
        print("3. Creating MasterAgent...")
        master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
        await master.initialize()
        
        after_init_ram = get_ram_mb()
        print(f"   After init: {after_init_ram:.1f} MB (+{after_init_ram - baseline_ram:.1f} MB)\n")
        
        # Run task
        print("4. Running task (with MOCK parser)...")
        result = await master.execute_goal(
            goal="Navigate to google.com",
            starting_url="https://www.google.com",
            timeout=60
        )
        
        after_task_ram = get_ram_mb()
        print(f"\n   After task: {after_task_ram:.1f} MB (+{after_task_ram - after_init_ram:.1f} MB)")
        
        # Cleanup
        print("\n5. Cleanup...")
        await master.cleanup()
        del master
        gc.collect()
        gc.collect()
        
        after_cleanup_ram = get_ram_mb()
        print(f"   After cleanup: {after_cleanup_ram:.1f} MB ({after_cleanup_ram - after_task_ram:+.1f} MB)")
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"RAM during task: {after_task_ram - after_init_ram:.1f} MB")
    print(f"RAM freed after cleanup: {after_task_ram - after_cleanup_ram:.1f} MB")
    print(f"RAM still held: {after_cleanup_ram - after_init_ram:.1f} MB")
    print("\n" + "="*70)
    
    if (after_cleanup_ram - after_init_ram) > 100:
        print("❌ LEAK DETECTED: RAM still held > 100 MB")
        print("   → Leak is in AGENT WORKFLOW, not parsing!")
    else:
        print("✅ NO MAJOR LEAK: Most RAM freed")
        print("   → Leak was from PARSING (OmniParser objects)")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(test_with_mock_parser())
