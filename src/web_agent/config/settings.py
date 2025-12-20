"""Global configuration settings"""

import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Browser Settings (defined early so other settings can reference it)
BROWSER_HEADLESS = False
# Desktop viewport size (16:10 aspect ratio to match 1920x1200 screen)
# Using 1440×900 - standard desktop resolution that fits well on 1920x1200 displays
BROWSER_WINDOW_SIZE = (1440, 900)
BROWSER_TIMEOUT = 30000  # milliseconds

# OmniParser Configuration
OMNIPARSER_ROOT = PROJECT_ROOT / "OmniParser"
OMNIPARSER_WEIGHTS = OMNIPARSER_ROOT / "weights"
ICON_DETECT_MODEL = OMNIPARSER_WEIGHTS / "icon_detect" / "model.pt"
ICON_CAPTION_MODEL = OMNIPARSER_WEIGHTS / "icon_caption_qwen"

# OmniParser Settings
BOX_THRESHOLD = 0.01
IOU_THRESHOLD = 0.9
USE_PADDLE_OCR = False  # Use EasyOCR (faster, more accurate, less RAM than PaddleOCR)
# Match browser width to avoid downscaling (was 640, caused 50%+ resolution loss)
OMNIPARSER_IMGSZ = BROWSER_WINDOW_SIZE[0]  # 1440px - same as browser width
# Reduced batch size for lower RAM usage (128 → 16)
# NOTE: batch_size parameter removed from get_som_labeled_img calls (not in gradio demo)
# This setting is kept for future use if needed
OMNIPARSER_BATCH_SIZE = 16

# Agent Limits
MASTER_TOKEN_LIMIT = 2000
WORKER_TOKEN_LIMIT = 8000
MAX_WORKER_DEPTH = 3
# Max action iterations per worker task
MAX_ACTION_ITERATIONS = 50  # Increased from 10 to allow more complex tasks

# Timeouts
# Increase task and action timeouts to accommodate longer interaction cycles with the game.
TASK_TIMEOUT = 300  # seconds
ACTION_TIMEOUT = None  # Removed - no hard timeout, rely on iterations limit
VERIFICATION_TIMEOUT = 30  # seconds

# Cache Settings
LLM_CACHE_TTL = 3600  # seconds
DOM_CACHE_TTL = 30  # seconds
ENABLE_L1_CACHE = True
ENABLE_L2_CACHE = False

# SQLite Database Settings (disk-based storage for memory efficiency)
DB_DIR = PROJECT_ROOT / ".cache"
WORKER_MEMORY_DB = DB_DIR / "worker_memory.db"
ACCOMPLISHMENTS_DB = DB_DIR / "accomplishments.db"

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = PROJECT_ROOT / "logs" / "agent.log"
ENABLE_DEBUG_OUTPUT = True
