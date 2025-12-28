# automata/web-agent/src/web_agent/core/supervisor_agent.py
"""
AI Supervisor Agent - Enhanced failure handling and conversation instrumentation.

This supervisor version makes failure handling fully AI-driven: every task failure
is fed to the DecisionEngine (no threshold gating), and the decisions + failure
details are appended to the supervisor conversation thread (if a ConversationManager
is available via the Gemini agent).

Design goals:
- Always consult AI on failures (more data-driven)
- Record failures, decisions and verification outputs to conversation threads
  so higher-level decision loops (MasterAgent / DecisionEngine) see full context
- Be robust: conversation instrumentation is best-effort and never raises
"""

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from web_agent.core.result import TaskResult
from web_agent.core.task import Task, TaskStatus
from web_agent.core.worker_agent import WorkerAgent
from web_agent.scheduling.scheduler import WorkerScheduler
from web_agent.supervision.decision_engine import (
    SupervisorAction,
    SupervisorDecision,
)
from web_agent.supervision.health_monitor import HealthMonitor
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn
from web_agent.storage.worker_memory import WorkerMemory, MemoryType
from web_agent.storage.accomplishment_store import AccomplishmentStore


@dataclass
class SupervisionResult:
    """Final supervision result"""

    success: bool
    completed_tasks: int
    failed_tasks: int
    total_tasks: int
    decisions_made: List[SupervisorDecision]
    execution_time: float
    final_state: Dict
    stop_reason: Optional[str] = None
    final_state_extra: Dict[str, Any] = field(default_factory=dict)


# Pydantic models for decision-making (formerly in DecisionEngine)
class DecisionRequest(BaseModel):
    """Input to decision engine"""

    goal: str
    failed_task: Dict
    execution_state: Dict
    downstream_tasks: List[Dict]
    failure_pattern: str
    current_url: str


class DecisionResponse(BaseModel):
    """Expected response from LLM"""

    action: SupervisorAction = Field(..., description="Chosen action")
    reasoning: str = Field(..., description="Detailed reasoning")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    task_id: Optional[str] = Field(None, description="Task ID to retry/skip")
    alternative: Optional[str] = Field(None, description="Backup plan")
    simplify_plan: Optional[bool] = Field(False, description="Simplify remaining tasks")
    suggested_continuation_attempts: Optional[int] = Field(
        None, description="Suggested number of additional supervised execution attempts"
    )
    new_tasks: Optional[List[Dict]] = Field(
        None, description="List of new tasks to add to current DAG"
    )


