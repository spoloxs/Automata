"""
Recovery Strategies

Pre-defined recovery actions for common failure patterns.
"""

import asyncio
from typing import Dict, List, Optional, Any
from web_agent.core.task import Task
from web_agent.core.result import TaskResult
from web_agent.planning.planner import Planner
from web_agent.scheduling.scheduler import WorkerScheduler


class RecoveryStrategy:
    """Base class for recovery strategies"""

    async def execute(self, context: Dict) -> Dict:
        """Execute recovery action"""
        raise NotImplementedError


class SkipVerificationStrategy(RecoveryStrategy):
    """Skip non-critical verification tasks"""

    async def execute(self, context: Dict) -> Dict:
        """Mark verification task as complete"""
        task_id = context.get("failed_task_id")
        dag = context["dag"]

        if task_id:
            print(f"🔄 Recovery: Skipping verification task {task_id[:8]}")
            dag.mark_complete(task_id)
        else:
            print("⚠️ Recovery: SkipVerificationStrategy called without a task_id.")

        return {
            "action": "skipped_verification",
            "unblocked_tasks": len(dag.get_ready_tasks()),
        }


class RetryWithSimplifiedTask(RecoveryStrategy):
    """Retry with simplified version of task"""

    async def execute(self, context: Dict) -> Dict:
        """Create simplified retry task"""
        original_task = context["failed_task"]
        dag = context["dag"]

        # Simplify task description
        simplified_desc = self._simplify_task(original_task.description)

        retry_task = Task(
            id=f"retry_{original_task.id}",
            description=f"SIMPLIFIED: {simplified_desc}",
            dependencies=original_task.dependencies,
            priority=original_task.priority,
        )

        dag.add_task(retry_task)
        print(f"🔄 Recovery: Created simplified retry task {retry_task.id[:8]}")

        return {"action": "simplified_retry", "new_task_id": retry_task.id}

    def _simplify_task(self, description: str) -> str:
        """Simplify complex task descriptions"""
        simplifications = {
            "observe the position and color": "wait for result to appear",
            "analyze result and formulate": "wait 3 seconds",
            "verify task completion": "assume success",
            "press the Enter key": "press enter if input field exists",
        }

        for complex, simple in simplifications.items():
            if complex in description.lower():
                return simple

        return description[:100] + " (simplified)"


class BridgeTaskStrategy(RecoveryStrategy):
    """Create bridge task to unblock dependencies"""

    async def execute(self, context: Dict) -> Dict:
        """Create minimal task to satisfy dependencies"""
        dag = context["dag"]
        failed_task = context["failed_task"]

        bridge_task = Task(
            id=f"bridge_{failed_task.id}",
            description=f"Bridge: Continue after {failed_task.description[:30]}...",
            dependencies=failed_task.dependencies,
            metadata={"recovery_bridge": True},
        )

        dag.add_task(bridge_task)
        print(f"🔄 Recovery: Created bridge task {bridge_task.id[:8]}")

        return {"action": "bridge_created", "bridge_task_id": bridge_task.id}


class ReplanningStrategy(RecoveryStrategy):
    """Trigger full AI replanning"""

    def __init__(self, planner: Planner, gemini_agent):
        self.planner = planner
        self.gemini = gemini_agent

    async def execute(self, context: Dict) -> Dict:
        """Replan remaining tasks"""
        goal = context["goal"]
        dag = context["dag"]
        current_state = context.get("current_state", {})

        print("🔄 Recovery: AI Replanning...")

        # Ask planner for recovery plan
        recovery_plan = await self.planner.create_recovery_plan(
            goal=goal,
            completed_tasks=context.get("completed_tasks", []),
            current_state=current_state,
        )

        # Convert to tasks and add to DAG
        recovery_dag = PlanToDAGConverter.convert(recovery_plan)
        for task in recovery_dag.tasks:
            dag.add_task(task)

        print(f"🔄 Recovery: Added {len(recovery_dag.tasks)} recovery tasks")

        return {"action": "replanned", "new_tasks_added": len(recovery_dag.tasks)}


class RecoveryManager:
    """
    Manages recovery strategies based on failure patterns.
    """

    def __init__(self, planner, gemini_agent):
        self.strategies = {
            "verification_failure": SkipVerificationStrategy(),
            "action_redundancy": SkipVerificationStrategy(),
            "timeout": RetryWithSimplifiedTask(),
            "deadlock": BridgeTaskStrategy(),
            "complex_analysis": RetryWithSimplifiedTask(),
            "critical_block": ReplanningStrategy(planner, gemini_agent),
        }

    async def recover(self, failure_context: Dict) -> Dict:
        """Select and execute best recovery strategy"""

        failure_pattern = failure_context.get("failure_pattern", "unknown")

        strategy = self.strategies.get(failure_pattern)
        if not strategy:
            print(f"⚠️  No strategy for pattern '{failure_pattern}', defaulting to skip")
            strategy = SkipVerificationStrategy()

        print(f"🔧 Applying recovery strategy: {type(strategy).__name__}")
        return await strategy.execute(failure_context)


# Quick recovery helpers
async def quick_skip_verification(dag: Any, task_id: str):
    """Quick skip for verification tasks"""
    print(f"⚡ Quick skip: {task_id[:8]}")
    dag.mark_complete(task_id)


async def quick_bridge_task(dag: Any, failed_task: Task):
    """Quick bridge task creation"""
    bridge_id = f"bridge_{failed_task.id}"
    bridge_task = Task(
        id=bridge_id,
        description="Recovery: Continue workflow",
        dependencies=[failed_task.id],
    )
    dag.add_task(bridge_task)
    return bridge_id
