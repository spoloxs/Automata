"""
Test element ID-based actions to verify refactoring works correctly.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from web_agent.execution.action_handler import ActionHandler, BrowserAction, ActionType
from web_agent.perception.screen_parser import Element
from web_agent.storage.worker_memory import WorkerMemory


async def test_element_id_click():
    """Test that click with element_id works"""
    print("\n" + "="*80)
    print("TEST 1: Click with element_id")
    print("="*80)
    
    # Create mock browser
    mock_browser = AsyncMock()
    mock_browser.click = AsyncMock(return_value=True)
    
    # Create action handler
    memory = WorkerMemory()
    handler = ActionHandler(
        browser_controller=mock_browser,
        memory=memory,
        viewport_size=(1280, 720)
    )
    
    # Create mock elements
    test_elements = [
        Element(
            id=0,
            type="button",
            bbox=[0.1, 0.1, 0.2, 0.15],  # normalized
            center=[0.15, 0.125],  # normalized
            content="Click me",
            interactivity=True,
            source="test"
        ),
        Element(
            id=5,
            type="input",
            bbox=[0.3, 0.3, 0.6, 0.35],  # normalized
            center=[0.45, 0.325],  # normalized
            content="",
            interactivity=True,
            source="test"
        )
    ]
    
    # Store elements in handler
    handler.current_elements = test_elements
    
    # Create click action with element_id
    action = BrowserAction(
        action_type=ActionType.CLICK,
        parameters={
            "element_id": 5,
            "reasoning": "Test click"
        }
    )
    
    # Execute action
    result = await handler.handle_action(action, test_elements)
    
    # Verify
    print(f"✓ Action success: {result.success}")
    print(f"✓ Browser.click called: {mock_browser.click.called}")
    
    if mock_browser.click.called:
        call_args = mock_browser.click.call_args[0]
        expected_x = int(0.45 * 1280)  # 576
        expected_y = int(0.325 * 720)  # 234
        print(f"✓ Called with: click({call_args[0]}, {call_args[1]})")
        print(f"✓ Expected: click({expected_x}, {expected_y})")
        
        if call_args[0] == expected_x and call_args[1] == expected_y:
            print("✅ TEST PASSED: Coordinates match!")
            return True
        else:
            print("❌ TEST FAILED: Coordinates don't match!")
            return False
    else:
        print("❌ TEST FAILED: Browser.click not called!")
        return False


async def test_element_id_type():
    """Test that type with element_id works"""
    print("\n" + "="*80)
    print("TEST 2: Type with element_id")
    print("="*80)
    
    # Create mock browser
    mock_browser = AsyncMock()
    mock_browser.click = AsyncMock(return_value=True)
    mock_browser.wait = AsyncMock(return_value=True)
    mock_browser.press_shortcut = AsyncMock(return_value=True)
    mock_browser.press_key = AsyncMock(return_value=True)
    mock_browser.type_text = AsyncMock(return_value=True)
    
    # Create action handler
    memory = WorkerMemory()
    handler = ActionHandler(
        browser_controller=mock_browser,
        memory=memory,
        viewport_size=(1280, 720)
    )
    
    # Create mock element
    test_elements = [
        Element(
            id=10,
            type="input",
            bbox=[0.3, 0.3, 0.6, 0.35],
            center=[0.45, 0.325],
            content="",
            interactivity=True,
            source="test"
        )
    ]
    
    handler.current_elements = test_elements
    
    # Create type action
    action = BrowserAction(
        action_type=ActionType.TYPE,
        parameters={
            "element_id": 10,
            "text": "test@example.com",
            "reasoning": "Test type"
        }
    )
    
    # Execute
    result = await handler.handle_action(action, test_elements)
    
    # Verify
    print(f"✓ Action success: {result.success}")
    print(f"✓ Browser.type_text called: {mock_browser.type_text.called}")
    
    if mock_browser.type_text.called:
        call_args = mock_browser.type_text.call_args[0]
        print(f"✓ Typed text: '{call_args[0]}'")
        
        if call_args[0] == "test@example.com":
            print("✅ TEST PASSED: Text matches!")
            return True
        else:
            print("❌ TEST FAILED: Text doesn't match!")
            return False
    else:
        print("❌ TEST FAILED: Browser.type_text not called!")
        return False


async def test_visual_element_click():
    """Test that click with visual element ID (9000+) works"""
    print("\n" + "="*80)
    print("TEST 3: Click visual element (temp ID 9000+)")
    print("="*80)
    
    # Create mock browser
    mock_browser = AsyncMock()
    mock_browser.click = AsyncMock(return_value=True)
    
    # Create action handler
    memory = WorkerMemory()
    handler = ActionHandler(
        browser_controller=mock_browser,
        memory=memory,
        viewport_size=(1280, 720)
    )
    
    # Simulate visual analysis finding elements
    handler.visual_elements[9000] = {
        "center_pixels": [640, 360],
        "bbox_pixels": [600, 340, 680, 380],
        "description": "Hidden button",
        "type": "button",
        "content": "Click me"
    }
    
    # Create click action with visual ID
    action = BrowserAction(
        action_type=ActionType.CLICK,
        parameters={
            "element_id": 9000,
            "reasoning": "Test visual click"
        }
    )
    
    # Execute
    result = await handler.handle_action(action, [])
    
    # Verify
    print(f"✓ Action success: {result.success}")
    print(f"✓ Browser.click called: {mock_browser.click.called}")
    
    if mock_browser.click.called:
        call_args = mock_browser.click.call_args[0]
        print(f"✓ Called with: click({call_args[0]}, {call_args[1]})")
        print(f"✓ Expected: click(640, 360)")
        
        if call_args[0] == 640 and call_args[1] == 360:
            print("✅ TEST PASSED: Visual element click works!")
            return True
        else:
            print("❌ TEST FAILED: Coordinates don't match!")
            return False
    else:
        print("❌ TEST FAILED: Browser.click not called!")
        return False


async def test_element_not_found():
    """Test error handling when element ID not found"""
    print("\n" + "="*80)
    print("TEST 4: Element ID not found (error handling)")
    print("="*80)
    
    # Create mock browser
    mock_browser = AsyncMock()
    mock_browser.click = AsyncMock(return_value=True)
    
    # Create action handler
    memory = WorkerMemory()
    handler = ActionHandler(
        browser_controller=mock_browser,
        memory=memory,
        viewport_size=(1280, 720)
    )
    
    # No elements
    handler.current_elements = []
    
    # Try to click non-existent element
    action = BrowserAction(
        action_type=ActionType.CLICK,
        parameters={
            "element_id": 999,
            "reasoning": "Test error"
        }
    )
    
    # Execute
    result = await handler.handle_action(action, [])
    
    # Verify
    print(f"✓ Action success: {result.success} (should be False)")
    print(f"✓ Error message: {result.error}")
    
    if not result.success and "not found" in result.error.lower():
        print("✅ TEST PASSED: Error handling works!")
        return True
    else:
        print("❌ TEST FAILED: Error not handled correctly!")
        return False


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("ELEMENT ID ACTION TESTS")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(await test_element_id_click())
    results.append(await test_element_id_type())
    results.append(await test_visual_element_click())
    results.append(await test_element_not_found())
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED!")
        print("\nThe element ID system is working correctly.")
        print("If agents still can't interact, the issue is elsewhere:")
        print("  - Check if elements are being parsed correctly")
        print("  - Verify browser controller is receiving actions")
        print("  - Check if Gemini is calling the tools")
    else:
        print("❌ SOME TESTS FAILED!")
        print("\nThe element ID system has issues that need fixing.")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
