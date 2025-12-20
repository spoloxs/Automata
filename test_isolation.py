"""
Systematic isolation test - mock each component to find exact leak source
"""
import asyncio
import gc
import psutil
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.core.master_agent import MasterAgent
from web_agent.config.settings import GEMINI_API_KEY
from web_agent.perception.screen_parser import Element
from mock_screen_parser import MockScreenParser


def get_ram_mb():
    """Get current process RAM in MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


# Mock components
class MockGeminiAgent:
    """Mock Gemini that returns canned responses"""
    def __init__(self, *args, **kwargs):
        print("🧪 MockGeminiAgent initialized")
        self.chat_histories = {}
    
    async def decide_actions(self, *args, **kwargs):
        print("🧪 MockGeminiAgent.decide_actions() - returning mark_complete")
        from web_agent.intelligence.gemini_agent import LLMResponse
        return LLMResponse(
            actions=[{"tool": "mark_complete", "reasoning": "Task complete"}],
            reasoning="Mock completion"
        )
    
    async def plan_task(self, *args, **kwargs):
        print("🧪 MockGeminiAgent.plan_task() - returning simple plan")
        return {
            "steps": [{"description": "Mock task", "complexity": "simple"}],
            "overall_strategy": "Mock strategy"
        }
    
    async def verify_task(self, *args, **kwargs):
        print("🧪 MockGeminiAgent.verify_task() - returning verified")
        return {
            "is_complete": True,
            "confidence": 100.0,
            "reasoning": "Mock verification"
        }
    
    async def explore_page(self, *args, **kwargs):
        print("🧪 MockGeminiAgent.explore_page() - returning no actions")
        return []
    
    def clear_context(self, thread_id):
        print(f"🧪 MockGeminiAgent.clear_context({thread_id[:20]}...)")
        if thread_id in self.chat_histories:
            del self.chat_histories[thread_id]


async def test_component(name, patches):
    """Test with specific mocks applied"""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")
    
    baseline = get_ram_mb()
    print(f"Baseline: {baseline:.1f} MB")
    
    # Apply all patches
    with patch.multiple('web_agent.intelligence.gemini_agent', **patches) if patches else MagicMock():
        master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
        await master.initialize()
        
        after_init = get_ram_mb()
        print(f"After init: {after_init:.1f} MB (+{after_init - baseline:.1f} MB)")
        
        try:
            result = await master.execute_goal(
                goal="Navigate to google.com",
                starting_url="https://www.google.com",
                timeout=60
            )
        except Exception as e:
            print(f"⚠️ Task failed: {e}")
        
        after_task = get_ram_mb()
        print(f"After task: {after_task:.1f} MB (+{after_task - after_init:.1f} MB)")
        
        await master.cleanup()
        del master
        gc.collect()
        gc.collect()
        
        after_cleanup = get_ram_mb()
        leaked = after_cleanup - after_init
        freed = after_task - after_cleanup
        
        print(f"After cleanup: {after_cleanup:.1f} MB ({freed:+.1f} MB)")
        print(f"\n📊 RESULT: Leaked {leaked:.1f} MB, Freed {freed:.1f} MB")
        
        return {
            "name": name,
            "leaked_mb": leaked,
            "freed_mb": freed,
            "leak_bad": leaked > 100
        }


async def run_all_tests():
    print("\n" + "="*70)
    print("SYSTEMATIC COMPONENT ISOLATION TEST")
    print("="*70)
    print("Testing each component with mocks to find leak source\n")
    
    results = []
    
    # Test 1: Everything REAL (baseline)
    print("\n🔬 Test 1: ALL REAL COMPONENTS (baseline)")
    result = await test_component("1. ALL REAL", {})
    results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 2: Mock ScreenParser only
    print("\n🔬 Test 2: MOCK ScreenParser only")
    with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
        result = await test_component("2. MOCK ScreenParser", {})
        results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 3: Mock Gemini only
    print("\n🔬 Test 3: MOCK Gemini only")
    with patch('web_agent.intelligence.gemini_agent.GeminiAgent', MockGeminiAgent):
        with patch('web_agent.core.master_agent.GeminiAgent', MockGeminiAgent):
            with patch('web_agent.core.worker_agent.GeminiAgent', MockGeminiAgent):
                with patch('web_agent.planning.planner.GeminiAgent', MockGeminiAgent):
                    result = await test_component("3. MOCK Gemini", {})
                    results.append(result)
    
    await asyncio.sleep(2)
    
    # Test 4: Mock BOTH ScreenParser AND Gemini
    print("\n🔬 Test 4: MOCK ScreenParser + Gemini")
    with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
        with patch('web_agent.intelligence.gemini_agent.GeminiAgent', MockGeminiAgent):
            with patch('web_agent.core.master_agent.GeminiAgent', MockGeminiAgent):
                with patch('web_agent.core.worker_agent.GeminiAgent', MockGeminiAgent):
                    with patch('web_agent.planning.planner.GeminiAgent', MockGeminiAgent):
                        result = await test_component("4. MOCK Parser + Gemini", {})
                        results.append(result)
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY - LEAK ISOLATION RESULTS")
    print("="*70)
    for r in results:
        status = "❌ LEAK" if r["leak_bad"] else "✅ OK"
        print(f"{status} {r['name']:30s}: Leaked {r['leaked_mb']:6.1f} MB, Freed {r['freed_mb']:6.1f} MB")
    
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)
    
    # Compare results
    baseline_leak = results[0]["leaked_mb"]
    for r in results[1:]:
        reduction = baseline_leak - r["leaked_mb"]
        if reduction > 50:
            print(f"✅ {r['name']}: Reduced leak by {reduction:.1f} MB - this component contributes!")
        elif reduction < -50:
            print(f"⚠️  {r['name']}: Leak INCREASED by {-reduction:.1f} MB")
        else:
            print(f"➖ {r['name']}: No significant change ({reduction:+.1f} MB)")
    
    print("="*70)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
