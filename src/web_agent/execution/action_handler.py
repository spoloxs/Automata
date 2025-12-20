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
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


class ActionType(Enum):
    """Supported action types"""

    CLICK = "click"
    TYPE = "type"
    PRESS_ENTER = "press_enter"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    WAIT = "wait"
    ANALYZE_VISUAL = "analyze_visual"
    STORE_DATA = "store_data"
    GET_ACCOMPLISHMENTS = "get_accomplishments"
    GET_ELEMENT_DETAILS = "get_element_details"
    SCROLL_TO_RESULT = "scroll_to_result"
    MARK_COMPLETE = "mark_complete"


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
            "analyze_visual_content": ActionType.ANALYZE_VISUAL,
            "store_data": ActionType.STORE_DATA,
            "get_accomplishments": ActionType.GET_ACCOMPLISHMENTS,
            "get_element_details": ActionType.GET_ELEMENT_DETAILS,
            "scroll_to_result": ActionType.SCROLL_TO_RESULT,
            "mark_task_complete": ActionType.MARK_COMPLETE,
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

        try:
            # Route to appropriate handler
            handler_map = {
                ActionType.CLICK: self._handle_click,
                ActionType.TYPE: self._handle_type,
                ActionType.PRESS_ENTER: self._handle_press_enter,
                ActionType.NAVIGATE: self._handle_navigate,
                ActionType.SCROLL: self._handle_scroll,
                ActionType.WAIT: self._handle_wait,
                ActionType.ANALYZE_VISUAL: self._handle_analyze_visual,
                ActionType.STORE_DATA: self._handle_store_data,
                ActionType.GET_ACCOMPLISHMENTS: self._handle_get_accomplishments,
                ActionType.GET_ELEMENT_DETAILS: self._handle_get_element_details,
                ActionType.SCROLL_TO_RESULT: self._handle_scroll_to_result,
                ActionType.MARK_COMPLETE: self._handle_mark_complete,
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

            # Record successful accomplishments
            if success and self.accomplishments:
                await self._record_accomplishment(action, metadata)

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

    async def _handle_analyze_visual(
        self, params: Dict, elements: list
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """Handle visual analysis request - IMMEDIATELY executes and returns results"""
        question = params.get("question", "")
        reasoning = params.get("reasoning", "")
        context = params.get("context")

        log_info(f"   🔍 Visual analysis requested: {question}")
        log_info(f"   💭 Reasoning: {reasoning}")

        try:
            # Capture screenshot
            screenshot = await self.browser.capture_screenshot()
            
            # Execute visual analysis IMMEDIATELY and await result
            log_info(f"   🤖 Calling Gemini Vision API...")
            result = await self.gemini.analyze_visual(
                screenshot=screenshot,
                question=question,
                context=context
            )
            
            # Free screenshot immediately
            del screenshot
            
            log_success(f"   ✅ Visual analysis complete!")
            log_info(f"   📝 Answer: {result['answer'][:200]}")
            
            if result.get("target_element_id"):
                log_info(f"   🎯 Found element ID: {result['target_element_id']}")
            if result.get("target_coordinates"):
                log_info(f"   📍 Coordinates: {result['target_coordinates']}")
            
            # NEW: Assign temp IDs to visually found elements
            if result.get("all_elements"):
                found_elements = result["all_elements"]
                temp_elements = []
                
                # Get viewport size for coordinate normalization
                viewport_width, viewport_height = self.viewport_size
                
                for idx, elem in enumerate(found_elements):
                    temp_id = 9000 + idx  # Start from 9000 to avoid conflicts
                    
                    # Get coordinates from element
                    center_coords = elem.get("center_coordinates", [viewport_width/2, viewport_height/2])
                    bbox_coords = elem.get("bbox", [0, 0, viewport_width, viewport_height])
                    
                    # CRITICAL: Gemini Vision returns PIXEL coordinates (not normalized)
                    # The visual_analysis_prompt explicitly asks for pixel values
                    # So we store pixels directly and calculate normalized versions
                    center_pixels = center_coords  # Already in pixels
                    bbox_pixels = bbox_coords  # Already in pixels
                    
                    # Calculate normalized versions (0-1 range) from pixels
                    center_normalized = [
                        center_coords[0] / viewport_width,
                        center_coords[1] / viewport_height
                    ]
                    
                    bbox_normalized = [
                        bbox_coords[0] / viewport_width if len(bbox_coords) > 0 else 0,
                        bbox_coords[1] / viewport_height if len(bbox_coords) > 1 else 0,
                        bbox_coords[2] / viewport_width if len(bbox_coords) > 2 else 1,
                        bbox_coords[3] / viewport_height if len(bbox_coords) > 3 else 1,
                    ] if len(bbox_coords) >= 4 else [0, 0, 1, 1]
                    
                    # Store visual element with temp ID
                    self.visual_elements[temp_id] = {
                        "center_pixels": center_pixels,
                        "bbox_pixels": bbox_pixels,
                        "center_normalized": center_normalized,
                        "bbox_normalized": bbox_normalized,
                        "description": elem.get("description", ""),
                        "type": elem.get("element_type", "unknown"),
                        "content": elem.get("content", ""),
                    }
                    
                    # Add temp_id to element
                    elem["temp_id"] = temp_id
                    temp_elements.append(elem)
                
                result["visual_elements"] = temp_elements
                result["note"] = f"Found {len(temp_elements)} elements with IDs 9000-{9000 + len(temp_elements) - 1}. These visual elements are now available in the element list for clicking/typing via their IDs."
                
                log_info(f"   🆔 Assigned {len(temp_elements)} visual elements with temp IDs 9000-{9000 + len(temp_elements) - 1}")
                log_info(f"   📍 Visual elements are now merged into element list for interaction")
            
            # Return the actual analysis result
            return True, None, result
            
        except Exception as e:
            log_error(f"   ❌ Visual analysis failed: {e}")
            import traceback
            traceback.print_exc()
            
            return False, f"Visual analysis error: {str(e)}", {
                "answer": f"Error: {str(e)}",
                "target_element_id": None,
                "target_coordinates": None,
                "confidence": 0.0
            }

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

    # ==================== Utilities ====================

    def _find_element(self, element_id: int, elements: list) -> Optional[Element]:
        """Find element by ID in elements list"""
        if not elements:
            return None

        for elem in elements:
            if elem.id == element_id:
                return elem

        return None

    def is_task_complete(self) -> bool:
        """Check if task has been marked complete"""
        return self.task_complete

    def reset_task_complete(self):
        """Reset task complete flag"""
        self.task_complete = False
    
    async def _record_accomplishment(self, action: BrowserAction, metadata: Optional[Dict]) -> None:
        """
        Record a successful action as an accomplishment.
        Only records significant actions to keep the store lean.
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
        
        # Build concise description and evidence
        description = ""
        evidence = metadata.copy() if metadata else {}
        context = {}
        
        if action.action_type == ActionType.NAVIGATE:
            url = action.parameters.get("url", "")
            description = f"Navigated to {url}"
            context["url"] = url
            
        elif action.action_type == ActionType.TYPE:
            text = action.parameters.get("text", "")
            element_id = action.parameters.get("element_id")
            description = f"Typed '{text}' into element {element_id}"
            evidence["text"] = text
            evidence["element_id"] = element_id
            
        elif action.action_type == ActionType.CLICK:
            element_id = action.parameters.get("element_id")
            description = f"Clicked element {element_id}"
            evidence["element_id"] = element_id
            
        elif action.action_type == ActionType.PRESS_ENTER:
            description = "Pressed Enter"
            
        elif action.action_type == ActionType.STORE_DATA:
            key = action.parameters.get("key", "")
            value = action.parameters.get("value")
            description = f"Extracted data: {key}"
            evidence["value"] = value
            context["key"] = key
            
        elif action.action_type == ActionType.MARK_COMPLETE:
            reasoning = action.parameters.get("reasoning", "")
            description = f"Completed: {reasoning}"
            evidence["reasoning"] = reasoning
        
        # Add current URL to context
        try:
            current_url = await self.browser.get_url()
            context["url"] = current_url
        except Exception:
            pass
        
        # Record it
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
