"""
Result data structures for task and execution results.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


@dataclass
class ActionResult:
    """Result from executing a single browser action"""
    action_type: str                    # click, type, navigate, etc.
    success: bool
    target: Optional[str] = None        # Element ID or description
    error: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'action_type': self.action_type,
            'success': self.success,
            'target': self.target,
            'error': self.error,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


@dataclass
class VerificationResult:
    """Result from task verification"""
    completed: bool                     # Is task complete?
    confidence: float                   # 0.0 to 1.0
    reasoning: str                      # Why task is/isn't complete
    evidence: List[str] = field(default_factory=list)  # Supporting evidence
    issues: List[str] = field(default_factory=list)    # Found issues
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'completed': self.completed,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'evidence': self.evidence,
            'issues': self.issues
        }


@dataclass
class TaskResult:
    """
    Result from executing a single task by a worker.
    """
    task_id: str
    success: bool
    
    # Execution details
    action_history: List[ActionResult] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[VerificationResult] = None
    
    # Timing
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    
    # Worker info
    worker_id: Optional[str] = None
    worker_thread_id: Optional[str] = None
    
    # Error info
    error: Optional[str] = None
    error_details: Optional[str] = None
    
    # Replan request (worker detected task-screen mismatch)
    needs_replan: bool = False
    replan_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'task_id': self.task_id,
            'success': self.success,
            'action_history': [a.to_dict() for a in self.action_history],
            'extracted_data': self.extracted_data,
            'verification': self.verification.to_dict() if self.verification else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'worker_id': self.worker_id,
            'worker_thread_id': self.worker_thread_id,
            'error': self.error,
            'error_details': self.error_details
        }


@dataclass
class ExecutionResult:
    """
    Final result from master agent executing a goal.
    Aggregates results from all tasks.
    """
    goal: str
    success: bool
    confidence: float
    
    # Task results
    task_results: List[TaskResult] = field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    # Aggregated data
    all_actions: List[ActionResult] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    
    # Verification
    verification: Optional[VerificationResult] = None
    
    # Timing
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    total_duration: Optional[float] = None
    
    # Metrics
    token_usage: Dict[str, int] = field(default_factory=dict)
    worker_count: int = 0
    
    # Error summary
    errors: List[str] = field(default_factory=list)
    
    def add_task_result(self, task_result: TaskResult):
        """Add a task result to aggregated results"""
        self.task_results.append(task_result)
        self.all_actions.extend(task_result.action_history)
        self.extracted_data.update(task_result.extracted_data)
        
        if task_result.success:
            self.completed_tasks += 1
        else:
            self.failed_tasks += 1
            if task_result.error:
                self.errors.append(f"Task {task_result.task_id}: {task_result.error}")
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'goal': self.goal,
            'success': self.success,
            'confidence': self.confidence,
            'task_results': [tr.to_dict() for tr in self.task_results],
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'all_actions': [a.to_dict() for a in self.all_actions],
            'extracted_data': self.extracted_data,
            'verification': self.verification.to_dict() if self.verification else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_duration': self.total_duration,
            'token_usage': self.token_usage,
            'worker_count': self.worker_count,
            'errors': self.errors
        }
    
    def __str__(self) -> str:
        """Human-readable summary"""
        lines = [
            f"\n{'='*60}",
            f"Execution Result: {'✅ SUCCESS' if self.success else '❌ FAILED'}",
            f"{'='*60}",
            f"Goal: {self.goal}",
            f"Confidence: {self.confidence:.1%}",
            f"",
            f"Tasks: {self.completed_tasks}/{self.total_tasks} completed",
            f"       {self.failed_tasks} failed",
            f"",
            f"Actions: {len(self.all_actions)} total",
            f"Duration: {self.total_duration:.2f}s" if self.total_duration else "Duration: N/A",
            f"Workers: {self.worker_count}",
        ]
        
        if self.errors:
            lines.append(f"\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")
        
        if self.verification:
            lines.append(f"\nVerification:")
            lines.append(f"  Reasoning: {self.verification.reasoning}")
            if self.verification.issues:
                lines.append(f"  Issues: {', '.join(self.verification.issues)}")
        
        lines.append(f"{'='*60}\n")
        return "\n".join(lines)