class AISupervisorAgent:
    """
    AI-Powered Supervisor with explicit state management.

    Enhancements in this file:
    - Fully AI-driven failure handling: every task failure is passed to the decision engine.
    - Conversation reporting: failures, decisions, and verification outputs are appended
      to the supervisor thread via ConversationManager (if available on gemini_agent).
    """

    def __init__(
        self,
        gemini_agent,
        planner,
        scheduler,
        max_retries: int = 2,
        supervision_interval: float = 2.0,
        conversation_manager: Optional[Any] = None,
        supervisor_thread_id: Optional[str] = None,
        screen_parser=None,  # CRITICAL: Shared ScreenParser from master
    ):
        log_debug("AISupervisorAgent.__init__ called")
        self.gemini_agent = gemini_agent
        self.planner = planner
        self.scheduler = scheduler
        self.max_retries = max_retries
        self.screen_parser = screen_parser  # Store shared parser

        # Health monitor (decision engine methods now integrated into supervisor)
        self.health_monitor = HealthMonitor()
        
        # Supervisor thread ID for structured LLM calls
        self.supervisor_thread_id_for_decisions = "supervisor_decision_engine"

        # Configuration
        self.supervision_interval = supervision_interval

        # Replan protection
        self.executed_task_count = 0
        self.last_replan_time = None
        self.consecutive_skips = 0  # Track consecutive skip decisions to prevent infinite loops
        self.MAX_CONSECUTIVE_SKIPS = 3  # Force replan after 3 consecutive skips
        # NO MIN_EXECUTIONS restriction - allow replanning anytime it makes sense
        self.REPLAN_COOLDOWN_SECONDS = 30  # Reduced from 60s - less restrictive
        self.consecutive_failures = 0

        # Execution state
        self.execution_id = str(uuid.uuid4())
        self.execution_start = None
        self.execution_history = []
        self.decisions_made: List[SupervisorDecision] = []
        # Supervisor-level memory to persist generic facts/results across tasks
        self.memory = WorkerMemory(namespace=f"supervisor_{self.execution_id[:8]}")
        # Use provided supervisor_thread_id if given, otherwise default to generated id
        self.supervisor_thread_id = (
            supervisor_thread_id
            if supervisor_thread_id is not None
            else f"supervisor_{self.execution_id}"
        )

        # Conversation instrumentation (best-effort)
        # Prefer explicit conversation_manager param; fall back to gemini_agent attribute
        self.conversation_manager = conversation_manager or getattr(
            gemini_agent, "conversation_manager", None
        )
        
        # Create accomplishment store for this supervision session
        # All workers will share this store to avoid redundant work
        self.accomplishment_store = AccomplishmentStore(
            session_id=self.execution_id,
            gemini_agent=gemini_agent
        )
        
        # URL change tracking for automatic replanning
        self.last_known_url = None
        self.url_changed_count = 0

        log_info(
            f"🧠 AI Supervisor {self.execution_id[:8]} initialized (thread: {self.supervisor_thread_id})"
        )

    # -------------------------
    # Public supervision API
    # -------------------------
    async def supervise_execution(
        self,
        goal: str,
        dag,
        browser_page,
        verifier,
    ) -> SupervisionResult:
        log_debug("AISupervisorAgent.supervise_execution called")
        """Main supervision loop with clean state management."""

        log_info(
            f"\n👁️  AI Supervisor supervising {len(dag.tasks)} tasks for goal: {goal[:100]}..."
        )

        self.execution_start = time.time()
        self.health_monitor.start_monitoring()

        # Attempt to append a system event to the conversation so other components see the start.
        await self._append_system_event(
            f"AI Supervisor starting execution for goal: {goal[:200]}",
            metadata={"dag_tasks": len(dag.tasks) if hasattr(dag, "tasks") else None},
        )

        try:
            result = await self._main_supervision_loop(
                goal, dag, browser_page, verifier
            )
            return result

        finally:
            await self._cleanup()

    # -------------------------
    # Core supervision loop
    # -------------------------
    async def _main_supervision_loop(self, goal: str, dag, browser_page, verifier):
        log_debug("AISupervisorAgent._main_supervision_loop called")
        """
        Core supervision loop with explicit state management.
        Flow: Query → Decide → Execute → Update State
        """

        iteration = 0
        # Run until DAG reaches a terminal state; supervisor has no artificial max-iteration timeout
        while not dag.is_complete():
            iteration += 1

            # Health monitoring with AI supervision
            health = self.health_monitor.get_health(dag)

            if iteration % 5 == 0:
                log_info(
                    f"📊 Health: {health.status} | Progress: {self.executed_task_count}/{len(dag.tasks)}"
                )
            
            # AI-SUPERVISED HEALTH INTERVENTION
            # When health is CRITICAL or DEGRADED, consult AI for recovery action
            if health.status in ["CRITICAL", "DEGRADED"] and self._can_replan():
                log_warn(f"   🏥 Health is {health.status} - requesting AI intervention...")
                health_decision = await self._ai_health_intervention(goal, dag, health)
                if health_decision:
                    log_info(f"   🧠 AI Health Decision: {health_decision.action} ({health_decision.confidence:.0%})")
                    await self._append_decision_to_thread(
                        health_decision, context={"health_status": health.status, "trigger": "health_intervention"}
                    )
                    await self._execute_decision(health_decision, dag, browser_page, verifier)

            # STEP 1: QUERY - Get ready tasks (no side effects)
            ready_tasks = dag.get_ready_tasks()

            if not ready_tasks:
                # No ready tasks - check for deadlock
                if self._can_replan():
                    deadlock_decision = await self._handle_deadlock(goal, dag)
                    await self._execute_decision(
                        deadlock_decision, dag, browser_page, verifier
                    )
                else:
                    # Silently wait - don't spam logs every 2 seconds
                    pass

                await asyncio.sleep(self.supervision_interval)
                continue

            # STEP 2: Execute ready tasks (bounded by scheduler)
            for task in ready_tasks[: self.scheduler.max_workers]:
                # STEP 3: COMMAND - Mark as running before execution
                try:
                    dag.mark_task_running(
                        task.id, f"supervisor_{self.execution_id[:8]}"
                    )
                except ValueError as e:
                    log_warn(f"   ⚠️  Cannot start task {task.id[:8]}: {e}")
                    continue

                # STEP 4: EXECUTE (with automatic retry)
                result = await self._execute_task_with_recovery(
                    task, browser_page, verifier
                )

                # STEP 5: RECORD execution history (store rich structured entry)
                try:
                    # Prefer TaskResult.to_dict() when available to capture structured info
                    res = result
                    res_dict = (
                        res.to_dict()
                        if hasattr(res, "to_dict")
                        else (res if isinstance(res, dict) else {})
                    )

                    # Normalize action_history entries to plain dicts for serialization
                    actions = []
                    for a in (
                        getattr(
                            res, "action_history", res_dict.get("action_history", [])
                        )
                        or []
                    ):
                        try:
                            actions.append(
                                a.to_dict() if hasattr(a, "to_dict") else dict(a)
                            )
                        except Exception:
                            # Last-resort representation
                            try:
                                actions.append(dict(a))
                            except Exception:
                                actions.append({"repr": str(a)})

                    entry = {
                        "task_id": task.id,
                        "task_desc": getattr(task, "description", None),
                        "timestamp": time.time(),
                        "result": res_dict,
                        "success": getattr(
                            res, "success", res_dict.get("success", None)
                        ),
                        "duration": getattr(
                            res, "duration", res_dict.get("duration", None)
                        ),
                        "error": getattr(
                            res,
                            "error",
                            res_dict.get("error", res_dict.get("error_details")),
                        ),
                        "verification": (
                            res_dict.get("verification")
                            if isinstance(res_dict.get("verification"), dict)
                            else None
                        ),
                        "action_history": actions,
                        "actions_count": len(actions),
                        "worker_id": getattr(
                            res, "worker_id", res_dict.get("worker_id")
                        ),
                        "worker_thread_id": getattr(
                            res, "worker_thread_id", res_dict.get("worker_thread_id")
                        ),
                        # attempt/try metadata may not always exist; keep if present
                        "attempt": getattr(res, "attempt", res_dict.get("attempt")),
                    }
                except Exception:
                    # Fallback to previous simple representation if something goes wrong
                    entry = {
                        "task_id": task.id,
                        "result": result,
                        "timestamp": time.time(),
                    }
                self.execution_history.append(entry)
                try:
                    # Persist per-task result and rolling history into supervisor memory
                    self.memory.store(
                        key=f"task:{task.id}:result",
                        value=entry,
                        memory_type=MemoryType.TASK,
                        tags=["result", task.id],
                        description=f"Result for task {task.id}",
                    )
                    history = self.memory.retrieve("history", default=[])
                    history = (history or [])[-49:] + [entry]
                    self.memory.store(
                        key="history",
                        value=history,
                        memory_type=MemoryType.LONG_TERM,
                        tags=["history"],
                        description="Rolling supervision history (last 50)",
                    )
                except Exception:
                    pass

                self.health_monitor.record_task_result(
                    task.id, result.success, result.duration
                )

                # STEP 5.5: CHECK FOR WORKER REPLAN REQUEST
                # Workers can detect task-screen mismatch and request replanning
                if hasattr(result, 'needs_replan') and result.needs_replan:
                    replan_reason = getattr(result, 'replan_reason', 'Worker detected task-screen mismatch')
                    log_warn(f"   🔄 Worker requested replan: {replan_reason}")
                    
                    # Mark task as failed since it couldn't be executed as planned
                    try:
                        dag.mark_task_failed(task.id, f"Replan requested: {replan_reason}")
                    except Exception as e:
                        log_debug(f"   ℹ️ Could not mark task failed: {e}")
                    
                    # CRITICAL: Worker replan requests BYPASS cooldown restrictions!
                    # The worker has direct observation and detected an impossible situation
                    log_info(f"   🧠 Triggering immediate replan based on worker feedback (bypassing cooldown)...")
                    
                    # Create AI decision for replan
                    replan_decision = SupervisorDecision(
                        action=SupervisorAction.REPLAN,
                        reasoning=f"Worker detected mismatch: {replan_reason}",
                        confidence=0.95,
                    )
                    
                    await self._append_decision_to_thread(
                        replan_decision, context={"trigger": "worker_replan_request", "task_id": task.id}
                    )
                    
                    # Execute the replan decision (worker requests bypass all restrictions)
                    await self._execute_decision(replan_decision, dag, browser_page, verifier)
                    
                    # Continue to next task - this one needs replanning
                    continue

                # STEP 6: COMMAND - Update final state based on result
                if result.success:
                    try:
                        dag.mark_task_completed(task.id)
                        self.executed_task_count += 1
                        self.consecutive_failures = 0
                        log_success(
                            f"   ✅ Task {task.id[:8]} completed ({self.executed_task_count} total)"
                        )
                        # Append a short success action to conversation
                        await self._append_task_summary_to_thread(
                            task, result, success=True
                        )
                        
                        # DISABLED: Automatic URL change replan was too aggressive
                        # Only worker-requested replans or AI health interventions should trigger replans
                        # await self._check_url_change_and_replan(goal, dag, browser_page, result)
                        
                    except ValueError as e:
                        log_error(f"   ❌ Error marking task completed: {e}")
                else:
                    try:
                        # Ensure error message is never None
                        error_message = result.error or "Task failed without error message"
                        dag.mark_task_failed(task.id, error_message)
                        self.consecutive_failures += 1
                        log_error(f"   ❌ Task {task.id[:8]} failed: {error_message}")

                        # FULLY AI-DRIVEN FAILURE HANDLING:
                        # Always consult the decision engine on failures, providing execution state
                        decision = await self._ai_failure_decision(
                            goal, task, result, dag
                        )

                        # Record decision and run it
                        await self._append_decision_to_thread(
                            decision, context={"task_id": task.id}
                        )
                        await self._execute_decision(
                            decision, dag, browser_page, verifier
                        )

                        # Append task failure summary to conversation thread
                        await self._append_task_summary_to_thread(
                            task, result, success=False
                        )

                    except ValueError as e:
                        log_error(f"   ❌ Error marking task failed: {e}")

            await asyncio.sleep(self.supervision_interval)

        return self._build_final_result(dag)

    # -------------------------
    # Replan / deadlock helpers
    # -------------------------
    def _can_replan(self) -> bool:
        """Check if replan is allowed based on cooldown only (no minimum execution restriction)"""
        if self.last_replan_time:
            elapsed = time.time() - self.last_replan_time
            if elapsed < self.REPLAN_COOLDOWN_SECONDS:
                # Cooldown active - prevent rapid replanning
                return False
        return True

    # The previous gating behavior for failures is removed to allow AI always-in-the-loop.
    def _should_handle_failure(self) -> bool:
        """Previously used to gate when to call AI; now always returns True."""
        return True

    # -------------------------
    # Task execution + recovery
    # -------------------------
    async def _execute_task_with_recovery(
        self, task: Task, browser_page, verifier
    ) -> TaskResult:
        """
        Execute task using PlannerAgent (which spawns workers).
        
        New Architecture:
        - Supervisor spawns PlannerAgent for each DAG task
        - PlannerAgent breaks down task and spawns WorkerAgents
        - Workers report back to PlannerAgent
        - PlannerAgent verifies completion and reports to Supervisor
        """
        try:
            # Import PlannerAgent
            from web_agent.core.planner_agent import PlannerAgent
            
            # Build execution history summary for planner context
            execution_summary = self._get_execution_summary_for_worker()
            
            # Create PlannerAgent for this task
            planner = PlannerAgent(
                planner_id=f"planner_{task.id[:8]}_sup0",
                task=task,
                browser_page=browser_page,
                gemini_agent=self.gemini_agent,
                verifier=verifier,
                screen_parser=self.screen_parser,  # CRITICAL: Share parser!
                parent_context={
                    "supervisor_mode": True,
                    "supervisor_thread": self.supervisor_thread_id,
                    "execution_history": execution_summary,
                    "execution_context": {
                        "goal": getattr(self, "current_goal", ""),
                        "completed_tasks": self.executed_task_count,
                        "total_tasks": len(getattr(self, "current_dag", [])) if hasattr(self, "current_dag") else 0,
                    },
                },
                accomplishment_store=self.accomplishment_store,
            )

            # PlannerAgent will spawn workers and manage execution
            result = await planner.execute_task()
            await planner.cleanup()
            return result

        except Exception as e:
            log_error(f"   💥 Task {task.id[:8]} exception: {e}")
            if "planner" in locals():
                try:
                    await planner.cleanup()
                except Exception:
                    pass
            return TaskResult(
                task_id=task.id,
                success=False,
                error=str(e),
                duration=0.0,
                action_history=[],
            )

    # -------------------------
    # AI decision integration
    # -------------------------
    async def _ai_failure_decision(
        self, goal: str, failed_task: Task, result: TaskResult, dag
    ) -> SupervisorDecision:
        """Get AI decision for task failure and record it to conversation thread."""

        state = self._capture_execution_state(goal, dag)

        decision = await self.decide_failure_action(
            goal=goal,
            failed_task={
                "id": failed_task.id,
                "description": failed_task.description,
                "error": result.error,
                "duration": result.duration,
                "actions": len(result.action_history)
                if getattr(result, "action_history", None)
                else 0,
            },
            execution_state=state,
            dag_state={
                "downstream_tasks": dag.get_dependent_tasks(failed_task.id),
                "failure_pattern": self._detect_failure_pattern(failed_task),
                "current_url": getattr(result, "current_url", "unknown"),
            },
        )

        # CRITICAL FIX: Ensure RETRY decisions always have task_id
        # If LLM returned RETRY but forgot to include task_id, populate it
        if decision.action == SupervisorAction.RETRY and not decision.task_id:
            decision.task_id = failed_task.id
            log_debug(f"   🔧 Auto-populated missing task_id for RETRY decision: {failed_task.id[:8]}")

        # keep in local decision list for final result reporting
        self.decisions_made.append(decision)

        # instrument conversation thread with decision
        await self._append_decision_to_thread(
            decision, context={"failed_task_id": failed_task.id}
        )

        return decision

    async def _ai_health_intervention(
        self, goal: str, dag, health
    ) -> Optional[SupervisorDecision]:
        """
        Consult AI for health-based intervention when execution health is CRITICAL or DEGRADED.
        
        This provides proactive recovery before complete deadlock.
        """
        try:
            state = self._capture_execution_state(goal, dag)
            
            # Build health-specific context
            health_context = {
                "status": health.status,
                "success_rate": health.success_rate,
                "concerns": health.concerns,
                "is_stuck": health.is_stuck,
                "is_deadlocked": health.is_deadlocked,
                "completed": health.completed_count,
                "failed": health.failed_count,
                "total": health.total_count,
                "elapsed_time": health.elapsed_time,
            }
            
            log_warn(f"   🏥 Health concerns: {', '.join(health.concerns)}")
            
            # Use decision engine to determine recovery action
            decision = await self.decide_failure_action(
                goal=goal,
                failed_task={
                    "id": "health_intervention",
                    "description": f"System health is {health.status}",
                    "error": f"Health concerns: {', '.join(health.concerns)}",
                    "duration": health.elapsed_time,
                    "actions": 0,
                },
                execution_state=state,
                dag_state={
                    "health": health_context,
                    "ready_tasks": len(dag.get_ready_tasks()),
                },
            )
            
            self.decisions_made.append(decision)
            return decision
            
        except Exception as e:
            log_error(f"   ❌ Health intervention failed: {e}")
            return None

    async def _handle_deadlock(self, goal: str, dag) -> SupervisorDecision:
        """Handle execution deadlock with AI (and record decision)."""
        state = self._capture_execution_state(goal, dag)
        decision = await self.decide_deadlock_resolution(
            goal=goal,
            blocked_tasks=dag.get_incomplete_tasks(),
            dag_state={"ready_tasks": len(dag.get_ready_tasks())},
        )

        self.decisions_made.append(decision)
        await self._append_decision_to_thread(decision, context={"deadlock": True})
        return decision

    async def _execute_decision(
        self, decision: SupervisorDecision, dag, browser_page, verifier
    ):
        """Execute supervisor decision with proper state management and instrumentation."""

        # Normalize action string for comparison
        action = None
        try:
            if isinstance(decision.action, str):
                action = decision.action.upper()
            else:
                # SupervisorAction Enum case
                action = decision.action.name.upper()
        except Exception:
            action = str(decision.action).upper()

        log_info(
            f"   🧠 Executing decision: {action} ({getattr(decision, 'confidence', 0.0):.0%})"
        )

        # Best-effort: append the raw decision dict to conversation thread
        await self._append_decision_to_thread(decision)

        if action == "RETRY":
            # RETRY: Reset the failed task to PENDING so it becomes ready again
            self.consecutive_skips = 0  # Reset skip counter on non-skip action
            task_id = getattr(decision, "task_id", None)
            if task_id:
                try:
                    # Reset task from FAILED to PENDING
                    task = dag.get_task(task_id)
                    if task and task.status == TaskStatus.FAILED:
                        task.status = TaskStatus.PENDING
                        task.error = None  # Clear previous error
                        log_info(f"   🔁 Reset task {task_id[:8]} to PENDING for retry")
                        await self._append_system_event(
                            f"Task {task_id} reset to PENDING for retry per AI decision",
                            metadata={"task_id": task_id},
                        )
                    else:
                        log_warn(f"   ⚠️ Cannot retry task {task_id[:8]}: not in FAILED state")
                except Exception as e:
                    log_error(f"   ❌ Failed to reset task for retry: {e}")
            else:
                log_warn("   ⚠️ RETRY decision missing task_id")

        elif action == "SKIP":
            # SKIP: mark the provided task skipped if task id specified
            task_id = getattr(decision, "task_id", None)
            if task_id:
                # Check for consecutive skip loop - force REPLAN if too many
                self.consecutive_skips += 1
                if self.consecutive_skips >= self.MAX_CONSECUTIVE_SKIPS:
                    log_error(f"   🔄 Too many consecutive SKIPs ({self.consecutive_skips}) - forcing REPLAN to break loop!")
                    self.consecutive_skips = 0  # Reset counter
                    # Force a replan by creating a REPLAN decision
                    replan_decision = SupervisorDecision(
                        action=SupervisorAction.REPLAN,
                        reasoning=f"Forced replan after {self.MAX_CONSECUTIVE_SKIPS} consecutive SKIPs to prevent infinite loop",
                        confidence=1.0,
                    )
                    await self._execute_decision(replan_decision, dag, browser_page, verifier)
                    return  # Exit after forcing replan
                
                try:
                    dag.mark_task_skipped(task_id)
                    # IMPORTANT: Count SKIP as execution progress
                    # SKIP is a deliberate decision that advances the workflow
                    self.executed_task_count += 1
                    log_warn(f"   ⏭️  Skipped task {task_id[:8]} per AI decision ({self.executed_task_count} total, {self.consecutive_skips} consecutive)")
                    
                    # Unblock dependent tasks by removing this task from their dependencies
                    dependent_tasks = dag.get_dependent_tasks(task_id)
                    for dep_task in dependent_tasks:
                        try:
                            if hasattr(dep_task, 'dependencies') and task_id in dep_task.dependencies:
                                dep_task.dependencies.remove(task_id)
                                log_info(f"   🔓 Unblocked task {dep_task.id[:8]} (removed dependency on skipped task)")
                        except Exception as e:
                            log_debug(f"   ℹ️ Could not remove dependency: {e}")
                    
                    await self._append_system_event(
                        f"Task {task_id} skipped per AI decision, {len(dependent_tasks)} dependents unblocked",
                        metadata={"task_id": task_id, "dependents_unblocked": len(dependent_tasks)},
                    )
                except ValueError as e:
                    # Fallback: if the task is already FAILED, force skip to unblock pipeline
                    try:
                        t = dag.get_task(task_id)
                        if t and getattr(t, "status", None) == TaskStatus.FAILED:
                            t.status = TaskStatus.SKIPPED
                            self.executed_task_count += 1
                            log_warn(
                                f"   ⏭️  Forced skip on failed task {task_id[:8]} to unblock DAG ({self.executed_task_count} total)"
                            )
                        else:
                            log_error(f"   ❌ Cannot skip task: {e}")
                    except Exception:
                        log_error(f"   ❌ Cannot skip task: {e}")

        elif action == "REPLAN":
            # If the DAG is not complete, prefer adding recovery tasks to the existing DAG
            # instead of discarding progress. If the DAG is complete, MasterAgent will
            # handle creating a fresh plan on the next supervised pass.
            self.consecutive_skips = 0  # Reset skip counter on replan
            try:
                if not dag.is_complete():
                    added = self._add_recovery_tasks(decision, dag)
                    await self._append_system_event(
                        "Added recovery tasks to current DAG per AI decision",
                        metadata={"count": added},
                    )
                else:
                    log_info(
                        "   ℹ️ DAG already complete; allowing MasterAgent to create a new plan."
                    )
            except Exception as e:
                log_error(f"   ❌ Failed to add recovery tasks: {e}")

        elif action == "ABORT":
            log_error(f"   🛑 AI Supervisor: Aborting execution per decision")
            dag.mark_all_complete()
            await self._append_system_event(
                "Execution aborted by AI decision",
                metadata={"reason": getattr(decision, "reasoning", None)},
            )

        elif action == "WAIT":
            # WAIT: backoff for a short period (configurable)
            wait_secs = 5
            log_info(f"   ⏸️ AI Decision=WAIT: sleeping {wait_secs}s")
            await asyncio.sleep(wait_secs)

        else:
            # Unrecognized action: log and ignore
            log_warn(f"   ⚠️ Unrecognized decision action: {action}")

    async def _trigger_replan(self, dag, browser_page):
        """Trigger AI replanning (best-effort)."""
        log_warn("   🔄 AI Supervisor: Triggering replan...")
        current_url = getattr(browser_page, "url", None)
        log_info(f"   📋 Replan would occur here (URL: {current_url})")
        await self._append_system_event(
            "AI-triggered replan requested", metadata={"current_url": current_url}
        )
        # Attempt a best-effort replanning using planner (if available)
        try:
            new_plan = await self.planner.create_plan(
                goal="", starting_url=current_url, explore=True
            )
            if new_plan:
                # Convert to DAG if planner returned a plan-like object
                try:
                    from web_agent.planning.dag_converter import PlanToDAGConverter

                    new_dag = PlanToDAGConverter.convert(new_plan)
                    # Replace dag tasks in-place if caller expects reference semantics; otherwise this is best-effort.
                    await self._append_system_event(
                        "Planner produced new plan for replan",
                        metadata={"plan_steps": len(getattr(new_plan, "steps", []))},
                    )
                except Exception:
                    # Planner returned something but conversion failed - record only
                    await self._append_system_event(
                        "Planner produced plan but DAG conversion failed", metadata={}
                    )
        except Exception as e:
            log_error(f"   ❌ Replan attempt failed: {e}")
            await self._append_system_event(
                "Replan attempt failed", metadata={"error": str(e)}
            )

    def _add_recovery_tasks(self, decision: SupervisorDecision, dag) -> int:
        """Add one or more recovery tasks into the current DAG based on the AI decision.

        - Uses `decision.alternative` as a single recovery step when provided.
        - If `decision` exposes `new_tasks` iterable (list of {description, dependencies?}),
          those will be added as additional tasks.
        - Tasks are added without introducing dependencies on failed tasks to avoid deadlocks.
        Returns the number of tasks added.
        """
        added = 0
        try:
            # Helper to add a single task
            def add_task_with_desc(desc: str) -> None:
                nonlocal added
                if not desc:
                    return
                t = Task(description=desc)
                dag.add_task(t)
                added += 1

            # If the AI chose RETRY and provided a task_id, add a retry task that mirrors dependencies
            try:
                if (
                    getattr(decision, "action", None) in (SupervisorAction.RETRY, "retry")
                    and getattr(decision, "task_id", None)
                ):
                    orig = dag.get_task(decision.task_id)
                    if orig is not None:
                        retry_desc = f"Retry: {orig.description}" if orig.description else "Retry failed step"
                        t = Task(description=retry_desc, dependencies=list(orig.dependencies) if hasattr(orig, "dependencies") else [])
                        dag.add_task(t)
                        # explicit dependencies are already in Task and added in add_task
                        added += 1
            except Exception:
                pass

            # Primary alternative task
            alt = getattr(decision, "alternative", None)
            if isinstance(alt, str) and alt.strip():
                add_task_with_desc(alt.strip())

            # Optional richer new_tasks structure
            maybe_new = getattr(decision, "new_tasks", None)
            if isinstance(maybe_new, list):
                for nt in maybe_new:
                    try:
                        desc = nt.get("description") if isinstance(nt, dict) else str(nt)
                        add_task_with_desc(desc)
                    except Exception:
                        continue
        except Exception:
            # If anything goes wrong, return what we could add
            return added
        return added

    # -------------------------
    # Utilities: capture state, detect failure pattern
    # -------------------------
    def _capture_execution_state(self, goal: str, dag) -> Dict:
        """
        Capture a normalized, structured execution state for decision making.

        This function returns both compact numeric summaries (for quick heuristics)
        and a bounded, structured `recent_history` suitable for causal analysis by
        the DecisionEngine LLM prompts. Keep the recent history short (last 10)
        and ensure entries are serializable and contain key fields (action summaries,
        result/error, durations, worker info).
        """
        health = self.health_monitor.get_health(dag)

        # Build a compact but informative recent_history for decisioning.
        recent = []
        for h in self.execution_history[-10:]:
            try:
                # Each entry is expected to be a dict-like snapshot created when tasks run.
                # We normalize to a compact representation containing only the most useful fields.
                action_history = h.get("action_history") or []
                # Build summarized actions (type, target, error) for up to first 6 actions
                actions_summary = []
                for a in action_history[:6]:
                    try:
                        if isinstance(a, dict):
                            actions_summary.append(
                                {
                                    "type": a.get("action_type") or a.get("type"),
                                    "target": a.get("target"),
                                    "error": a.get("error"),
                                }
                            )
                        else:
                            # best-effort extraction for action objects
                            actions_summary.append(
                                {
                                    "type": getattr(a, "action_type", str(a))[:80],
                                    "target": getattr(a, "target", None),
                                }
                            )
                    except Exception:
                        actions_summary.append({"type": str(a)[:80]})
                recent.append(
                    {
                        "timestamp": h.get("timestamp"),
                        "task_id": h.get("task_id"),
                        "description": h.get("task_desc") or h.get("description"),
                        "success": h.get("success"),
                        "error": h.get("error"),
                        "duration": h.get("duration"),
                        "actions_count": h.get("actions_count", len(action_history)),
                        "action_summary": actions_summary,
                        "worker_id": h.get("worker_id"),
                        "worker_thread_id": h.get("worker_thread_id"),
                        "verification": h.get("verification"),
                    }
                )
            except Exception:
                # Fallback minimal entry
                try:
                    recent.append(
                        {"task_id": h.get("task_id"), "success": h.get("success")}
                    )
                except Exception:
                    recent.append({})

        # Determine total tasks robustly
        try:
            total_tasks = len(dag.tasks)
        except Exception:
            try:
                total_tasks = dag.get_task_count()
            except Exception:
                total_tasks = 0

        return {
            "goal": goal,
            "completed": len(dag.get_completed_tasks()),
            "failed": len(dag.get_failed_tasks()),
            "remaining": len(dag.get_incomplete_tasks()),
            "total": total_tasks,
            "all_tasks": total_tasks,
            "executed_count": self.executed_task_count,
            "consecutive_failures": self.consecutive_failures,
            "health_status": health.status,
            "success_rate": health.success_rate,
            "elapsed_time": time.time() - (self.execution_start or time.time()),
            # include a compact supervision history sample with structured entries
            "recent_history": recent,
        }

    def _detect_failure_pattern(self, task: Task) -> str:
        """Detect failure pattern from task description"""
        desc = (task.description or "").lower()
        if "verify" in desc or "check" in desc or "analyze" in desc:
            return "verification_failure"
        elif "press" in desc or "enter" in desc or "click" in desc:
            return "action_redundancy"
        return "unknown_failure"

    def _build_final_result(self, dag) -> SupervisionResult:
        """Build final supervision result and include stop_reason for higher-level decisions."""
        try:
            if dag.is_complete():
                stop_reason = "dag_complete"
            else:
                stop_reason = "stopped_before_completion"
        except Exception:
            stop_reason = "unknown_stop"

        final_state = self._capture_execution_state("final", dag)

        return SupervisionResult(
            success=dag.is_complete(),
            completed_tasks=len(dag.get_completed_tasks()),
            failed_tasks=len(dag.get_failed_tasks()),
            total_tasks=len(dag.tasks),
            decisions_made=self.decisions_made,
            execution_time=time.time() - (self.execution_start or time.time()),
            final_state=final_state,
            stop_reason=stop_reason,
        )

    async def _check_url_change_and_replan(
        self, goal: str, dag, browser_page, result: TaskResult
    ):
        """
        Detect significant URL changes and trigger automatic replanning with exploration.
        This ensures the agent adapts to new pages by discovering all content first.
        """
        try:
            # Get current URL from result or browser
            current_url = getattr(result, "current_url", None) or getattr(browser_page, "url", None)
            
            if not current_url:
                return  # Can't detect change without URL
            
            # Initialize tracking on first check
            if self.last_known_url is None:
                self.last_known_url = current_url
                log_debug(f"   📍 Initial URL tracked: {current_url}")
                return
            
            # Check if URL changed (any change triggers replan)
            # This includes domain, path, query params, and fragments
            if self.last_known_url != current_url:
                self.url_changed_count += 1
                log_warn(f"   🌐 URL CHANGED ({self.url_changed_count}x): {self.last_known_url} → {current_url}")
                
                # Update tracked URL
                self.last_known_url = current_url
                
                # Check if we can replan (respects cooldown + minimum executions)
                if self._can_replan():
                    log_info(f"   🔄 Triggering automatic replan due to URL change...")
                    
                    try:
                        # Use planner to explore the new page comprehensively
                        log_info(f"   🕵️  Planner will explore new page: {current_url}")
                        new_plan = await self.planner.create_plan(
                            goal=goal,
                            starting_url=current_url,
                            explore=True,  # IMPORTANT: Full exploration of new page
                            thread_id=self.supervisor_thread_id,
                        )
                        
                        if new_plan and hasattr(new_plan, 'steps'):
                            # Convert plan to tasks and add to DAG
                            from web_agent.planning.dag_converter import PlanToDAGConverter
                            new_dag = PlanToDAGConverter.convert(new_plan)
                            
                            # Handle old DAG tasks on URL change:
                            # 1. Keep completed tasks (they represent real progress)
                            # 2. Skip incomplete tasks (they're for the old page, no longer relevant)
                            skipped_count = 0
                            incomplete_tasks = dag.get_incomplete_tasks()
                            
                            for old_task in incomplete_tasks:
                                try:
                                    # Skip tasks that are for the old URL
                                    if old_task.status in [TaskStatus.PENDING, TaskStatus.BLOCKED]:
                                        dag.mark_task_skipped(old_task.id)
                                        self.executed_task_count += 1  # Count skip as progress
                                        skipped_count += 1
                                        log_debug(f"      ⏭️  Skipped old task {old_task.id[:8]} (page changed)")
                                except Exception as e:
                                    log_debug(f"      ℹ️ Could not skip old task: {e}")
                            
                            # Add new tasks to current DAG
                            added_count = 0
                            # Get actual Task objects from DAG, not just IDs
                            for task_id in new_dag.tasks:
                                try:
                                    task = new_dag.get_task(task_id)
                                    if task:
                                        dag.add_task(task)
                                        added_count += 1
                                except Exception as e:
                                    log_debug(f"      ℹ️ Could not add task: {e}")
                            
                            self.last_replan_time = time.time()
                            log_success(f"   ✅ Replan complete: Skipped {skipped_count} old tasks, added {added_count} new tasks")
                            
                            await self._append_system_event(
                                f"Automatic replan triggered by URL change: skipped {skipped_count} old tasks, added {added_count} new tasks",
                                metadata={
                                    "old_url": self.last_known_url,
                                    "new_url": current_url,
                                    "tasks_skipped": skipped_count,
                                    "tasks_added": added_count,
                                    "exploration_done": True,
                                }
                            )
                        else:
                            log_warn(f"   ⚠️ Planner returned no steps for new page")
                            
                    except Exception as e:
                        log_error(f"   ❌ Auto-replan failed: {e}")
                        await self._append_system_event(
                            f"Auto-replan failed on URL change",
                            metadata={"error": str(e), "url": current_url}
                        )
                else:
                    log_debug(f"   ⏳ URL changed but replan not permitted yet (cooldown or min executions)")
                    
        except Exception as e:
            log_debug(f"   ℹ️ URL change detection error (non-fatal): {e}")
    
    # -------------------------
    # Conversation instrumentation helpers (best-effort)
    # -------------------------
    async def _append_system_event(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """Append a system-level event to the supervisor thread (if conv manager available)."""
        try:
            if self.conversation_manager:
                await self.conversation_manager.store.append_event(
                    thread_id=self.supervisor_thread_id,
                    role="system",
                    content=content,
                    metadata=metadata or {},
                )
        except Exception:
            # never raise - instrumentation is best-effort
            log_debug("   ℹ️ Failed to append system event to conversation (ignored)")

    async def _append_task_summary_to_thread(
        self, task: Task, result: TaskResult, success: bool
    ):
        """Append a compact task summary to the supervisor thread."""
        try:
            if not self.conversation_manager:
                return
            details = {
                "task_id": task.id,
                "task_desc": task.description,
                "success": bool(success),
                "duration": float(getattr(result, "duration", 0.0) or 0.0),
                "error": getattr(result, "error", None),
                "actions": len(getattr(result, "action_history", []) or []),
            }
            # use ConversationManager.append_action if available
            try:
                await self.conversation_manager.append_action(
                    thread_id=self.supervisor_thread_id,
                    actor="supervisor",
                    action_desc="task_summary",
                    success=bool(success),
                    details=details,
                )
            except Exception:
                # fallback to direct append_event
                await self.conversation_manager.store.append_event(
                    thread_id=self.supervisor_thread_id,
                    role="supervisor",
                    content=f"task_summary: {details}",
                    metadata=details,
                )
        except Exception:
            log_debug("   ℹ️ Failed to append task summary to conversation (ignored)")

    async def _append_decision_to_thread(
        self, decision: SupervisorDecision, context: Optional[Dict[str, Any]] = None
    ):
        """Append the raw decision details to the supervisor thread for traceability."""
        try:
            if not self.conversation_manager:
                return
            # Convert dataclass-like decision to a serializable dict
            dec = {}
            try:
                # try dataclass asdict if possible
                dec = (
                    asdict(decision)
                    if hasattr(decision, "__dataclass_fields__")
                    else decision.__dict__
                )
            except Exception:
                # last-resort conversion
                dec = {
                    k: getattr(decision, k, None)
                    for k in [
                        "action",
                        "reasoning",
                        "confidence",
                        "task_id",
                        "alternative",
                        "new_tasks",
                    ]
                }
            if context:
                dec.update({"context": context})
            try:
                await self.conversation_manager.append_decision(
                    thread_id=self.supervisor_thread_id,
                    decision=dec,
                )
            except Exception:
                # fallback to store append_event
                await self.conversation_manager.store.append_event(
                    thread_id=self.supervisor_thread_id,
                    role="decision",
                    content=str(dec),
                    metadata=dec,
                )
        except Exception:
            log_debug("   ℹ️ Failed to append decision to conversation (ignored)")

    # -------------------------
    # Decision Engine Methods (formerly DecisionEngine class)
    # -------------------------
    async def decide_failure_action(
        self, goal: str, failed_task: Dict, execution_state: Dict, dag_state: Dict
    ) -> SupervisorDecision:
        """Decide what to do when a task fails."""
        # Normalize execution state to a stable schema for LLM prompts
        normalized_state = self._normalize_execution_state(execution_state)
        request = DecisionRequest(
            goal=goal,
            failed_task=failed_task,
            execution_state=normalized_state,
            downstream_tasks=dag_state.get("downstream_tasks", []),
            failure_pattern=dag_state.get("failure_pattern", "unknown"),
            current_url=dag_state.get("current_url", ""),
        )

        # Get AI decision
        decision = await self._call_decision_llm(request)

        print(f"\n🧠 AI Decision: {decision.action.value}")
        print(f"   Confidence: {decision.confidence:.1%}")
        print(f"   Reasoning: {decision.reasoning[:100]}...")

        return SupervisorDecision(
            action=decision.action,
            reasoning=decision.reasoning,
            confidence=decision.confidence,
            task_id=decision.task_id,
            alternative=decision.alternative,
            new_tasks=getattr(decision, "new_tasks", None),
        )

    async def decide_deadlock_resolution(
        self, goal: str, blocked_tasks: List[Dict], dag_state: Dict
    ) -> SupervisorDecision:
        """Decide how to resolve execution deadlock."""
        prompt = self._build_deadlock_prompt(goal, blocked_tasks, dag_state)
        response = await self.gemini_agent.action_llm.ainvoke(
            [{"role": "user", "content": prompt}]
        )
        return self._parse_decision_response(response.content)

    async def should_continue(
        self,
        execution_state: Dict,
        verification: Optional[Dict] = None,
        conversation_context: Optional[Dict] = None,
    ) -> bool:
        """Decide whether the master should continue running supervised execution passes."""
        try:
            # Prefer LangChain structured output if GeminiAgent exposes it
            if hasattr(self.gemini_agent, "continuation_llm"):
                conv_summary = ""
                conv_events = ""
                if conversation_context and isinstance(conversation_context, dict):
                    conv_summary = conversation_context.get("summary", "") or ""
                    recent = conversation_context.get("recent_messages", []) or []
                    lines = []
                    for m in recent[-10:]:
                        role = m.get("role", "event")
                        content = m.get("content", "")
                        snippet = content.replace("\n", " ")
                        if len(snippet) > 300:
                            snippet = snippet[:297] + "..."
                        lines.append(f"[{role}] {snippet}")
                    conv_events = "\n".join(lines)

                prompt = (
                    "You are an AI Supervisor Decision Engine.\n\n"
                    "Given the execution state, the verifier assessment, and a short conversation summary\n"
                    "with recent events, return a structured response indicating whether the master should\n"
                    "run another supervised execution pass.\n\n"
                    f"Execution state: {execution_state}\n\nVerification: {verification}\n\n"
                    f"Conversation summary: {conv_summary}\n\nRecent events:\n{conv_events}\n\n"
                )
                result = await self.gemini_agent.continuation_llm.ainvoke(prompt)
                return bool(getattr(result, "should_continue", False))

            # Fallback heuristic
            try:
                conf = 0.0
                if verification is not None:
                    conf = float(getattr(verification, "confidence", 0.0))
            except Exception:
                conf = 0.0
            remaining = execution_state.get("total", 1) - execution_state.get("completed", 0)
            return bool(conf < 0.95 and remaining > 0)

        except Exception:
            return False

    async def _call_decision_llm(self, request: DecisionRequest) -> DecisionResponse:
        """Call the structured decision LLM and return a validated DecisionResponse."""
        from web_agent.core.error_types import ErrorClassifier
        
        failed_task_dict = request.failed_task if isinstance(request.failed_task, dict) else {}
        error_message = failed_task_dict.get("error", "")
        
        # Extract progress metrics from recent history
        progress_metrics_dict = None
        recent_history = request.execution_state.get('raw', {}).get('recent_history', [])
        if recent_history:
            last_run = recent_history[-1]
            result = last_run.get('result', {})
            extracted_data = result.get('extracted_data', {})
            progress_metrics_dict = extracted_data.get('progress_metrics')
        
        # Classify the error using structured system
        structured_error = ErrorClassifier.classify(error_message, progress_metrics_dict)
        
        # Build detailed progress information
        progress_info = ""
        if structured_error.progress_metrics:
            metrics = structured_error.progress_metrics
            progress_info = f"""
STRUCTURED ERROR ANALYSIS:
Error Category: {structured_error.category.value}
{f"Timeout Reason: {structured_error.timeout_reason.value}" if structured_error.timeout_reason else ""}
Suggested Action: {structured_error.suggested_action}
Is Recoverable: {structured_error.is_recoverable}

DETAILED PROGRESS METRICS:
- Actions executed: {metrics.actions_executed}
- Successful actions: {metrics.successful_actions} 
- Failed actions: {metrics.failed_actions}
- Success rate: {metrics.success_rate:.1%}
- State changes: {metrics.state_changes}
- Has meaningful progress: {metrics.has_meaningful_progress}

Recent Actions Pattern:
{self._format_action_pattern(metrics.last_10_actions)}

RECOMMENDATION:
{self._generate_recommendation(structured_error)}
"""

        prompt = f"""You are an AI Supervisor Decision Engine for web automation.

GOAL: {request.goal}

FAILED TASK:
{self._format_failed_task(request.failed_task)}
{progress_info}

EXECUTION STATE:
- Progress: {request.execution_state.get('completed', 0)} / {request.execution_state.get('total', 0)}
- Failed: {request.execution_state.get('failed', 0)}

DECISION REQUIRED:
Choose ONE action and return a structured response.

RULES:
- RETRY: First failure, temporary issue
- SKIP: Non-critical verification
- REPLAN: Task made progress but needs continuation
- ABORT: Goal unreachable
"""

        messages = [
            {"role": "system", "content": "You are a production-grade AI supervisor for web automation."},
            {"role": "user", "content": prompt},
        ]

        try:
            if hasattr(self.gemini_agent, "decision_llm"):
                result = await self.gemini_agent.decision_llm.ainvoke(messages)
                action_str = getattr(result, "action", None)
                try:
                    action_enum = SupervisorAction(action_str)
                except Exception:
                    action_enum = SupervisorAction.SKIP

                return DecisionResponse(
                    action=action_enum,
                    reasoning=getattr(result, "reasoning", ""),
                    confidence=float(getattr(result, "confidence", 0.0)),
                    task_id=getattr(result, "task_id", None),
                    alternative=getattr(result, "alternative", None),
                    new_tasks=getattr(result, "new_tasks", None),
                )
        except Exception as e:
            print(f"⚠️  Decision engine fallback: {e}")
            return DecisionResponse(
                action=SupervisorAction.SKIP,
                reasoning="Decision engine error - defaulting to skip",
                confidence=0.5,
            )

    def _normalize_execution_state(self, state: Dict) -> Dict:
        """Normalize execution_state to a stable schema."""
        if not isinstance(state, dict):
            state = {}
        normalized = dict(state)
        
        def to_int(val, default=0):
            if isinstance(val, int):
                return val
            try:
                if val is None:
                    return default
                if isinstance(val, (list, tuple, set, dict)):
                    return len(val)
                return int(val)
            except Exception:
                return default

        normalized["completed"] = to_int(state.get("completed", 0), 0)
        normalized["failed"] = to_int(state.get("failed", 0), 0)
        normalized["total"] = to_int(state.get("total", 0), 0)
        
        try:
            normalized["elapsed_time"] = float(state.get("elapsed_time", 0) or 0.0)
        except Exception:
            normalized["elapsed_time"] = 0.0

        try:
            normalized["raw"] = dict(state)
        except Exception:
            normalized["raw"] = {"state": state}

        return normalized

    def _build_deadlock_prompt(self, goal: str, blocked_tasks: List[Dict], dag_state: Dict) -> str:
        """Builds the prompt for resolving a deadlock."""
        task_list = "\n".join([f"  - {task.id}: {task.description}" for task in blocked_tasks[:5]])
        return f"""You are an AI Supervisor responsible for unblocking execution.

**SITUATION:** Execution is DEADLOCKED. No tasks can run.

**GOAL:** {goal}

**BLOCKED TASKS:**
{task_list}

**DECISION REQUIRED:**
Choose ONE action to resolve the deadlock. Respond in VALID JSON.
"""

    def _format_failed_task(self, task: Dict) -> str:
        """Format failed task info"""
        return f"""Description: {task.get('description', 'N/A')}
Error: {task.get('error', 'Unknown')}
Duration: {task.get('duration', 0):.1f}s
"""

    def _format_action_pattern(self, actions: List[Dict[str, Any]]) -> str:
        """Format action pattern analysis"""
        if not actions:
            return "No actions recorded"
        lines = []
        for i, action in enumerate(actions, 1):
            action_type = action.get('type', 'unknown')
            success = action.get('success', False)
            status = "✓" if success else "✗"
            lines.append(f"  {i}. [{status}] {action_type}")
        return "\n".join(lines) if lines else "No pattern detected"
    
    def _generate_recommendation(self, structured_error) -> str:
        """Generate structured recommendation based on error analysis"""
        from web_agent.core.error_types import ErrorCategory
        
        if structured_error.category == ErrorCategory.TIMEOUT:
            if structured_error.progress_metrics and structured_error.progress_metrics.has_meaningful_progress:
                return "This is an ITERATIVE TASK making measurable progress. Recommend REPLAN with continuation task."
            else:
                return "Task timed out without progress. Recommend SKIP or RETRY based on criticality."
        elif structured_error.is_recoverable:
            return f"Error is recoverable. Suggested action: {structured_error.suggested_action.upper()}"
        else:
            return "Unrecoverable error - recommend ABORT."
    
    def _parse_decision_response(self, content: Any) -> SupervisorDecision:
        """Parse structured decision response or fallback JSON content."""
        try:
            if not isinstance(content, str) and hasattr(content, "action"):
                action_val = getattr(content, "action", None)
                try:
                    action_enum = SupervisorAction(action_val)
                except Exception:
                    action_enum = SupervisorAction.SKIP
                return SupervisorDecision(
                    action=action_enum,
                    reasoning=getattr(content, "reasoning", ""),
                    confidence=float(getattr(content, "confidence", 0.0)),
                )
            data = json.loads(content) if isinstance(content, str) else dict(content)
            try:
                action_enum = SupervisorAction(data.get("action"))
            except Exception:
                action_enum = SupervisorAction.SKIP
            return SupervisorDecision(
                action=action_enum,
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception:
            return SupervisorDecision(
                action=SupervisorAction.SKIP,
                reasoning="Parse error - default skip",
                confidence=0.3,
            )

    def _get_execution_summary_for_worker(self) -> Dict[str, Any]:
        """
        Build a compact execution history summary for worker context.
        Workers need to know what was already attempted to avoid repeating failed actions.
        """
        try:
            # Get last 5 task executions for context
            recent_tasks = []
            for entry in self.execution_history[-5:]:
                try:
                    recent_tasks.append({
                        "task": entry.get("task_desc", ""),
                        "success": entry.get("success", False),
                        "error": entry.get("error", ""),
                        "actions_count": entry.get("actions_count", 0),
                    })
                except Exception:
                    continue
            
            return {
                "completed_count": self.executed_task_count,
                "recent_tasks": recent_tasks,
                "decisions_made": len(self.decisions_made),
                "health_status": self.health_monitor.get_health(getattr(self, "current_dag", None)).status if hasattr(self, "current_dag") else "UNKNOWN",
            }
        except Exception as e:
            log_debug(f"   ℹ️  Could not build execution summary: {e}")
            return {"completed_count": self.executed_task_count}

    # -------------------------
    # Cleanup and finalization
    # -------------------------
    async def _cleanup(self):
        """Cleanup supervisor resources (best-effort instrumentation)."""
        log_info(f"🧹 AI Supervisor {self.execution_id[:8]} cleaned up")
        log_info(
            f"   📊 Final stats: {self.executed_task_count} tasks executed, {len(self.decisions_made)} decisions made"
        )
        # Attempt to persist a final summary event
        try:
            await self._append_system_event(
                f"Supervisor finished. Executed: {self.executed_task_count}, Decisions: {len(self.decisions_made)}",
                metadata={
                    "executed": self.executed_task_count,
                    "decisions": len(self.decisions_made),
                },
            )
        except Exception:
            pass
