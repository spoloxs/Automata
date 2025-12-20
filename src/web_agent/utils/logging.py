"""
Structured logging utilities.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from web_agent.config.settings import LOG_LEVEL, LOG_FILE, ENABLE_DEBUG_OUTPUT


class ColoredFormatter(logging.Formatter):
    """Colored console output formatter"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    log_level: str = LOG_LEVEL,
    log_file: Optional[Path] = LOG_FILE,
    enable_debug: bool = ENABLE_DEBUG_OUTPUT
):
    """
    Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (None to disable file logging)
        enable_debug: Enable debug output to console
    """
    # Create logger
    logger = logging.getLogger('web_agent')
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if enable_debug else logging.INFO)
    console_formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


# Global logger instance
logger = setup_logging()


def log_task_start(task_id: str, description: str):
    """Log task start"""
    logger.info(f"🎯 Task {task_id[:8]} started: {description}")


def log_task_complete(task_id: str, success: bool, duration: float):
    """Log task completion"""
    icon = "✅" if success else "❌"
    logger.info(f"{icon} Task {task_id[:8]} {'completed' if success else 'failed'} in {duration:.2f}s")


def log_action(action_type: str, success: bool, details: str = ""):
    """Log action execution"""
    icon = "✅" if success else "❌"
    logger.debug(f"{icon} Action: {action_type} {details}")


def log_error(error: str, details: Optional[str] = None):
    """Log error"""
    logger.error(f"❌ Error: {error}")
    if details:
        logger.debug(f"   Details: {details}")