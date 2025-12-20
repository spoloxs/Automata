"""
Supervision Package

AI-powered supervisor that monitors execution, handles failures,
and makes intelligent decisions to keep execution on track.
"""

from web_agent.supervision.decision_engine import DecisionEngine, SupervisorDecision
from web_agent.supervision.health_monitor import ExecutionHealth, HealthMonitor

__all__ = [
    "DecisionEngine",
    "SupervisorDecision",
    "HealthMonitor",
    "ExecutionHealth",
]
