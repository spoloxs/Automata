"""
Structured error classification system for web automation tasks.

This module provides a hierarchical taxonomy of task failures to enable
intelligent decision-making without string matching or hacks.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorCategory(str, Enum):
    """High-level error categories"""
    TIMEOUT = "timeout"
    ELEMENT_NOT_FOUND = "element_not_found"
    ACTION_FAILED = "action_failed"
    NAVIGATION_ERROR = "navigation_error"
    VERIFICATION_FAILED = "verification_failed"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"


class TimeoutReason(str, Enum):
    """Specific reasons for timeout"""
    MAX_ITERATIONS = "max_iterations_reached"
    TIME_LIMIT = "time_limit_exceeded"
    NO_PROGRESS = "no_progress_detected"
    STUCK_STATE = "stuck_in_same_state"


@dataclass
class ProgressMetrics:
    """Structured progress information"""
    actions_executed: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    last_10_actions: List[Dict[str, Any]] = None
    convergence_detected: bool = False
    convergence_metric: Optional[str] = None
    convergence_value: Optional[Any] = None
    state_changes: int = 0
    unique_states_visited: int = 0
    
    def __post_init__(self):
        if self.last_10_actions is None:
            self.last_10_actions = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        total = self.actions_executed
        return (self.successful_actions / total) if total > 0 else 0.0
    
    @property
    def has_meaningful_progress(self) -> bool:
        """Determine if meaningful progress was made"""
        return (
            self.successful_actions > 0 and
            (self.state_changes > 0 or self.convergence_detected)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "actions_executed": self.actions_executed,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "success_rate": self.success_rate,
            "last_10_actions": self.last_10_actions,
            "convergence_detected": self.convergence_detected,
            "convergence_metric": self.convergence_metric,
            "convergence_value": self.convergence_value,
            "state_changes": self.state_changes,
            "unique_states_visited": self.unique_states_visited,
            "has_meaningful_progress": self.has_meaningful_progress,
        }


@dataclass
class StructuredError:
    """Structured representation of task errors"""
    category: ErrorCategory
    message: str
    progress_metrics: Optional[ProgressMetrics] = None
    timeout_reason: Optional[TimeoutReason] = None
    context: Dict[str, Any] = None
    is_recoverable: bool = True
    suggested_action: Optional[str] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "category": self.category.value,
            "message": self.message,
            "progress_metrics": self.progress_metrics.to_dict() if self.progress_metrics else None,
            "timeout_reason": self.timeout_reason.value if self.timeout_reason else None,
            "context": self.context,
            "is_recoverable": self.is_recoverable,
            "suggested_action": self.suggested_action,
        }


class ErrorClassifier:
    """Classifies error messages into structured error types"""
    
    @staticmethod
    def classify(error_message: str, progress_metrics: Optional[Dict] = None) -> StructuredError:
        """
        Classify an error message into a structured error type.
        
        Args:
            error_message: Raw error message from task failure
            progress_metrics: Optional progress metrics dictionary
            
        Returns:
            StructuredError with classification and context
        """
        if not error_message:
            return StructuredError(
                category=ErrorCategory.UNKNOWN,
                message="No error message provided",
                is_recoverable=False
            )
        
        # Convert progress metrics dict to ProgressMetrics object
        metrics = None
        if progress_metrics:
            metrics = ProgressMetrics(
                actions_executed=progress_metrics.get('actions_executed', 0),
                successful_actions=progress_metrics.get('successful_actions', 0),
                failed_actions=progress_metrics.get('failed_actions', 0),
                last_10_actions=progress_metrics.get('last_10_actions', []),
                convergence_detected=progress_metrics.get('convergence_detected', False),
                convergence_metric=progress_metrics.get('convergence_metric'),
                convergence_value=progress_metrics.get('convergence_value'),
                state_changes=progress_metrics.get('state_changes', 0),
                unique_states_visited=progress_metrics.get('unique_states_visited', 0),
            )
        
        error_lower = error_message.lower()
        
        # Timeout classification with reason detection
        if any(keyword in error_lower for keyword in ['timeout', 'timed out', 'time limit']):
            # Determine specific timeout reason
            timeout_reason = TimeoutReason.TIME_LIMIT
            if 'max iteration' in error_lower:
                timeout_reason = TimeoutReason.MAX_ITERATIONS
            elif metrics and not metrics.has_meaningful_progress:
                timeout_reason = TimeoutReason.NO_PROGRESS
            elif 'stuck' in error_lower or 'loop' in error_lower:
                timeout_reason = TimeoutReason.STUCK_STATE
            
            # Determine if recoverable based on progress
            is_recoverable = metrics.has_meaningful_progress if metrics else False
            suggested_action = "continue" if is_recoverable else "retry"
            
            return StructuredError(
                category=ErrorCategory.TIMEOUT,
                message=error_message,
                progress_metrics=metrics,
                timeout_reason=timeout_reason,
                is_recoverable=is_recoverable,
                suggested_action=suggested_action,
                context={
                    "detailed_reason": timeout_reason.value,
                    "progress_summary": f"Made progress: {metrics.has_meaningful_progress}" if metrics else "No metrics"
                }
            )
        
        # Element not found
        if any(keyword in error_lower for keyword in ['element not found', 'cannot find', 'no element']):
            return StructuredError(
                category=ErrorCategory.ELEMENT_NOT_FOUND,
                message=error_message,
                progress_metrics=metrics,
                is_recoverable=True,
                suggested_action="retry" if not metrics or metrics.actions_executed < 3 else "skip"
            )
        
        # Action failures
        if any(keyword in error_lower for keyword in ['click failed', 'type failed', 'action failed']):
            return StructuredError(
                category=ErrorCategory.ACTION_FAILED,
                message=error_message,
                progress_metrics=metrics,
                is_recoverable=True,
                suggested_action="retry"
            )
        
        # Navigation errors
        if any(keyword in error_lower for keyword in ['navigation', 'navigate', 'page load']):
            return StructuredError(
                category=ErrorCategory.NAVIGATION_ERROR,
                message=error_message,
                progress_metrics=metrics,
                is_recoverable=True,
                suggested_action="retry"
            )
        
        # Verification failures
        if any(keyword in error_lower for keyword in ['verification', 'verify', 'not complete']):
            return StructuredError(
                category=ErrorCategory.VERIFICATION_FAILED,
                message=error_message,
                progress_metrics=metrics,
                is_recoverable=True,
                suggested_action="skip"  # Verifications are often skippable
            )
        
        # System errors
        if any(keyword in error_lower for keyword in ['exception', 'error:', 'failed to']):
            return StructuredError(
                category=ErrorCategory.SYSTEM_ERROR,
                message=error_message,
                progress_metrics=metrics,
                is_recoverable=False,
                suggested_action="abort"
            )
        
        # Unknown error
        return StructuredError(
            category=ErrorCategory.UNKNOWN,
            message=error_message,
            progress_metrics=metrics,
            is_recoverable=True,
            suggested_action="retry"
        )
