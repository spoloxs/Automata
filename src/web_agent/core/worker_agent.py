"""
Worker Agent - Executes a single task with isolated context.
State management handled by caller (Supervisor).
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from web_agent.config.settings import (
    BROWSER_WINDOW_SIZE,
    MAX_ACTION_ITERATIONS,
    WORKER_TOKEN_LIMIT,
)
from web_agent.core.result import ActionResult, TaskResult, VerificationResult
from web_agent.core.task import Task, TaskStatus
from web_agent.execution.action_handler import ActionHandler
from web_agent.execution.action_loop import ActionLoop, BrowserAction, Observation
from web_agent.execution.browser_controller import BrowserController
from web_agent.perception.screen_parser import ScreenParser
from web_agent.storage.worker_memory import WorkerMemory
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


class WorkerAgent:
    """
    Worker agent that executes a single task with isolated context.

    Responsibility: Execute task and return result
    State management: Handled by caller (Supervisor)

    Each worker:
    - Has unique thread_id for isolated LLM context
    - Has namespaced memory to prevent pollution
    - Runs observe-decide-act loop until task completion
    - Self-verifies task completion
    - Returns result WITHOUT changing task state
    - Is disposable after task execution
    """

    def __init__(
        self,
        worker_id: str,
        task: Task,
        browser_page,  # Playwright Page (shared)
        gemini_agent,  # Intelligence layer (for decide_action)
        verifier,  # Verification layer
        parent_context: Optional[Dict] = None,
        accomplishment_store=None,  # Optional AccomplishmentStore
        screen_parser=None,  # CRITICAL: Shared ScreenParser from master
    ):
        log_debug("WorkerAgent.__init__ called")
        """
        Initialize worker agent.

        Args:
            worker_id: Unique worker identifier
            task: Task to execute (should already be marked RUNNING by supervisor)
            browser_page: Shared Playwright page
            gemini_agent: Intelligence layer for decision making
            verifier: Verification layer for task validation
            parent_context: Minimal context from master (goal, url)
            accomplishment_store: Optional shared accomplishment store
            screen_parser: Shared ScreenParser instance (CRITICAL for memory efficiency!)
        """
        self.worker_id = worker_id
        self.task = task
        self.parent_context = parent_context or {}
        self.accomplishment_store = accomplishment_store

        # Unique thread_id for isolated LLM context
        self.thread_id = f"worker_{worker_id}_{uuid.uuid4().hex[:8]}"

        # Initialize components
        self.browser = BrowserController(page=browser_page)
        # CRITICAL: Use shared parser if provided, else create new (backward compat)
        self.parser = screen_parser if screen_parser is not None else ScreenParser()
        self.memory = WorkerMemory(namespace=worker_id)
        self.action_handler = ActionHandler(
            browser_controller=self.browser,
            memory=self.memory,
            viewport_size=BROWSER_WINDOW_SIZE,
            accomplishment_store=accomplishment_store,
            agent_id=worker_id,
            gemini_agent=gemini_agent,
        )

        # Intelligence & verification
        self.gemini_agent = gemini_agent
        self.verifier = verifier

        # Action loop
        # If the master provided conversation instrumentation via parent_context, pick it up
        conv_mgr = None
        supervisor_thread_key = "supervisor_thread"
        if isinstance(self.parent_context, dict):
            try:
                conv_mgr = self.parent_context.get("conversation_manager", None)
            except Exception:
                conv_mgr = None
            try:
                supervisor_thread_key = self.parent_context.get(
                    "supervisor_thread_key", "supervisor_thread"
                )
            except Exception:
                supervisor_thread_key = "supervisor_thread"

        # Expose conversation manager on the worker for instrumentation (best-effort)
        # so worker-level verification outputs and run summaries can be appended to the
        # supervisor conversation thread.
        self.conversation_manager = conv_mgr

        self.action_loop = ActionLoop(
            browser_controller=self.browser,
            screen_parser=self.parser,
            action_handler=self.action_handler,
            memory=self.memory,
            decision_function=self._decide_actions,
            viewport_size=BROWSER_WINDOW_SIZE,
            conversation_manager=conv_mgr,
            supervisor_thread_key=supervisor_thread_key,
        )

        log_info(f"   🏗️  Worker {worker_id[:8]} initialized (thread: {self.thread_id})")

    async def execute_task(self) -> TaskResult:
        log_debug("WorkerAgent.execute_task called")
        """
        Execute the assigned task and return result.

        Does NOT manage task state - caller is responsible for:
        - Marking task as RUNNING before calling this
        - Marking task as COMPLETED/FAILED after receiving result

        Returns:
            TaskResult with execution details
        """
        log_info(f"\n{'=' * 60}")
        log_info(f"🔧 Worker {self.worker_id[:8]} executing task {self.task.id[:8]}")
        log_info(f"   Task: {self.task.description}")
        log_info(f"{'=' * 60}")

        # ✅ Verify task is in RUNNING state (should be set by supervisor)
        if self.task.status != TaskStatus.RUNNING:
            log_warn(
                f"   ⚠️  Task {self.task.id[:8]} expected to be RUNNING, "
                f"got {self.task.status}. Continuing anyway..."
            )

        start_time = time.time()

        try:
            # STEP 1: Check if task matches current screen state
            task_feasible, mismatch_reason = await self._check_task_feasibility()
            
            if not task_feasible:
                log_warn(f"   ⚠️  Task-screen mismatch detected!")
                log_warn(f"   📋 Task: {self.task.description}")
                log_warn(f"   🚫 Issue: {mismatch_reason}")
                log_warn(f"   🔄 Requesting replan...")
                
                # Return result indicating need for replan
                end_time = time.time()
                return TaskResult(
                    task_id=self.task.id,
                    success=False,
                    needs_replan=True,
                    replan_reason=mismatch_reason,
                    action_history=[],
                    extracted_data=self.memory.get_all(),
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    worker_id=self.worker_id,
                    worker_thread_id=self.thread_id,
                    error=f"Task-screen mismatch: {mismatch_reason}",
                )
            
            # STEP 2: Run action loop until task completion (NO TIMEOUT - iteration-based only)
            success, action_history, error = await self.action_loop.run(
                task_description=self.task.description,
                max_iterations=MAX_ACTION_ITERATIONS,
                timeout=None,  # No timeout - rely on iteration limit
            )

            end_time = time.time()
            duration = end_time - start_time

            # Verify task completion (if marked complete)
            verification = None
            if success:
                verification = await self._verify_completion()
                # Override success based on verification
                success = verification.completed

            # ✅ Build result WITHOUT changing task state
            # Supervisor will handle state transitions based on this result
            result = TaskResult(
                task_id=self.task.id,
                success=success,
                action_history=action_history,
                extracted_data=self.memory.get_all(),
                verification=verification,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                worker_id=self.worker_id,
                worker_thread_id=self.thread_id,
                error=error,
            )

            # Best-effort: append a concise run-summary action to the supervisor conversation thread so
            # the decision engine / master can reason about why a run stopped and how much progress was made.
            try:
                conv_mgr = getattr(self, "conversation_manager", None)
                if conv_mgr:
                    # Discover supervisor thread id from parent context or worker memory.
                    thread_id = None
                    try:
                        if isinstance(self.parent_context, dict):
                            thread_id = (
                                self.parent_context.get("supervisor_thread")
                                or self.parent_context.get("supervisor")
                                or thread_id
                            )
                    except Exception:
                        thread_id = thread_id
                    try:
                        mem_all = (
                            self.memory.get_all()
                            if hasattr(self.memory, "get_all")
                            else {}
                        )
                        if not thread_id and isinstance(mem_all, dict):
                            thread_id = (
                                mem_all.get("supervisor_thread")
                                or mem_all.get("supervisor")
                                or mem_all.get("supervisor_thread_key")
                            )
                    except Exception:
                        pass

                    if thread_id:
                        summary_details = {
                            "task_id": self.task.id,
                            "task_description": self.task.description,
                            "worker_id": self.worker_id,
                            "worker_thread_id": self.thread_id,
                            "success": bool(result.success),
                            "duration": float(result.duration)
                            if result.duration is not None
                            else None,
                            "actions_executed": len(result.action_history)
                            if result.action_history is not None
                            else 0,
                            "error": result.error,
                        }
                        try:
                            # Append a discrete action event named 'task_summary' to capture the run outcome.
                            await conv_mgr.append_action(
                                thread_id,
                                actor=self.worker_id,
                                action_desc="task_summary",
                                success=bool(result.success),
                                details=summary_details,
                            )
                            # Also append verification object if present for richer decision context.
                            if verification:
                                await conv_mgr.append_verification(
                                    thread_id, verification.to_dict()
                                )
                        except Exception:
                            # Best-effort instrumentation should not affect execution
                            pass
            except Exception:
                # swallow any unexpected instrumentation errors
                pass

            log_info(f"\n{'=' * 60}")
            log_success(
                f"{'✅' if success else '❌'} Worker {self.worker_id[:8]} "
                f"{'COMPLETED' if success else 'FAILED'}"
            )
            log_info(f"   Duration: {duration:.2f}s")
            log_info(f"   Actions: {len(action_history)}")
            if verification:
                log_info(f"   Verification: {verification.confidence:.1%} confident")
            log_info(f"{'=' * 60}\n")

            return result

        except Exception as e:
            log_error(f"\n❌ Worker {self.worker_id[:8]} encountered error: {e}")
            import traceback

            traceback.print_exc()

            end_time = time.time()

            # ✅ Return error result WITHOUT changing task state
            return TaskResult(
                task_id=self.task.id,
                success=False,
                error=str(e),
                error_details=traceback.format_exc(),
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                worker_id=self.worker_id,
                worker_thread_id=self.thread_id,
            )

    async def _decide_actions(
        self, observation: Observation, task: str, memory: WorkerMemory
    ) -> List[BrowserAction]:
        """
        Decide next actions using Gemini agent.

        This is the bridge between action loop and intelligence layer.

        Args:
            observation: Current state observation
            task: Task description
            memory: Worker memory

        Returns:
            List of BrowserActions to execute
        """
        # Format elements for LLM
        from web_agent.perception.element_formatter import ElementFormatter

        # Pass viewport size for pixel coordinate conversion
        viewport_size = await self.browser.get_viewport_size() if self.browser else (1440, 900)
        elements_text = ElementFormatter.format_for_llm(
            observation.elements, 
            max_elements=None,  # Send ALL elements, no truncation
            viewport_size=viewport_size
        )

        # Get accomplishment summary if store is available
        accomplishment_summary = None
        if self.accomplishment_store:
            try:
                accomplishment_summary = self.accomplishment_store.get_summary()
                log_info(f"      📋 Accomplishment summary ({len(self.accomplishment_store.accomplishments)} items):")
                log_info(f"      {accomplishment_summary[:200]}...")
            except Exception as e:
                log_debug(f"      ⚠️  Could not get accomplishment summary: {e}")
        else:
            log_warn(f"      ⚠️  No accomplishment store available for worker {self.worker_id}")

        # Call Gemini agent's decide_action
        actions_data = await self.gemini_agent.decide_action(
            task=task,
            elements=observation.elements,
            url=observation.url,
            thread_id=self.thread_id,
            storage_data=memory.get_all(),
            viewport_size=self.action_handler.viewport_size,
            accomplishment_summary=accomplishment_summary,
        )

        # Convert to BrowserAction objects
        actions = []
        if isinstance(actions_data, list):
            for action_data in actions_data:
                try:
                    action = BrowserAction.from_tool_call(
                        tool_name=action_data.get(
                            "tool", action_data.get("action_type")
                        ),
                        parameters=action_data.get("parameters", {}),
                    )
                    actions.append(action)
                except Exception as e:
                    log_warn(f"      ⚠️  Failed to parse action: {e}")

        return actions

    async def _check_task_feasibility(self) -> tuple[bool, str]:
        """
        Check if the task can be executed on the current screen.
        
        Returns:
            Tuple of (is_feasible, reason)
        """
        try:
            # Get current screen state
            screenshot = await self.browser.capture_screenshot()
            elements = self.parser.parse(screenshot)
            url = await self.browser.get_url()
            
            # Format for LLM
            from web_agent.perception.element_formatter import ElementFormatter
            elements_text = ElementFormatter.format_for_llm(elements)
            
            # Ask Gemini if task is feasible given current screen
            prompt = f"""You are a task feasibility analyzer.

