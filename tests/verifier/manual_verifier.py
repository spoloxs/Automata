#!/usr/bin/env python3
"""
Test TaskVerifier with REAL OmniParser Output
Opens Bing.com, takes screenshot, and verifies with real parsed content
"""
import asyncio
import os
from pathlib import Path
import sys
from PIL import Image
from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

print(f"📂 Project root: {PROJECT_ROOT}")

# Add OmniParser to path
OMNIPARSER_HOME = os.getenv(
    "OMNIPARSER_HOME", os.path.abspath(os.path.join(PROJECT_ROOT, "OmniParser"))
)

from web_agent.core import OmniParserParser
from web_agent.core.gemini_agent import GeminiAgent
from web_agent.agents.modules.task_verifier import TaskVerifier


async def main():
    """Test verifier with real OmniParser output from live browser"""

    # 1. Setup Browser
    print("🌐 Starting browser...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page(viewport={"width": 1280, "height": 720})

    # 2. Navigate to Bing
    print("🔗 Navigating to Bing.com...")
    await page.goto("https://www.bing.com", wait_until="domcontentloaded")
    await asyncio.sleep(2)  # Wait for page to fully load

    # 3. Take screenshot
    print("📸 Capturing screenshot...")
    screenshot_path = "bing_screenshot.png"
    await page.screenshot(path=screenshot_path)
    screenshot = Image.open(screenshot_path)
    print(f"✅ Screenshot saved: {screenshot.size}")

    # 4. Setup OmniParser - USE CORRECT INIT
    print("\n🔧 Loading OmniParser...")
    config = {
        "som_model_path": os.path.join(
            OMNIPARSER_HOME, "weights", "icon_detect", "model.pt"
        ),
        "caption_model_name": "florence2",
        "caption_model_path": os.path.join(
            OMNIPARSER_HOME, "weights", "icon_caption_florence"
        ),  # ✅ Fixed path
        "BOX_TRESHOLD": 0.01,
    }

    parser = OmniParserParser(config)  # ✅ Use OmniParserParser
    print("✅ OmniParser loaded")

    # 5. Parse with OmniParser - GET ALL 3 OUTPUTS
    print("\n🔍 Parsing screen with OmniParser...")
    parse_result = parser.parse_screen(screenshot)
    if asyncio.iscoroutine(parse_result):
        parse_result = await parse_result

    labeled_img, elements, parsed_content_list = parse_result

    print(f"\n✅ OmniParser found {len(parsed_content_list)} text elements")
    print(f"✅ OmniParser found {len(elements)} bounding boxes")

    # Show first 20 parsed elements
    print("\n📋 Parsed Content (first 20 elements):")
    for i, text in enumerate(parsed_content_list[:20]):
        print(f"  [{i}] {text}")

    # Save labeled image for debugging
    labeled_img.save("bing_labeled.png")
    print("\n💾 Saved labeled image: bing_labeled.png")

    # 6. Enrich elements with actual text content
    print("\n🔗 Enriching elements with parsed content...")
    enriched_elements = []
    for i, elem in enumerate(elements):
        elem_copy = elem.copy()
        # Add actual text from parsed_content_list
        if i < len(parsed_content_list):
            elem_copy["text"] = parsed_content_list[i]
            elem_copy["content"] = parsed_content_list[i]
        else:
            elem_copy["text"] = "[icon]"
            elem_copy["content"] = "[icon]"
        enriched_elements.append(elem_copy)

    print(f"✅ Enriched {len(enriched_elements)} elements with text")

    # 7. Type in search box and search
    print("\n⌨️ Performing search action...")
    search_box = await page.query_selector('textarea[name="q"], input[name="q"]')
    if search_box:
        await search_box.fill("Python tutorials")
        print("✅ Typed 'Python tutorials'")
        await asyncio.sleep(1)
        await search_box.press("Enter")
        print("✅ Pressed Enter")
        await asyncio.sleep(3)  # Wait for results

        # Take screenshot after search
        await page.screenshot(path="bing_after_search.png")
        screenshot_after = Image.open("bing_after_search.png")
        print(f"📸 Screenshot after search: {screenshot_after.size}")

        # Parse after-search state
        print("\n🔍 Parsing screen after search...")
        parse_after = parser.parse_screen(screenshot_after)
        if asyncio.iscoroutine(parse_after):
            parse_after = await parse_after
        _, elements_after, parsed_after = parse_after

        print(f"✅ Found {len(parsed_after)} elements after search")
        print("\n📋 Parsed Content After Search (first 20):")
        for i, text in enumerate(parsed_after[:20]):
            print(f"  [{i}] {text}")

        # Enrich after-search elements
        enriched_after = []
        for i, elem in enumerate(elements_after):
            elem_copy = elem.copy()
            if i < len(parsed_after):
                elem_copy["text"] = parsed_after[i]
                elem_copy["content"] = parsed_after[i]
            else:
                elem_copy["text"] = "[icon]"
                elem_copy["content"] = "[icon]"
            enriched_after.append(elem_copy)
    else:
        print("⚠️ Search box not found, using initial state for verification")
        enriched_after = enriched_elements

    # 8. Setup Gemini Agent
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        await browser.close()
        await playwright.stop()
        return

    print("\n🤖 Initializing Gemini Agent...")
    agent = GeminiAgent(api_key=api_key)

    # 9. Create TaskVerifier
    print("🔍 Creating TaskVerifier...")
    verifier = TaskVerifier(gemini_agent=agent, web_agent=None)

    # 10. Test verification
    task_description = "Search for 'Python tutorials' on Bing"
    action_history = [
        {
            "action_type": "TYPE",
            "text": "Python tutorials",
            "coordinates": None,
            "success": True,
            "reasoning": "Typed search query into search box",
        },
        {
            "action_type": "PRESS_KEY",
            "text": "Enter",
            "success": True,
            "reasoning": "Submitted search query",
        },
    ]

    print(f"\n{'='*60}")
    print("🧪 TESTING VERIFIER WITH REAL OMNIPARSER OUTPUT")
    print(f"{'='*60}")
    print(f"Task: {task_description}")
    print(f"Actions performed: {len(action_history)}")
    print(f"Elements to verify: {len(enriched_after)}")

    # 11. Run verification
    result = await verifier.verify_task_completion(
        task=task_description,  # ✅ task (not task_description)
        elements=enriched_after,  # ✅ elements (not parsed_screen)
        action_history=action_history,
        storage_data={},
    )

    # 12. Display results
    print(f"\n{'='*60}")
    print("📊 VERIFICATION RESULTS")
    print(f"{'='*60}")
    print(f"✅ Completed: {result.get('completed', False)}")
    print(f"📊 Confidence: {result.get('confidence', 0.0):.2f}")
    print(f"💭 Reasoning: {result.get('reasoning', 'N/A')}")

    if result.get("completed"):
        print("\n🎉 Task verified as COMPLETE!")
    else:
        print("\n⚠️ Task NOT complete")
        if result.get("next_steps"):
            print(f"📝 Next steps: {result['next_steps']}")

    # 13. Cleanup
    print("\n🧹 Cleaning up...")
    await browser.close()
    await playwright.stop()
    print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())
