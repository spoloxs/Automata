"""
Worker scheduler - Spawns and manages worker agents.
"""
import asyncio
import time
from typing import Callable, List, Dict
from collections import deque
from web_agent.core.task import TaskDAG, Task, TaskStatus
from web_agent.core.result import TaskResult
from web_agent.core.worker_agent import WorkerAgent

class WorkerScheduler:
    """
    Schedules and manages worker agents for parallel task execution.
    """
    def __init__(self, max_parallel_workers: int = 4):
        self.max_workers = max_parallel_workers
        self.active_workers: Dict[str, WorkerAgent] = {}
        self.task_results: Dict[str, TaskResult] = {}
    async def execute_dag(
        self,
        dag: TaskDAG,
        worker_factory: Callable[[Task], WorkerAgent],
        timeout: int = 300
    ) -> Dict[str, any]:
        print(f"\n🚀 Starting DAG execution")
        print(f"   Total tasks: {dag.get_task_count()}")
        print(f"   Max parallel workers: {self.max_workers}")
        start_time = time.time()
        pending_tasks = asyncio.Queue()
        ready_tasks = dag.get_ready_tasks()
        for task in ready_tasks:
            await pending_tasks.put(task)
        print(f"   📋 {len(ready_tasks)} tasks ready to start")
        async def worker_loop(worker_id: int):
            print(f"   🔧 Worker {worker_id} started")
            while True:
                if dag.is_complete():
                    break
                if time.time() - start_time > timeout:
                    print(f"   ⏱️  Worker {worker_id}: Global timeout reached")
                    break
                try:
                    task = await asyncio.wait_for(pending_tasks.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if dag.is_complete():
                        break
                    if dag.get_completed_count() < dag.get_task_count():
                        continue
                    else:
                        break
                print(f"   📌 Worker {worker_id} assigned task {task.id[:8]}")
                worker = worker_factory(task)
                self.active_workers[task.id] = worker
                try:
                    result = await worker.execute_task()
                    self.task_results[task.id] = result
                    await worker.cleanup()
                    del self.active_workers[task.id]
                    newly_ready = dag.get_ready_tasks()
                    for ready_task in newly_ready:
                        await pending_tasks.put(ready_task)
                    if newly_ready:
                        print(f"   ➕ {len(newly_ready)} new tasks became ready")
                except Exception as e:
                    print(f"   ❌ Worker {worker_id} error executing task {task.id[:8]}: {e}")
                    task.mark_failed(str(e))
                    self.task_results[task.id] = TaskResult(
                        task_id=task.id,
                        success=False,
                        error=str(e),
                        worker_id=f"worker_{worker_id}"
                    )
            print(f"   🛑 Worker {worker_id} finished")
        workers = [worker_loop(i) for i in range(self.max_workers)]
        await asyncio.gather(*workers)
        elapsed = time.time() - start_time
        completed = dag.get_completed_count()
        failed = dag.get_failed_count()
        print(f"\n📊 DAG execution complete")
        print(f"   ⏱️  Time: {elapsed:.2f}s")
        print(f"   ✅ Completed: {completed}/{dag.get_task_count()}")
        print(f"   ❌ Failed: {failed}/{dag.get_task_count()}")
        return {
            'completed': completed,
            'failed': failed,
            'total': dag.get_task_count(),
            'elapsed_time': elapsed,
            'task_results': self.task_results
        }
