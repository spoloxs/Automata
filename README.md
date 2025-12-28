# AI Web Automation Agent

A sophisticated multi-agent web automation system powered by **Google Gemini 2.5 Pro**, featuring visual perception via OmniParser, intelligent task planning, and autonomous self-supervised execution.

## Features

- **Multi-Agent Architecture** - Supervisor coordinates isolated worker agents to prevent token limit issues
- **Visual Perception** - OmniParser (using Qwen2-VL and EasyOCR) for accurate element detection without relying on DOM selectors
- **AI-Driven Planning** - Gemini decomposes complex goals into executable task DAGs
- **Self-Verification** - Agents verify their own task completion with confidence scoring
- **Adaptive Replanning** - Automatic recovery from failures with AI-driven decision making
- **Persistent Memory** - Workers share accomplishments across tasks to avoid redundant work
- **Type Safety** - LangChain + Pydantic for structured outputs

## Table of Contents

- [Architecture](#architecture)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Architecture

> **For detailed architecture documentation, see [README_ARCHITECTURE.md](README_ARCHITECTURE.md)**

### System Overview

The system follows a **3-tier hierarchical multi-agent architecture**:

```
┌───────────────────────────────────────────────────────────┐
│                    MasterAgent                             │
│                (Singleton Orchestrator)                    │
│                                                            │
│  • Goal decomposition → StructuredPlan                    │
│  • Plan → TaskDAG conversion                              │
│  • Supervisor coordination                                │
│  • Decision-driven continuation loops                     │
│  • Final verification & aggregation                       │
│                                                            │
│  Shared Resources (Singleton):                            │
│  • GeminiAgent (LLM) • ScreenParser (OmniParser)         │
│  • BrowserController • ConversationManager               │
└─────────────────────┬─────────────────────────────────────┘
                      │ spawns per DAG
                      ▼
┌───────────────────────────────────────────────────────────┐
│              AISupervisorAgent                             │
│            (Task Monitor & Recovery)                       │
│                                                            │
│  Lifespan: Single TaskDAG                                 │
│                                                            │
│  • Health monitoring (deadlock, stuck, progress)          │
│  • Worker lifecycle (spawn, monitor, cleanup)             │
│  • AI-driven failure recovery (RETRY/SKIP/REPLAN)         │
│  • AccomplishmentStore sharing                            │
│  • Automatic replanning on worker request                 │
│                                                            │
│  Key Limits: 30s replan cooldown, max 3 consecutive skips│
└─────────────────────┬─────────────────────────────────────┘
                      │ spawns per task
                      ▼
┌───────────────────────────────────────────────────────────┐
│                  WorkerAgent                               │
│             (Disposable Executor)                          │
│                                                            │
│  Lifespan: Single task (max 50 iterations)                │
│                                                            │
│  • ActionLoop: observe → decide → act                     │
│  • Task feasibility check (detect mismatches)             │
│  • Execute via ActionHandler (with delays)                │
│  • Self-verification of completion                        │
│  • Record accomplishments to shared store                 │
│                                                            │
│  Context Isolation: Unique thread_id per worker           │
└───────────────────────────────────────────────────────────┘
```

### Execution Flow

```
User Goal → MasterAgent
    ↓
1. Planner explores page & creates StructuredPlan
    ↓
2. PlanToDAGConverter → TaskDAG with dependencies
    ↓
3. AISupervisorAgent monitors DAG execution
    ├─ Spawns WorkerAgent per ready task
    ├─ WorkerAgent runs ActionLoop (observe-decide-act)
    ├─ Health monitoring & AI recovery decisions
    └─ Handles worker replan requests
    ↓
4. MasterAgent verifies final goal
    ↓
5. DecisionEngine decides whether to continue
    ├─ If yes & DAG complete: Create new plan
    └─ Loop until goal achieved or decision says stop
    ↓
Return ExecutionResult
```

### Key Components

**1. MasterAgent** (Singleton)
- **Purpose**: Top-level orchestrator coordinating entire session
- **Flow**: Navigate → Plan → DAG → Supervise → Verify → Loop
- **Shared Resources**: Single GeminiAgent, ScreenParser, Browser, Redis store
- **Memory**: Aggressive cleanup (CUDA cache, GC, singleton reset)

**2. AISupervisorAgent** (Per-DAG)
- **Purpose**: Monitors task execution & recovers from failures
- **Loop**: Health check → Ready tasks → Spawn workers → Handle results
- **AI Decisions**: RETRY (reset task), SKIP (unblock deps), REPLAN (add recovery), ABORT (exit)
- **Protection**: 30s cooldown, max 3 consecutive skips, worker requests bypass

**3. WorkerAgent** (Per-Task)
- **Purpose**: Executes single task with observe-decide-act loop
- **Feasibility**: Detects task-screen mismatches → requests replan
- **Thread ID**: `worker_worker_{task_id}_sup{N}_{uuid}` (isolation)
- **Limits**: Max 50 iterations per task

**4. ActionLoop** (Worker Core)
- **OBSERVE**: Screenshot → OmniParser (cached) → DOM enrichment
- **DECIDE**: Gemini structured output → tool call (click/type/etc)
- **ACT**: ActionHandler executes with delays (prevents mis-clicks)

**5. Supporting Systems**

- **ScreenParser**: OmniParser wrapper with SQLite cache (80%+ hit rate)
- **GeminiAgent**: gemini-2.5-pro with structured outputs (planning, actions, decisions, verification)
- **ConversationManager**: Conversation storage with Redis + in-memory fallback
- **AccomplishmentStore**: Session-scoped shared cache (work deduplication)
- **DecisionEngine**: AI-driven recovery & continuation decisions
- **HealthMonitor**: Tracks success rate, detects deadlocks, stuck situations

### Design Principles

1. **Separation of Concerns**: Master orchestrates, Supervisor monitors, Worker executes
2. **Resource Sharing**: Single expensive resources (OmniParser, Gemini, Browser)
3. **Context Isolation**: Unique thread_ids prevent Gemini pollution, enable parallelism
4. **AI-Driven Recovery**: No hardcoded rules - AI analyzes failures & decides actions
5. **Memory Efficiency**: Aggressive caching, cleanup, immediate object deletion
6. **Type Safety**: Pydantic models + LangChain structured outputs (no JSON parsing)

### Performance

**Resource Usage** (with GPU):
- RAM: ~6-8 GB (OmniParser + Qwen2-VL + Browser)
- VRAM: ~4-6 GB (Vision models)
- Latency: 1-2s per action (cache hit), 4-6s (cache miss)

**Optimizations**:
- Screen caching: 80%+ hit rate → 3-4x speedup
- Accomplishment sharing: 30-50% fewer redundant actions
- Parallel execution: Up to 4x workers → 2-3x speedup
- Early feasibility: Saves 5-10 wasted iterations per mismatch

## System Requirements

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **RAM** | 8 GB | 16+ GB |
| **GPU** | None (CPU inference) | NVIDIA GPU with 6GB+ VRAM for faster OmniParser |
| **Storage** | 8+ GB free space | 16+ GB free space |

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/spoloxs/automata.git
cd automata/web-agent
```

### 2. Create a Virtual Environment

It's recommended to use a virtual environment to avoid dependency conflicts.

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Setup OmniParser Weights

**IMPORTANT**: This project includes a **customized OmniParser** implementation in the `OmniParser/` directory. Do **NOT** use the original Microsoft OmniParser repository - always use the included version which has been optimized for this project.

Download the required pre-trained model weights:

```bash
# Download weights to the included OmniParser directory
cd OmniParser/weights

# Download icon detection model
wget https://huggingface.co/microsoft/OmniParser/resolve/main/icon_detect/model.safetensors -P icon_detect/

# Download caption model (choose one based on your preference if not using Qwen or EasyOCR for OCR):
# Option 1: Florence (recommended for better accuracy)
wget https://huggingface.co/microsoft/OmniParser/resolve/main/icon_caption_florence/model.safetensors -P icon_caption_florence/

# Option 2: BLIP2 (lighter alternative)
wget https://huggingface.co/microsoft/OmniParser/resolve/main/icon_caption_blip2/model.safetensors -P icon_caption_blip2/
```

**Required files structure:**
```
OmniParser/weights/
├── icon_detect/
│   └── model.safetensors
└── icon_caption_florence/  (or icon_caption_blip2/)
    └── model.safetensors
```

### 6. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your **Gemini API key**:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

**Note**: Some environment variables are still being migrated to use `.env` configuration. Most settings can be found in [src/web_agent/config/settings.py](src/web_agent/config/settings.py).

**Get Gemini API Key**: https://aistudio.google.com/app/apikey

### 7. Install and Start Redis

Redis is used for persistent conversation storage and caching:

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows (WSL2):**
```bash
sudo apt-get install redis-server
sudo service redis-server start
```

**Verify Redis is running:**
```bash
redis-cli ping  # Should return "PONG"
```

### 8. Verify Installation

```bash
python -c "import torch; print(f'PyTorch: {torch.__version__}')"
python -c "from playwright.async_api import async_playwright; print('Playwright OK')"
python -c "import redis; print(f'Redis: {redis.__version__}')"
python scripts/verify_setup.py
```

## Quick Start

### Simple Example

```python
import asyncio
from web_agent.core.master_agent import MasterAgent

async def main():
    # Initialize the master agent
    master = MasterAgent(max_parallel_workers=2)
    await master.initialize()

    try:
        # Execute the automation goal
        result = await master.execute_goal(
            goal="Search for 'Python asyncio tutorial' and click the first result",
            starting_url="https://www.google.com"
        )

        # Check results
        print(f"Success: {result.success}")
        print(f"Tasks completed: {result.completed_tasks}/{result.total_tasks}")
    finally:
        # Always cleanup resources
        await master.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

### Running Examples

```bash
# Simple search example
python examples/simple_search.py

# Form filling
python examples/form_filling.py

# Data extraction
python examples/data_extraction.py

# Interactive mode
python main.py
```

## Configuration

### Environment Variables (.env)

```env
# Gemini API
GEMINI_API_KEY=your_key_here
# Model is hardcoded to gemini-2.5-pro in gemini_agent.py

# Browser Settings
BROWSER_HEADLESS=false
BROWSER_TIMEOUT=30000  # milliseconds
BROWSER_WINDOW_SIZE=1440,900

# Agent Limits
MAX_WORKER_DEPTH=3
WORKER_TOKEN_LIMIT=100000
MAX_ACTION_ITERATIONS=50

# Memory & Caching
ENABLE_SCREEN_CACHE=true
CACHE_TTL_SECONDS=3600
ENABLE_ACCOMPLISHMENT_STORE=true

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARN, ERROR
```

### Settings (config/settings.py)

Key configuration options:

```python
# Vision Model Settings
OMNIPARSER_DEVICE = "cuda"  # or "cpu"
OMNIPARSER_BATCH_SIZE = 8

# LLM Settings
GEMINI_TEMPERATURE = 0.7
GEMINI_MAX_TOKENS = 8192

# Supervisor Settings
REPLAN_COOLDOWN_SECONDS = 30
MAX_CONSECUTIVE_SKIPS = 3
SUPERVISION_INTERVAL = 2.0  # seconds

# Worker Settings
ACTION_DELAY_BEFORE = 0.3  # seconds before click/type
ACTION_DELAY_AFTER = 0.7   # seconds after click/type
```

## Usage Examples

### Example 1: Web Search & Click

```python
result = await master.execute_goal(
    goal="Search for 'machine learning' on Google and click the Wikipedia result",
    starting_url="https://www.google.com"
)
```

### Example 2: Form Filling

```python
result = await master.execute_goal(
    goal="Fill out the contact form with name 'John Doe' and email 'john@example.com', then submit",
    starting_url="https://example.com/contact"
)
```

### Example 3: Data Extraction

```python
result = await master.execute_goal(
    goal="Extract the top 5 news headlines from the homepage",
    starting_url="https://news.ycombinator.com"
)

# Access extracted data
if result.success:
    print(result.extracted_data)
```

### Example 4: Multi-Step Workflow

```python
result = await master.execute_goal(
    goal="""
    1. Go to GitHub
    2. Search for 'web automation'
    3. Click on the first repository
    4. Star the repository
    5. Navigate to the Issues tab
    """,
    starting_url="https://github.com"
)
```

## Project Structure

```
web-agent/
├── config/                  # Configuration
│   └── settings.py          # Global settings
├── src/web_agent/           # Main source code
│   ├── core/                # Core agents
│   │   ├── master_agent.py      # Orchestrator
│   │   ├── supervisor_agent.py  # Task monitor
│   │   └── worker_agent.py      # Task executor
│   ├── planning/            # Task planning
│   │   ├── planner.py           # Goal decomposition
│   │   └── dag_converter.py     # Plan to DAG
│   ├── scheduling/          # Worker management
│   │   └── scheduler.py         # Worker pool
│   ├── execution/           # Action execution
│   │   ├── action_loop.py       # Observe-decide-act
│   │   ├── action_handler.py    # Action execution
│   │   └── browser_controller.py # Playwright wrapper
│   ├── perception/          # Visual perception
│   │   ├── screen_parser.py     # OmniParser integration
│   │   ├── omniparser_wrapper.py
│   │   └── element_formatter.py
│   ├── intelligence/        # LLM integration
│   │   ├── gemini_agent.py      # Gemini wrapper
│   │   ├── prompt_builder.py    # Prompt generation
│   │   └── tool_definitions.py  # Action schemas
│   ├── verification/        # Task verification
│   │   └── verifier.py          # Completion checking
│   ├── supervision/         # Health monitoring
│   │   ├── health_monitor.py    # Health tracking
│   │   └── decision_engine.py   # AI recovery
│   └── storage/             # Memory & caching
│       ├── screen_cache.py      # Screenshot cache
│       ├── accomplishment_store.py
│       └── worker_memory.py
├── OmniParser/              # Vision model (submodule)
├── examples/                # Usage examples
├── tests/                   # Unit & integration tests
├── scripts/                 # Utility scripts
├── .env.example             # Example environment file
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Project metadata
└── README.md                # This file
```

## How It Works

### Execution Flow

```
1. User provides goal → Master Agent
   ↓
2. Planner decomposes goal → Task DAG
   ↓
3. Scheduler creates Supervisor for DAG
   ↓
4. Supervisor spawns Workers for each task
   ↓
5. Worker executes Observe-Decide-Act loop
   │  ┌─→ Observe: Screenshot + OmniParser
   │  │  ┌─→ Decide: Gemini chooses action
   │  │  │  ┌─→ Act: Execute via Playwright
   │  │  │  │  ┌─→ Verify: Check completion
   │  └──┴──┴──┴──┘ (loop until done)
   ↓
6. Supervisor monitors health & recovers failures
   ↓
7. Master aggregates results & verifies goal
   ↓
8. Return final result to user
```

### Key Design Principles

1. **Separation of Concerns**
   - Master = Orchestration
   - Supervisor = Monitoring
   - Worker = Execution

2. **Context Isolation**
   - Each worker has unique `thread_id`
   - Prevents context pollution
   - Allows parallel execution

3. **Token Management**
   - Workers are disposable (auto-cleanup)
   - Master is persistent (session-long)
   - Structured outputs prevent token waste

4. **Intelligent Recovery**
   - AI-driven failure analysis
   - Automatic retry/skip/replan decisions
   - Health monitoring prevents deadlocks

5. **Visual-First Approach**
   - OmniParser for element detection
   - DOM enrichment for semantic context
   - Works on dynamic/Shadow DOM sites

## Troubleshooting

### Common Issues

**Issue: "OmniParser weights not found"**
```bash
# Download weights manually
cd OmniParser/weights
wget https://huggingface.co/microsoft/OmniParser/resolve/main/icon_detect/model.safetensors
```

**Issue: "Gemini API rate limit exceeded"**
- Wait 60 seconds between retries
- Reduce `max_parallel_workers` in MasterAgent
- Check API quota: https://aistudio.google.com/app/apikey

**Issue: "Browser timeout"**
- Increase `BROWSER_TIMEOUT` in .env
- Check internet connection
- Try headless mode: `BROWSER_HEADLESS=true`

**Issue: "CUDA out of memory"**
```python
# Use CPU for OmniParser
OMNIPARSER_DEVICE = "cpu"  # in config/settings.py
```

**Issue: "Worker stuck in infinite loop"**
- Check logs for "max iterations reached"
- Supervisor will auto-replan after cooldown
- Reduce `MAX_ACTION_ITERATIONS` if needed

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
python main.py
```

Or in code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Tips

1. **Enable GPU acceleration** (if available)
   ```python
   OMNIPARSER_DEVICE = "cuda"
   ```

2. **Use screen caching**
   ```python
   ENABLE_SCREEN_CACHE = True
   ```

3. **Reduce parallel workers** (if memory constrained)
   ```python
   master = MasterAgent(max_parallel_workers=1)
   ```

4. **Use headless mode** (faster)
   ```bash
   BROWSER_HEADLESS=true
   ```

## 🚧 Work in Progress

The following improvements are currently under development:

### Performance Optimizations
- **Faster execution** - Optimizing action delays and caching strategies
- **Reduced latency** - Streamlining observe-decide-act cycle
- **Better resource usage** - Memory management improvements

### iframe Support(It's able to detect and solve them but still needs some improvemens)
- **Cross-origin iframe handling** - Working on seamless iframe context switching
- **Complex nested iframes** - Support for deeply nested iframe structures
- **Crossword puzzles** - Specialized handling for iframe-based games and puzzles

### Vision System Improvements
- **Optimizing visual analysis** - Currently, when OmniParser can't detect elements, the system falls back to Gemini Vision API (sends full screenshots). Future improvements include:
  - Better OmniParser tuning and configuration
  - Enhanced DOM-based fallback strategies
  - Hybrid detection methods to reduce API calls
  - Improved element detection for complex UIs

### Planned Features
- Enhanced error recovery strategies with smarter retry logic
- Better handling of dynamic content and lazy-loaded elements
- Multi-page workflow optimization
- Faster plan generation and optimization
- Support for additional LLM providers (Claude, GPT-4, etc.)
