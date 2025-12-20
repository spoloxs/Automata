"""
Visual integration test - opens real browser to show element ID system working.
Run this to SEE the element ID system in action!
"""

import asyncio
from web_agent.execution.browser_controller import BrowserController
from web_agent.execution.action_handler import ActionHandler, BrowserAction, ActionType
from web_agent.perception.screen_parser import ScreenParser, Element
from web_agent.storage.worker_memory import WorkerMemory
from web_agent.perception.element_formatter import ElementFormatter


async def create_test_page():
    """Create a simple HTML test page"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Element ID Test Page</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 40px;
            background: #f0f0f0;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            border: 2px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 5px;
        }
        button:hover {
            background: #45a049;
        }
        #result {
            margin-top: 20px;
            padding: 15px;
            background: #e8f5e9;
            border-radius: 4px;
            display: none;
        }
        .info {
            background: #e3f2fd;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Element ID Test Page</h1>
        
        <div class="info">
            <strong>This page tests the element ID system!</strong><br>
            Watch as the automation clicks elements using IDs instead of coordinates.
        </div>
        
        <form id="testForm">
            <label for="name">Name:</label>
            <input type="text" id="name" placeholder="Enter your name">
            
            <label for="email">Email:</label>
            <input type="email" id="email" placeholder="Enter your email">
            
            <button type="button" id="submitBtn" onclick="handleSubmit()">Submit Form</button>
            <button type="button" id="clearBtn" onclick="clearForm()">Clear</button>
        </form>
        
        <div id="result"></div>
    </div>
    
    <script>
        function handleSubmit() {
            const name = document.getElementById('name').value;
            const email = document.getElementById('email').value;
            const result = document.getElementById('result');
            
            result.innerHTML = `<strong>✅ Form Submitted!</strong><br>Name: ${name}<br>Email: ${email}`;
            result.style.display = 'block';
        }
        
        function clearForm() {
            document.getElementById('name').value = '';
            document.getElementById('email').value = '';
            document.getElementById('result').style.display = 'none';
        }
    </script>
</body>
</html>
"""
    
    # Write to temp file
    import tempfile
    import os
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8')
    temp_file.write(html)
    temp_file.close()
    
    return f"file://{temp_file.name}"


