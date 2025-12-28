"""
Action History Store - Structured storage of action outcomes and learnings.

This module tracks what each action did or didn't accomplish, enabling:
- Learning from past actions
- Avoiding repeated failures
- Understanding what works for specific elements/pages
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


@dataclass
class PageContext:
    """Context about the page state at the time of action"""
    url: str
    title: Optional[str] = None
    elements_count: int = 0
    viewport_size: Optional[tuple] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActionOutcome:
    """
    Detailed record of what an action accomplished.
    
    This captures not just success/failure but WHAT changed as a result.
    """
    # Basic action info
    action_type: str  # click, type, navigate, scroll, etc.
    target: Optional[str] = None  # Element ID or description
    parameters: Dict[str, Any] = field(default_factory=dict)  # e.g., text typed, scroll amount
    
    # Success/failure
    success: bool = False
    error: Optional[str] = None
    
    # Context
    before_context: Optional[PageContext] = None
    after_context: Optional[PageContext] = None
    
    # What changed (the key learnings)
    changes_observed: List[str] = field(default_factory=list)  # e.g., "Modal opened", "Form submitted"
    url_changed: bool = False
    new_elements_appeared: List[str] = field(default_factory=list)  # Descriptions of new elements
    elements_disappeared: List[str] = field(default_factory=list)
    
    # Expected vs actual
    expected_outcome: Optional[str] = None  # What we thought would happen
    actual_outcome: str = ""  # What actually happened
    outcome_matched: bool = False  # Did it match expectations?
    
    # Learning
    lesson_learned: Optional[str] = None  # What we learned from this action
    should_retry: bool = False  # Should this action be retried if it fails?
    retry_reason: Optional[str] = None
    
    # Metadata
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage/serialization"""
        return {
            'action_type': self.action_type,
            'target': self.target,
            'parameters': self.parameters,
            'success': self.success,
            'error': self.error,
            'before_context': self.before_context.to_dict() if self.before_context else None,
            'after_context': self.after_context.to_dict() if self.after_context else None,
            'changes_observed': self.changes_observed,
            'url_changed': self.url_changed,
            'new_elements_appeared': self.new_elements_appeared,
            'elements_disappeared': self.elements_disappeared,
            'expected_outcome': self.expected_outcome,
            'actual_outcome': self.actual_outcome,
            'outcome_matched': self.outcome_matched,
            'lesson_learned': self.lesson_learned,
            'should_retry': self.should_retry,
            'retry_reason': self.retry_reason,
            'timestamp': self.timestamp,
            'duration_ms': self.duration_ms
        }
    
    def to_summary(self) -> str:
        """Human-readable one-line summary"""
        status = "✅" if self.success else "❌"
        action_desc = f"{self.action_type}"
        if self.target:
            action_desc += f" on '{self.target}'"
        if self.parameters:
            # Add key parameters (like typed text)
            if 'text' in self.parameters:
                action_desc += f" with text '{self.parameters['text'][:20]}...'"
        
        result = f"{status} {action_desc}"
        if not self.success and self.error:
            result += f" → {self.error}"
        elif self.actual_outcome:
            result += f" → {self.actual_outcome}"
        
        return result


