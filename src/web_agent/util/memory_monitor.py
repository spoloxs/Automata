"""
Memory Monitor - Track system RAM usage (not VRAM)
"""

import psutil
import os
from typing import Dict, Optional
from web_agent.util.logger import log_info, log_debug, log_warn


class MemoryMonitor:
    """Monitor and log system RAM usage"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.baseline_ram = None
    
    def get_ram_usage(self) -> Dict[str, float]:
        """
        Get current RAM usage in MB.
        
        Returns:
            Dict with process_ram_mb, system_ram_used_mb, system_ram_percent
        """
        # Process memory (RSS = Resident Set Size, actual RAM used)
        process_mem = self.process.memory_info()
        process_ram_mb = process_mem.rss / (1024 * 1024)
        
        # System memory
        system_mem = psutil.virtual_memory()
        system_ram_used_mb = system_mem.used / (1024 * 1024)
        system_ram_percent = system_mem.percent
        
        return {
            "process_ram_mb": round(process_ram_mb, 1),
            "system_ram_used_mb": round(system_ram_used_mb, 1),
            "system_ram_percent": round(system_ram_percent, 1),
        }
    
    def log_ram(self, label: str = "", level: str = "info"):
        """
        Log current RAM usage with optional label.
        
        Args:
            label: Description of what's happening (e.g., "After planner.create_plan")
            level: Log level (info, debug, warn)
        """
        usage = self.get_ram_usage()
        
        message = (
            f"🧠 RAM {label}: "
            f"Process={usage['process_ram_mb']:.0f}MB, "
            f"System={usage['system_ram_used_mb']:.0f}MB ({usage['system_ram_percent']:.1f}%)"
        )
        
        if level == "info":
            log_info(message)
        elif level == "debug":
            log_debug(message)
        elif level == "warn":
            log_warn(message)
    
    def set_baseline(self):
        """Set baseline RAM to measure growth"""
        self.baseline_ram = self.get_ram_usage()["process_ram_mb"]
        log_info(f"🧠 RAM Baseline: {self.baseline_ram:.0f}MB")
    
    def log_delta_from_baseline(self, label: str = ""):
        """Log RAM change from baseline"""
        if self.baseline_ram is None:
            self.log_ram(label)
            return
        
        current = self.get_ram_usage()
        delta = current["process_ram_mb"] - self.baseline_ram
        sign = "+" if delta >= 0 else ""
        
        message = (
            f"🧠 RAM {label}: "
            f"{current['process_ram_mb']:.0f}MB ({sign}{delta:.0f}MB from baseline)"
        )
        
        if abs(delta) > 500:  # Warn if >500MB growth
            log_warn(message)
        else:
            log_info(message)


# Global instance for easy access
_memory_monitor: Optional[MemoryMonitor] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get singleton memory monitor"""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


def log_ram(label: str = ""):
    """Convenience function to log RAM"""
    get_memory_monitor().log_ram(label)
