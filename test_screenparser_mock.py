"""
Test ScreenParser with mock data to see instance reuse
"""
import sys
from pathlib import Path
from PIL import Image
import io

project_root = Path(__file__).parent / "src"
sys.path.insert(0, str(project_root))

from web_agent.perception.screen_parser import ScreenParser


def create_mock_screenshot():
    """Create a tiny mock screenshot"""
    # Create a 100x100 white image
    img = Image.new('RGB', (100, 100), color='white')
    return img


def test_screenparser_instances():
    print("\n" + "="*70)
    print("SCREENPARSER MOCK TEST - Instance Reuse Check")
    print("="*70)
    
    # Create first ScreenParser
    print("\n1. Creating first ScreenParser...")
    parser1 = ScreenParser()
    print(f"   ✅ ScreenParser #1 created: id={id(parser1)}, omniparser_id={id(parser1.omniparser)}")
    
    # Create second ScreenParser
    print("\n2. Creating second ScreenParser...")
    parser2 = ScreenParser()
    print(f"   ✅ ScreenParser #2 created: id={id(parser2)}, omniparser_id={id(parser2.omniparser)}")
    
    # Check if they share the same OmniParser
    print("\n3. Checking OmniParser reuse...")
    if id(parser1.omniparser) == id(parser2.omniparser):
        print(f"   ✅ GOOD: Both ScreenParsers share the same OmniParser instance!")
    else:
        print(f"   ❌ BAD: Different OmniParser instances created!")
        print(f"      Parser1 OmniParser: {id(parser1.omniparser)}")
        print(f"      Parser2 OmniParser: {id(parser2.omniparser)}")
    
    # Create mock screenshot
    print("\n4. Creating mock screenshot...")
    mock_img = create_mock_screenshot()
    print(f"   ✅ Mock image created: {mock_img.size}")
    
    # Parse with parser1 (will fail but that's ok - we just want to see the instance)
    print("\n5. Attempting parse with parser1...")
    try:
        parser1.parse(mock_img)
    except Exception as e:
        print(f"   ⚠️  Parse failed (expected): {type(e).__name__}")
        print(f"   → But we can see the instance IDs in the logs above")
    
    # Parse with parser2
    print("\n6. Attempting parse with parser2...")
    try:
        parser2.parse(mock_img)
    except Exception as e:
        print(f"   ⚠️  Parse failed (expected): {type(e).__name__}")
        print(f"   → But we can see the instance IDs in the logs above")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"ScreenParser instances are: {'DIFFERENT' if id(parser1) != id(parser2) else 'SAME'}")
    print(f"OmniParser instances are: {'DIFFERENT ❌' if id(parser1.omniparser) != id(parser2.omniparser) else 'SAME ✅'}")
    print("\nExpected behavior:")
    print("  - ScreenParser instances: DIFFERENT (one per worker)")
    print("  - OmniParser instances: SAME (shared singleton)")
    print("="*70)


if __name__ == "__main__":
    test_screenparser_instances()
