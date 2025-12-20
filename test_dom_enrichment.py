#!/usr/bin/env python3
"""
Test DOM enrichment functionality.
Verifies that elements are enriched with DOM data from the browser.
"""

import asyncio
from playwright.async_api import async_playwright
from web_agent.execution.browser_controller import BrowserController
from web_agent.perception.screen_parser import ScreenParser, enrich_elements_with_dom
from web_agent.util.logger import log_info, log_success, log_error, log_warn


async def test_dom_enrichment():
    """Test that DOM enrichment adds HTML context to elements"""
    
    print("\n" + "="*80)
    print("DOM ENRICHMENT TEST")
    print("="*80 + "\n")
    
    # Create a simple test HTML page
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DOM Enrichment Test</title>
    </head>
    <body>
        <h1>Test Page</h1>
        <button id="submit-btn" class="primary-button" role="button">Submit</button>
        <input id="email-input" class="form-control" type="email" placeholder="Enter email">
        <a href="#" id="test-link" class="nav-link">Click me</a>
        <div id="content" class="container">
            <p>Some text content</p>
        </div>
    </body>
    </html>
    """
    
    playwright = None
    browser = None
    
    try:
        # Initialize Playwright and browser
        log_info("1. Initializing browser...")
        playwright = await async_playwright().start()
        browser_instance = await playwright.chromium.launch(headless=False)
        context = await browser_instance.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()
        
        # Navigate to data URL with test HTML
        log_info("2. Loading test HTML...")
        await page.goto(f"data:text/html,{test_html}")
        await asyncio.sleep(1)  # Let page load
        
        # Create controller and parser
        log_info("3. Creating BrowserController and ScreenParser...")
        browser = BrowserController(page=page)
        parser = ScreenParser()
        
        # Capture and parse
        log_info("4. Capturing screenshot and parsing elements...")
        screenshot = await browser.capture_screenshot()
        elements = parser.parse(screenshot)
        log_info(f"   Found {len(elements)} elements")
        
        # Show elements BEFORE enrichment
        print("\n" + "-"*80)
        print("BEFORE DOM ENRICHMENT:")
        print("-"*80)
        for elem in elements[:5]:  # Show first 5
            print(f"[{elem.id}] {elem.type}: '{elem.content}'")
            print(f"   dom_tag: {elem.dom_tag}")
            print(f"   dom_id: {elem.dom_id}")
            print(f"   dom_class: {elem.dom_class}")
        
        # Enrich with DOM data
        log_info("\n5. Enriching elements with DOM data...")
        viewport_size = (1440, 900)
        enriched_elements = await enrich_elements_with_dom(elements, browser, viewport_size)
        
        # Show elements AFTER enrichment
        print("\n" + "-"*80)
        print("AFTER DOM ENRICHMENT:")
        print("-"*80)
        for elem in enriched_elements[:5]:  # Show first 5
            print(f"[{elem.id}] {elem.type}: '{elem.content}'")
            print(f"   dom_tag: {elem.dom_tag}")
            print(f"   dom_id: {elem.dom_id}")
            print(f"   dom_class: {elem.dom_class}")
            print(f"   dom_role: {elem.dom_role}")
            print(f"   dom_placeholder: {elem.dom_placeholder}")
        
        # Verify enrichment worked
        print("\n" + "="*80)
        print("VERIFICATION:")
        print("="*80)
        
        enriched_count = sum(1 for elem in enriched_elements if elem.dom_tag is not None)
        total_count = len(enriched_elements)
        
        log_info(f"Total elements: {total_count}")
        log_info(f"Enriched with DOM: {enriched_count}")
        log_info(f"Enrichment rate: {enriched_count/total_count*100:.1f}%")
        
        # Check specific elements
        button_elem = None
        input_elem = None
        link_elem = None
        
        for elem in enriched_elements:
            if 'submit' in elem.content.lower():
                button_elem = elem
            elif 'email' in elem.content.lower():
                input_elem = elem
            elif 'click me' in elem.content.lower():
                link_elem = elem
        
        print("\nSPECIFIC ELEMENT CHECKS:")
        
        if button_elem:
            log_info("✓ Found button element:")
            log_info(f"  tag: {button_elem.dom_tag} (expected: 'button')")
            log_info(f"  id: {button_elem.dom_id} (expected: 'submit-btn')")
            log_info(f"  class: {button_elem.dom_class} (expected: 'primary-button')")
            
            if button_elem.dom_tag == 'button' and 'submit-btn' in str(button_elem.dom_id):
                log_success("  ✅ Button enrichment PASSED")
            else:
                log_error("  ❌ Button enrichment FAILED")
        else:
            log_warn("  ⚠️ Button element not found")
        
        if input_elem:
            log_info("\n✓ Found input element:")
            log_info(f"  tag: {input_elem.dom_tag} (expected: 'input')")
            log_info(f"  id: {input_elem.dom_id} (expected: 'email-input')")
            log_info(f"  placeholder: {input_elem.dom_placeholder} (expected: 'Enter email')")
            
            if input_elem.dom_tag == 'input' and 'Enter email' in str(input_elem.dom_placeholder):
                log_success("  ✅ Input enrichment PASSED")
            else:
                log_error("  ❌ Input enrichment FAILED")
        else:
            log_warn("  ⚠️ Input element not found")
        
        if link_elem:
            log_info("\n✓ Found link element:")
            log_info(f"  tag: {link_elem.dom_tag} (expected: 'a')")
            log_info(f"  id: {link_elem.dom_id} (expected: 'test-link')")
            
            if link_elem.dom_tag == 'a':
                log_success("  ✅ Link enrichment PASSED")
            else:
                log_error("  ❌ Link enrichment FAILED")
        else:
            log_warn("  ⚠️ Link element not found")
        
        # Overall result
        print("\n" + "="*80)
        if enriched_count > 0:
            log_success(f"✅ DOM ENRICHMENT TEST PASSED ({enriched_count}/{total_count} elements enriched)")
        else:
            log_error(f"❌ DOM ENRICHMENT TEST FAILED (0/{total_count} elements enriched)")
        print("="*80 + "\n")
        
    except Exception as e:
        log_error(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        if browser_instance:
            await browser_instance.close()
        if playwright:
            await playwright.stop()


if __name__ == "__main__":
    asyncio.run(test_dom_enrichment())
