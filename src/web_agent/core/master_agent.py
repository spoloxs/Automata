"""
Master Agent - Top-level orchestrator for multi-agent web automation.
Decomposes goals, spawns workers, aggregates results.
"""

import time
import uuid
import threading
from typing import Any, Dict, Optional

from web_agent.config.settings import GEMINI_API_KEY
from web_agent.core.result import ExecutionResult, VerificationResult
from web_agent.core.task import TaskDAG
from web_agent.core.worker_agent import WorkerAgent
from web_agent.execution.browser_controller import BrowserController
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.perception.screen_parser import ScreenParser
from web_agent.planning.dag_converter import PlanToDAGConverter
from web_agent.planning.planner import Planner
from web_agent.scheduling.scheduler import WorkerScheduler
from web_agent.storage.result_store import ResultStore
from web_agent.storage.redis_conversation_store import RedisConversationStore, ConversationManager
from web_agent.core.supervisor_agent import AISupervisorAgent
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn
from web_agent.util.memory_monitor import get_memory_monitor
from web_agent.verification.task_verifier import TaskVerifier


class MasterAgent:
    """
    Master orchestrator that decomposes goals and manages worker agents.
    
    SINGLETON PATTERN: Only ONE MasterAgent instance should exist at a time.
    This ensures all worker agents share the same ScreenParser, GeminiAgent,
    and other heavy resources.

    Architecture:
    - Never executes actions directly
    - Only orchestrates: plan → spawn workers → aggregate results
    - Maintains minimal context (no action history pollution)
    """
    
    _instance: Optional['MasterAgent'] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern: Only allow one MasterAgent instance at a time."""
        with cls._lock:
            if cls._instance is not None:
                log_warn(f"⚠️  MasterAgent singleton already exists (id: {cls._instance.master_id})")
                log_warn(f"⚠️  Returning existing instance. Call cleanup() before creating a new one.")
                return cls._instance
            
            instance = super().__new__(cls)
            cls._instance = instance
            return instance

    @classmethod
    def reset_singleton(cls):
        """Reset singleton instance (for testing purposes only)."""
        log_warn("🔄 Resetting MasterAgent singleton (testing mode)")
        with cls._lock:
            cls._instance = None

    def __init__(
        self,
        api_key: Optional[str] = GEMINI_API_KEY,
        browser_page=None,
        max_parallel_workers: int = 4,
        box_threshold: Optional[float] = 0.89,  # Optimized default based on testing
        iou_threshold: Optional[float] = 0.5,   # Optimized default based on testing
    ):
        # Skip re-initialization if already initialized
        if hasattr(self, '_initialized') and self._initialized:
            log_debug("MasterAgent already initialized, skipping re-init")
            return
            
        log_debug("MasterAgent.__init__ called")
        self.master_id = f"master_{uuid.uuid4().hex[:8]}"
        self.api_key = api_key
        self.max_workers = max_parallel_workers
        self.browser = BrowserController(page=browser_page)
        self.parser = ScreenParser(
            box_threshold=box_threshold,
            iou_threshold=iou_threshold
        )
        # Conversation store and manager to preserve planner/supervisor decision context
        # Use Redis for memory-efficient storage
        self.conversation_store = RedisConversationStore()
        self.conversation_manager = ConversationManager(self.conversation_store)
        self.gemini = GeminiAgent(
            api_key=str(api_key) if api_key is not None else ""
        )
        # Attach conversation manager to gemini so decision helpers can access conversation context
        try:
            # Use setattr to avoid static attribute checks on GeminiAgent
            setattr(self.gemini, "conversation_manager", self.conversation_manager)
        except Exception:
            pass
        self.verifier = TaskVerifier(gemini_agent=self.gemini)
        self.planner = Planner(
            gemini_agent=self.gemini,
            browser_controller=self.browser,
            screen_parser=self.parser,
        )
        # Attach conversation manager so planner can record and use conversation context
        # (allows planner to append plan observations / snapshots into master conversation)
        try:
            # Use setattr to avoid creating a hard dependency on planner attributes
            setattr(self.planner, "conversation_manager", self.conversation_manager)
        except Exception:
            pass
        self.scheduler = WorkerScheduler(max_parallel_workers=max_parallel_workers)
        self.result_store = ResultStore()
        self.current_goal: Optional[str] = None
        self.current_dag: Optional[TaskDAG] = None
        self._initialized = True  # Mark as initialized
        log_info(f"🎯 MasterAgent {self.master_id} initialized (SINGLETON)")
        log_info(f"   Max workers: {max_parallel_workers}")

    async def initialize(self):
        log_debug("MasterAgent.initialize called")
        await self.browser.initialize()
        log_success("   ✅ Browser initialized")
        
        # Initialize Redis conversation store
        await self.conversation_store.initialize()
        log_success("   ✅ Conversation store initialized")

    async def execute_goal(
        self, goal: str, starting_url: Optional[str] = None, timeout: int = 300
    ) -> ExecutionResult:
        log_debug("MasterAgent.execute_goal called")
        log_info("=" * 70)
        log_info("🎯 MASTER AGENT: Executing Goal")
        log_info("=" * 70)
        log_info(f"Goal: {goal}")
        if starting_url:
            log_info(f"Starting URL: {starting_url}")
        log_info("=" * 70)
        start_time = time.time()
        self.current_goal = goal
        
        # Set baseline RAM and log initial usage
        mem_monitor = get_memory_monitor()
        mem_monitor.set_baseline()

        # We'll instantiate the supervisor once we have a stable supervisor thread id
        supervisor = None

        try:
            if starting_url:
                log_info(f"🌐 Navigating to {starting_url}")
                await self.browser.navigate(starting_url)

            log_info("\n📋 STEP 1: Planning")
            # Create conversation threads for planner and supervisor so we can preserve history
            planner_thread = f"planner_{self.master_id}"
            supervisor_thread = f"supervisor_{self.master_id}"
            # expose supervisor thread on master for worker parenting / later instrumentation
            self.last_supervisor_thread = supervisor_thread

            # Initialize AI Supervisor now that we have a supervisor thread id and the conversation manager.
            try:
                supervisor = AISupervisorAgent(
                    gemini_agent=self.gemini,
                    planner=self.planner,
                    scheduler=self.scheduler,
                    max_retries=2,
                    conversation_manager=self.conversation_manager,
                    supervisor_thread_id=supervisor_thread,
                    screen_parser=self.parser,  # CRITICAL: Share master's parser!
                )
            except Exception as e:
                log_warn(f"   ⚠️ Could not instantiate AISupervisorAgent: {e}")
                supervisor = None

            # Record that planning started
            try:
                await self.conversation_store.append_event(
                    planner_thread,
                    role="system",
                    content=f"Starting plan for goal: {goal}",
                    metadata={"starting_url": starting_url},
                )
            except Exception:
                # best-effort logging to conversation store should not break execution
                pass

            # Generate the plan (planner accepts optional thread_id to record context)
            plan = await self.planner.create_plan(
                goal=goal,
                starting_url=starting_url,
                explore=True,
                thread_id=planner_thread,
            )
            log_debug(f"Plan: {plan}")

            # Append a brief plan summary to the supervisor thread for visibility and later decisions
            try:
                summary_meta = {
                    "steps": len(getattr(plan, "steps", [])),
                    "complexity": getattr(plan, "complexity", None),
                    "estimated_time": getattr(plan, "estimated_total_time", None),
                }
                await self.conversation_store.append_event(
                    supervisor_thread,
                    role="planner",
                    content=f"Plan created with {summary_meta['steps']} steps",
                    metadata=summary_meta,
                )
            except Exception:
                pass

            log_info("\n📊 STEP 2: Converting to DAG")
            dag = PlanToDAGConverter.convert(plan)
            self.current_dag = dag

            # Initialize and log initial ready tasks immediately after DAG conversion.
            try:
                initial_ready = dag.get_ready_tasks()
                if initial_ready:
                    ready_summaries = ", ".join(
                        [
                            f"{t.id[:8]}:{t.description[:40].strip()}"
                            for t in initial_ready
                        ]
                    )
                    log_info(
                        f"   📋 {len(initial_ready)} initial ready task(s): {ready_summaries}"
                    )
                else:
                    log_warn(
                        "   ⚠️ No initial ready tasks detected after DAG conversion; possible dependency issue."
                    )
            except Exception as e:
                log_error(f"   ❌ Error while initializing ready tasks: {e}")

            log_debug(f"DAG Visualization:\n{dag.visualize()}")

            log_info("\n🚀 STEP 3: AI Supervised Execution")
            log_info("   🧠 AI Supervisor activated")

            # Record supervised execution start in the conversation thread so the decision engine
            # and planner can later inspect what happened (progress, observations).
            try:
                await self.conversation_store.append_event(
                    supervisor_thread,
                    role="system",
                    content="Starting supervised execution",
                    metadata={
                        "dag_tasks": len(dag.tasks) if hasattr(dag, "tasks") else None
                    },
                )
            except Exception:
                pass

            # Run supervised execution (if supervisor available)
            if supervisor is not None:
                supervision_result = await supervisor.supervise_execution(
                    goal=goal,
                    dag=dag,
                    browser_page=self.browser.get_page(),
                    verifier=self.verifier,
                )
            else:
                # Best-effort fallback supervision result when AI supervisor is unavailable.
                log_warn(
                    "   ⚠️ AI Supervisor unavailable. Falling back to a minimal supervision result."
                )

                class _FallbackSupervisionResult:
                    def __init__(self, dag_obj):
                        self.success = False
                        self.completed_tasks = (
                            len(dag_obj.get_completed_tasks())
                            if hasattr(dag_obj, "get_completed_tasks")
                            else 0
                        )
                        self.total_tasks = (
                            len(dag_obj.tasks) if hasattr(dag_obj, "tasks") else 0
                        )
                        self.failed_tasks = (
                            len(dag_obj.get_failed_tasks())
                            if hasattr(dag_obj, "get_failed_tasks")
                            else 0
                        )
                        self.decisions_made = []
                        self.execution_time = 0.0
                        self.stop_reason = "no_supervisor"

                supervision_result = _FallbackSupervisionResult(dag)

            log_info("\n📦 STEP 4: Aggregating Results")
            # Convert supervision result to ExecutionResult
            execution_result = self._convert_supervision_result(
                supervision_result, start_time
            )

            log_info("\n🔍 STEP 5: Final Verification")
            final_verification = await self._verify_final_goal(goal)
            execution_result.verification = final_verification
            
            # Trust final verification if it's confident, even if task accounting was messy
            is_verified = bool(getattr(final_verification, "completed", False))
            verification_conf = float(getattr(final_verification, "confidence", 0.0))
            
            if is_verified and verification_conf > 0.8:
                # Strong verification overrides task tracking
                execution_result.success = True
                log_success(f"   ✅ Success confirmed by strong verification ({verification_conf:.1%}) despite task stats")
            else:
                # Fallback to combination of verification and task progress
                execution_result.success = (
                    is_verified
                    and execution_result.confidence >= 0.5
                )

            # Ask the decision engine whether to continue. The decision engine (AI)
            # controls whether another supervised execution pass should run.
            try:
                execution_state_for_decision = {
                    "completed": execution_result.completed_tasks,
                    "total": execution_result.total_tasks,
                    "failed": execution_result.failed_tasks,
                    "elapsed_time": time.time() - start_time,
                    "supervisor_thread": supervisor_thread,
                    "dag_complete": dag.is_complete() if dag is not None else False,
                    "supervision": {
                        "stop_reason": getattr(supervision_result, "stop_reason", None),
                        "decisions_made": len(
                            getattr(supervision_result, "decisions_made", []) or []
                        ),
                        "execution_time": getattr(
                            supervision_result, "execution_time", None
                        ),
                        "completed_tasks": getattr(
                            supervision_result, "completed_tasks", None
                        ),
                        "failed_tasks": getattr(
                            supervision_result, "failed_tasks", None
                        ),
                    },
                }

                # Initialize progress tracking (completed + failed = total work done)
                prev_completed = execution_result.completed_tasks + execution_result.failed_tasks
                while True:
                    # Best-effort: fetch recent conversation context for the supervisor thread
                    conversation_context = None
                    try:
                        thread_id = execution_state_for_decision.get(
                            "supervisor_thread"
                        )
                        if thread_id and getattr(self, "conversation_manager", None):
                            conversation_context = (
                                await self.conversation_manager.get_context(
                                    thread_id, recent=20, include_summary=True
                                )
                            )
                            # If the DAG just completed, trigger an automatic summary pass so the
                            # decision LLM gets a concise representation of the run.
                            if execution_state_for_decision.get(
                                "dag_complete"
                            ) and hasattr(self.gemini, "summarize_history"):
                                try:
                                    new_summary = await self.gemini.summarize_history(
                                        thread_id, conversation_context
                                    )
                                    try:
                                        await self.conversation_manager.set_summary(
                                            thread_id, new_summary
                                        )
                                        conversation_context = (
                                            await self.conversation_manager.get_context(
                                                thread_id,
                                                recent=20,
                                                include_summary=True,
                                            )
                                        )
                                    except Exception:
                                        pass
                                except Exception:
                                    pass

                            # Append a concise supervision summary event so the decision engine sees what happened.
                            try:
                                summary_payload = {
                                    "completed_tasks": getattr(
                                        execution_result, "completed_tasks", None
                                    ),
                                    "total_tasks": getattr(
                                        execution_result, "total_tasks", None
                                    ),
                                    "failed_tasks": getattr(
                                        execution_result, "failed_tasks", None
                                    ),
                                    "success": bool(
                                        getattr(execution_result, "success", False)
                                    ),
                                    "verification_completed": bool(
                                        getattr(final_verification, "completed", False)
                                    )
                                    if final_verification is not None
                                    else False,
                                    "verification_confidence": float(
                                        getattr(final_verification, "confidence", 0.0)
                                    )
                                    if final_verification is not None
                                    else 0.0,
                                    "supervision_stop_reason": getattr(
                                        supervision_result, "stop_reason", None
                                    ),
                                }
                                await self.conversation_store.append_event(
                                    thread_id,
                                    role="supervisor",
                                    content=f"Supervision summary: completed {summary_payload['completed_tasks']}/{summary_payload['total_tasks']}, failed {summary_payload['failed_tasks']}, success={summary_payload['success']}, stop_reason={summary_payload.get('supervision_stop_reason')}",
                                    metadata=summary_payload,
                                )
                                try:
                                    anchors_text = (
                                        "Decision anchors (examples):\n"
                                        "1) If supervision shows 0/3 progress and stop_reason=no_ready_tasks -> continue:false\n"
                                        "2) If supervision shows progress increased (e.g., 2/3) but verification confidence is low -> continue:true\n"
                                        "3) If DAG is complete and verification.completed is False -> continue:true (replan or another supervised pass)\n"
                                    )
                                    await self.conversation_store.append_event(
                                        thread_id,
                                        role="system",
                                        content=anchors_text,
                                        metadata={"type": "decision_anchors"},
                                    )
                                except Exception:
                                    pass

                                conversation_context = (
                                    await self.conversation_manager.get_context(
                                        thread_id, recent=20, include_summary=True
                                    )
                                )
                            except Exception:
                                pass
                    except Exception:
                        conversation_context = None

                    # Decide whether to continue: prefer supervisor if available
                    try:
                        if supervisor is not None:
                            # Build a robust verification payload for the decision call
                            verification_payload = None
                            try:
                                if final_verification is not None:
                                    if isinstance(final_verification, dict):
                                        verification_payload = final_verification
                                    elif hasattr(final_verification, "to_dict"):
                                        try:
                                            verification_payload = (
                                                final_verification.to_dict()
                                            )
                                        except Exception:
                                            verification_payload = {
                                                "completed": getattr(
                                                    final_verification,
                                                    "completed",
                                                    False,
                                                ),
                                                "confidence": getattr(
                                                    final_verification,
                                                    "confidence",
                                                    0.0,
                                                ),
                                                "reasoning": getattr(
                                                    final_verification, "reasoning", ""
                                                ),
                                            }
                                    else:
                                        verification_payload = {
                                            "completed": getattr(
                                                final_verification, "completed", False
                                            ),
                                            "confidence": getattr(
                                                final_verification, "confidence", 0.0
                                            ),
                                            "reasoning": getattr(
                                                final_verification, "reasoning", ""
                                            ),
                                        }
                            except Exception:
                                verification_payload = None

                            should_continue = (
                                await supervisor.should_continue(
                                    execution_state_for_decision,
                                    verification_payload,
                                    conversation_context,
                                )
                            )
                        else:
                            # Fallback heuristic: continue only if verifier confidence is low and there are remaining tasks.
                            remaining = execution_state_for_decision.get(
                                "total", 0
                            ) - execution_state_for_decision.get("completed", 0)
                            conf = 0.0
                            try:
                                if final_verification is not None:
                                    # final_verification is a VerificationResult dataclass - use attribute access
                                    conf = float(getattr(final_verification, "confidence", 0.0))
                                else:
                                    conf = 0.0
                            except Exception:
                                conf = 0.0
                            should_continue = bool(conf < 0.9 and remaining > 0)
                    except Exception as e:
                        log_warn(f"Decision engine continuation check failed: {e}")
                        should_continue = False

                    if not should_continue:
                        log_info(
                            "   ⛔ Decision engine advised to stop continuing supervised execution."
                        )
                        break

                    log_info(
                        "   🔁 Decision engine requested continuation - preparing another supervised pass"
                    )

                    # If the current DAG is already complete, allow the planner to create a new DAG
                    if dag.is_complete():
                        log_info(
                            "   ℹ️ Current DAG is complete; generating a new plan per decision engine request."
                        )
                        try:
                            # Clean up old plan and DAG before creating new ones
                            old_dag = dag
                            del old_dag
                            import gc
                            gc.collect()
                            
                            # Get current URL to avoid navigating back to original starting_url
                            current_url = await self.browser.get_url()
                            log_info(f"   📍 Creating new plan from current URL: {current_url}")
                            
                            plan = await self.planner.create_plan(
                                goal=goal, starting_url=current_url, explore=True
                            )
                            new_dag = PlanToDAGConverter.convert(plan)
                            
                            # Clean up plan object after DAG conversion
                            del plan
                            gc.collect()
                            
                            self.current_dag = new_dag
                            dag = new_dag

                            try:
                                initial_ready = dag.get_ready_tasks()
                                if initial_ready:
                                    ready_summaries = ", ".join(
                                        [
                                            f"{t.id[:8]}:{t.description[:40].strip()}"
                                            for t in initial_ready
                                        ]
                                    )
                                    log_info(
                                        f"   📋 {len(initial_ready)} new initial ready task(s): {ready_summaries}"
                                    )
                                else:
                                    log_warn(
                                        "   ⚠️ No initial ready tasks detected after new DAG conversion; possible dependency issue."
                                    )
                            except Exception as e:
                                log_error(
                                    f"   ❌ Error while initializing ready tasks for new DAG: {e}"
                                )

                            log_debug(f"New DAG Visualization:\n{dag.visualize()}")

                            # Reset progress tracking for new DAG (completed + failed)
                            prev_completed = execution_result.completed_tasks + execution_result.failed_tasks
                        except Exception as e:
                            log_error(f"   ❌ Failed to create a new plan/DAG: {e}")
                    else:
                        log_debug(
                            "   ℹ️ Reusing existing DAG for another supervised execution pass"
                        )

                    # Run another supervised execution pass (guarded)
                    if supervisor is not None:
                        more_result = await supervisor.supervise_execution(
                            goal=goal,
                            dag=dag,
                            browser_page=self.browser.get_page(),
                            verifier=self.verifier,
                        )
                    else:
                        log_warn(
                            "   ⚠️ AI Supervisor unavailable for continuation pass; skipping additional supervised pass."
                        )
                        more_result = supervision_result

                    try:
                        supervision_result = more_result
                    except Exception:
                        pass

                    execution_result = self._convert_supervision_result(
                        more_result, start_time
                    )

                    final_verification = await self._verify_final_goal(goal)
                    execution_result.verification = final_verification
                    execution_result.success = (
                        bool(getattr(final_verification, "completed", False))
                        and execution_result.confidence >= 0.5
                    )

                    # Update state for next decision call
                    execution_state_for_decision.update(
                        {
                            "completed": execution_result.completed_tasks,
                            "total": execution_result.total_tasks,
                            "failed": execution_result.failed_tasks,
                            "elapsed_time": time.time() - start_time,
                        }
                    )

                    # Let AI supervisor decide when to stop - no manual progress checks
                    prev_completed = execution_result.completed_tasks + execution_result.failed_tasks

                    if execution_result.success or bool(
                        getattr(final_verification, "completed", False)
                    ):
                        log_info(
                            "   ✅ Goal appears complete after decision-engine-driven continuation"
                        )
                        break
            except Exception as e:
                log_warn(f"Decision engine continuation loop failed: {e}")

            log_debug(f"{execution_result}")
            return execution_result

        except Exception as e:
            log_error(f"\n❌ Master agent error: {e}")
            import traceback

            traceback.print_exc()
            return ExecutionResult(
                goal=goal,
                success=False,
                confidence=0.0,
                total_tasks=self.current_dag.get_task_count()
                if self.current_dag
                else 0,
                completed_tasks=0,
                failed_tasks=0,
                start_time=start_time,
                end_time=time.time(),
                total_duration=time.time() - start_time,
                errors=[str(e)],
            )

    def _create_worker(self, task) -> WorkerAgent:
        worker_id = f"worker_{task.id[:8]}"
        log_info(f"worker_{task.id[:8]} created")
        return WorkerAgent(
            worker_id=worker_id,
            task=task,
            browser_page=self.browser.get_page(),
            gemini_agent=self.gemini,
            verifier=self.verifier,
            parent_context=self._get_minimal_context(),
            screen_parser=self.parser,  # CRITICAL: Share master's parser!
        )

    def _get_minimal_context(self) -> Dict[str, Any]:
        """Return a minimal context for workers; include conversation manager and supervisor thread when available."""
        ctx: Dict[str, Any] = {"goal": self.current_goal, "master_id": self.master_id}
        try:
            if hasattr(self, "conversation_manager"):
                ctx["conversation_manager"] = self.conversation_manager
            if hasattr(self, "last_supervisor_thread") and self.last_supervisor_thread:
                ctx["supervisor_thread"] = self.last_supervisor_thread
                ctx["supervisor_thread_key"] = "supervisor_thread"
        except Exception:
            pass
        return ctx

    async def _aggregate_results(
        self, goal: str, scheduler_results: Dict, start_time: float
    ) -> ExecutionResult:
        end_time = time.time()
        total_duration = end_time - start_time
        task_results = list(scheduler_results.get("task_results", {}).values())
        result = ExecutionResult(
            goal=goal,
            success=scheduler_results.get("failed", 1) == 0,
            confidence=0.0,
            total_tasks=scheduler_results.get("total", 0),
            completed_tasks=scheduler_results.get("completed", 0),
            failed_tasks=scheduler_results.get("failed", 0),
            start_time=start_time,
            end_time=end_time,
            total_duration=total_duration,
            worker_count=self.max_workers,
        )
        for task_result in task_results:
            result.add_task_result(task_result)
        if result.total_tasks > 0:
            result.confidence = result.completed_tasks / result.total_tasks
        log_info(f"   📊 Aggregated {len(task_results)} task results")
        log_success(f"   ✅ Success rate: {result.confidence:.1%}")
        return result

    async def _verify_final_goal(self, goal: str) -> VerificationResult:
        screenshot = await self.browser.capture_screenshot()
        elements = self.parser.parse(screenshot)
        url = await self.browser.get_url()
        all_data = {}
        for result in self.result_store.get_all_results():
            all_data.update(result.extracted_data)
        log_info(f"   🔍 Verifying goal: {goal}")
        verification = await self.verifier.verify_task_completion(
            task=goal,
            elements=elements,
            url=url,
            storage_data=all_data,
            action_history=[],
            thread_id=f"{self.master_id}_verification",
            screenshot=screenshot,
        )
        
        # Free screenshot and elements immediately after verification
        del screenshot, elements
        import gc
        gc.collect()
        
        if verification.completed:
            log_success(
                f"   ✅ Goal verified complete ({verification.confidence:.1%} confident)"
            )
        else:
            log_error(
                f"   ❌ Goal not complete ({verification.confidence:.1%} confident)"
            )
            log_warn(f"   📝 Reason: {verification.reasoning}")
        return verification

    def _convert_supervision_result(self, supervision_result, start_time):
        """Convert supervisor result to ExecutionResult"""
        end_time = time.time()
        # Defensive: avoid division by zero if supervisor_result.total_tasks is zero
        total = getattr(supervision_result, "total_tasks", 0) or 1
        confidence = getattr(supervision_result, "completed_tasks", 0) / total
        # Ensure goal is always a string (coalesce None to empty string)
        goal_str = self.current_goal if self.current_goal is not None else ""
        return ExecutionResult(
            goal=goal_str,
            success=bool(getattr(supervision_result, "success", False)),
            confidence=confidence,
            total_tasks=getattr(supervision_result, "total_tasks", 0),
            completed_tasks=getattr(supervision_result, "completed_tasks", 0),
            failed_tasks=getattr(supervision_result, "failed_tasks", 0),
            start_time=start_time,
            end_time=end_time,
            total_duration=end_time - start_time,
        )

    async def cleanup(self):
        """Comprehensive cleanup - clears all memory and persistent storage"""
        log_info(f"\n🧹 Cleaning up master agent {self.master_id}")
        
        # Clear Gemini chat histories (in-memory)
        active_sessions = self.gemini.get_active_sessions()
        if active_sessions > 0:
            log_info(f"   🧠 Clearing {active_sessions} Gemini sessions")
            # Clear all chat histories from memory
            if hasattr(self.gemini, 'chat_histories'):
                self.gemini.chat_histories.clear()
                log_success(f"   ✅ Cleared {active_sessions} Gemini chat histories")
        
        # Clear conversation store (Redis or in-memory)
        try:
            log_info("   🗄️  Clearing conversation store")
            await self.conversation_store.cleanup()
            log_success("   ✅ Conversation store cleaned up")
        except Exception as e:
            log_warn(f"   ⚠️ Conversation store cleanup failed: {e}")
        
        # Cleanup browser resources
        try:
            await self.browser.cleanup()
            log_success("   ✅ Browser cleanup complete")
        except Exception as e:
            log_warn(f"   ⚠️ Browser cleanup failed: {e}")
        
        # Clear result store
        try:
            self.result_store.clear()
            log_success("   ✅ Result store cleared")
        except Exception as e:
            log_warn(f"   ⚠️ Result store clear failed: {e}")
        
        # CRITICAL: Aggressively delete ALL data structures to free RAM
        try:
            # Delete large objects
            if hasattr(self, 'current_dag'):
                del self.current_dag
            if hasattr(self, 'planner'):
                del self.planner
            if hasattr(self, 'scheduler'):
                del self.scheduler
            
            # Delete all instance variables to break circular references
            self.current_goal = None
            self.result_store = None
            self.verifier = None
            self.parser = None
            self.browser = None
            self.gemini = None
            self.conversation_manager = None
            self.conversation_store = None
            
            # CRITICAL: Reset OmniParser singleton to free ML models
            try:
                from web_agent.perception.omniparser_wrapper import reset_omniparser
                reset_omniparser()
                log_success("   ✅ OmniParser singleton reset")
            except Exception as e:
                log_warn(f"   ⚠️ OmniParser reset failed: {e}")
            
            # Clear CUDA cache to free VRAM
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    log_success("   ✅ CUDA cache cleared")
            except Exception:
                pass
                
            # Force garbage collection
            import gc
            gc.collect()
            gc.collect()  # Call twice for cyclic references
            log_success("   ✅ All objects deleted and GC forced")
        except Exception as e:
            log_warn(f"   ⚠️ Object deletion failed: {e}")
        
        # Reset singleton instance to allow new MasterAgent creation
        MasterAgent._instance = None
        MasterAgent._instance_lock = False
        self._initialized = False
        
        log_success(f"   ✅ Master agent {self.master_id} cleanup complete")
        log_info(f"   🔓 Singleton released - new MasterAgent can be created")