class ActionHistoryStore:
    """
    Stores and retrieves action history with structured outcomes.
    
    Enables agents to:
    - Learn from past actions
    - Avoid repeating failures
    - Understand patterns (e.g., "clicking X always opens modal Y")
    """
    
    def __init__(self):
        self.actions: List[ActionOutcome] = []
        self.patterns: Dict[str, List[str]] = {}  # Action patterns learned
        self.failed_attempts: Dict[str, int] = {}  # Track repeated failures
    
    def record_action(self, outcome: ActionOutcome):
        """Record an action outcome"""
        self.actions.append(outcome)
        
        # Track failures
        if not outcome.success and outcome.target:
            key = f"{outcome.action_type}_{outcome.target}"
            self.failed_attempts[key] = self.failed_attempts.get(key, 0) + 1
        
        # Learn patterns
        if outcome.success and outcome.changes_observed:
            pattern_key = f"{outcome.action_type}_{outcome.target}"
            if pattern_key not in self.patterns:
                self.patterns[pattern_key] = []
            self.patterns[pattern_key].extend(outcome.changes_observed)
    
    def get_recent_actions(self, count: int = 10) -> List[ActionOutcome]:
        """Get the most recent N actions"""
        return self.actions[-count:] if len(self.actions) >= count else self.actions
    
    def get_actions_by_type(self, action_type: str) -> List[ActionOutcome]:
        """Get all actions of a specific type"""
        return [a for a in self.actions if a.action_type == action_type]
    
    def get_failed_actions(self) -> List[ActionOutcome]:
        """Get all failed actions"""
        return [a for a in self.actions if not a.success]
    
    def get_successful_actions(self) -> List[ActionOutcome]:
        """Get all successful actions"""
        return [a for a in self.actions if a.success]
    
    def has_failed_repeatedly(self, action_type: str, target: str, threshold: int = 3) -> bool:
        """Check if this action has failed repeatedly"""
        key = f"{action_type}_{target}"
        return self.failed_attempts.get(key, 0) >= threshold
    
    def get_pattern_for_action(self, action_type: str, target: str) -> List[str]:
        """Get learned patterns for a specific action"""
        key = f"{action_type}_{target}"
        return self.patterns.get(key, [])
    
    def get_similar_successful_actions(
        self, 
        action_type: str, 
        similarity_threshold: float = 0.5
    ) -> List[ActionOutcome]:
        """
        Find successful actions similar to the given type.
        Useful for learning what works in similar situations.
        """
        successful = self.get_successful_actions()
        return [a for a in successful if a.action_type == action_type]
    
    def to_summary_string(self, recent: int = 5) -> str:
        """
        Create a human-readable summary of recent actions.
        This can be included in agent prompts.
        """
        if not self.actions:
            return "No previous actions recorded."
        
        recent_actions = self.get_recent_actions(recent)
        lines = [f"Recent Actions (last {len(recent_actions)}):"]
        
        for i, action in enumerate(recent_actions, 1):
            lines.append(f"{i}. {action.to_summary()}")
            if action.lesson_learned:
                lines.append(f"   💡 Learned: {action.lesson_learned}")
        
        # Add patterns summary
        if self.patterns:
            lines.append("\nLearned Patterns:")
            for pattern_key, outcomes in list(self.patterns.items())[:3]:
                lines.append(f"  • {pattern_key}: {', '.join(set(outcomes[:3]))}")
        
        # Add warnings about repeated failures
        repeated_failures = {k: v for k, v in self.failed_attempts.items() if v >= 2}
        if repeated_failures:
            lines.append("\n⚠️  Repeated Failures:")
            for action, count in repeated_failures.items():
                lines.append(f"  • {action}: failed {count} times")
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Export to dictionary for serialization"""
        return {
            'actions': [a.to_dict() for a in self.actions],
            'patterns': self.patterns,
            'failed_attempts': self.failed_attempts
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ActionHistoryStore':
        """Create from dictionary"""
        store = cls()
        # Reconstruct actions (simplified - would need full reconstruction)
        store.patterns = data.get('patterns', {})
        store.failed_attempts = data.get('failed_attempts', {})
        return store
    
    def clear(self):
        """Clear all history"""
        self.actions.clear()
        self.patterns.clear()
        self.failed_attempts.clear()


# Singleton instance
_action_history_store: Optional[ActionHistoryStore] = None


def get_action_history_store() -> ActionHistoryStore:
    """Get the global action history store instance"""
    global _action_history_store
    if _action_history_store is None:
        _action_history_store = ActionHistoryStore()
    return _action_history_store


def reset_action_history_store():
    """Reset the global store (for testing or new sessions)"""
    global _action_history_store
    if _action_history_store is not None:
        _action_history_store.clear()
    _action_history_store = None
