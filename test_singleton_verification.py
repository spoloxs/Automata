"""
Test script to verify MasterAgent singleton pattern and instance sharing.

This script demonstrates that:
1. Only ONE MasterAgent can exist at a time
2. All workers share the same ScreenParser, GeminiAgent, etc.
3. Attempting to create a second MasterAgent returns the existing instance
4. After cleanup(), a new MasterAgent can be created
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY


async def test_singleton_pattern():
    """Test that MasterAgent enforces singleton pattern."""
    print("=" * 70)
    print("TEST 1: Singleton Pattern Enforcement")
    print("=" * 70)
    
    # Create first MasterAgent
    print("\n1️⃣  Creating first MasterAgent...")
    master1 = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=2)
    master1_id = id(master1)
    print(f"   ✅ Created master1 with id: {master1_id}")
    print(f"   ✅ MasterAgent.master_id: {master1.master_id}")
    
    # Try to create second MasterAgent (should return same instance)
    print("\n2️⃣  Attempting to create second MasterAgent...")
    master2 = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=2)
    master2_id = id(master2)
    print(f"   ✅ Returned master2 with id: {master2_id}")
    
    # Verify they are the same instance
    if master1_id == master2_id:
        print(f"\n   ✅ SUCCESS: master1 and master2 are the SAME instance!")
        print(f"   ✅ Singleton pattern is working correctly")
    else:
        print(f"\n   ❌ FAILURE: master1 and master2 are DIFFERENT instances!")
        print(f"   ❌ Singleton pattern is NOT working")
        return False
    
    # Verify they share the same components
    print("\n3️⃣  Verifying component sharing...")
    parser1_id = id(master1.parser)
    parser2_id = id(master2.parser)
    gemini1_id = id(master1.gemini)
    gemini2_id = id(master2.gemini)
    
    print(f"   ScreenParser: master1={parser1_id}, master2={parser2_id}")
    print(f"   GeminiAgent:  master1={gemini1_id}, master2={gemini2_id}")
    
    if parser1_id == parser2_id and gemini1_id == gemini2_id:
        print(f"   ✅ Components are shared (same object IDs)")
    else:
        print(f"   ❌ Components are NOT shared (different object IDs)")
        return False
    
    # Cleanup
    print("\n4️⃣  Cleaning up master1...")
    await master1.cleanup()
    print(f"   ✅ Cleanup complete - singleton released")
    
    # Create new MasterAgent after cleanup
    print("\n5️⃣  Creating new MasterAgent after cleanup...")
    master3 = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=2)
    master3_id = id(master3)
    print(f"   ✅ Created master3 with id: {master3_id}")
    print(f"   ✅ MasterAgent.master_id: {master3.master_id}")
    
    if master3_id != master1_id:
        print(f"\n   ✅ SUCCESS: master3 is a NEW instance (different from master1)")
        print(f"   ✅ Cleanup correctly released the singleton")
    else:
        print(f"\n   ❌ FAILURE: master3 is the SAME as master1 (cleanup failed)")
        return False
    
    # Final cleanup
    await master3.cleanup()
    
    print("\n" + "=" * 70)
    print("✅ ALL SINGLETON TESTS PASSED!")
    print("=" * 70)
    return True


async def test_worker_sharing():
    """Test that workers share the same component instances."""
    print("\n" + "=" * 70)
    print("TEST 2: Worker Instance Sharing")
    print("=" * 70)
    
    # Create MasterAgent
    print("\n1️⃣  Creating MasterAgent...")
    master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=2)
    await master.initialize()
    
    # Get component IDs from master
    master_parser_id = id(master.parser)
    master_gemini_id = id(master.gemini)
    master_verifier_id = id(master.verifier)
    
    print(f"   MasterAgent component IDs:")
    print(f"   - ScreenParser: {master_parser_id}")
    print(f"   - GeminiAgent:  {master_gemini_id}")
    print(f"   - TaskVerifier: {master_verifier_id}")
    
    # Create two test tasks
    from web_agent.core.task import Task
    
    task1 = Task(description="Test task 1")
    task2 = Task(description="Test task 2")
    
    # Create workers
    print("\n2️⃣  Creating workers...")
    worker1 = master._create_worker(task1)
    worker2 = master._create_worker(task2)
    
    # Get component IDs from workers
    worker1_parser_id = id(worker1.parser)
    worker1_gemini_id = id(worker1.gemini_agent)
    worker1_verifier_id = id(worker1.verifier)
    
    worker2_parser_id = id(worker2.parser)
    worker2_gemini_id = id(worker2.gemini_agent)
    worker2_verifier_id = id(worker2.verifier)
    
    print(f"   Worker1 component IDs:")
    print(f"   - ScreenParser: {worker1_parser_id}")
    print(f"   - GeminiAgent:  {worker1_gemini_id}")
    print(f"   - TaskVerifier: {worker1_verifier_id}")
    
    print(f"\n   Worker2 component IDs:")
    print(f"   - ScreenParser: {worker2_parser_id}")
    print(f"   - GeminiAgent:  {worker2_gemini_id}")
    print(f"   - TaskVerifier: {worker2_verifier_id}")
    
    # Verify sharing
    print("\n3️⃣  Verifying instance sharing...")
    
    all_same = True
    
    # Check ScreenParser
    if master_parser_id == worker1_parser_id == worker2_parser_id:
        print(f"   ✅ ScreenParser: SHARED across master and all workers")
    else:
        print(f"   ❌ ScreenParser: NOT SHARED")
        all_same = False
    
    # Check GeminiAgent
    if master_gemini_id == worker1_gemini_id == worker2_gemini_id:
        print(f"   ✅ GeminiAgent: SHARED across master and all workers")
    else:
        print(f"   ❌ GeminiAgent: NOT SHARED")
        all_same = False
    
    # Check TaskVerifier
    if master_verifier_id == worker1_verifier_id == worker2_verifier_id:
        print(f"   ✅ TaskVerifier: SHARED across master and all workers")
    else:
        print(f"   ❌ TaskVerifier: NOT SHARED")
        all_same = False
    
    # Cleanup
    await worker1.cleanup()
    await worker2.cleanup()
    await master.cleanup()
    
    if all_same:
        print("\n" + "=" * 70)
        print("✅ ALL WORKER SHARING TESTS PASSED!")
        print("=" * 70)
        return True
    else:
        print("\n" + "=" * 70)
        print("❌ WORKER SHARING TESTS FAILED!")
        print("=" * 70)
        return False


async def main():
    """Run all tests."""
    print("\n" + "🔬" * 35)
    print("SINGLETON & INSTANCE SHARING VERIFICATION")
    print("🔬" * 35 + "\n")
    
    try:
        # Test 1: Singleton pattern
        test1_passed = await test_singleton_pattern()
        
        # Test 2: Worker sharing
        test2_passed = await test_worker_sharing()
        
        # Final result
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)
        print(f"Test 1 (Singleton Pattern):      {'✅ PASSED' if test1_passed else '❌ FAILED'}")
        print(f"Test 2 (Worker Instance Sharing): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
        print("=" * 70)
        
        if test1_passed and test2_passed:
            print("\n🎉 ALL TESTS PASSED! 🎉")
            print("\nConclusion:")
            print("✅ MasterAgent singleton pattern is working correctly")
            print("✅ All workers share the same component instances")
            print("✅ Memory efficiency is maximized")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED")
            return 1
            
    except Exception as e:
        print(f"\n❌ Test execution failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
