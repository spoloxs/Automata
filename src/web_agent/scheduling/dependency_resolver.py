"""
Dependency resolver for TaskDAG.
Handles topological sorting and dependency checking.
"""
from typing import List, Set, Dict
from collections import deque, defaultdict

from web_agent.core.task import Task, TaskDAG, TaskStatus


class DependencyResolver:
    """
    Resolves task dependencies and provides execution order.
    """
    
    def __init__(self, dag: TaskDAG):
        """
        Initialize resolver.
        
        Args:
            dag: TaskDAG to resolve
        """
        self.dag = dag
    
    def get_execution_levels(self) -> List[List[str]]:
        """
        Get tasks organized by execution level (for parallel execution).
        Tasks in the same level can run in parallel.
        
        Returns:
            List of levels, each containing task IDs that can run in parallel
        """
        # Build adjacency list and in-degree count
        in_degree = defaultdict(int)
        adjacency = defaultdict(list)
        all_tasks = set(self.dag.tasks.keys())
        
        for task_id, task in self.dag.tasks.items():
            if task_id not in in_degree:
                in_degree[task_id] = 0
            
            for dep_id in task.dependencies:
                adjacency[dep_id].append(task_id)
                in_degree[task_id] += 1
        
        # Find all tasks with no dependencies (level 0)
        current_level = [tid for tid in all_tasks if in_degree[tid] == 0]
        levels = []
        
        while current_level:
            levels.append(current_level)
            next_level = []
            
            # Remove current level tasks and update in-degrees
            for task_id in current_level:
                for dependent_id in adjacency[task_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_level.append(dependent_id)
            
            current_level = next_level
        
        return levels
    
    def can_run(self, task_id: str) -> bool:
        """
        Check if a task can run (all dependencies satisfied).
        
        Args:
            task_id: Task ID to check
        
        Returns:
            True if task can run
        """
        task = self.dag.get_task(task_id)
        if not task:
            return False
        
        # Task must be in PENDING or READY state
        if task.status not in [TaskStatus.PENDING, TaskStatus.READY]:
            return False
        
        # All dependencies must be completed
        for dep_id in task.dependencies:
            dep_task = self.dag.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        
        return True
    
    def get_ready_tasks(self) -> List[Task]:
        """
        Get all tasks that are ready to execute.
        
        Returns:
            List of tasks ready to run
        """
        ready_tasks = []
        
        for task_id, task in self.dag.tasks.items():
            # Skip if already terminal
            if task.is_terminal():
                continue
            
            # Check if can run
            if self.can_run(task_id):
                # Mark as ready if still pending
                if task.status == TaskStatus.PENDING:
                    task.mark_ready()
                ready_tasks.append(task)
        
        return ready_tasks
    
    def get_blocked_tasks(self) -> List[Task]:
        """
        Get all tasks that are blocked by dependencies.
        
        Returns:
            List of blocked tasks
        """
        blocked_tasks = []
        
        for task_id, task in self.dag.tasks.items():
            if task.status == TaskStatus.PENDING and not self.can_run(task_id):
                blocked_tasks.append(task)
        
        return blocked_tasks
    
    def get_critical_path(self) -> List[str]:
        """
        Get the critical path (longest dependency chain).
        
        Returns:
            List of task IDs in critical path
        """
        # Build dependency graph
        levels = self.get_execution_levels()
        
        if not levels:
            return []
        
        # Find path with most levels
        critical_path = []
        for level in levels:
            if level:
                # Pick first task in each level for simplicity
                critical_path.append(level[0])
        
        return critical_path
    
    def estimate_parallel_time(self) -> int:
        """
        Estimate execution time if all parallel tasks run simultaneously.
        
        Returns:
            Estimated time in seconds
        """
        levels = self.get_execution_levels()
        total_time = 0
        
        for level in levels:
            # Find maximum time in this level
            level_max_time = 0
            for task_id in level:
                task = self.dag.get_task(task_id)
                if task and 'estimated_time' in task.metadata:
                    level_max_time = max(level_max_time, task.metadata['estimated_time'])
                else:
                    level_max_time = max(level_max_time, 30)  # Default 30s
            
            total_time += level_max_time
        
        return total_time
    
    def estimate_sequential_time(self) -> int:
        """
        Estimate execution time if all tasks run sequentially.
        
        Returns:
            Estimated time in seconds
        """
        total_time = 0
        
        for task_id, task in self.dag.tasks.items():
            if 'estimated_time' in task.metadata:
                total_time += task.metadata['estimated_time']
            else:
                total_time += 30  # Default 30s
        
        return total_time
    
    def get_parallelization_benefit(self) -> float:
        """
        Calculate potential speedup from parallelization.
        
        Returns:
            Speedup factor (sequential_time / parallel_time)
        """
        sequential = self.estimate_sequential_time()
        parallel = self.estimate_parallel_time()
        
        if parallel == 0:
            return 1.0
        
        return sequential / parallel
    
    def validate_dag(self) -> tuple[bool, List[str]]:
        """
        Validate DAG for cycles and orphaned tasks.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle_dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = self.dag.get_task(task_id)
            if task:
                for dep_id in task.dependencies:
                    if dep_id not in visited:
                        if has_cycle_dfs(dep_id):
                            return True
                    elif dep_id in rec_stack:
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        # Check each task
        for task_id in self.dag.tasks.keys():
            if task_id not in visited:
                if has_cycle_dfs(task_id):
                    errors.append(f"Cycle detected involving task {task_id}")
        
        # Check for invalid dependencies (referencing non-existent tasks)
        for task_id, task in self.dag.tasks.items():
            for dep_id in task.dependencies:
                if dep_id not in self.dag.tasks:
                    errors.append(f"Task {task_id} depends on non-existent task {dep_id}")
        
        return len(errors) == 0, errors
    
    def get_dependency_tree(self, task_id: str) -> Dict:
        """
        Get dependency tree for a specific task.
        
        Args:
            task_id: Root task ID
        
        Returns:
            Dictionary representing dependency tree
        """
        task = self.dag.get_task(task_id)
        if not task:
            return {}
        
        tree = {
            'id': task_id,
            'description': task.description,
            'status': task.status.value,
            'dependencies': []
        }
        
        for dep_id in task.dependencies:
            dep_tree = self.get_dependency_tree(dep_id)
            if dep_tree:
                tree['dependencies'].append(dep_tree)
        
        return tree
    
    def print_execution_plan(self):
        """Print execution plan with levels"""
        levels = self.get_execution_levels()
        
        print("\n" + "="*60)
        print("EXECUTION PLAN")
        print("="*60)
        print(f"Total tasks: {self.dag.get_task_count()}")
        print(f"Execution levels: {len(levels)}")
        print(f"Max parallelization: {max(len(level) for level in levels) if levels else 0} tasks")
        print(f"Sequential time estimate: {self.estimate_sequential_time()}s")
        print(f"Parallel time estimate: {self.estimate_parallel_time()}s")
        print(f"Speedup factor: {self.get_parallelization_benefit():.2f}x")
        print("="*60)
        
        for i, level in enumerate(levels):
            print(f"\nLevel {i} ({len(level)} task(s), can run in parallel):")
            for task_id in level:
                task = self.dag.get_task(task_id)
                if task:
                    deps = f" [depends on: {task.dependencies}]" if task.dependencies else ""
                    print(f"  - {task.description[:50]}{deps}")
        
        print("="*60 + "\n")
