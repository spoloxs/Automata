"""
Health Monitor

Tracks execution health and detects issues.
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from web_agent.core.task import TaskStatus


@dataclass
class ExecutionHealth:
    """Current health status of execution"""

    status: str  # "HEALTHY", "DEGRADED", "CRITICAL"
    completed_count: int
    failed_count: int
    total_count: int
    elapsed_time: float
    success_rate: float
    avg_task_duration: float
    concerns: List[str]
    is_stuck: bool
    is_deadlocked: bool


class HealthMonitor:
    """
    Monitors execution health and detects issues.

    Tracks:
    - Task completion rate
    - Failure patterns
    - Performance metrics
    - Deadlock detection
    """

    def __init__(self):
        self.start_time = None
        self.task_history = []
        self.last_progress_time = None
        self.stuck_threshold = 60  # seconds without progress

    def start_monitoring(self):
        """Start monitoring execution"""
        self.start_time = time.time()
        self.last_progress_time = time.time()
        self.task_history = []

    def record_task_result(self, task_id: str, success: bool, duration: float):
        """Record a task completion"""
        self.task_history.append(
            {
                "task_id": task_id,
                "success": success,
                "duration": duration,
                "timestamp": time.time(),
            }
        )

        if success:
            self.last_progress_time = time.time()

    def get_health(self, dag) -> ExecutionHealth:
        """Calculate current execution health"""

        completed_count = dag.get_completed_count()
        incomplete_count = (
            dag.get_task_count() - completed_count - dag.get_failed_count()
        )
        failed_count = dag.get_failed_count()
        total = dag.get_task_count()
        elapsed = time.time() - self.start_time if self.start_time else 0

        # Calculate metrics
        success_rate = completed_count / max(completed_count + failed_count, 1)
        avg_duration = self._calculate_avg_duration()

        # Detect issues
        concerns = []
        is_stuck = self._is_stuck()
        is_deadlocked = self._is_deadlocked(dag)

        if is_stuck:
            concerns.append("No progress in last 60 seconds")
        if is_deadlocked:
            concerns.append("Tasks are blocked by failed dependencies")
        if success_rate < 0.5 and completed_count > 2:
            concerns.append("Success rate below 50%")
        if avg_duration > 30:
            concerns.append("Tasks taking longer than expected")

        # Determine status - Be less aggressive to avoid unnecessary interventions
        # CRITICAL only when execution is truly stuck or severely broken
        if is_deadlocked and incomplete_count > 0:
            status = "CRITICAL"
        elif failed_count >= 3 and failed_count > completed_count * 2:
            # Only CRITICAL if many failures (3+) and way more failures than successes
            status = "CRITICAL"
        elif success_rate < 0.3 and (completed_count + failed_count) >= 5:
            # Only DEGRADED if success rate is very low AND we have enough data
            status = "DEGRADED"
        elif is_stuck and elapsed > 120:
            # Only DEGRADED if stuck for >2 minutes
            status = "DEGRADED"
        else:
            # Default to HEALTHY - let tasks run unless clearly broken
            status = "HEALTHY"

        return ExecutionHealth(
            status=status,
            completed_count=completed_count,
            failed_count=failed_count,
            total_count=total,
            elapsed_time=elapsed,
            success_rate=success_rate,
            avg_task_duration=avg_duration,
            concerns=concerns,
            is_stuck=is_stuck,
            is_deadlocked=is_deadlocked,
        )

    def _calculate_avg_duration(self) -> float:
        """Calculate average task duration"""
        if not self.task_history:
            return 0.0

        durations = [t["duration"] for t in self.task_history if t["success"]]
        return sum(durations) / len(durations) if durations else 0.0

    def _is_stuck(self) -> bool:
        """Check if execution is stuck"""
        if not self.last_progress_time:
            return False

        time_since_progress = time.time() - self.last_progress_time
        return time_since_progress > self.stuck_threshold

    def _is_deadlocked(self, dag) -> bool:
        """Check if execution is deadlocked without mutating DAG state.

        Note: calling `dag.get_ready_tasks()` may change task statuses as a side-effect
        (it marks tasks READY). To avoid falsely mutating the DAG during health checks,
        compute readiness conservatively here without altering task state.
        """
        # Determine ready tasks without mutating DAG state
        ready = []
        for task in getattr(dag, "get_all_tasks", lambda: list(dag.tasks.values()))():
            # Only consider tasks that are still pending
            if getattr(task, "status", None) != TaskStatus.PENDING:
                continue

            # Check whether all dependencies are completed without touching task state
            all_deps_done = True
            for dep_id in getattr(task, "dependencies", []) or []:
                dep_task = dag.get_task(dep_id)
                if (
                    not dep_task
                    or getattr(dep_task, "status", None) != TaskStatus.COMPLETED
                ):
                    all_deps_done = False
                    break

            if all_deps_done:
                ready.append(task)

        incomplete_count = (
            dag.get_task_count() - dag.get_completed_count() - dag.get_failed_count()
        )

        # Deadlock: there are incomplete tasks but none are ready to run
        return incomplete_count > 0 and len(ready) == 0
