"""
Test cursor visibility and persistence
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from web_agent.execution.browser_controller import BrowserController


async def test_cursor():
    """Test that cursor is visible and persists"""
    print("\n" + "="*60)
    print("CURSOR VISIBILITY TEST")
    print("="*60)
    
    browser = BrowserController()
    
    try:
        # Step 1: Initialize browser (should create cursor)
        print("\n1️⃣  Initializing browser...")
        await browser.initialize()
        print("   ✅ Browser initialized")
        
        # Step 2: Navigate to a simple page
        print("\n2️⃣  Navigating to example.com...")
        await browser.navigate("https://example.com")
        print("   ✅ Navigation complete")
        
        # Step 3: Click somewhere (should move cursor)
        print("\n3️⃣  Clicking at center (720, 450)...")
        await browser.click(720, 450)
        print("   ✅ Click executed")
        
        # Step 4: Wait to see cursor
        print("\n4️⃣  Waiting 3 seconds for visual inspection...")
        print("   👀 CHECK THE BROWSER NOW:")
        print("   - You should see a RED ARROW cursor at (720, 450)")
        print("   - Size: 32x32 pixels")
        print("   - Should have dark shadow")
        await asyncio.sleep(3)
        
        # Step 5: Click at different position
        print("\n5️⃣  Clicking at new position (400, 300)...")
        await browser.click(400, 300)
        print("   ✅ Click executed")
        print("   👀 Cursor should now be at (400, 300)")
        await asyncio.sleep(2)
        
        # Step 6: Navigate to new page (cursor should persist)
        print("\n6️⃣  Navigating to new page...")
        await browser.navigate("https://www.google.com")
        print("   ✅ Navigation complete")
        print("   👀 Cursor should STILL be at (400, 300) - persistence test!")
        await asyncio.sleep(3)
        
        # Step 7: Check browser console for cursor logs
        print("\n7️⃣  Checking console logs...")
        console_logs = await browser.evaluate_js("""
            // Return any console logs about cursor
            'Check browser DevTools Console (F12) for cursor initialization logs'
        """)
        print(f"   💬 {console_logs}")
        
        # Step 8: Verify cursor element exists in DOM
        print("\n8️⃣  Verifying cursor in DOM...")
        cursor_exists = await browser.evaluate_js("""
            const cursor = document.getElementById('ai-cursor');
            if (cursor) {
                return {
                    exists: true,
                    position: cursor.style.left + ', ' + cursor.style.top,
                    size: cursor.style.width + ' x ' + cursor.style.height,
                    zIndex: cursor.style.zIndex
                };
            }
            return { exists: false };
        """)
        
        if cursor_exists and cursor_exists.get('exists'):
            print("   ✅ Cursor element found in DOM!")
            print(f"   📍 Position: {cursor_exists.get('position')}")
            print(f"   📐 Size: {cursor_exists.get('size')}")
            print(f"   🔝 Z-Index: {cursor_exists.get('zIndex')}")
        else:
            print("   ❌ Cursor element NOT found in DOM!")
            print("   ⚠️  This means cursor initialization failed")
        
        # Final wait
        print("\n9️⃣  Final visual check - 5 seconds...")
        print("   👀 LOOK AT THE BROWSER:")
        print("   - Is there a RED ARROW visible?")
        print("   - Is it at position (400, 300)?")
        print("   - Does it have a dark shadow?")
        await asyncio.sleep(5)
        
        print("\n" + "="*60)
        if cursor_exists and cursor_exists.get('exists'):
            print("✅ CURSOR TEST PASSED")
            print("   Cursor is in DOM and should be visible")
        else:
            print("❌ CURSOR TEST FAILED")
            print("   Cursor element not found in DOM")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Keep browser open for manual inspection
        print("\n⏸️  Browser will stay open for 10 more seconds for inspection...")
        await asyncio.sleep(10)
        
        print("🧹 Cleaning up...")
        await browser.cleanup()
        print("✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_cursor())
