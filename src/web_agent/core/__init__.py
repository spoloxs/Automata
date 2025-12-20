"""Core package - Master/Worker agents and task system"""
from web_agent.core.master_agent import MasterAgent
from web_agent.core.worker_agent import WorkerAgent
from web_agent.core.task import Task, TaskDAG, TaskStatus, TaskPriority
from web_agent.core.result import ExecutionResult, TaskResult, ActionResult, VerificationResult

__all__ = [
    'MasterAgent',
    'WorkerAgent',
    'Task',
    'TaskDAG',
    'TaskStatus',
    'TaskPriority',
    'ExecutionResult',
    'TaskResult',
    'ActionResult',
    'VerificationResult',
]
