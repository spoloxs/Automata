"""
Action loop implementation.
Core observe-decide-act cycle for worker agents.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from web_agent.config.settings import ACTION_TIMEOUT, MAX_ACTION_ITERATIONS
from web_agent.core.result import ActionResult
from web_agent.execution.action_handler import ActionHandler, BrowserAction
from web_agent.execution.browser_controller import BrowserController
from web_agent.perception.screen_parser import ScreenParser
from web_agent.storage.worker_memory import WorkerMemory
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


@dataclass
class Observation:
    """Represents current state observation"""

    screenshot: Any  # PIL Image
    elements: List[Any]  # List of Elements
    url: str
    timestamp: float


class ActionLoop:
    """
    Core action loop: observe → decide → act → verify.
    Runs until task is marked complete or max iterations reached.
    """

    def __init__(
        self,
        browser_controller: BrowserController,
        screen_parser: ScreenParser,
        action_handler: ActionHandler,
        memory: WorkerMemory,
        decision_function: callable,  # Function that decides next actions
        viewport_size: tuple = (1280, 720),
        conversation_manager=None,
        supervisor_thread_key: str = "supervisor_thread",
    ):
        """
        Initialize action loop.

        Args:
            browser_controller: Browser control interface
            screen_parser: Screen parsing interface
            action_handler: Action execution interface
            memory: Worker memory storage
            decision_function: Async function(observation, task) -> List[BrowserAction]
            viewport_size: Browser viewport dimensions
            conversation_manager: optional ConversationManager for appending events (best-effort)
            supervisor_thread_key: key in worker memory that may contain the supervisor thread id
        """
        self.browser = browser_controller
        self.parser = screen_parser
        self.action_handler = action_handler
        self.memory = memory
        self.decide_next_actions = decision_function
        self.viewport_size = viewport_size

        # Optional conversation manager and supervisor thread discovery key.
        # These are used to append action events to the supervisor conversation if available.
        self.conversation_manager = conversation_manager
        self.supervisor_thread_key = supervisor_thread_key

    async def run(
        self,
        task_description: str,
        max_iterations: int = MAX_ACTION_ITERATIONS,
        timeout: int = ACTION_TIMEOUT,
    ) -> tuple[bool, List[ActionResult], str]:
        """
        Run the action loop until task completion or timeout.

        Args:
            task_description: Description of task to accomplish
            max_iterations: Maximum number of action cycles
            timeout: Maximum time in seconds

        Returns:
            Tuple of (success, action_history, error_message)
        """
        log_info(f"\n🔄 Starting action loop for task: {task_description}")
        log_info(f"   Max iterations: {max_iterations}, Timeout: {timeout}s")

        action_history = []
        start_time = time.time()
        iteration = 0
        last_progress_time = start_time
        
        # Track progress for dynamic timeout extension with structured metrics
        from web_agent.core.error_types import ProgressMetrics
        progress_metrics = ProgressMetrics(
            actions_executed=0,
            successful_actions=0,
            failed_actions=0,
            last_10_actions=[],
            state_changes=0,
            unique_states_visited=0,
            convergence_detected=False
        )
        visited_states = set()  # Track unique states for convergence detection

        # Reset task complete flag
        self.action_handler.reset_task_complete()

        while iteration < max_iterations:
            iteration += 1
            elapsed = time.time() - start_time

            # Timeout check - ONLY if timeout is set (None means no timeout)
            if timeout is not None:
                # Dynamic timeout: extend if making progress
                effective_timeout = timeout
                if elapsed > timeout:
                    # Check if we've made progress recently (within last 30s)
                    time_since_progress = time.time() - last_progress_time
                    if time_since_progress < 30 and progress_metrics.successful_actions > 0:
                        # Extend timeout by 60s if making progress
                        effective_timeout = timeout + 60
                        log_info(f"   🔄 Extended timeout to {effective_timeout}s due to progress")
                    
                    if elapsed > effective_timeout:
                        log_warn(f"   ⏱️  Timeout reached after {elapsed:.1f}s")
                        # Save progress metrics to memory for supervisor
                        self.memory.store("progress_metrics", progress_metrics.to_dict())
                        return False, action_history, f"Timeout after {effective_timeout}s (made {progress_metrics.successful_actions} successful actions)"

            log_info(f"\n   🔁 Iteration {iteration}/{max_iterations}")

            try:
                # Step 1: Observe current state
                observation = await self._observe()

                # Step 2: Check if task already complete (before deciding)
                if self.action_handler.is_task_complete():
                    log_success(f"   ✅ Task marked complete in iteration {iteration}")
                    return True, action_history, None

                # Step 3: Decide next actions
                actions = await self._decide(observation, task_description)

                if not actions:
                    log_warn(f"   ⚠️  No actions decided this iteration - will retry next iteration")
                    # Don't stop immediately - allow agent to self-correct on next iteration
                    await asyncio.sleep(1.0)  # Brief pause before retry
                    continue

                # Step 4: Execute actions
                results = await self._act(actions, observation.elements)
                action_history.extend(results)
                
                # CRITICAL FIX: Append tool results to chat history so AI remembers them
                # Without this, visual analysis and other tool results are lost between iterations!
                await self._append_tool_results_to_history(actions, results)
                
                # CRITICAL FIX: Delete observation screenshot immediately to prevent memory leak
                # Screenshots accumulate rapidly (5-10MB each × 50-100 iterations = 500MB-1GB per task)
                screenshot = observation.screenshot
                del observation.screenshot
                del screenshot
                import gc
                gc.collect()
                
                # Update progress metrics and track state changes
                prev_url = observation.url
                for result in results:
                    progress_metrics.actions_executed += 1
                    if result.success:
                        progress_metrics.successful_actions += 1
                        last_progress_time = time.time()
                    else:
                        progress_metrics.failed_actions += 1
                    
                    # Keep last 10 actions for pattern detection
                    progress_metrics.last_10_actions.append({
                        "type": result.action_type,
                        "success": result.success,
                        "iteration": iteration
                    })
                    if len(progress_metrics.last_10_actions) > 10:
                        progress_metrics.last_10_actions.pop(0)
                
                # Track state changes (URL changes indicate page transitions)
                current_url = await self.browser.get_url()
                if current_url != prev_url:
                    progress_metrics.state_changes += 1
                    visited_states.add(current_url)
                    progress_metrics.unique_states_visited = len(visited_states)

                # Step 5: Check if task marked complete after actions
                if self.action_handler.is_task_complete():
                    log_success(
                        f"   ✅ Task marked complete after iteration {iteration}"
                    )
                    return True, action_history, None

                # Step 6: Check if any action failed critically
                critical_failure = any(
                    not r.success and r.action_type in ["navigate", "click", "type"]
                    for r in results
                )

                if critical_failure:
                    log_warn(f"   ⚠️  Critical action failure detected")
                    # Continue anyway - agent might recover

                # Small delay between iterations
                await asyncio.sleep(0.5)

            except Exception as e:
                log_error(f"   ❌ Error in iteration {iteration}: {e}")
                import traceback

                traceback.print_exc()
                return (
                    False,
                    action_history,
                    f"Error in iteration {iteration}: {str(e)}",
                )

        # Max iterations reached without completion
        log_warn(
            f"   ⚠️  Max iterations ({max_iterations}) reached without task completion"
        )
        return False, action_history, f"Max iterations ({max_iterations}) reached"

    async def _observe(self) -> Observation:
        """
        Observe current page state with intelligent caching.
        
        Checks cache for both OmniParser and visual analysis results,
        merges them if available.

        Returns:
            Observation object with screenshot, elements, URL
        """
        # Capture screenshot
        screenshot = await self.browser.capture_screenshot()
        
        # Get current URL
        url = await self.browser.get_url()

        # Parse screen elements (cached if possible)
        elements = self.parser.parse(screenshot)
        
        # ENRICH elements with DOM data
        from web_agent.perception.screen_parser import enrich_elements_with_dom
        elements = await enrich_elements_with_dom(elements, self.browser, self.viewport_size)

        # PROACTIVE: Check if we have cached visual analysis for this exact screen
        # This merges visual elements into the prompt automatically
        try:
            from web_agent.storage.screen_cache import get_screen_cache
            cache = get_screen_cache()
            
            # Try to get cached visual analysis (use generic exploration question)
            # We look for any visual analysis done on this exact screenshot
            cached_visual = cache.get_visual_analysis(
                screenshot, 
                "Identify all interactive elements and their locations"
            )
            
            if cached_visual and cached_visual.get('all_elements'):
                log_success(f"      ✅ Found cached visual analysis with {len(cached_visual['all_elements'])} elements")
                
                # Merge visual elements into elements list
                from web_agent.perception.screen_parser import Element
                
                for idx, visual_elem in enumerate(cached_visual['all_elements']):
                    temp_id = 9000 + idx  # Visual elements start at 9000
                    
                    # Create Element object (use description as content)
                    element = Element(
                        id=temp_id,
                        type=visual_elem.get('element_type', 'visual'),
                        bbox=tuple(visual_elem.get('bbox', [0, 0, 0, 0])),
                        center=tuple(visual_elem.get('center_coordinates', [0.5, 0.5])),
                        content=visual_elem.get('description', f'Visual element {temp_id}'),
                        interactivity=True,  # Visual elements are interactive
                        source='visual_analysis_cached'
                    )
                    elements.append(element)
                
                log_debug(f"      🔍 Merged {len(cached_visual['all_elements'])} cached visual elements (IDs 9000+)")
        except Exception as e:
            log_debug(f"      ⚠️  Cache check failed: {e}")

        # ALSO merge any visual elements from recent analyze_visual_content calls
        # These override cached elements if present
        if hasattr(self.action_handler, 'visual_elements') and self.action_handler.visual_elements:
            from web_agent.perception.screen_parser import Element
            
            # Remove any cached visual elements (they'll be replaced by fresh ones)
            elements = [e for e in elements if e.id < 9000]
            
            for temp_id, visual_data in self.action_handler.visual_elements.items():
                # Create Element object from visual analysis data (use description as content)
                visual_element = Element(
                    id=temp_id,
                    type=visual_data.get('type', 'visual'),
                    bbox=tuple(visual_data.get('bbox_normalized', [0, 0, 0, 0])),
                    center=tuple(visual_data.get('center_normalized', [0.5, 0.5])),
                    content=visual_data.get('description', f'Visual element {temp_id}'),
                    interactivity=True,  # Visual elements are interactive
                    source='visual_analysis_recent'
                )
                elements.append(visual_element)
            
            log_debug(f"      🔍 Added {len(self.action_handler.visual_elements)} recent visual elements (IDs 9000+)")

        log_debug(f"      👁️  Observed {len(elements)} total elements at {url}")

        return Observation(
            screenshot=screenshot, elements=elements, url=url, timestamp=time.time()
        )

    async def _decide(
        self, observation: Observation, task_description: str
    ) -> List[BrowserAction]:
        """
        Decide next actions based on observation.

        Args:
            observation: Current state observation
            task_description: Task to accomplish

        Returns:
            List of BrowserActions to execute
        """
        log_debug(f"      🤔 Deciding actions...")

        # Call decision function (provided by intelligence layer)
        actions = await self.decide_next_actions(
            observation=observation, task=task_description, memory=self.memory
        )

        if actions:
            log_info(f"      💡 Decided {len(actions)} action(s):")
            for i, action in enumerate(actions, 1):
                log_debug(
                    f"         {i}. {action.action_type.value}: {action.parameters}"
                )

        return actions

    async def _act(
        self, actions: List[BrowserAction], elements: List[Any]
    ) -> List[ActionResult]:
        """
        Execute list of actions with auto-scroll and screen re-parsing.
        
        CRITICAL: For each action, we:
        1. Check if target element is visible
        2. Scroll to make it visible if needed
        3. Re-parse screen to get fresh coordinates
        4. Execute action with updated coordinates

        Args:
            actions: Actions to execute
            elements: Current page elements (for action execution)

        Returns:
            List of ActionResults
        """
        results = []

        for i, action in enumerate(actions, 1):
            log_info(
                f"      ⚡ Executing action {i}/{len(actions)}: {action.action_type.value}"
            )

            # CRITICAL: Scroll element into view BEFORE executing
            # This ensures element is visible and we have fresh coordinates
            needs_scroll = action.action_type.value in ['click', 'type', 'scroll_to_result']
            
            if needs_scroll and 'element_id' in action.parameters:
                elem_id = action.parameters['element_id']
                
                # Find element in current list
                elem = next((e for e in elements if e.id == elem_id), None)
                
                if elem:
                    # Convert normalized coordinates to pixels
                    x = int(elem.center[0] * self.viewport_size[0])
                    y = int(elem.center[1] * self.viewport_size[1])
                    
                    # Check if element is in viewport (with margin)
                    viewport_margin = 100  # pixels from edge
                    viewport_w, viewport_h = self.viewport_size
                    
                    is_visible = (
                        viewport_margin < x < (viewport_w - viewport_margin) and
                        viewport_margin < y < (viewport_h - viewport_margin)
                    )
                    
                    if not is_visible:
                        log_info(f"         📜 Element {elem_id} not in viewport, scrolling into view...")
                        
                        try:
                            # Scroll element to center of viewport
                            await self.browser._center_on_position(x, y)
                            await asyncio.sleep(0.5)  # Wait for scroll to complete
                            
                            # CRITICAL: Re-parse screen to get fresh element positions
                            log_debug(f"         🔄 Re-parsing screen after scroll...")
                            screenshot = await self.browser.capture_screenshot()
                            elements = self.parser.parse(screenshot)
                            
                            # Re-enrich with DOM
                            from web_agent.perception.screen_parser import enrich_elements_with_dom
                            elements = await enrich_elements_with_dom(elements, self.browser, self.viewport_size)
                            
                            # Free screenshot
                            del screenshot
                            import gc
                            gc.collect()
                            
                            log_success(f"         ✅ Scrolled and re-parsed {len(elements)} elements")
                            
                        except Exception as e:
                            log_warn(f"         ⚠️  Scroll failed: {e}")
                            # Continue anyway - element might still work
                else:
                    log_debug(f"         ℹ️  Element {elem_id} not found in element list")

            # Execute action with current (possibly updated) elements
            result = await self.action_handler.handle_action(action, elements)
            results.append(result)

            if result.success:
                log_success(f"         ✅ Success")
            else:
                log_error(f"         ❌ Failed: {result.error}")

            # If a conversation manager is available, attempt to append this action event
            # to the supervisor thread recorded in worker memory (best-effort, non-fatal).
            try:
                conv_mgr = getattr(self, "conversation_manager", None)
                if conv_mgr:
                    # Try to discover the supervisor thread id from worker memory
                    thread_id = None
                    try:
                        # memory.get_all() is used elsewhere in the codebase to fetch worker memory.
                        mem_all = (
                            self.memory.get_all()
                            if hasattr(self.memory, "get_all")
                            else {}
                        )
                    except Exception:
                        mem_all = {}
                    # Common keys we look for (configurable via supervisor_thread_key)
                    if isinstance(mem_all, dict):
                        thread_id = (
                            mem_all.get(self.supervisor_thread_key)
                            or mem_all.get("supervisor_thread")
                            or mem_all.get("supervisor")
                        )
                    # Determine actor (worker namespace) if available
                    actor = (
                        getattr(self.memory, "namespace", None)
                        or getattr(self.memory, "worker_id", None)
                        or "worker"
                    )
                    if thread_id:
                        # Build a concise action description and details
                        action_desc = getattr(
                            action, "action_type", getattr(action, "type", "action")
                        )
                        # Convert action_desc to string if needed
                        try:
                            action_desc_str = (
                                action_desc.value
                                if hasattr(action_desc, "value")
                                else str(action_desc)
                            )
                        except Exception:
                            action_desc_str = str(action_desc)
                        details = {
                            "target": getattr(result, "target", None),
                            "error": getattr(result, "error", None),
                            "metadata": getattr(result, "metadata", {})
                            if hasattr(result, "metadata")
                            else {},
                        }
                        # Append action event (best-effort, do not break on failure)
                        try:
                            await conv_mgr.append_action(
                                thread_id,
                                actor,
                                action_desc_str,
                                bool(result.success),
                                details,
                            )
                        except Exception:
                            # swallow - do not fail action execution on conversation append errors
                            pass
            except Exception:
                # swallow any unexpected errors from best-effort instrumentation
                pass

            # Small delay between actions
            if i < len(actions):
                await asyncio.sleep(0.3)

        return results
    
    async def _append_tool_results_to_history(
        self, actions: List[BrowserAction], results: List[ActionResult]
    ):
        """
        Append tool execution results to Gemini chat history.
        
        CRITICAL: This allows the AI to remember what tools returned!
        Without this, analyze_visual_content results and other tool outputs are lost.
        
        Args:
            actions: Actions that were executed
            results: Results from executing those actions
        """
        import json
        
        log_debug(f"      🔍 Attempting to append {len(results)} tool results to history...")
        
        try:
            # Get the GeminiAgent instance from the decision function
            # The decision function is a bound method of WorkerAgent, which has gemini attribute
            if not hasattr(self.decide_next_actions, '__self__'):
                log_debug(f"      ⚠️  decide_next_actions is not a bound method, cannot get Gemini")
                return  # Not a bound method, can't get Gemini
            
            worker_agent = self.decide_next_actions.__self__
            if not hasattr(worker_agent, 'gemini'):
                return  # No gemini attribute
            
            gemini = worker_agent.gemini
            if not hasattr(gemini, 'append_tool_results'):
                return  # No append_tool_results method
            
            # Check if there are pending tool calls
            if not hasattr(gemini, '_pending_tool_calls') or not gemini._pending_tool_calls:
                return  # No pending tool calls to match
            
            # Get thread_id from worker memory
            thread_id = None
            try:
                mem_all = self.memory.get_all() if hasattr(self.memory, 'get_all') else {}
                if isinstance(mem_all, dict):
                    thread_id = mem_all.get('thread_id') or mem_all.get('worker_id')
            except Exception:
                pass
            
            if not thread_id:
                return  # Can't append without thread_id
            
            # Build tool results from actions and results
            tool_results = []
            pending_calls = gemini._pending_tool_calls
            
            for i, (action, result) in enumerate(zip(actions, results)):
                # Match with pending tool call if available
                tool_call_id = f'call_{i}'
                tool_name = action.action_type.value
                
                if i < len(pending_calls):
                    tool_call = pending_calls[i]
                    tool_call_id = tool_call.get('id', f'call_{i}')
                    tool_name = tool_call.get('name', tool_name)
                
                # Build human-readable content with clear descriptions
                action_type = action.action_type.value
                
                if result.metadata and 'answer' in result.metadata:
                    # Visual analysis tool - include full context
                    coords = result.metadata.get('target_coordinates', [])
                    coords_desc = ""
                    if coords and len(coords) >= 2:
                        coords_desc = f" Target location: normalized coordinates [{coords[0]:.3f}, {coords[1]:.3f}] (where 0.0=left/top, 1.0=right/bottom)"
                    
                    content = json.dumps({
                        'tool': 'analyze_visual_content',
                        'success': result.success,
                        'description': f"Visual analysis completed with {result.metadata.get('confidence', 0.0):.0%} confidence",
                        'answer': result.metadata['answer'],
                        'target_element_id': result.metadata.get('target_element_id'),
                        'target_coordinates': result.metadata.get('target_coordinates'),
                        'coordinates_explanation': coords_desc.strip(),
                        'confidence': result.metadata.get('confidence', 0.0)
                    }, indent=2)
                    
                elif action_type == 'click':
                    # Click action - explain coordinates
                    x = action.parameters.get('x', 0)
                    y = action.parameters.get('y', 0)
                    content = json.dumps({
                        'tool': 'click',
                        'success': result.success,
                        'description': f"Clicked at pixel position ({x}, {y})",
                        'x_pixels': x,
                        'y_pixels': y,
                        'explanation': "Coordinates are absolute pixel positions on the screen",
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                elif action_type == 'scroll':
                    # Scroll action - explain direction and amount
                    direction = action.parameters.get('direction', 'down')
                    amount = action.parameters.get('amount', 0)
                    content = json.dumps({
                        'tool': 'scroll',
                        'success': result.success,
                        'description': f"Scrolled {direction.upper()} by {amount} pixels",
                        'direction': direction,
                        'amount_pixels': amount,
                        'explanation': f"Moved the page viewport {amount}px in the {direction} direction",
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                elif action_type == 'type':
                    # Type action - explain what was typed
                    text = action.parameters.get('text', '')
                    content = json.dumps({
                        'tool': 'type',
                        'success': result.success,
                        'description': f"Typed text: '{text[:50]}{'...' if len(text) > 50 else ''}'",
                        'text_length': len(text),
                        'full_text': text,
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                elif action_type == 'navigate':
                    # Navigate action
                    url = action.parameters.get('url', '')
                    content = json.dumps({
                        'tool': 'navigate',
                        'success': result.success,
                        'description': f"Navigated to URL: {url}",
                        'url': url,
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                elif action_type == 'wait':
                    # Wait action
                    duration = action.parameters.get('duration', 0)
                    content = json.dumps({
                        'tool': 'wait',
                        'success': result.success,
                        'description': f"Waited for {duration} seconds",
                        'duration_seconds': duration,
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                elif action_type == 'store_data':
                    # Store data action
                    key = action.parameters.get('key', '')
                    value = action.parameters.get('value', '')
                    content = json.dumps({
                        'tool': 'store_data',
                        'success': result.success,
                        'description': f"Stored data with key '{key}'",
                        'key': key,
                        'value_preview': str(value)[:100],
                        'explanation': "Data saved to worker memory for later retrieval",
                        'error': result.error if not result.success else None
                    }, indent=2)
                    
                else:
                    # Generic action - include whatever metadata we have
                    content = json.dumps({
                        'tool': action_type,
                        'success': result.success,
                        'description': f"Executed {action_type} action",
                        'parameters': action.parameters,
                        'metadata': result.metadata,
                        'error': result.error if not result.success else None
                    }, indent=2)
                
                tool_results.append({
                    'tool_call_id': tool_call_id,
                    'name': tool_name,
                    'content': content
                })
            
            # Append to history
            if tool_results:
                gemini.append_tool_results(thread_id, tool_results)
                log_debug(f"      📝 Appended {len(tool_results)} tool result(s) to chat history")
            
        except Exception as e:
            # Best effort - don't fail action loop if this fails
            log_warn(f"      ⚠️  Failed to append tool results to history: {e}")
            import traceback
            traceback.print_exc()