async def run_visual_test():
    """Run visual test with real browser"""
    print("\n" + "="*80)
    print("🎬 VISUAL ELEMENT ID TEST")
    print("="*80)
    print("\nOpening browser in VISIBLE mode...")
    print("Watch the automation use element IDs to interact!\n")
    
    # Create test page
    test_url = await create_test_page()
    print(f"✓ Created test page: {test_url}\n")
    
    # Temporarily disable headless mode
    import web_agent.config.settings as settings
    original_headless = settings.BROWSER_HEADLESS
    settings.BROWSER_HEADLESS = False
    
    # Initialize browser (NON-HEADLESS!)
    browser = BrowserController()
    await browser.initialize()
    
    # Restore original setting
    settings.BROWSER_HEADLESS = original_headless
    
    try:
        print("Step 1: Navigating to test page...")
        await browser.navigate(test_url)
        await asyncio.sleep(2)  # Let you see the page
        
        # Create mock elements (simulating what OmniParser would find)
        print("\nStep 2: Creating mock elements (simulating OmniParser output)...")
        mock_elements = [
            Element(
                id=0,
                type="h1",
                bbox=[0.25, 0.08, 0.75, 0.12],
                center=[0.5, 0.1],
                content="Element ID Test Page",
                interactivity=False,
                source="test",
                dom_tag="h1"
            ),
            Element(
                id=1,
                type="input",
                bbox=[0.25, 0.28, 0.75, 0.32],
                center=[0.5, 0.3],
                content="",
                interactivity=True,
                source="test",
                dom_tag="input",
                dom_id="name",
                dom_placeholder="Enter your name"
            ),
            Element(
                id=2,
                type="input",
                bbox=[0.25, 0.38, 0.75, 0.42],
                center=[0.5, 0.4],
                content="",
                interactivity=True,
                source="test",
                dom_tag="input",
                dom_id="email",
                dom_placeholder="Enter your email"
            ),
            Element(
                id=3,
                type="button",
                bbox=[0.25, 0.48, 0.45, 0.53],
                center=[0.35, 0.505],
                content="Submit Form",
                interactivity=True,
                source="test",
                dom_tag="button",
                dom_id="submitBtn"
            ),
            Element(
                id=4,
                type="button",
                bbox=[0.46, 0.48, 0.60, 0.53],
                center=[0.53, 0.505],
                content="Clear",
                interactivity=True,
                source="test",
                dom_tag="button",
                dom_id="clearBtn"
            )
        ]
        
        # Show formatted elements (what agent sees)
        print("\n" + "="*80)
        print("What the AGENT sees (simplified format):")
        print("="*80)
        formatted = ElementFormatter.format_for_llm(mock_elements, viewport_size=(1280, 720))
        print(formatted)
        
        # Create action handler
        memory = WorkerMemory()
        handler = ActionHandler(
            browser_controller=browser,
            memory=memory,
            viewport_size=(1280, 720)
        )
        handler.current_elements = mock_elements
        
        print("\n" + "="*80)
        print("EXECUTING ACTIONS USING ELEMENT IDs")
        print("="*80)
        
        # Test 1: Type in name field
        print("\n⌨️  TEST 1: Type in name field using element_id=1")
        action1 = BrowserAction(
            action_type=ActionType.TYPE,
            parameters={
                "element_id": 1,
                "text": "John Doe",
                "reasoning": "Testing element ID typing"
            }
        )
        result1 = await handler.handle_action(action1, mock_elements)
        print(f"   Result: {'✅ SUCCESS' if result1.success else '❌ FAILED'}")
        await asyncio.sleep(2)
        
        # Test 2: Type in email field
        print("\n⌨️  TEST 2: Type in email field using element_id=2")
        action2 = BrowserAction(
            action_type=ActionType.TYPE,
            parameters={
                "element_id": 2,
                "text": "john@example.com",
                "reasoning": "Testing element ID typing"
            }
        )
        result2 = await handler.handle_action(action2, mock_elements)
        print(f"   Result: {'✅ SUCCESS' if result2.success else '❌ FAILED'}")
        await asyncio.sleep(2)
        
        # Test 3: Click submit button
        print("\n🖱️  TEST 3: Click submit button using element_id=3")
        action3 = BrowserAction(
            action_type=ActionType.CLICK,
            parameters={
                "element_id": 3,
                "reasoning": "Testing element ID click"
            }
        )
        result3 = await handler.handle_action(action3, mock_elements)
        print(f"   Result: {'✅ SUCCESS' if result3.success else '❌ FAILED'}")
        await asyncio.sleep(3)
        
        # Test 4: Click clear button
        print("\n🖱️  TEST 4: Click clear button using element_id=4")
        action4 = BrowserAction(
            action_type=ActionType.CLICK,
            parameters={
                "element_id": 4,
                "reasoning": "Testing element ID click"
            }
        )
        result4 = await handler.handle_action(action4, mock_elements)
        print(f"   Result: {'✅ SUCCESS' if result4.success else '❌ FAILED'}")
        await asyncio.sleep(2)
        
        print("\n" + "="*80)
        print("✅ VISUAL TEST COMPLETE!")
        print("="*80)
        print("\nDid you see:")
        print("  1. ✓ Text typed in name field?")
        print("  2. ✓ Text typed in email field?")
        print("  3. ✓ Form submission (green box appeared)?")
        print("  4. ✓ Form cleared?")
        print("\nIf YES to all, the element ID system is working perfectly!")
        print("\nClosing browser in 5 seconds...")
        await asyncio.sleep(5)
        
    finally:
        await browser.cleanup()
        print("\n✓ Browser closed")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("VISUAL INTEGRATION TEST - ELEMENT ID SYSTEM")
    print("="*80)
    print("\nThis test will:")
    print("  1. Open a VISIBLE browser window")
    print("  2. Load a test page")
    print("  3. Use element IDs to interact")
    print("  4. Show you exactly what's happening")
    print("\nPress Ctrl+C to cancel, or wait to start...")
    
    try:
        asyncio.run(run_visual_test())
        print("\n✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
