"""
Planner Agent - Executes DAG tasks by spawning and managing Worker Agents.

Architecture:
- PlannerAgent receives a Task from the DAG
- PlannerAgent analyzes the task and creates a mini-plan
- PlannerAgent spawns Worker Agents to execute sub-tasks
- Workers report back to PlannerAgent
- PlannerAgent verifies overall task completion
- PlannerAgent reports back to Supervisor

This creates a hierarchy: Supervisor → Planner Agents → Worker Agents
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from web_agent.core.result import TaskResult
from web_agent.core.task import Task
from web_agent.core.worker_agent import WorkerAgent
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.perception.element_formatter import ElementFormatter
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


class PlannerAgent:
    """
    Planner Agent - Manages task execution by spawning workers.
    
    Responsibilities:
    - Break down DAG task into actionable sub-tasks
    - Spawn Worker Agents for each sub-task
    - Track worker progress and results
    - Verify task completion
    - Adapt plan based on worker feedback
    """

    def __init__(
        self,
        planner_id: str,
        task: Task,
        browser_page,
        gemini_agent: GeminiAgent,
        verifier,
        screen_parser,
        parent_context: Optional[Dict] = None,
        accomplishment_store=None,
    ):
        self.planner_id = planner_id
        self.task = task
        self.browser = browser_page
        self.gemini = gemini_agent
        self.verifier = verifier
        self.parser = screen_parser
        self.parent_context = parent_context or {}
        self.accomplishment_store = accomplishment_store
        
        # Planner state
        self.subtasks: List[Dict] = []
        self.worker_results: List[TaskResult] = []
        self.max_workers = 3  # Max concurrent workers
        self.max_iterations = 10  # Max adaptation cycles
        
        log_info(f"🎯 PlannerAgent {planner_id} initialized for task: {task.description[:60]}")

    async def execute_task(self) -> TaskResult:
        """
        Execute the task by spawning and managing workers.
        
        Flow:
        1. Analyze task and create execution plan
        2. Spawn workers to execute sub-tasks
        3. Monitor worker progress
        4. Adapt plan based on feedback
        5. Verify overall completion
        6. Return consolidated result
        """
        start_time = time.time()
        
        try:
            log_info(f"\n🎯 Planner {self.planner_id} executing: {self.task.description}")
            
            # STEP 1: Create execution plan
            await self._create_execution_plan()
            
            if not self.subtasks:
                log_warn(f"   ⚠️ No subtasks generated - marking as failed")
                return self._create_failure_result("No execution plan generated", start_time)
            
            log_info(f"   📋 Created plan with {len(self.subtasks)} sub-tasks")
            
            # STEP 2: Execute subtasks with workers
            iteration = 0
            while iteration < self.max_iterations:
                iteration += 1
                log_info(f"\n   🔄 Iteration {iteration}/{self.max_iterations}")
                
                # Execute pending subtasks
                pending_tasks = [st for st in self.subtasks if not st.get('completed', False)]
                
                if not pending_tasks:
                    log_success(f"   ✅ All sub-tasks completed!")
                    break
                
                log_info(f"   📊 {len(pending_tasks)} pending sub-tasks")
                
                # Spawn workers for pending tasks (respecting max_workers limit)
                tasks_to_execute = pending_tasks[:self.max_workers]
                results = await self._execute_subtasks_parallel(tasks_to_execute)
                
                # Process worker results and adapt plan
                should_continue = await self._process_worker_results(results)
                
                if not should_continue:
                    log_info(f"   🛑 Stopping execution (task complete or unrecoverable)")
                    break
            
            # STEP 3: Verify overall task completion
            verification = await self._verify_task_completion()
            
            # STEP 4: Build consolidated result
            return self._build_final_result(verification, start_time)
            
        except Exception as e:
            log_error(f"   ❌ Planner execution error: {e}")
            import traceback
            traceback.print_exc()
            return self._create_failure_result(str(e), start_time)

    async def _create_execution_plan(self):
        """
        Analyze the task and create a plan of sub-tasks for workers.
        
        Uses Gemini to decompose the task into actionable sub-tasks.
        """
        try:
            # Get current page state
            screenshot = await self.browser.screenshot()
            from PIL import Image
            import io
            screenshot_img = Image.open(io.BytesIO(screenshot))
            
            elements = self.parser.parse(screenshot_img)
            viewport_size = (self.browser.viewport_size['width'], self.browser.viewport_size['height'])
            elements_text = ElementFormatter.format_for_planner(elements, viewport_size=viewport_size)
            
            # Free screenshot
            del screenshot, screenshot_img
            
            # Get current URL
            current_url = self.browser.url
            
            log_info(f"   🔍 Analyzing page with {len(elements)} elements")
            
            # Build planning prompt
            prompt = f"""You are a PLANNER AGENT breaking down a task into actionable sub-tasks for WORKER AGENTS.

