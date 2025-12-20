"""
Web Agent - Multi-agent web automation system.

Official Python Packaging Authority src layout.
"""
__version__ = "0.1.0"

from web_agent.core.master_agent import MasterAgent
from web_agent.core.worker_agent import WorkerAgent

__all__ = ["MasterAgent", "WorkerAgent"]
