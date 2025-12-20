#!/usr/bin/env python3
"""
Test Screen Cache functionality
"""
import asyncio
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_agent.storage.screen_cache import ScreenCache
from web_agent.perception.screen_parser import Element

print("\n" + "="*70)
print("SCREEN CACHE TEST")
print("="*70)

def create_test_image(text: str, size=(100, 100)) -> Image.Image:
    """Create a test image with text"""
    img = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), text, fill='black')
    return img

def test_screenparser_cache():
    """Test ScreenParser cache functionality"""
    print("\n1. Testing ScreenParser Cache")
    print("-" * 70)
    
    cache = ScreenCache()
    
    # Create test image
    img1 = create_test_image("Screen 1")
    
    # Create test elements
    elements = [
        Element(
            id=0,
            type="text",
            bbox=(0.0, 0.0, 0.5, 0.5),
            center=(0.25, 0.25),
            content="Button A",
            interactivity=True,
            source="test"
        ),
        Element(
            id=1,
            type="icon",
            bbox=(0.5, 0.5, 1.0, 1.0),
            center=(0.75, 0.75),
            content="Icon B",
            interactivity=False,
            source="test"
        ),
    ]
    
    # First access - should be MISS
    print("   📥 First access (should be MISS)...")
    result1 = cache.get_screen_parser_result(img1)
    if result1 is None:
        print("   ✅ Cache MISS (expected)")
    else:
        print("   ❌ Cache HIT (unexpected!)")
        return False
    
    # Store in cache
    print("   💾 Storing elements in cache...")
    cache.store_screen_parser_result(img1, elements)
    print("   ✅ Stored successfully")
    
    # Second access - should be HIT
    print("   📥 Second access (should be HIT)...")
    result2 = cache.get_screen_parser_result(img1)
    if result2 is not None:
        print(f"   ✅ Cache HIT! Got {len(result2)} elements")
        if len(result2) == len(elements):
            print(f"   ✅ Element count matches: {len(result2)}")
        else:
            print(f"   ❌ Element count mismatch: {len(result2)} vs {len(elements)}")
            return False
    else:
        print("   ❌ Cache MISS (unexpected!)")
        return False
    
    # Test with different image - should be MISS
    print("   📥 Third access with different image (should be MISS)...")
    img2 = create_test_image("Screen 2")  # Different content
    result3 = cache.get_screen_parser_result(img2)
    if result3 is None:
        print("   ✅ Cache MISS for different image (expected)")
    else:
        print("   ❌ Cache HIT for different image (unexpected!)")
        return False
    
    return True

def test_visual_analysis_cache():
    """Test Visual Analysis cache functionality"""
    print("\n2. Testing Visual Analysis Cache")
    print("-" * 70)
    
    cache = ScreenCache()
    
    # Create test image
    img1 = create_test_image("Test Page")
    question = "Find the button"
    
    # Test result
    result_data = {
        "answer": "Found a button at top-left",
        "target_element_id": 5,
        "target_coordinates": [0.25, 0.30],
        "confidence": 0.95,
        "all_elements": [
            {
                "id": 1,
                "description": "Submit button",
                "center_coordinates": [0.25, 0.30],
                "bbox": [0.20, 0.25, 0.30, 0.35],
                "element_type": "button",
                "content": "Submit"
            }
        ]
    }
    
    # First access - should be MISS
    print(f"   📥 First access for question: '{question}'...")
    cached1 = cache.get_visual_analysis(img1, question)
    if cached1 is None:
        print("   ✅ Cache MISS (expected)")
    else:
        print("   ❌ Cache HIT (unexpected!)")
        return False
    
    # Store in cache
    print("   💾 Storing visual analysis in cache...")
    cache.store_visual_analysis(img1, question, result_data)
    print("   ✅ Stored successfully")
    
    # Second access - should be HIT
    print("   📥 Second access (should be HIT)...")
    cached2 = cache.get_visual_analysis(img1, question)
    if cached2 is not None:
        print(f"   ✅ Cache HIT! Got answer: {cached2['answer'][:50]}...")
        if cached2['confidence'] == 0.95:
            print(f"   ✅ Data preserved correctly (confidence: {cached2['confidence']})")
        else:
            print(f"   ❌ Data corrupted (confidence: {cached2['confidence']})")
            return False
    else:
        print("   ❌ Cache MISS (unexpected!)")
        return False
    
    # Test with different question - should be MISS
    print("   📥 Third access with different question (should be MISS)...")
    different_question = "Find the link"
    cached3 = cache.get_visual_analysis(img1, different_question)
    if cached3 is None:
        print("   ✅ Cache MISS for different question (expected)")
    else:
        print("   ❌ Cache HIT for different question (unexpected!)")
        return False
    
    return True

def test_cache_stats():
    """Test cache statistics"""
    print("\n3. Testing Cache Statistics")
    print("-" * 70)
    
    cache = ScreenCache()
    
    # Reset by creating new cache instance
    cache.clear()
    cache = ScreenCache()
    
    # Create test images
    img1 = create_test_image("Test 1")
    img2 = create_test_image("Test 2")
    
    # Do some operations
    print("   📊 Performing test operations...")
    
    # ScreenParser operations
    cache.get_screen_parser_result(img1)  # Miss
    cache.store_screen_parser_result(img1, [])
    cache.get_screen_parser_result(img1)  # Hit
    cache.get_screen_parser_result(img2)  # Miss
    
    # Visual analysis operations
    cache.get_visual_analysis(img1, "test")  # Miss
    cache.store_visual_analysis(img1, "test", {"answer": "test"})
    cache.get_visual_analysis(img1, "test")  # Hit
    
    # Get stats
    stats = cache.get_stats()
    print(f"\n   📈 Cache Statistics:")
    print(f"      ScreenParser cached: {stats['parser_cached']}")
    print(f"      Visual cached: {stats['visual_cached']}")
    print(f"      Parser hits: {stats['parser_hits']}")
    print(f"      Parser misses: {stats['parser_misses']}")
    print(f"      Parser hit rate: {stats['parser_hit_rate']:.1f}%")
    print(f"      Visual hits: {stats['visual_hits']}")
    print(f"      Visual misses: {stats['visual_misses']}")
    print(f"      Visual hit rate: {stats['visual_hit_rate']:.1f}%")
    
    # Verify stats
    if stats['parser_hits'] == 1 and stats['parser_misses'] == 2:
        print("   ✅ ScreenParser stats correct")
    else:
        print(f"   ❌ ScreenParser stats wrong: {stats['parser_hits']} hits, {stats['parser_misses']} misses")
        return False
    
    if stats['visual_hits'] == 1 and stats['visual_misses'] == 1:
        print("   ✅ Visual analysis stats correct")
    else:
        print(f"   ❌ Visual analysis stats wrong: {stats['visual_hits']} hits, {stats['visual_misses']} misses")
        return False
    
    return True

def main():
    """Run all tests"""
    print("\nRunning Screen Cache tests...\n")
    
    tests = [
        ("ScreenParser Cache", test_screenparser_cache),
        ("Visual Analysis Cache", test_visual_analysis_cache),
        ("Cache Statistics", test_cache_stats),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ❌ Test '{name}' failed with exception:")
            print(f"      {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