TASK TO ACCOMPLISH:
{self.task.description}

CURRENT PAGE STATE:
URL: {current_url}
Elements visible: {len(elements)}
Elements: {elements_text[:1500]}...

YOUR JOB:
Break this task into 1-5 SPECIFIC, ACTIONABLE sub-tasks that workers can execute.

RULES:
1. Each sub-task must be CONCRETE and VERIFIABLE
2. Sub-tasks should be SEQUENTIAL (dependencies matter)
3. **NEVER use element IDs (e.g., [12]) or Coordinates.** Use descriptive language.
   - ❌ BAD: "Click element [42]"
   - ✅ GOOD: "Click the 'Submit' button in the center form"
   - Worker agents will find the correct element ID at runtime.
4. If elements are missing, include "scroll to find" or "navigate to find" sub-tasks
5. Keep it SIMPLE - workers will handle the details

EXAMPLES:

Good sub-tasks:
- "Click the 'Games' link in top navigation"
- "Scroll down 500px to reveal more content"
- "Type 'test' into the input field labeled 'Search'"
- "Verify that results appear with at least 1 item"

Bad sub-tasks:
- "Navigate to games section" (how? where?)
- "Find the button" (which button? where?)
- "Play the game" (too vague)

Return a JSON array of sub-tasks:
[
  {{
    "description": "Specific action to take",
    "expected_outcome": "What should happen after this action",
    "critical": true/false
  }}
]
"""
            
            # Get plan from Gemini
            response = await self.gemini.action_llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse response
            import json
            import re
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                subtasks_data = json.loads(json_match.group(0))
                
                for idx, st in enumerate(subtasks_data):
                    self.subtasks.append({
                        'index': idx,
                        'description': st.get('description', ''),
                        'expected_outcome': st.get('expected_outcome', ''),
                        'critical': st.get('critical', True),
                        'completed': False,
                        'result': None,
                    })
                
                log_success(f"   ✅ Created {len(self.subtasks)} sub-tasks")
                for st in self.subtasks:
                    log_debug(f"      {st['index']+1}. {st['description']}")
            else:
                log_warn(f"   ⚠️ Could not parse subtasks from response")
                # Fallback: create single subtask
                self.subtasks = [{
                    'index': 0,
                    'description': self.task.description,
                    'expected_outcome': 'Task completed',
                    'critical': True,
                    'completed': False,
                    'result': None,
                }]
                
        except Exception as e:
            log_error(f"   ❌ Planning error: {e}")
            # Fallback: create single subtask
            self.subtasks = [{
                'index': 0,
                'description': self.task.description,
                'expected_outcome': 'Task completed',
                'critical': True,
                'completed': False,
                'result': None,
            }]

    async def _execute_subtasks_parallel(self, tasks: List[Dict]) -> List[TaskResult]:
        """
        Execute multiple sub-tasks in parallel by spawning workers.
        """
        results = []
        
        async def execute_single_subtask(subtask: Dict) -> TaskResult:
            """Execute a single subtask with a worker"""
            worker_id = f"{self.planner_id}_worker_{subtask['index']}"
            
            # Create a Task object for the worker
            worker_task = Task(
                description=subtask['description'],
            )
            
            # CRITICAL: Mark task as running before passing to worker
            # This satisfies the status check in WorkerAgent.execute_task
            try:
                worker_task.mark_running(worker_id)
            except ValueError:
                # Should not happen for new task, but safe fallback
                worker_task.status = "running"
                worker_task.assigned_worker = worker_id
                worker_task.start_time = time.time()
            
            log_info(f"      🤖 Spawning worker {worker_id} for: {subtask['description'][:50]}")
            
            try:
                # Create worker
                worker = WorkerAgent(
                    worker_id=worker_id,
                    task=worker_task,
                    browser_page=self.browser,
                    gemini_agent=self.gemini,
                    verifier=self.verifier,
                    parent_context={
                        "planner_id": self.planner_id,
                        "subtask_index": subtask['index'],
                        "expected_outcome": subtask['expected_outcome'],
                        **self.parent_context,
                    },
                    accomplishment_store=self.accomplishment_store,
                    screen_parser=self.parser,
                )
                
                # Execute task
                result = await worker.execute_task()
                
                # Cleanup
                await worker.cleanup()
                
                log_info(f"      {'✅' if result.success else '❌'} Worker {worker_id}: {('Success' if result.success else f'Failed - {result.error}')}")
                
                return result
                
            except Exception as e:
                log_error(f"      ❌ Worker {worker_id} exception: {e}")
                return TaskResult(
                    task_id=worker_task.id,
                    success=False,
                    error=str(e),
                    duration=0.0,
                    action_history=[],
                )
        
        # Execute all subtasks in parallel
        results = await asyncio.gather(*[execute_single_subtask(task) for task in tasks])
        
        return results

    async def _process_worker_results(self, results: List[TaskResult]) -> bool:
        """
        Process worker results and update subtask status.
        
        Returns:
            bool: True if should continue execution, False if complete or failed
        """
        for i, result in enumerate(results):
            # Find matching subtask
            subtask = self.subtasks[i] if i < len(self.subtasks) else None
            
            if subtask:
                subtask['completed'] = result.success
                subtask['result'] = result
                self.worker_results.append(result)
                
                if not result.success and subtask['critical']:
                    log_warn(f"      ⚠️ Critical subtask failed: {subtask['description'][:50]}")
                    # Could add retry logic here or adapt the plan
        
        # Check if we should continue
        all_completed = all(st['completed'] for st in self.subtasks)
        any_critical_failed = any(
            not st['completed'] and st['critical']
            for st in self.subtasks
        )
        
        if all_completed:
            return False  # Done
        
        if any_critical_failed:
            # Try to adapt the plan based on failures
            await self._adapt_plan_from_failures()
        
        return True  # Continue

    async def _adapt_plan_from_failures(self):
        """
        Adapt the execution plan based on worker failures.
        
        RE-ANALYZES CURRENT SCREEN and creates NEW subtasks based on reality.
        This is critical for handling dynamic pages where elements change.
        """
        failed_tasks = [st for st in self.subtasks if not st['completed'] and st['critical']]
        
        if not failed_tasks:
            return
        
        log_warn(f"   🔄 Adapting plan based on {len(failed_tasks)} failed task(s)")
        
        for failed in failed_tasks:
            log_debug(f"      Failed: {failed['description'][:60]}")
        
        try:
            # CRITICAL: Re-capture CURRENT screen state
            screenshot = await self.browser.screenshot()
            from PIL import Image
            import io
            screenshot_img = Image.open(io.BytesIO(screenshot))
            
            elements = self.parser.parse(screenshot_img)
            viewport_size = (self.browser.viewport_size['width'], self.browser.viewport_size['height'])
            elements_text = ElementFormatter.format_for_planner(elements, viewport_size=viewport_size)
            current_url = self.browser.url
            
            # Free screenshot
            del screenshot, screenshot_img
            
            log_info(f"   🔄 Re-analyzing current page: {len(elements)} elements visible")
            
            # Extract failed element IDs to explicitly exclude them
            failed_element_ids = set()
            for f in failed_tasks:
                desc = f['description']
                # Extract element IDs like [011], [012] from description
                import re
                ids_found = re.findall(r'\[(\d+)\]', desc)
                failed_element_ids.update(ids_found)
            
            # Build failures summary with explicit element ID exclusions
            failures_summary = "\n".join([
                f"- {f['description']}: {f['result'].error if f['result'] else 'Unknown error'}"
                for f in failed_tasks[:3]
            ])
            
            excluded_ids_text = ""
            if failed_element_ids:
                excluded_ids_text = f"\n**FORBIDDEN ELEMENT IDs:** {', '.join(sorted(failed_element_ids))} - These IDs DO NOT EXIST on current page!\n"
            
            # Check if goal might already be partially achieved
            goal_check_prompt = f"""QUICK ANALYSIS: Look at current page state for task: {self.task.description}

