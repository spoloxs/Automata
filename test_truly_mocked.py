"""
PROPERLY mock EVERYTHING - no OmniParser, no GPU usage
"""
import sys
from pathlib import Path

# Add to path FIRST
project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

# Create mock BEFORE any imports
from unittest.mock import Mock, patch
from PIL import Image

# Mock OmniParser wrapper to return proper mock
class MockOmniParserWrapper:
    def parse_screen_simple(self, screenshot):
        print("🧪 MOCK: parse_screen_simple() called - returning fake elements")
        # Return list of dicts like real OmniParser
        return [
            {
                'id': 0,
                'type': 'icon',
                'bbox': [0.38, 0.06, 0.60, 0.20],
                'center': [0.49, 0.13],
                'content': 'Google Logo',
                'interactivity': True,
                'source': 'mock'
            },
            {
                'id': 1,
                'type': 'icon',
                'bbox': [0.29, 0.24, 0.69, 0.30],
                'center': [0.49, 0.27],
                'content': 'Search Box',
                'interactivity': True,
                'source': 'mock'
            },
            {
                'id': 2,
                'type': 'text',
                'bbox': [0.44, 0.51, 0.54, 0.54],
                'center': [0.49, 0.52],
                'content': 'Privacy',
                'interactivity': False,
                'source': 'mock'
            },
        ]

def mock_get_omniparser():
    print("🧪 MOCK: get_omniparser() called - returning MockOmniParserWrapper")
    return MockOmniParserWrapper()

# Mock ScreenParser to return fake elements  
class MockScreenParser:
    def __init__(self):
        print("🧪 MOCK: ScreenParser created (no OmniParser)")
        self.omniparser = None
    
    def parse(self, screenshot: Image.Image):
        print(f"🧪 MOCK: parse() called - returning 3 fake elements")
        from web_agent.perception.screen_parser import Element
        return [
            Element(0, 'icon', (0.38, 0.06, 0.60, 0.20), (0.49, 0.13), 'Google', True, 'mock'),
            Element(1, 'icon', (0.29, 0.24, 0.69, 0.30), (0.49, 0.27), 'Search', True, 'mock'),
            Element(2, 'text', (0.44, 0.51, 0.54, 0.54), (0.49, 0.52), 'Terms', False, 'mock'),
        ]

# Patch BOTH get_omniparser AND ScreenParser
with patch('web_agent.perception.omniparser_wrapper.get_omniparser', mock_get_omniparser):
    with patch('web_agent.perception.screen_parser.get_omniparser', mock_get_omniparser):
        with patch('web_agent.perception.screen_parser.ScreenParser', MockScreenParser):
            # NOW import (will use mocks)
            import asyncio
            import gc
            import psutil
            from web_agent.core.master_agent import MasterAgent
            from web_agent.config.settings import GEMINI_API_KEY
            
            def get_ram():
                return psutil.Process().memory_info().rss / 1024 / 1024
            
            async def test():
                print("\n" + "="*70)
                print("TRULY MOCKED TEST - NO OMNIPARSER AT ALL")
                print("="*70)
                print("If you see OmniParser loading messages, the mock FAILED")
                print("="*70)
                
                baseline = get_ram()
                print(f"\nBaseline: {baseline:.1f} MB")
                
                master = MasterAgent(api_key=GEMINI_API_KEY, max_parallel_workers=1)
                await master.initialize()
                after_init = get_ram()
                print(f"After init: {after_init:.1f} MB (+{after_init - baseline:.1f} MB)")
                
                await master.execute_goal(
                    goal="Navigate to google.com",
                    starting_url="https://www.google.com",
                    timeout=60
                )
                after_task = get_ram()
                print(f"After task: {after_task:.1f} MB (+{after_task - after_init:.1f} MB)")
                
                await master.cleanup()
                del master
                gc.collect()
                gc.collect()
                after_cleanup = get_ram()
                
                leaked = after_cleanup - after_init
                freed = after_task - after_cleanup
                
                print(f"After cleanup: {after_cleanup:.1f} MB ({freed:+.1f} MB)")
                print(f"\n📊 LEAKED: {leaked:.1f} MB")
                print("="*70)
                
                if leaked > 100:
                    print("❌ LEAK IN AGENT WORKFLOW (not parsing)")
                else:
                    print("✅ NO LEAK: Parsing was the culprit")
                print("="*70)
            
            asyncio.run(test())
