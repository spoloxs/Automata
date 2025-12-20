"""
Find what's using all the RAM
"""
import asyncio
import gc
import sys
from pathlib import Path

project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


async def test():
    print("\n" + "="*70)
    print("MEMORY INVESTIGATION - What's using the RAM?")
    print("="*70)
    
    # Create and run task
    print("\nCreating MasterAgent and running task...")
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
    await master.initialize()
    
    result = await master.execute_goal(
        goal="Navigate to google.com",
        starting_url="https://www.google.com",
        timeout=60
    )
    
    print("\n" + "="*70)
    print("OBJECTS IN MEMORY (before cleanup)")
    print("="*70)
    
    # Check what modules are loaded
    print("\n📦 Loaded modules with 'ocr' or 'paddle' or 'easy':")
    for name in sys.modules.keys():
        if 'ocr' in name.lower() or 'paddle' in name.lower() or 'easy' in name.lower():
            print(f"  - {name}")
    
    # Check OmniParser utils
    print("\n📦 OmniParser utils module:")
    if 'omniparser_utils' in sys.modules:
        utils = sys.modules['omniparser_utils']
        print(f"  ✅ Found omniparser_utils module")
        print(f"  - Has 'reader': {hasattr(utils, 'reader')}")
        print(f"  - Has 'paddle_ocr': {hasattr(utils, 'paddle_ocr')}")
    else:
        print("  ❌ No omniparser_utils in sys.modules")
    
    # Check object counts
    print("\n📊 Object counts:")
    gc.collect()
    objects = gc.get_objects()
    print(f"  Total objects: {len(objects)}")
    
    # Cleanup
    print("\n" + "="*70)
    print("CLEANUP")
    print("="*70)
    await master.cleanup()
    del master
    gc.collect()
    gc.collect()
    
    print("\n" + "="*70)
    print("AFTER CLEANUP")
    print("="*70)
    
    # Check again
    print("\n📦 OmniParser utils after cleanup:")
    if 'omniparser_utils' in sys.modules:
        utils = sys.modules['omniparser_utils']
        print(f"  ✅ Still in modules")
        print(f"  - Has 'reader': {hasattr(utils, 'reader')}")
        print(f"  - Has 'paddle_ocr': {hasattr(utils, 'paddle_ocr')}")
    else:
        print("  ✅ Removed from sys.modules")
    
    gc.collect()
    objects_after = gc.get_objects()
    print(f"\n📊 Objects after cleanup: {len(objects_after)} (was {len(objects)})")
    print(f"  Difference: {len(objects) - len(objects_after)}")


if __name__ == "__main__":
    asyncio.run(test())