Current elements: {elements_text[:1000]}...

Has the GOAL already been achieved (even if method was different)? 
- If filling form: is data already in form fields?
- If navigating: are you already at destination?  
- If clicking: did the expected result already happen?

Reply ONLY: "GOAL_ACHIEVED" or "NEED_NEW_APPROACH"
"""
            
            check_response = await self.gemini.action_llm.ainvoke([{"role": "user", "content": goal_check_prompt}])
            check_content = check_response.content if hasattr(check_response, 'content') else str(check_response)
            
            if "GOAL_ACHIEVED" in check_content.upper():
                log_success(f"   ✅ Goal already achieved despite failures - marking subtasks complete")
                # Mark all as completed
                for st in self.subtasks:
                    st['completed'] = True
                return
            
            prompt = f"""You are ADAPTING an execution plan because previous sub-tasks FAILED.

ORIGINAL TASK GOAL:
{self.task.description}

WHAT FAILED:
{failures_summary}
{excluded_ids_text}
CURRENT PAGE STATE (RE-ANALYZED):
URL: {current_url}
Elements NOW visible: {len(elements)}
Current elements: {elements_text[:1500]}...

YOUR JOB:
Create NEW sub-tasks that will ACTUALLY achieve the goal using current page state.

CRITICAL RULES:
1. **NEVER use element IDs that failed** - they DO NOT EXIST!{f" (Forbidden: {', '.join(sorted(failed_element_ids))})" if failed_element_ids else ""}
2. **USE DESCRIPTIVE IDENTIFIERS** (e.g., "Click the 'Submit' button", "Type into 'Email' field"). Do NOT use IDs like [12].
3. **PRESERVE DATA INTEGRITY**: If the goal says type "john@example.com", you MUST use that EXACT text. Do NOT make up "test@example.com" or other placeholders.
4. **Focus on the ACTUAL GOAL**, not recovering from failures
5. If you can't find what you need, maybe scroll OR accept current state and move forward

