"""
Result store for master agent.
Stores task results and provides aggregation.
"""
from typing import Dict, List, Optional
from web_agent.core.result import TaskResult

class ResultStore:
    """
    Stores and manages task results at the master level.
    """
    def __init__(self):
        self.results: Dict[str, TaskResult] = {}
    def store_result(self, result: TaskResult):
        self.results[result.task_id] = result
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        return self.results.get(task_id)
    def get_all_results(self) -> List[TaskResult]:
        return list(self.results.values())
    def get_successful_results(self) -> List[TaskResult]:
        return [r for r in self.results.values() if r.success]
    def get_failed_results(self) -> List[TaskResult]:
        return [r for r in self.results.values() if not r.success]
    def get_success_rate(self) -> float:
        if not self.results:
            return 0.0
        successful = len(self.get_successful_results())
        return successful / len(self.results)
    def clear(self):
        self.results.clear()
