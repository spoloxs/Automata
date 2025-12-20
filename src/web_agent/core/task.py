"""
Task and Task DAG (Directed Acyclic Graph) system.
Represents decomposed work units and their dependencies.
Clean separation of queries and commands.
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class TaskStatus(Enum):
    """Task execution status"""

    PENDING = "pending"
    READY = "ready"  # Dependencies satisfied, ready to execute
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    """Task priority levels"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """
    Represents a single task with explicit state transitions.

    State machine:
    PENDING → RUNNING → COMPLETED
                      → FAILED
    """

    description: str  # Human-readable task description
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    metadata: Dict = field(default_factory=dict)  # Additional task data

    # Auto-generated fields
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TaskStatus = field(default=TaskStatus.PENDING)
    priority: TaskPriority = field(default=TaskPriority.NORMAL)

    # Execution tracking
    assigned_worker: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None

    def mark_running(self, worker_id: str):
        """Transition: PENDING/READY → RUNNING"""
        if self.status not in [TaskStatus.PENDING, TaskStatus.READY]:
            raise ValueError(
                f"Cannot mark task {self.id} as running from status {self.status}"
            )
        self.status = TaskStatus.RUNNING
        self.assigned_worker = worker_id
        self.start_time = time.time()

    def mark_completed(self):
        """Transition: RUNNING → COMPLETED"""
        if self.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Cannot mark task {self.id} as completed from status {self.status}"
            )
        self.status = TaskStatus.COMPLETED
        self.end_time = time.time()

    def mark_failed(self, error: str):
        """Transition: RUNNING → FAILED"""
        if self.status != TaskStatus.RUNNING:
            raise ValueError(
                f"Cannot mark task {self.id} as failed from status {self.status}"
            )
        self.status = TaskStatus.FAILED
        self.error = error
        self.end_time = time.time()

    def mark_skipped(self):
        """Transition: PENDING/READY → SKIPPED"""
        # Allow supervisor to skip tasks that have already failed to unblock DAG
        if self.status not in [TaskStatus.PENDING, TaskStatus.READY, TaskStatus.FAILED]:
            raise ValueError(
                f"Cannot mark task {self.id} as skipped from status {self.status}"
            )
        self.status = TaskStatus.SKIPPED

    def can_execute(self) -> bool:
        """Check if task can be executed now."""
        return self.status in [TaskStatus.PENDING, TaskStatus.READY]

    def is_terminal(self) -> bool:
        """Check if task is in terminal state (completed/failed/skipped)"""
        return self.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.SKIPPED,
        ]

    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        return {
            "id": self.id,
            "description": self.description,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "status": self.status.value,
            "priority": self.priority.value,
            "assigned_worker": self.assigned_worker,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
        }


class TaskDAG:
    """
    Directed Acyclic Graph with clean state management.

    Design principles:
    - Queries don't mutate state (pure functions)
    - Commands explicitly change state
    - State transitions controlled by caller
    """

    def __init__(self):
        self.tasks: Dict[str, Task] = {}  # task_id -> Task
        self.adjacency: Dict[str, Set[str]] = {}  # task_id -> set of dependent task_ids
        self.reverse_adjacency: Dict[
            str, Set[str]
        ] = {}  # task_id -> set of dependency task_ids

    # ==================== COMMANDS (State Mutations) ====================

    def add_task(self, task: Task) -> None:
        """Add a task to the DAG"""
        if task.id in self.tasks:
            raise ValueError(f"Task {task.id} already exists in DAG")

        self.tasks[task.id] = task
        self.adjacency[task.id] = set()
        self.reverse_adjacency[task.id] = set()

        # Add dependencies
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                raise ValueError(f"Dependency {dep_id} not found for task {task.id}")
            self.add_dependency(task.id, dep_id)

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        """
        Add dependency: task_id depends on depends_on.

        Args:
            task_id: The task that has a dependency
            depends_on: The task that must complete first
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        if depends_on not in self.tasks:
            raise ValueError(f"Dependency task {depends_on} not found")

        # Add to adjacency lists
        self.adjacency[depends_on].add(task_id)
        self.reverse_adjacency[task_id].add(depends_on)

        # Update task's dependency list
        if depends_on not in self.tasks[task_id].dependencies:
            self.tasks[task_id].dependencies.append(depends_on)

        # Check for cycles
        if self._has_cycle():
            # Rollback
            self.adjacency[depends_on].remove(task_id)
            self.reverse_adjacency[task_id].remove(depends_on)
            self.tasks[task_id].dependencies.remove(depends_on)
            raise ValueError(
                f"Adding dependency creates a cycle: {task_id} -> {depends_on}"
            )

    def mark_task_running(self, task_id: str, worker_id: str) -> None:
        """Explicitly mark task as running (command)."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.mark_running(worker_id)

    def mark_task_completed(self, task_id: str) -> None:
        """Explicitly mark task as completed (command)."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.mark_completed()

    def mark_task_failed(self, task_id: str, error: str) -> None:
        """Explicitly mark task as failed (command)."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.mark_failed(error)

    def mark_task_skipped(self, task_id: str) -> None:
        """Explicitly mark task as skipped (command)."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task.mark_skipped()

    def mark_all_complete(self) -> None:
        """Emergency complete all tasks (for abort scenarios)."""
        for task in self.tasks.values():
            if not task.is_terminal():
                task.status = TaskStatus.SKIPPED

    # ==================== QUERIES (No Side Effects) ====================

    def get_ready_tasks(self) -> List[Task]:
        """
        Query for tasks ready to execute (pure function, no side effects).

        A task is ready if:
        1. Not in a terminal or active state (RUNNING, COMPLETED, FAILED, SKIPPED)
        2. All dependencies are COMPLETED

        Returns:
            List of ready tasks, sorted by priority (highest first)
        """
        ready = []

        for task in self.tasks.values():
            # Skip tasks that are already being processed or done
            if task.status in [
                TaskStatus.RUNNING,
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.SKIPPED,
            ]:
                continue

            # Check if all dependencies are completed
            all_deps_satisfied = all(
                self.tasks[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if all_deps_satisfied:
                ready.append(task)

        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        return list(self.tasks.values())

    def get_task_count(self) -> int:
        """Get total number of tasks"""
        return len(self.tasks)

    def get_completed_count(self) -> int:
        """Get number of completed tasks"""
        return sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)

    def get_failed_count(self) -> int:
        """Get number of failed tasks"""
        return sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)

    def get_completed_tasks(self) -> List[Task]:
        """Return list of completed Task objects"""
        return [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> List[Task]:
        """Return list of failed Task objects"""
        return [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]

    def get_incomplete_tasks(self) -> List[Task]:
        """Return list of tasks that are not in a terminal state"""
        return [t for t in self.tasks.values() if not t.is_terminal()]

    def get_dependent_tasks(self, task_id: str) -> List[dict]:
        """Return downstream tasks (dependents) for a given task id as list of dicts."""
        dependents = []
        for dep_id in self.adjacency.get(task_id, set()):
            t = self.tasks.get(dep_id)
            if t:
                dependents.append(
                    {"id": t.id, "description": t.description, "status": t.status.value}
                )
        return dependents

    def is_complete(self) -> bool:
        """Check if all tasks are in terminal state"""
        return all(t.is_terminal() for t in self.tasks.values())

    def _has_cycle(self) -> bool:
        """Check if DAG has cycles using DFS"""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self.adjacency.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if dfs(task_id):
                    return True

        return False

    def get_execution_order(self) -> List[List[str]]:
        """
        Get topologically sorted execution order in levels.

        Returns:
            List of levels, where each level contains task IDs that can run in parallel
        """
        in_degree = {
            task_id: len(deps) for task_id, deps in self.reverse_adjacency.items()
        }
        levels = []

        while True:
            # Find all tasks with in_degree 0
            current_level = [
                task_id for task_id, degree in in_degree.items() if degree == 0
            ]

            if not current_level:
                break

            levels.append(current_level)

            # Remove current level and update in_degrees
            for task_id in current_level:
                del in_degree[task_id]
                for dependent in self.adjacency[task_id]:
                    if dependent in in_degree:
                        in_degree[dependent] -= 1

        return levels

    def visualize(self) -> str:
        """Generate ASCII visualization of DAG"""
        lines = ["Task DAG:"]
        lines.append("=" * 50)

        for level_idx, level in enumerate(self.get_execution_order()):
            lines.append(f"\nLevel {level_idx + 1}:")
            for task_id in level:
                task = self.tasks[task_id]
                status_icon = {
                    TaskStatus.PENDING: "⏸️",
                    TaskStatus.READY: "🟢",
                    TaskStatus.RUNNING: "🔄",
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.FAILED: "❌",
                    TaskStatus.SKIPPED: "⏭️",
                }[task.status]

                lines.append(f"  {status_icon} [{task_id[:8]}] {task.description[:50]}")
                if task.dependencies:
                    dep_str = ", ".join([d[:8] for d in task.dependencies])
                    lines.append(f"      ↳ depends on: {dep_str}")

        return "\n".join(lines)
