"""Agent-specific configuration"""

WORKER_CONFIG = {
    "max_iterations": 10,
    "action_timeout": 30,
    "verification_required": True,
    "save_screenshots": True,
}

MASTER_CONFIG = {
    "max_parallel_workers": 4,
    "global_timeout": 300,
    "enable_exploration": True,
    "max_exploration_steps": 3,
}

PLANNER_CONFIG = {
    "max_steps": 10,
    "enable_delegation": True,
    "prefer_simple_plans": True,
}
