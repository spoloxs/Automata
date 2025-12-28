"""
Task planner - Decomposes high-level goals into executable steps.
"""

import asyncio
import gc
import time
from typing import Optional

from web_agent.execution.browser_controller import BrowserController
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.perception.element_formatter import ElementFormatter
from web_agent.perception.screen_parser import ScreenParser
from web_agent.planning.plan_structures import StructuredPlan
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn
from web_agent.util.memory_monitor import get_memory_monitor


class Planner:
    """
    Task planner that decomposes high-level goals into structured plans.
    """

    def __init__(
        self,
        gemini_agent: GeminiAgent,
        browser_controller: BrowserController,
        screen_parser: ScreenParser,
        accomplishment_store=None,  # NEW: Track what's been done
    ):
        self.gemini = gemini_agent
        self.browser = browser_controller
        self.parser = screen_parser
        self.accomplishment_store = accomplishment_store  # NEW: Avoid repeating work

        # Optional conversation manager may be attached externally (e.g., MasterAgent)
        # as `planner.conversation_manager`. If present, planner will record plan events.
        self.conversation_manager = getattr(self, "conversation_manager", None)

    async def create_plan(
        self,
        goal: str,
        starting_url: Optional[str] = None,
        explore: bool = True,
        thread_id: Optional[str] = None,
    ) -> StructuredPlan:
        """
        Create a structured plan for the given goal.
        Memory-optimized: cleans up screenshots and intermediate data after use.

        New: accepts optional `thread_id` parameter. If provided, the planner will
        include the thread_id in plan metadata and (if a conversation manager is
        attached on this planner instance) will append the plan to the conversation
        for traceability.
        """
        log_info(f"\n📋 Creating plan for goal: {goal}")
        start_time = time.time()
        
        # Log RAM before planning
        mem_monitor = get_memory_monitor()
        mem_monitor.log_ram("before planning")
        
        # Get current URL first
        current_url = await self.browser.get_url()
        
        # Only navigate if starting_url is provided AND different from current URL
        # This prevents unnecessary page refreshes during replanning
        if starting_url and starting_url != current_url:
            await self.browser.navigate(starting_url)
            current_url = await self.browser.get_url()
        log_info(f"   📍 Starting URL: {current_url}")
        
        # Capture screenshot for both parsing and visual analysis
        screenshot = await self.browser.capture_screenshot()
        elements = self.parser.parse(screenshot)
        viewport_size = await self.browser.get_viewport_size()
        # Use planner-specific format - more concise but still complete
        elements_text = ElementFormatter.format_for_planner(elements, viewport_size=viewport_size)
        log_info(f"   🔍 Found {len(elements)} elements on page")
        
        mem_monitor.log_ram("after initial parse")
        
        # VISUAL ANALYSIS DISABLED - Elements from OmniParser are sufficient for planning
        # Visual analysis should only be used by workers as a last resort when needed
        log_info(f"   ℹ️  Planning with {len(elements)} elements from OmniParser (visual analysis disabled)")
        
        # Create empty visual_insights to maintain API compatibility
        visual_insights = {
            'answer': 'Visual analysis skipped - using OmniParser elements only',
            'confidence': 1.0,
            'target_element_id': None,
            'target_coordinates': None
        }
        
        # Now free screenshot after parsing
        del screenshot
        
        mem_monitor.log_ram("after element parsing")
        
        exploration_history = []
        if explore:
            log_info(f"   🕵️  Exploring page...")
            exploration_history = await self._explore_page(elements_text)
            log_info(f"   ✅ Exploration complete ({len(exploration_history)} actions)")
            mem_monitor.log_ram("after exploration")
        
        # Get accomplishment summary to prevent repetition
        accomplishment_summary = None
        if self.accomplishment_store:
            try:
                accomplishment_summary = self.accomplishment_store.get_summary()
                log_info(f"   📋 Including accomplishment history ({len(self.accomplishment_store.accomplishments)} items)")
                log_debug(f"   Accomplishments: {accomplishment_summary[:200]}...")
            except Exception as e:
                log_warn(f"   ⚠️  Could not get accomplishment summary: {e}")
        
        log_info(f"   🤔 Generating plan with Gemini (including visual insights & accomplishments)...")
        plan_data = await self.gemini.create_plan(
            goal=goal,
            url=current_url,
            elements_text=elements_text,
            exploration_history=exploration_history,
            visual_insights=visual_insights,
            accomplishment_summary=accomplishment_summary,
        )
        
        # Free intermediate data after Gemini call
        del elements, elements_text, exploration_history
        
        plan = StructuredPlan.from_gemini_output(goal, plan_data)
        del plan_data  # Free Gemini response data
        
        # Attach planning metadata including the originating URL and thread id (if provided)
        plan.metadata["starting_url"] = current_url
        plan.metadata["created_at"] = time.time()
        if thread_id:
            plan.metadata["planner_thread"] = thread_id
            log_debug(
                f"   ℹ️ Planner thread id provided: {thread_id}; annotated plan metadata"
            )

            # If a conversation manager was attached to this planner, attempt to record the plan.
            conv_mgr = getattr(self, "conversation_manager", None)
            if conv_mgr:
                try:
                    # Append the plan (as dict) to the conversation store for auditing and future context.
                    await conv_mgr.append_plan(thread_id, plan.to_dict())
                    log_debug("   ℹ️ Plan appended to conversation manager")
                except Exception as e:
                    log_warn(f"   ⚠️ Failed to append plan to conversation manager: {e}")

        # Force garbage collection after planning
        gc.collect()
        
        elapsed = time.time() - start_time
        log_success(
            f"   ✅ Plan created: {len(plan.steps)} steps, {plan.complexity} complexity"
        )
        log_info(f"   ⏱️  Planning time: {elapsed:.2f}s")
        log_debug(f"   🧹 Memory freed: screenshot, elements, plan_data")
        
        return plan

    async def _explore_page(self, elements_text: str, max_actions: int = 15) -> list:
        """
        INTELLIGENT page exploration - explores until page is fully understood.
        
        Gemini decides how to explore based on:
        - Page complexity
        - Element visibility
        - Semantic completeness
        
        Terminates when:
        - Gemini signals completion (scroll amount=0)
        - Max actions reached (safety limit)
        - No meaningful new content discovered
        
        Returns detailed exploration history for the planner.
        Memory-optimized: explicitly deletes screenshots after parsing.
        """
        exploration_history = []
        
        log_info("      🔍 Starting intelligent page exploration...")
        log_info(f"      📊 Max exploration actions: {max_actions} (will stop early if page fully understood)")
        
        # Get current URL for context
        current_url = await self.browser.get_url()
        
        exploration_history.append(
            f"Starting exploration of: {current_url}"
        )
        
        # Track discovered content to detect when exploration is complete
        previous_element_count = 0
        no_new_content_count = 0
        
        # Let Gemini explore the page intelligently until it's fully understood
        for action_num in range(max_actions):
            log_info(f"      🤖 Exploration action {action_num + 1}/{max_actions}")
            
            # Capture current page state
            screenshot = await self.browser.capture_screenshot()
            elements = self.parser.parse(screenshot)
            del screenshot  # Free immediately
            
            viewport_size = await self.browser.get_viewport_size()
            formatted_elements = ElementFormatter.format_for_llm(
                elements, 
                max_elements=None,  # Send ALL elements 
                viewport_size=viewport_size
            )
            element_count = len(elements)
            
            # Build element list with CENTER COORDINATES in PIXELS for clicking
            viewport_size = await self.browser.get_viewport_size()
            width, height = viewport_size
            
            elements_with_coords = []
            for elem in elements[:50]:  # Show first 50 for exploration
                try:
                    if hasattr(elem, 'center') and elem.center:
                        # Convert normalized coordinates (0-1) to pixels
                        cx_normalized, cy_normalized = elem.center
                        cx = int(cx_normalized * width)
                        cy = int(cy_normalized * height)
                        
                        elem_type = getattr(elem, 'type', 'unknown')
                        content = getattr(elem, 'content', '')
                        interactivity = getattr(elem, 'interactivity', False)
                        
                        elements_with_coords.append(
                            f"[{elem_type}] \"{content[:30]}\" at ({cx}, {cy}) {'✓clickable' if interactivity else ''}"
                        )
                except Exception:
                    continue
            
            elements_summary = "\n".join(elements_with_coords[:30])  # Show top 30
            
            # Ask Gemini: "How should we explore this page?"
            exploration_prompt = f"""You are INTELLIGENTLY exploring a web page to understand its structure and content.

Current page state:
- URL: {current_url}
- Visible elements: {element_count}

TOP ELEMENTS WITH COORDINATES (use these exact x, y values):
{elements_summary}

INTELLIGENT EXPLORATION STRATEGY - Action {action_num + 1} of {max_actions}:

PRIORITY 1: Handle Overlays/Popups FIRST
- Look for cookie banners, GDPR notices, ad overlays, login prompts
- Look for "Close", "Accept", "Dismiss", "Continue", "X" buttons
- Click to dismiss these BEFORE exploring content
- Check element descriptions for: "overlay", "modal", "popup", "banner", "consent"

PRIORITY 2: Explore Visible Content
- Examine what's currently visible
- Look for tabs, accordions, expandable sections
- Click to reveal hidden content if present

PRIORITY 3: Scroll to Discover More (ONLY if needed)
- If Priority 1 & 2 are done AND you suspect more content below
- Scroll down to see additional content
- Don't scroll if overlay/popup is blocking the view

PRIORITY 4: Signal Completion
- scroll(direction="down", amount=0) - Use this when exploration is complete

Available actions (use EXACT coordinates from the list above):
- click(x=<number>, y=<number>) - Click using exact pixel coordinates shown above
- scroll(direction="down", amount=500) - Scroll down 500px
- scroll(direction="down", amount=0) - Signal exploration complete

CRITICAL: Use click(x=123, y=456) with the EXACT coordinates shown in the element list!

Choose ONE action based on current priority. BE SMART - handle popups before scrolling!
"""
            
            # Get Gemini's decision
            thread_id = f"exploration_{action_num}"
            actions = await self.gemini.decide_action(
                task=exploration_prompt,
                elements=elements,
                url=current_url,
                thread_id=thread_id,
                storage_data={},
                viewport_size=await self.browser.get_viewport_size(),
            )
            
            if not actions:
                # Clean up before breaking
                del elements, formatted_elements
                gc.collect()
                exploration_history.append(f"Action {action_num + 1}: No action suggested, stopping exploration")
                break
            
            # Execute the first action
            action = actions[0]
            tool_name = action.get("tool", "unknown")
            params = action.get("parameters", {})
            
            log_info(f"      🛠️ Gemini chose: {tool_name} with {params}")
            
            # Execute the exploration action
            try:
                if tool_name == "scroll":
                    direction = params.get("direction", "down")
                    amount = params.get("amount", 0)
                    
                    # If amount is 0, Gemini is signaling "page fully explored"
                    if amount == 0:
                        exploration_history.append(f"Action {action_num + 1}: Gemini signaled exploration complete")
                        break
                    
                    await self.browser.scroll(direction, amount)
                    await asyncio.sleep(0.5)  # Wait for content to load
                    exploration_history.append(f"Action {action_num + 1}: Scrolled {direction} by {amount}px")
                    
                elif tool_name == "click":
                    # Support both element_id and x/y coordinates
                    element_id = params.get("element_id")
                    x = params.get("x")
                    y = params.get("y")
                    
                    if element_id is not None:
                        # Convert element_id to coordinates
                        try:
                            # Find element by ID in our current elements list
                            target_element = None
                            for elem in elements:
                                if elem.id == element_id:
                                    target_element = elem
                                    break
                            
                            if target_element and hasattr(target_element, 'center'):
                                # Get center coordinates (already in pixels)
                                center_x, center_y = target_element.center
                                await self.browser.click(center_x, center_y)
                                await asyncio.sleep(0.5)
                                exploration_history.append(f"Action {action_num + 1}: Clicked element {element_id} at ({center_x:.0f}, {center_y:.0f})")
                            else:
                                exploration_history.append(f"Action {action_num + 1}: Click failed - element {element_id} not found or has no center")
                        except Exception as e:
                            exploration_history.append(f"Action {action_num + 1}: Click failed - error getting element coordinates: {e}")
                    
                    elif x is not None and y is not None:
                        # Direct x/y coordinates
                        await self.browser.click(x, y)
                        await asyncio.sleep(0.5)
                        exploration_history.append(f"Action {action_num + 1}: Clicked at ({x}, {y})")
                    else:
                        exploration_history.append(f"Action {action_num + 1}: Click failed - missing element_id or x/y coordinates")
                    
                else:
                    exploration_history.append(f"Action {action_num + 1}: Unknown action {tool_name}, skipping")
                    
            except Exception as e:
                log_warn(f"      ⚠️ Exploration action failed: {e}")
                exploration_history.append(f"Action {action_num + 1}: Failed - {str(e)}")
            
            # Force cleanup after each action
            gc.collect()
        
        exploration_history.append(f"Exploration complete: {len(exploration_history)} actions taken")
        
        # CRITICAL: Clear Gemini chat histories for exploration threads to prevent RAM leak
        # Each exploration action creates a thread (exploration_0, exploration_1, etc.)
        # Without cleanup, these accumulate forever!
        for i in range(max_actions):
            thread_id = f"exploration_{i}"
            if hasattr(self.gemini, 'clear_context'):
                try:
                    self.gemini.clear_context(thread_id)
                except Exception:
                    pass  # Best effort cleanup
        
        log_success(f"      ✅ LLM-driven exploration complete")
        log_debug(f"      🧹 Memory cleanup: {len(exploration_history)} history items")
        
        return exploration_history