TASK TO EXECUTE:
{self.task.description}

CURRENT SCREEN STATE:
URL: {url}
Elements visible: {len(elements)}

ELEMENTS:
{elements_text[:2000]}

ANALYSIS REQUIRED:
Can this task be executed?

**CRITICAL: You have access to the `navigate` tool!**
- If the task mentions a URL (e.g., "Navigate to https://example.com"), you can ALWAYS do it using navigate(url)
- You do NOT need to find navigation elements on the current screen
- The navigate tool works regardless of what's currently visible

Common mismatch scenarios that are TRULY infeasible:
1. Task asks to click specific element that doesn't exist AND can't be found by scrolling
2. Task requires data from previous step that wasn't completed
3. Task asks to interact with content that doesn't exist on the target page

Scenarios that ARE feasible:
1. Task says "navigate to URL" → ALWAYS feasible (use navigate tool)
2. Task says "click link to go somewhere" → Feasible (can find link or use navigate)
3. Elements might be off-screen → Feasible (can scroll)
4. Task on different page → Feasible (can navigate there)

Return JSON:
{{
    "feasible": true/false,
    "reason": "Brief explanation"
}}

**Be liberal - mark feasible unless TRULY impossible. Remember you have navigate, click, scroll, and visual analysis tools!**"""

            # Use action_llm for simple text response
            response = await self.gemini_agent.action_llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse response
            import json
            import re
            
            # Try to extract JSON from response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Look for JSON object
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    is_feasible = bool(data.get('feasible', True))
                    reason = data.get('reason', 'No specific reason provided')
                    
                    # Free resources
                    del screenshot, elements
                    import gc
                    gc.collect()
                    
                    return is_feasible, reason
                except:
                    pass
            
            # Default to feasible if parsing fails
            del screenshot, elements
            import gc
            gc.collect()
            return True, "Feasibility check passed (parser fallback)"
            
        except Exception as e:
            log_warn(f"   ⚠️ Feasibility check error: {e}")
            # Default to feasible on error
            return True, f"Feasibility check skipped ({str(e)})"
    
    async def _verify_completion(self) -> VerificationResult:
        """
        Verify task completion using verifier.

        Returns:
            VerificationResult
        """
        log_info(f"      🔍 Verifying task completion...")

        # Get current state
        screenshot = await self.browser.capture_screenshot()
        elements = self.parser.parse(screenshot)
        url = await self.browser.get_url()

        # Call verifier
        verification = await self.verifier.verify_task_completion(
            task=self.task.description,
            url=url,
            elements=elements,
            storage_data=self.memory.get_all(),
            thread_id=self.thread_id,
            screenshot=screenshot,
        )
        
        # Free screenshot and elements immediately after verification
        del screenshot, elements
        import gc
        gc.collect()

        if verification.completed:
            log_success(
                f"      ✅ Verified complete ({verification.confidence:.1%} confident)"
            )
        else:
            log_error(
                f"      ❌ Verification failed ({verification.confidence:.1%} confident)"
            )
            log_warn(f"         Reason: {verification.reasoning}")

        # Best-effort: append verification output to supervisor conversation thread if available.
        try:
            conv_mgr = getattr(self, "conversation_manager", None)
            if conv_mgr:
                # Try to discover supervisor thread id from parent context or worker memory.
                thread_id = None
                try:
                    if isinstance(self.parent_context, dict):
                        thread_id = (
                            self.parent_context.get("supervisor_thread")
                            or self.parent_context.get("supervisor")
                            or thread_id
                        )
                except Exception:
                    thread_id = thread_id
                try:
                    mem_all = (
                        self.memory.get_all() if hasattr(self.memory, "get_all") else {}
                    )
                    if not thread_id and isinstance(mem_all, dict):
                        thread_id = (
                            mem_all.get("supervisor_thread")
                            or mem_all.get("supervisor_thread_key")
                            or mem_all.get("supervisor")
                        )
                except Exception:
                    # ignore memory access errors
                    pass
                # If we found a supervisor thread id, append verification details
                if thread_id:
                    try:
                        await conv_mgr.append_verification(
                            thread_id, verification.to_dict()
                        )
                    except Exception:
                        # best-effort only
                        pass
        except Exception:
            # swallow instrumentation errors
            pass

        return verification

    async def cleanup(self):
        """
        Cleanup worker resources.

        Note: Browser page is shared, so we don't close it.
        Only clear worker-specific memory.
        """
        try:
            log_info(f"   🧹 Cleaning up worker {self.worker_id[:8]}")
            self.memory.clear()
            
            # CRITICAL: Clear Gemini chat history for this thread to prevent RAM leak
            # Each worker creates a unique thread_id and accumulates conversation history
            # Without this cleanup, chat_histories dict grows unbounded!
            if hasattr(self, 'gemini_agent') and hasattr(self.gemini_agent, 'clear_context'):
                self.gemini_agent.clear_context(self.thread_id)
                log_debug(f"   🧹 Cleared Gemini chat history for thread {self.thread_id[:20]}")
            
            log_success(f"   ✅ Worker {self.worker_id[:8]} cleaned up")
        except Exception as e:
            log_error(f"   ⚠️  Cleanup error for worker {self.worker_id[:8]}: {e}")

    def get_thread_id(self) -> str:
        """Get worker's unique thread ID"""
        return self.thread_id

    def get_worker_id(self) -> str:
        """Get worker ID"""
        return self.worker_id

    def get_task(self) -> Task:
        """Get assigned task"""
        return self.task
