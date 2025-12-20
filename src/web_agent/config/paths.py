"""
Path configuration - always works in development and production.
"""

import os
from pathlib import Path

# === Always resolve from this file's location ===
# src/web_agent/config/paths.py → project root
PACKAGE_ROOT = Path(__file__).parent.parent  # web_agent/
PROJECT_ROOT = PACKAGE_ROOT.parent.parent  # project root

# === OmniParser (external, at project root) ===
OMNIPARSER_ROOT = PROJECT_ROOT / "OmniParser"
OMNIPARSER_WEIGHTS = OMNIPARSER_ROOT / "weights"
ICON_DETECT_MODEL = OMNIPARSER_WEIGHTS / "icon_detect" / "model.pt"
ICON_CAPTION_MODEL = OMNIPARSER_WEIGHTS / "icon_caption_qwen"

# === User data directories ===
USER_DATA_DIR = Path.home() / ".web-agent"
DATA_DIR = USER_DATA_DIR / "data"
LOGS_DIR = USER_DATA_DIR / "logs"
SCREENSHOTS_DIR = USER_DATA_DIR / "screenshots"
CACHE_DIR = USER_DATA_DIR / ".cache"

# Environment overrides
DATA_DIR = Path(os.getenv("WEB_AGENT_DATA", DATA_DIR))
LOGS_DIR = Path(os.getenv("WEB_AGENT_LOGS", LOGS_DIR))
SCREENSHOTS_DIR = Path(os.getenv("WEB_AGENT_SCREENSHOTS", SCREENSHOTS_DIR))

# Create directories
for directory in [DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# === Logging ===
LOG_FILE = LOGS_DIR / "agent.log"


# === Helper functions ===
def get_relative_path(target: Path) -> str:
    """Get path relative to project root"""
    try:
        return str(target.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(target)