SMART STRATEGIES:
- If you already typed data successfully, don't retry - move to next step
- If popup won't close, work around it (fill form anyway)
- If element moved/changed, find the NEW version on current page
- Use simple, direct actions that actually work

Return JSON array of NEW sub-tasks (or empty [] if goal already achieved):
[
  {{
    "description": "Concrete action description (use EXACT data from goal)",
    "expected_outcome": "Clear result",  
    "critical": false
  }}
]
"""
            
            # Get NEW plan from Gemini
            response = await self.gemini.action_llm.ainvoke([{"role": "user", "content": prompt}])
            
            # Parse response
            import json
            import re
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                new_subtasks_data = json.loads(json_match.group(0))
                
                # Mark old failed tasks as completed (to avoid re-trying them)
                for failed in failed_tasks:
                    failed['completed'] = True
                    failed['adapted'] = True
                
                # Add NEW subtasks
                next_index = len(self.subtasks)
                for idx, st in enumerate(new_subtasks_data):
                    self.subtasks.append({
                        'index': next_index + idx,
                        'description': st.get('description', ''),
                        'expected_outcome': st.get('expected_outcome', ''),
                        'critical': st.get('critical', True),
                        'completed': False,
                        'result': None,
                        'is_adaptive': True,  # Mark as created during adaptation
                    })
                
                log_success(f"   ✅ Created {len(new_subtasks_data)} NEW adaptive sub-tasks")
                for st in new_subtasks_data:
                    log_debug(f"      NEW: {st.get('description', '')[:60]}")
            else:
                log_warn(f"   ⚠️ Could not parse adaptive subtasks from response")
                
        except Exception as e:
            log_error(f"   ❌ Adaptive planning error: {e}")
            import traceback
            traceback.print_exc()

    async def _verify_task_completion(self):
        """
        Verify that the overall task was completed successfully.
        
        Uses the verifier to check final page state against task goal.
        """
        from web_agent.core.result import VerificationResult
        
        try:
            # Get current page state
            screenshot = await self.browser.screenshot()
            from PIL import Image
            import io
            screenshot_img = Image.open(io.BytesIO(screenshot))
            
            elements = self.parser.parse(screenshot_img)
            current_url = self.browser.url
            
            # Build action history from all workers
            all_actions = []
            for result in self.worker_results:
                all_actions.extend(result.action_history)
            
            # Verify with verifier
            verification = await self.verifier.verify_task_completion(
                task=self.task.description,
                elements=elements,
                url=current_url,
                storage_data={},
                action_history=all_actions,
                thread_id=f"{self.planner_id}_verification",
                screenshot=screenshot_img,
            )
            
            # Free resources
            del screenshot, screenshot_img
            
            log_info(f"   🔍 Verification: {'✅ Complete' if verification.completed else '❌ Incomplete'} ({verification.confidence:.0%})")
            
            return verification
            
        except Exception as e:
            log_error(f"   ❌ Verification error: {e}")
            return VerificationResult(
                completed=False,
                confidence=0.0,
                reasoning=f"Verification error: {str(e)}",
                evidence=[],
                issues=[str(e)],
            )

    def _build_final_result(self, verification, start_time: float) -> TaskResult:
        """
        Build the final consolidated result from all worker results.
        
        Args:
            verification: VerificationResult object
            start_time: Task start time
        """
        duration = time.time() - start_time
        
        # Aggregate all actions from workers
        all_actions = []
        for result in self.worker_results:
            all_actions.extend(result.action_history)
        
        # Determine overall success using proper attribute access
        success = verification.completed and verification.confidence >= 0.5
        
        # Collect errors
        errors = []
        for result in self.worker_results:
            if not result.success and result.error:
                errors.append(result.error)
        
        return TaskResult(
            task_id=self.task.id,
            success=success,
            duration=duration,
            action_history=all_actions,
            verification=verification,
            error="; ".join(errors) if errors else None,
            extracted_data={
                'subtasks_completed': sum(1 for st in self.subtasks if st['completed']),
                'subtasks_total': len(self.subtasks),
                'workers_spawned': len(self.worker_results),
            },
        )

    def _create_failure_result(self, error: str, start_time: float) -> TaskResult:
        """Create a failure result"""
        return TaskResult(
            task_id=self.task.id,
            success=False,
            error=error,
            duration=time.time() - start_time,
            action_history=[],
        )

    async def cleanup(self):
        """Cleanup planner resources"""
        log_debug(f"   🧹 Planner {self.planner_id} cleaned up")
