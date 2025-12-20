"""
Low-level browser operations using Playwright.
Handles all direct interactions with the browser.
"""

import asyncio
import io
from typing import Optional, Tuple

from PIL import Image
from playwright.async_api import Browser, Page, async_playwright

from web_agent.config.settings import (
    BROWSER_HEADLESS,
    BROWSER_TIMEOUT,
    BROWSER_WINDOW_SIZE,
)
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


class BrowserController:
    """
    Low-level browser control using Playwright.
    Provides atomic operations: click, type, navigate, screenshot.
    """

    def __init__(self, page: Optional[Page] = None):
        """
        Initialize browser controller.

        Args:
            page: Existing Playwright page (for worker agents sharing browser)
                  If None, will create new browser instance
        """
        self.page = page
        self.browser: Optional[Browser] = None
        self.playwright_instance = None
        self._owns_browser = page is None

    async def initialize(self) -> Page:
        """
        Initialize browser if not provided.

        Returns:
            Playwright Page object
        """
        if self.page is not None:
            return self.page

        # Create new browser
        self.playwright_instance = await async_playwright().start()
        self.browser = await self.playwright_instance.chromium.launch(
            headless=BROWSER_HEADLESS,
            args=[
                f"--window-size={BROWSER_WINDOW_SIZE[0]},{BROWSER_WINDOW_SIZE[1]}",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await self.browser.new_context(
            viewport={
                "width": BROWSER_WINDOW_SIZE[0],
                "height": BROWSER_WINDOW_SIZE[1],
            },
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        self.page = await context.new_page()
        self.page.set_default_timeout(BROWSER_TIMEOUT)

        return self.page

    async def cleanup(self):
        """Cleanup browser resources (only if we own the browser)"""
        if self._owns_browser and self.browser:
            # CRITICAL: Close all contexts to free their cached data (DOM, network, etc.)
            try:
                for context in self.browser.contexts:
                    await context.close()
            except Exception as e:
                log_warn(f"⚠️ Context cleanup error: {e}")
            
            # Close browser
            await self.browser.close()
            
            # Stop Playwright
            if self.playwright_instance:
                await self.playwright_instance.stop()
        
        # CRITICAL: Even if we don't own the browser, clear the page reference
        # to help Python GC free the page object and its associated data
        self.page = None

    # ==================== Navigation ====================

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> bool:
        """
        Navigate to URL in the SAME tab (does NOT open new tabs).

        Args:
            url: URL to navigate to
            wait_until: When to consider navigation complete
                       ('load', 'domcontentloaded', 'networkidle')

        Returns:
            True if successful, False otherwise
        
        Note:
            This method ALWAYS reuses the existing page/tab.
            It will NOT create new tabs or windows.
        """
        try:
            # IMPORTANT: page.goto() navigates in the SAME tab, does not open new tabs
            await self.page.goto(url, wait_until=wait_until, timeout=BROWSER_TIMEOUT)
            await asyncio.sleep(1)  # Wait for dynamic content
            return True
        except Exception as e:
            log_error(f"❌ Navigation failed: {e}")
            return False

    async def get_url(self) -> str:
        """Get current page URL"""
        return self.page.url

    async def go_back(self) -> bool:
        """Navigate back in history"""
        try:
            await self.page.go_back(wait_until="domcontentloaded")
            return True
        except Exception as e:
            log_error(f"❌ Go back failed: {e}")
            return False

    # ==================== Screenshots ====================

    async def capture_screenshot(self) -> Image.Image:
        """
        Capture full-page screenshot.

        Returns:
            PIL Image object
        """
        screenshot_bytes = await self.page.screenshot(full_page=False)
        return Image.open(io.BytesIO(screenshot_bytes))

    async def capture_element_screenshot(self, selector: str) -> Optional[Image.Image]:
        """
        Capture screenshot of specific element.

        Args:
            selector: CSS selector for element

        Returns:
            PIL Image or None if element not found
        """
        try:
            element = await self.page.query_selector(selector)
            if element:
                screenshot_bytes = await element.screenshot()
                return Image.open(io.BytesIO(screenshot_bytes))
        except Exception as e:
            log_error(f"❌ Element screenshot failed: {e}")
        return None

    # ==================== Mouse Actions ====================

    async def click(self, x: int, y: int, button: str = "left") -> bool:
        """
        Click at pixel coordinates.
        Does NOT auto-scroll - agent must manually scroll if needed.

        Args:
            x: X coordinate (pixels)
            y: Y coordinate (pixels)
            button: Mouse button ('left', 'right', 'middle')

        Returns:
            True if successful
        """
        try:
            # Wait before click to prevent mis-clicks and double-clicks
            await asyncio.sleep(0.3)
            
            # Perform click (no auto-scrolling)
            await self.page.mouse.click(x, y, button=button)
            
            # Wait after click for action to take effect
            await asyncio.sleep(0.7)
            return True
        except Exception as e:
            log_error(f"❌ Click failed at ({x}, {y}): {e}")
            return False

    async def double_click(self, x: int, y: int) -> bool:
        """Double click at coordinates"""
        try:
            # Wait before double-click
            await asyncio.sleep(0.3)
            
            await self.page.mouse.dblclick(x, y)
            
            # Wait after double-click
            await asyncio.sleep(0.7)
            return True
        except Exception as e:
            log_error(f"❌ Double click failed: {e}")
            return False

    async def hover(self, x: int, y: int) -> bool:
        """Hover mouse at coordinates"""
        try:
            await self.page.mouse.move(x, y)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            log_error(f"❌ Hover failed: {e}")
            return False

    async def drag(self, from_x: int, from_y: int, to_x: int, to_y: int) -> bool:
        """Drag from one point to another"""
        try:
            await self.page.mouse.move(from_x, from_y)
            await self.page.mouse.down()
            await self.page.mouse.move(to_x, to_y)
            await self.page.mouse.up()
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            log_error(f"❌ Drag failed: {e}")
            return False

    # ==================== Keyboard Actions ====================

    async def type_text(self, text: str, delay: int = 50) -> bool:
        """
        Type text (must have element focused).

        Args:
            text: Text to type
            delay: Delay between keystrokes (ms)

        Returns:
            True if successful
        """
        try:
            # Wait before typing to ensure element is ready
            await asyncio.sleep(0.2)
            
            await self.page.keyboard.type(text, delay=delay)
            
            # Wait after typing for text to be processed
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            log_error(f"❌ Type text failed: {e}")
            return False

    async def press_key(self, key: str) -> bool:
        """
        Press a key (e.g., 'Enter', 'Tab', 'Escape').

        Args:
            key: Key name (Playwright format)

        Returns:
            True if successful
        """
        try:
            # Wait before key press
            await asyncio.sleep(0.2)
            
            await self.page.keyboard.press(key)
            
            # Wait after key press
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            log_error(f"❌ Press key failed: {e}")
            return False

    async def press_shortcut(self, shortcut: str) -> bool:
        """
        Press keyboard shortcut (e.g., 'Control+C', 'Meta+V').

        Args:
            shortcut: Shortcut string

        Returns:
            True if successful
        """
        try:
            await self.page.keyboard.press(shortcut)
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            log_error(f"❌ Shortcut failed: {e}")
            return False

    # ==================== Scrolling ====================

    async def scroll(self, direction: str, amount: int = 500) -> bool:
        """
        Scroll page.

        Args:
            direction: 'up' or 'down'
            amount: Pixels to scroll

        Returns:
            True if successful
        """
        try:
            delta_y = -amount if direction == "up" else amount
            await self.page.evaluate(f"window.scrollBy(0, {delta_y})")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            log_error(f"❌ Scroll failed: {e}")
            return False

    async def scroll_to_element(self, x: int, y: int) -> bool:
        """Scroll to make coordinates visible"""
        try:
            await self.page.evaluate(f"window.scrollTo({x}, {y})")
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            log_error(f"❌ Scroll to element failed: {e}")
            return False

    # ==================== Page Info ====================

    async def get_page_title(self) -> str:
        """Get page title"""
        return await self.page.title()

    async def get_viewport_size(self) -> Tuple[int, int]:
        """Get viewport dimensions"""
        viewport = self.page.viewport_size
        return viewport["width"], viewport["height"]

    async def wait_for_navigation(self, timeout: int = 30000) -> bool:
        """Wait for navigation to complete"""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
            return True
        except Exception as e:
            log_error(f"❌ Wait for navigation failed: {e}")
            return False

    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """Wait for element to appear"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # ==================== DOM Queries ====================

    async def query_selector(self, selector: str) -> Optional[any]:
        """Query single element by CSS selector"""
        try:
            return await self.page.query_selector(selector)
        except Exception:
            return None

    async def query_all_selectors(self, selector: str) -> list:
        """Query all elements matching selector"""
        try:
            return await self.page.query_selector_all(selector)
        except Exception:
            return []

    async def evaluate_js(self, script: str) -> any:
        """Execute JavaScript and return result"""
        try:
            return await self.page.evaluate(script)
        except Exception as e:
            print(f"❌ JS evaluation failed: {e}")
            return None

    async def query_dom_at_position(self, x: int, y: int) -> dict:
        """
        Query DOM element at specific pixel coordinates.
        
        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
        
        Returns:
            Dictionary with DOM information:
            {
                'tag': str,  # HTML tag name
                'role': str,  # ARIA role
                'id': str,  # HTML id
                'class': str,  # HTML class
                'text': str,  # Inner text
                'placeholder': str,  # Placeholder (for inputs)
            }
        """
        try:
            result = await self.page.evaluate(f"""
                (() => {{
                    const elem = document.elementFromPoint({x}, {y});
                    if (!elem) return null;
                    
                    return {{
                        tag: elem.tagName.toLowerCase(),
                        role: elem.getAttribute('role') || '',
                        id: elem.id || '',
                        class: elem.className || '',
                        text: elem.innerText || elem.textContent || '',
                        placeholder: elem.placeholder || '',
                        type: elem.type || '',  // For inputs
                        name: elem.name || '',  // Form element name
                        value: elem.value || '',  // Current value
                    }};
                }})();
            """)
            
            return result if result else {}
        except Exception as e:
            log_debug(f"   ⚠️ DOM query at ({x}, {y}) failed: {e}")
            return {}

    # ==================== Private Helpers ====================
    
    async def _center_on_position(self, x: int, y: int):
        """
        Smoothly center the page on the specified position.
        
        Args:
            x: X coordinate (pixels) to center on
            y: Y coordinate (pixels) to center on
        """
        try:
            viewport = await self.get_viewport_size()
            viewport_width, viewport_height = viewport
            
            # Calculate scroll position to center the target
            # Target should be in the middle of the viewport
            scroll_x = x - (viewport_width // 2)
            scroll_y = y - (viewport_height // 2)
            
            # Ensure we don't scroll to negative positions
            scroll_x = max(0, scroll_x)
            scroll_y = max(0, scroll_y)
            
            log_debug(f"      📍 Centering on ({x}, {y}) → scroll to ({scroll_x}, {scroll_y})")
            
            # Smooth scroll to center the position
            await self.page.evaluate(f"""
                (() => {{
                    window.scrollTo({{
                        left: {scroll_x},
                        top: {scroll_y},
                        behavior: 'smooth'
                    }});
                }})();
            """)
            
            # Wait for smooth scroll to complete
            await asyncio.sleep(0.3)
            
        except Exception as e:
            log_warn(f"      ⚠️  Auto-center failed: {e}")
            # Don't fail the click if centering fails
            pass

    # ==================== Utility ====================

    async def wait(self, seconds: float):
        """Wait for specified seconds"""
        await asyncio.sleep(seconds)

    def get_page(self) -> Page:
        """Get underlying Playwright page"""
        return self.page
