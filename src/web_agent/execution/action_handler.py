"""
High-level action handler.
Converts agent decisions into browser operations.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from web_agent.core.result import ActionResult
from web_agent.execution.browser_controller import BrowserController
from web_agent.perception.screen_parser import Element
from web_agent.storage.worker_memory import WorkerMemory
from web_agent.storage.accomplishment_store import AccomplishmentStore, AccomplishmentType
from web_agent.storage.action_history_store import (
    get_action_history_store,
    ActionOutcome,
    PageContext,
)
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


class ActionType(Enum):
    """Supported action types"""

    CLICK = "click"
    TYPE = "type"
    PRESS_ENTER = "press_enter"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    WAIT = "wait"
    STORE_DATA = "store_data"
    GET_ACCOMPLISHMENTS = "get_accomplishments"
    GET_ELEMENT_DETAILS = "get_element_details"
    SCROLL_TO_RESULT = "scroll_to_result"
    MARK_COMPLETE = "mark_complete"
    # Tab management
    GET_TABS = "get_tabs"
    SWITCH_TAB = "switch_tab"
    # Micro-agent delegation actions
    IDENTIFY_AND_CLICK = "identify_and_click"
    IDENTIFY_AND_TYPE = "identify_and_type"


@dataclass
class BrowserAction:
    """Represents a browser action to execute"""

    action_type: ActionType
    parameters: Dict[str, Any]
    reasoning: Optional[str] = None

    @classmethod
    def from_tool_call(cls, tool_name: str, parameters: Dict) -> "BrowserAction":
        """Create action from LLM tool call"""
        action_type_map = {
            "click": ActionType.CLICK,
            "type": ActionType.TYPE,
            "press_enter": ActionType.PRESS_ENTER,
            "navigate": ActionType.NAVIGATE,
            "scroll": ActionType.SCROLL,
            "wait": ActionType.WAIT,
            "store_data": ActionType.STORE_DATA,
            "get_accomplishments": ActionType.GET_ACCOMPLISHMENTS,
            "get_element_details": ActionType.GET_ELEMENT_DETAILS,
            "scroll_to_result": ActionType.SCROLL_TO_RESULT,
            "mark_task_complete": ActionType.MARK_COMPLETE,
            # Tab management
            "get_tabs": ActionType.GET_TABS,
            "switch_tab": ActionType.SWITCH_TAB,
            # Micro-agent delegation
            "identify_and_click": ActionType.IDENTIFY_AND_CLICK,
            "identify_and_type": ActionType.IDENTIFY_AND_TYPE,
        }

        action_type = action_type_map.get(tool_name)
        if not action_type:
            raise ValueError(f"Unknown tool: {tool_name}")

        return cls(
            action_type=action_type,
            parameters=parameters,
            reasoning=parameters.get("reasoning"),
        )


class ActionHandler:
    """
    Handles execution of browser actions.
    Converts high-level actions into browser operations.
    """

    def __init__(
        self,
        browser_controller: BrowserController,
        memory: WorkerMemory,
        viewport_size: tuple = (1280, 720),
        accomplishment_store: Optional[AccomplishmentStore] = None,
        agent_id: str = "unknown",
        gemini_agent = None,
    ):
        log_debug("ActionHandler.__init__ called")
        self.browser = browser_controller
        self.memory = memory
        self.viewport_size = viewport_size
        self.task_complete = False
        self.accomplishments = accomplishment_store
        self.agent_id = agent_id
        self.gemini = gemini_agent

        # NEW: Store current elements for element_id lookups
        self.current_elements = []
        
        # Store visually found elements with temp IDs (9000+)
        self.visual_elements = {}  # Maps temp_id -> element data
        self._visual_elements_page_state = None  # Track when visual elements were captured
        
        # Track important element positions for scroll-back before completion
        self._key_element_position = None  # (x, y) of last important interaction

    async def handle_action(
        self, action: BrowserAction, elements: list = None
    ) -> ActionResult:
        # Store elements for element_id lookups
        if elements:
            self.current_elements = elements
        log_debug("ActionHandler.handle_action called")
        """
        Execute a browser action.

        Args:
            action: Action to execute
            elements: Current page elements (for element lookups)

        Returns:
            ActionResult with success status
        """
        start_time = time.time()

        # NEW: Capture "before" context for action history
        try:
            before_url = await self.browser.get_url()
            before_elements_count = len(self.current_elements)
            before_context = PageContext(
                url=before_url,
                elements_count=before_elements_count,
                viewport_size=self.viewport_size
            )
        except Exception:
            before_context = None
            before_url = "unknown"

        try:
            # Route to appropriate handler
            handler_map = {
                ActionType.CLICK: self._handle_click,
                ActionType.TYPE: self._handle_type,
                ActionType.PRESS_ENTER: self._handle_press_enter,
                ActionType.NAVIGATE: self._handle_navigate,
                ActionType.SCROLL: self._handle_scroll,
                ActionType.WAIT: self._handle_wait,
                ActionType.STORE_DATA: self._handle_store_data,
                ActionType.GET_ACCOMPLISHMENTS: self._handle_get_accomplishments,
                ActionType.GET_ELEMENT_DETAILS: self._handle_get_element_details,
                ActionType.SCROLL_TO_RESULT: self._handle_scroll_to_result,
                ActionType.MARK_COMPLETE: self._handle_mark_complete,
                # Tab management
                ActionType.GET_TABS: self._handle_get_tabs,
                ActionType.SWITCH_TAB: self._handle_switch_tab,
                # Micro-agent delegation handlers
                ActionType.IDENTIFY_AND_CLICK: self._handle_identify_and_click,
                ActionType.IDENTIFY_AND_TYPE: self._handle_identify_and_type,
            }

            handler = handler_map.get(action.action_type)
            if not handler:
                log_error(f"No handler for action type: {action.action_type}")
                return ActionResult(
                    action_type=action.action_type.value,
                    success=False,
                    error=f"No handler for action type: {action.action_type}",
                )

            # Execute handler
            success, error, metadata = await handler(action.parameters, elements)

            # Record ALL accomplishments (success AND failure) for agent learning
            if self.accomplishments:
                await self._record_accomplishment(action, metadata, success, error)

            # NEW: Record action outcome to history store
            try:
                after_url = await self.browser.get_url()
                after_elements_count = len(elements) if elements else 0
                after_context = PageContext(
                    url=after_url,
                    elements_count=after_elements_count,
                    viewport_size=self.viewport_size
                )
                
                # Detect what changed
                changes_observed = []
                url_changed = False
                if before_url != after_url:
                    changes_observed.append(f"URL changed to {after_url}")
                    url_changed = True
                
                # Build outcome
                outcome = ActionOutcome(
                    action_type=action.action_type.value,
                    target=str(action.parameters.get("element_id", action.parameters.get("url", ""))),
                    parameters=action.parameters,
                    success=success,
                    error=error,
                    before_context=before_context,
                    after_context=after_context,
                    changes_observed=changes_observed,
                    url_changed=url_changed,
                    expected_outcome=action.reasoning,
                    actual_outcome="Success" if success else (error or "Failed"),
                    outcome_matched=success,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                
                # Record it
                get_action_history_store().record_action(outcome)
            except Exception as e:
                log_debug(f"Failed to record action history: {e}")

            return ActionResult(
                action_type=action.action_type.value,
                success=success,
                target=str(
                    action.parameters.get(
                        "element_id", action.parameters.get("url", "")
                    )
                ),
                error=error,
                timestamp=start_time,
                metadata=metadata or {},
            )

        except Exception as e:
            return ActionResult(
                action_type=action.action_type.value,
                success=False,
                error=str(e),
                timestamp=start_time,
            )

    # ==================== Action Handlers ====================

    async def _handle_click(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle click action - supports both element_id and direct coordinates"""
        
        # NEW: Support element_id parameter
        if "element_id" in params:
            elem_id = params["element_id"]
            
            # Check if it's a visual element (temp ID 9000+)
            if elem_id >= 9000 and elem_id in self.visual_elements:
                visual_elem = self.visual_elements[elem_id]
                x, y = visual_elem["center_pixels"]
                log_info(f"   🖱️  Clicking VISUAL element ID {elem_id} ({visual_elem['description']}) at ({x}, {y})")
            else:
                # Regular element from OmniParser
                elem = next((e for e in self.current_elements if e.id == elem_id), None)
                
                if not elem:
                    return False, f"Element ID {elem_id} not found", None
                
                # Convert normalized coordinates to pixels
                x = int(elem.center[0] * self.viewport_size[0])
                y = int(elem.center[1] * self.viewport_size[1])
                
                # Apply offset compensation for CSS borders/padding
                # Testing shows a consistent 2px offset due to typical element borders
                x += 2
                y += 2
                
                log_info(f"   🖱️  Clicking element ID {elem_id} at ({x}, {y})")
        else:
            # Legacy: Direct coordinates
            x = params.get("x")
            y = params.get("y")
            
            if x is None or y is None:
                return False, "Missing element_id or x/y coordinates", None
            
            log_info(f"   🖱️  Clicking at coordinates ({x}, {y})")

        # Click at coordinates
        success = await self.browser.click(int(x), int(y))

        return success, None if success else "Click failed", {"x": x, "y": y}

    async def _handle_type(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle type action - supports both element_id and direct coordinates"""
        text = params.get("text", "")
        
        # NEW: Support element_id parameter
        if "element_id" in params:
            elem_id = params["element_id"]
            
            # Check if it's a visual element (temp ID 9000+)
            if elem_id >= 9000 and elem_id in self.visual_elements:
                visual_elem = self.visual_elements[elem_id]
                x, y = visual_elem["center_pixels"]
                log_info(f"   ⌨️  Typing '{text}' into VISUAL element ID {elem_id} ({visual_elem['description']}) at ({x}, {y})")
            else:
                # Regular element from OmniParser
                elem = next((e for e in self.current_elements if e.id == elem_id), None)
                
                if not elem:
                    return False, f"Element ID {elem_id} not found", None
                
                # Convert normalized coordinates to pixels
                x = int(elem.center[0] * self.viewport_size[0])
                y = int(elem.center[1] * self.viewport_size[1])
                
                # Apply offset compensation for CSS borders/padding
                # Testing shows a consistent 2px offset due to typical element borders
                x += 2
                y += 2
                
                log_info(f"   ⌨️  Typing '{text}' into element ID {elem_id} at ({x}, {y})")
        else:
            # Legacy: Direct coordinates
            x = params.get("x")
            y = params.get("y")
            
            if x is None or y is None:
                return False, "Missing element_id or x/y coordinates", None
            
            log_info(f"   ⌨️  Typing '{text}' at coordinates ({x}, {y})")

        # Click to focus
        await self.browser.click(int(x), int(y))
        await self.browser.wait(0.3)

        # Clear existing text (Ctrl+A, Delete)
        await self.browser.press_shortcut("Control+A")
        await self.browser.press_key("Backspace")

        # Type text
        success = await self.browser.type_text(text, delay=50)

        return success, None if success else "Type failed", {"text": text, "x": x, "y": y}

    async def _handle_press_enter(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle press Enter key"""
        log_info(f"   ⏎  Pressing Enter")
        success = await self.browser.press_key("Enter")
        return success, None if success else "Press Enter failed", None

    async def _handle_navigate(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle navigation"""
        url = params.get("url")

        if not url:
            return False, "Missing url parameter", None

        log_info(f"   [ActionHandler] 🌐 Navigating to {url}")
        success = await self.browser.navigate(url)
        log_info(f"   [ActionHandler] 🌐 Navigation success: {success}")

        return success, None if success else "Navigation failed", {"url": url}

    async def _handle_scroll(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle scroll action"""
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)

        log_info(f"   📜 Scrolling {direction} by {amount}px")
        success = await self.browser.scroll(direction, amount)

        return (
            success,
            None if success else "Scroll failed",
            {"direction": direction, "amount": amount},
        )

    async def _handle_wait(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle wait action"""
        seconds = params.get("seconds", 1.0)

        log_info(f"   ⏳ Waiting {seconds}s")
        await self.browser.wait(seconds)

        return True, None, {"seconds": seconds}

    async def _handle_store_data(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle data storage"""
        key = params.get("key")
        value = params.get("value")

        if not key:
            return False, "Missing key parameter", None

        log_info(f"   💾 Storing data: {key}")
        self.memory.store(key, value)

        return True, None, {"key": key}

    async def _handle_get_element_details(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle request for detailed element information"""
        element_ids = params.get("element_ids", [])
        
        if not element_ids:
            return False, "No element_ids provided", None
        
        log_info(f"   🔍 Getting details for {len(element_ids)} element(s)")
        
        # Use ElementFormatter to get details
        from web_agent.perception.element_formatter import ElementFormatter
        
        details = ElementFormatter.get_element_details(
            self.current_elements,
            element_ids,
            self.viewport_size
        )
        
        log_success(f"   ✅ Retrieved details for {len(details)} elements")
        
        return True, None, {"details": details}

    async def _handle_get_accomplishments(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle request for accomplishment summary"""
        log_info(f"   📋 Retrieving accomplishment summary")
        
        if not self.accomplishments:
            summary = "No accomplishment tracking available"
        else:
            try:
                summary = self.accomplishments.get_summary()
                log_info(f"      Found {len(self.accomplishments.accomplishments)} accomplishments")
            except Exception as e:
                summary = f"Error retrieving accomplishments: {e}"
        
        # Store in memory so agent can access it
        self.memory.store("accomplishment_summary", summary)
        
        return True, None, {"summary": summary, "count": len(self.accomplishments.accomplishments) if self.accomplishments else 0}

    async def _handle_scroll_to_result(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle scroll to result - centers page on important element before completion"""
        reasoning = params.get("reasoning", "Scrolling to result")
        
        # NEW: Support element_id parameter
        if "element_id" in params:
            elem_id = params["element_id"]
            
            # Check if it's a visual element (temp ID 9000+)
            if elem_id >= 9000 and elem_id in self.visual_elements:
                visual_elem = self.visual_elements[elem_id]
                x, y = visual_elem["center_pixels"]
                log_info(f"   📍 Scrolling to VISUAL element ID {elem_id} ({visual_elem['description']}) at ({x}, {y}): {reasoning}")
            else:
                # Regular element from OmniParser
                elem = next((e for e in self.current_elements if e.id == elem_id), None)
                
                if not elem:
                    return False, f"Element ID {elem_id} not found", None
                
                # Convert normalized coordinates to pixels
                x = int(elem.center[0] * self.viewport_size[0])
                y = int(elem.center[1] * self.viewport_size[1])
                log_info(f"   📍 Scrolling to element ID {elem_id} at ({x}, {y}): {reasoning}")
        else:
            # Legacy: Direct coordinates
            x = params.get("x")
            y = params.get("y")
            
            if x is None or y is None:
                return False, "Missing element_id or x/y coordinates", None
            
            log_info(f"   📍 Scrolling to result at ({x}, {y}): {reasoning}")

        try:
            # Use browser's center_on_position method to scroll the element into center view
            await self.browser._center_on_position(int(x), int(y))
            log_success(f"   ✅ Scrolled to center result element")
            
            return True, None, {"x": x, "y": y, "reasoning": reasoning}
        except Exception as e:
            log_error(f"   ❌ Scroll to result failed: {e}")
            return False, f"Scroll to result failed: {str(e)}", None

    async def _handle_mark_complete(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle task completion marker"""
        reasoning = params.get("reasoning", "Task completed")

        log_success(f"   ✅ Task marked complete: {reasoning}")
        self.task_complete = True

        return True, None, {"reasoning": reasoning}

    # ==================== Tab Management Handlers ====================

    async def _handle_get_tabs(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle request for tab list"""
        log_info(f"   📑 Retrieving open tabs")
        tabs = await self.browser.get_tabs()
        
        # Format for output
        tab_list_str = "\n".join([
            f"[{t['id']}] {'(ACTIVE) ' if t['active'] else ''}{t['title']} - {t['url']}"
            for t in tabs
        ])
        
        if not tabs:
            tab_list_str = "No open tabs found (or failed to retrieve)"
            
        log_info(f"      Found {len(tabs)} tabs")
        
        # Store in memory
        self.memory.store("open_tabs", tabs)
        
        return True, None, {"tabs": tabs, "summary": tab_list_str}

    async def _handle_switch_tab(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle switch tab"""
        tab_id = params.get("tab_id")
        reasoning = params.get("reasoning", "")
        
        if tab_id is None:
            return False, "Missing tab_id parameter", None
            
        log_info(f"   📑 Switching to tab {tab_id}: {reasoning}")
        success = await self.browser.switch_to_tab(int(tab_id))
        
        if success:
            log_success(f"   ✅ Switched to tab {tab_id}")
            return True, None, {"tab_id": tab_id}
        else:
            log_error(f"   ❌ Failed to switch to tab {tab_id}")
            return False, f"Failed to switch to tab {tab_id}", None

    # ==================== Micro-Agent Delegation Handlers ====================

    async def _handle_identify_and_click(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Handle two-phase click: identify element by description, then click it.
        Reduces hallucination by separating identification from execution.
        """
        description = params.get("description", "")
        context = params.get("context", "")
        reasoning = params.get("reasoning", "")
        
        log_info(f"   🎯 Two-phase click: {description}")
        log_debug(f"      Reasoning: {reasoning}")
        
        # Get micro-agent coordinator from worker
        # Note: This will be set by worker when it initializes action_handler
        if not hasattr(self, 'micro_agents'):
            log_warn("   ⚠️  Micro-agents not available, falling back to visual analysis")
            return False, "Micro-agents not initialized", None
        
        try:
            # Delegate to micro-agent coordinator
            result = await self.micro_agents.click_element_by_description(
                description=description,
                elements=elements or self.current_elements,
                context=context
            )
            
            if result.success:
                log_success(f"   ✅ Two-phase click succeeded")
                return True, None, result.data
            else:
                log_error(f"   ❌ Two-phase click failed: {result.error}")
                return False, result.error, None
                
        except Exception as e:
            log_error(f"   ❌ Two-phase click error: {e}")
            return False, str(e), None

    async def _handle_identify_and_type(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Handle two-phase type: identify element by description, then type into it.
        Reduces hallucination by separating identification from execution.
        """
        description = params.get("description", "")
        text = params.get("text", "")
        context = params.get("context", "")
        reasoning = params.get("reasoning", "")
        
        log_info(f"   🎯 Two-phase type: {description}")
        log_debug(f"      Text: '{text}'")
        log_debug(f"      Reasoning: {reasoning}")
        
        # Get micro-agent coordinator from worker
        if not hasattr(self, 'micro_agents'):
            log_warn("   ⚠️  Micro-agents not available")
            return False, "Micro-agents not initialized", None
        
        try:
            # Delegate to micro-agent coordinator
            result = await self.micro_agents.type_into_element_by_description(
                description=description,
                text=text,
                elements=elements or self.current_elements,
                context=context
            )
            
            if result.success:
                log_success(f"   ✅ Two-phase type succeeded")
                return True, None, result.data
            else:
                log_error(f"   ❌ Two-phase type failed: {result.error}")
                return False, result.error, None
                
        except Exception as e:
            log_error(f"   ❌ Two-phase type error: {e}")
            return False, str(e), None

    # ==================== Utilities ====================

    def is_task_complete(self) -> bool:
        """Check if task has been marked complete"""
        return self.task_complete

    def reset_task_complete(self):
        """Reset task complete flag"""
        self.task_complete = False
    
    async def _record_accomplishment(self, action: BrowserAction, metadata: Optional[Dict], success: bool, error: Optional[str]) -> None:
        """
        Record BOTH successful AND failed actions with MEANINGFUL outcomes.
        Agent learns from failures as much as successes!
        Shows what happened, whether it worked, and any errors.
        """
        if not self.accomplishments:
            return
        
        # Map action types to accomplishment types
        type_mapping = {
            ActionType.NAVIGATE: AccomplishmentType.NAVIGATION,
            ActionType.TYPE: AccomplishmentType.INPUT,
            ActionType.CLICK: AccomplishmentType.CLICK,
            ActionType.PRESS_ENTER: AccomplishmentType.INPUT,
            ActionType.STORE_DATA: AccomplishmentType.DATA_EXTRACTION,
            ActionType.MARK_COMPLETE: AccomplishmentType.GOAL_COMPLETION,
        }
        
        acc_type = type_mapping.get(action.action_type)
        if not acc_type:
            return  # Skip recording wait, scroll, etc.
        
        # Get action history for this action to see what actually happened
        from web_agent.storage.action_history_store import get_action_history_store
        
        recent_actions = get_action_history_store().get_recent_actions(count=1)
        action_outcome = recent_actions[0] if recent_actions else None
        
        # Build MEANINGFUL description with outcomes AND errors
        description = ""
        evidence = metadata.copy() if metadata else {}
        context = {}
        
        # Add success/failure indicator
        status_prefix = "✓" if success else "✗"
        
        if action.action_type == ActionType.NAVIGATE:
            url = action.parameters.get("url", "")
            description = f"{status_prefix} Navigated to {url}"
            context["url"] = url
            if success and action_outcome and action_outcome.url_changed:
                description += f" → reached {action_outcome.after_context.url}"
            elif not success:
                description += f" → FAILED: {error or 'Unknown error'}"
            
        elif action.action_type == ActionType.TYPE:
            text = action.parameters.get("text", "")
            element_id = action.parameters.get("element_id")
            description = f"{status_prefix} Typed '{text}' into element {element_id}"
            evidence["text"] = text
            evidence["element_id"] = element_id
            if success and action.reasoning:
                description += f" ({action.reasoning[:50]})"
            elif not success:
                description += f" → FAILED: {error or 'Type action failed'}"
            
        elif action.action_type == ActionType.CLICK:
            element_id = action.parameters.get("element_id")
            description = f"{status_prefix} Clicked element {element_id}"
            evidence["element_id"] = element_id
            
            if success and action_outcome:
                # Success: show what happened
                if action_outcome.url_changed:
                    description += f" → navigated to {action_outcome.after_context.url}"
                elif action_outcome.changes_observed:
                    changes = ", ".join(action_outcome.changes_observed[:2])
                    description += f" → {changes}"
                elif action.reasoning:
                    description += f" ({action.reasoning[:60]})"
            elif not success:
                # Failure: show error
                description += f" → FAILED: {error or 'Click failed'}"
            
        elif action.action_type == ActionType.PRESS_ENTER:
            description = f"{status_prefix} Pressed Enter"
            if success and action_outcome and action_outcome.url_changed:
                description += f" → navigated to {action_outcome.after_context.url}"
            elif not success:
                description += f" → FAILED: {error or 'Enter failed'}"
            
        elif action.action_type == ActionType.STORE_DATA:
            key = action.parameters.get("key", "")
            value = action.parameters.get("value")
            description = f"{status_prefix} Extracted {key} = {str(value)[:50]}"
            evidence["value"] = value
            context["key"] = key
            if not success:
                description += f" → FAILED: {error or 'Store failed'}"
            
        elif action.action_type == ActionType.MARK_COMPLETE:
            reasoning = action.parameters.get("reasoning", "")
            description = f"{status_prefix} Completed: {reasoning[:100]}"
            evidence["reasoning"] = reasoning
            if not success:
                description += f" → FAILED: {error or 'Completion mark failed'}"
        
        # Add success/error to context for filtering
        context["success"] = success
        if error:
            context["error"] = error
        
        # Add current URL to context
        try:
            current_url = await self.browser.get_url()
            context["url"] = current_url
            context["reasoning"] = action.reasoning if action.reasoning else ""
        except Exception:
            pass
        
        # Record it with full outcome (success or failure)
        try:
            self.accomplishments.record(
                type=acc_type,
                description=description,
                agent_id=self.agent_id,
                evidence=evidence,
                context=context,
            )
            log_debug(f"      📝 Recorded: {description}")
        except Exception as e:
            log_debug(f"      ⚠️  Failed to record accomplishment: {e}")
