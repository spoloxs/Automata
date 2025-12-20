# Detailed Architecture Documentation

## System Architecture Overview

The system follows a **3-tier hierarchical multi-agent architecture** with clear separation of concerns:

```
┌────────────────────────────────────────────────────────────────────┐
│                         MasterAgent                                 │
│                  (Singleton Orchestrator)                           │
│                                                                     │
│  Responsibilities:                                                  │
│  • Goal decomposition via Planner                                  │
│  • Plan→DAG conversion                                             │
│  • Supervision coordination                                        │
│  • Final verification & aggregation                                │
│  • Decision-driven continuation loops                              │
│                                                                     │
│  Shared Resources (Singleton):                                     │
│  • GeminiAgent (LLM interface)                                     │
│  • ScreenParser (OmniParser wrapper)                               │
│  • BrowserController (Playwright)                                  │
│  • ConversationManager (Redis-backed context)                      │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          │ spawns per DAG
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                    AISupervisorAgent                                │
│                   (Task Monitor & Recovery)                         │
│                                                                     │
│  Lifespan: Single TaskDAG execution                                │
│                                                                     │
│  Responsibilities:                                                  │
│  • Health monitoring (deadlock, progress, stuck detection)         │
│  • Worker lifecycle management (spawn, monitor, cleanup)           │
│  • AI-driven failure recovery (retry/skip/replan decisions)        │
│  • Accomplishment sharing across workers                           │
│  • Automatic replanning on worker request                          │
│                                                                     │
│  Key Features:                                                      │
│  • 30-second replan cooldown                                       │
│  • Max 3 consecutive skips (prevents loops)                        │
│  • 2-second supervision interval                                   │
│  • Conversation thread instrumentation                             │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          │ spawns per task
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                       WorkerAgent                                   │
│                  (Disposable Task Executor)                         │
│                                                                     │
│  Lifespan: Single task (max 50 iterations)                         │
│                                                                     │
│  Responsibilities:                                                  │
│  • Run ActionLoop (observe→decide→act cycle)                       │
│  • Execute browser actions via ActionHandler                       │
│  • Self-verification of task completion                            │
│  • Detect task-screen mismatches (request replan)                  │
│  • Record accomplishments to shared store                          │
│                                                                     │
│  Context Isolation:                                                 │
│  • Unique thread_id prevents Gemini context pollution             │
│  • Shared ScreenParser (cache efficiency)                          │
│  • Shared AccomplishmentStore (work deduplication)                 │
└────────────────────────────────────────────────────────────────────┘
```

## Component Deep Dive

### 1. MasterAgent (master_agent.py)

**Purpose**: Top-level orchestrator - long-running singleton coordinating entire automation session

**Singleton Pattern**: Only ONE MasterAgent instance allowed at a time to ensure resource sharing

**Key Methods**:
- `execute_goal(goal, starting_url)` - Main entry point
- `_verify_final_goal()` - Final verification after DAG execution
- `cleanup()` - Comprehensive resource cleanup (CUDA, Redis, browser, etc.)

**Execution Flow**:
```python
1. Navigate to starting_url (if provided)
2. Planner.create_plan(goal) → StructuredPlan
3. PlanToDAGConverter.convert(plan) → TaskDAG
4. AISupervisorAgent.supervise_execution(DAG)
5. Loop with decision engine:
   - Verify final goal
   - Ask decision_engine.should_continue()
   - If yes & DAG complete: create new plan → new DAG
   - Run another supervised execution pass
   - Repeat until decision engine says stop
6. Return ExecutionResult
```

**Shared Resources**:
- `GeminiAgent` - Single LLM interface for all agents
- `ScreenParser` - Single OmniParser instance (expensive to create)
- `BrowserController` - Shared browser page
- `ConversationManager` - Redis-backed conversation storage
- `TaskVerifier` - Verification logic

**Memory Management**:
- Aggressive cleanup on `cleanup()`
- Resets OmniParser singleton
- Clears CUDA cache
- Forces GC twice for cyclic references
- Clears Redis conversation store

### 2. AISupervisorAgent (supervisor_agent.py)

**Purpose**: Monitors and recovers individual DAG execution

**Lifespan**: Created per TaskDAG, disposed after completion

**Main Loop** (`_main_supervision_loop`):
```python
while not dag.is_complete():
    # Health check
    if health in [CRITICAL, DEGRADED] and can_replan():
        decision = _ai_health_intervention()
        execute_decision(decision)
    
    # Get ready tasks
    ready_tasks = dag.get_ready_tasks()
    
    if not ready_tasks:
        # Deadlock handling
        if can_replan():
            decision = _handle_deadlock()
            execute_decision(decision)
    
    # Execute tasks
    for task in ready_tasks[:max_workers]:
        dag.mark_task_running(task.id)
        result = _execute_task_with_recovery(task)
        
        # Check for worker replan request
        if result.needs_replan:
            # Worker detected mismatch - immediate replan
            decision = SupervisorDecision(REPLAN, ...)
            execute_decision(decision)
            continue
        
        if result.success:
            dag.mark_task_completed(task.id)
        else:
            dag.mark_task_failed(task.id)
            # AI-driven failure decision
            decision = _ai_failure_decision(task, result)
            execute_decision(decision)
```

**AI Recovery Decisions** (via DecisionEngine):
- `RETRY` - Reset task to PENDING for another attempt
- `SKIP` - Mark task skipped, unblock dependents
- `REPLAN` - Add recovery tasks to DAG
- `ABORT` - Mark all tasks complete (emergency exit)
- `WAIT` - Sleep 5 seconds (rate limiting)

**Health Monitoring** (via HealthMonitor):
- Tracks success rate, avg duration, stuck detection
- Deadlock detection (no ready tasks but incomplete tasks exist)
- Status: HEALTHY / DEGRADED / CRITICAL
- Concerns: "No progress in 60s", "Below 50% success rate", etc.

**Replan Protection**:
- 30-second cooldown between replans
- Max 3 consecutive SKIPs (forces REPLAN after 3rd)
- Worker replan requests BYPASS all restrictions

### 3. WorkerAgent (worker_agent.py)

**Purpose**: Disposable agent executing a single task

**Lifespan**: Created per task, max 50 action loop iterations

**Unique Thread ID**: `worker_worker_{task_id}_sup{N}_{uuid}`
- Prevents Gemini context pollution
- Allows parallel execution without interference

**Main Flow** (`execute_task`):
```python
# Feasibility check
feasible, reason = await _check_task_feasibility()
if not feasible:
    # Request replan via result flag
    return TaskResult(needs_replan=True, replan_reason=reason)

# Run action loop
result = await ActionLoop(
    task, browser, gemini, elements, ...
).run()

# Self-verification
verification = await _verify_completion()

return TaskResult(
    success=verification.completed,
    verification=verification,
    action_history=result.actions,
    ...
)
```

**Task Feasibility Check**:
- Compares task description to current screen elements
- Detects mismatches (e.g., task says "click search" but no search on screen)
- Sets `needs_replan=True` to trigger supervisor replan

### 4. ActionLoop (action_loop.py)

**Purpose**: Core observe-decide-act cycle within worker

**Loop Structure**:
```python
for iteration in range(max_iterations):
    # OBSERVE
    observation = await _observe()
    # - Capture screenshot
    # - Parse with OmniParser
    # - Check cache first (avoid redundant parsing)
    # - Enrich with DOM data
    # - Format for LLM
    
    # DECIDE
    decision = await _decide(observation)
    # - Build prompt with task + elements + history
    # - Call Gemini with structured tool definitions
    # - Get tool call (click, type, navigate, etc.)
    
    # ACT
    result = await _act(decision)
    # - Execute via ActionHandler
    # - Record to history
    # - Check if task marked complete
    
    if task_complete:
        break
```

**Iteration Limits**:
- Max 50 iterations (prevents infinite loops)
- Can be configured via `MAX_ACTION_ITERATIONS`

### 5. ActionHandler (action_handler.py)

**Purpose**: Executes browser actions with delays to prevent mis-clicks

**Supported Actions**:
- `click(element_id)` - Click on visual element
- `type(element_id, text)` - Type text into element  
- `press_enter()` - Press Enter key
- `navigate(url)` - Navigate to URL
- `scroll(direction, amount)` - Scroll page
- `wait(seconds)` - Wait for specified time
- `analyze_visual(element_id)` - Get detailed element info
- `store_data(key, value)` - Store extracted data
- `mark_complete(message)` - Mark task done
- `get_accomplishments()` - Retrieve shared accomplishments
- `scroll_to_result(query)` - Scroll to search result

**Action Delays** (prevents mis-clicks):
- Click: 0.3s before + 0.7s after = 1.0s total
- Type: 0.2s before + 0.5s after = 0.7s total
- Key press: 0.2s before + 0.5s after = 0.7s total

**Accomplishment Recording**:
- Workers record actions to shared AccomplishmentStore
- Other workers retrieve to avoid redundant work
- Example: If Worker A clicked "Login", Worker B won't click it again

### 6. Planner (planner.py)

**Purpose**: Decomposes high-level goals into structured plans

**Process**:
```python
async def create_plan(goal, starting_url, explore=True):
    # Optional: Explore page first
    if explore:
        elements = parse_screen()
        exploration_actions = _explore_page(elements)
        # Returns 3-5 key actions available on page
    
    # Call Gemini with structured output
    plan_data = await gemini.planning_llm.ainvoke(
        prompt=f"Create plan for: {goal}\n
                Available actions: {exploration_actions}"
    )
    
    # Convert to StructuredPlan
    plan = StructuredPlan.from_gemini_output(goal, plan_data)
    return plan
```

**StructuredPlan**:
- `goal`: High-level objective
- `steps`: List of Step objects
- `complexity`: Simple/Medium/Complex
- `estimated_total_time`: Time estimate in seconds

**Step Object**:
- `number`: Step number
- `description`: What to do
- `type`: NAVIGATION / INTERACTION / DATA_ENTRY / VERIFICATION / WAIT
- `dependencies`: List of step numbers this depends on
- `estimated_time`: Time estimate

### 7. PlanToDAGConverter (dag_converter.py)

**Purpose**: Converts StructuredPlan to executable TaskDAG

**Conversion Logic**:
```python
dag = TaskDAG()
for step in plan.steps:
    task = Task(
        id=uuid(),
        description=step.description,
        priority=HIGH if step.type == VERIFICATION else MEDIUM,
        dependencies=step.dependencies  # From plan
    )
    dag.add_task(task)

# Validate no cycles
if dag._has_cycle():
    raise ValueError("Plan contains circular dependencies")

return dag
```

**TaskDAG**:
- Directed Acyclic Graph of tasks
- Tracks task status (PENDING / RUNNING / COMPLETED / FAILED / SKIPPED)
- `get_ready_tasks()` - Returns tasks with all dependencies met
- `mark_task_completed/failed/skipped()` - State transitions
- `is_complete()` - All tasks in terminal state

### 8. ScreenParser (screen_parser.py)

**Purpose**: Wrapper around OmniParser for visual element detection

**Singleton Pattern**: Single instance shared across all agents

**Vision Models Used**:
- **OmniParser**: Icon detection model (icon_detect/model.pt)
- **Qwen2-VL**: Caption generation (icon_caption_qwen)
- **EasyOCR**: Text detection (default, faster than PaddleOCR)

**Caching**:
- SQLite-based screen cache
- Hashes screenshot → checks cache → returns cached parse if hit
- Avoids expensive OmniParser inference on repeated screens
- TTL: 3600 seconds (configurable)

**Parse Flow**:
```python
def parse(screenshot):
    # Check cache
    cache_key = hash_image(screenshot)
    cached = screen_cache.get(cache_key)
    if cached:
        return cached.elements
    
    # Parse with OmniParser
    elements = omniparser.process(screenshot)
    # elements = [{id, bbox, type, description, ...}, ...]
    
    # Enrich with DOM
    for element in elements:
        dom_data = browser.query_dom_at_position(element.x, element.y)
        element.update(dom_data)
    
    # Cache result
    screen_cache.set(cache_key, elements)
    
    return elements
```

**Element Format**:
```python
{
    'id': 1234,  # Visual element ID
    'bbox': [x1, y1, x2, y2],
    'center': [x, y],
    'type': 'button',  # From OmniParser
    'text': 'Search',  # From Qwen2-VL
    'description': 'Blue search button',
    # DOM enrichment:
    'tag': 'button',
    'role': 'search',
    'class': 'search-btn',
    'clickable': True,
}
```

### 9. GeminiAgent (gemini_agent.py)

**Purpose**: Unified interface to Google Gemini with structured outputs

**Model**: All LLMs use `gemini-2.5-pro` (hardcoded in gemini_agent.py)

**Multiple LLM Instances** (different schemas):
- `planning_llm` - Plan creation (returns PlanOutput schema)
- `action_llm` - Action decisions (returns tool calls via bind_tools)
- `verification_llm` - Task verification (returns VerificationOutput)
- `decision_llm` - Supervisor decisions (returns DecisionOutput)
- `health_llm` - Health assessment (returns HealthAssessmentOutput)
- `continuation_llm` - Continue decision (returns ContinueDecision)
- `vision_llm` - Visual analysis (returns VisualAnalysisOutput)

**Thread Management**:
- Each worker has unique `thread_id`
- `chat_histories[thread_id]` = conversation history
- Prevents context pollution between workers
- `clear_thread()` - Clean up after worker disposal

**Structured Outputs** (LangChain):
```python
# Example: action_llm
action_llm = ChatGoogleGenerativeAI(...).with_structured_output(
    ActionToolCall  # Pydantic model
)
result = await action_llm.ainvoke(messages)
# result is validated ActionToolCall object, not JSON string
```

### 10. ConversationManager (redis_conversation_store.py)

**Purpose**: Persistent conversation storage for decision context

**Redis with In-Memory Fallback**:
- **Primary**: Redis (key: `conversation:{thread_id}`, TTL: 24h)
- **Fallback**: In-memory dict (if Redis unavailable/fails)
- Automatically falls back on Redis connection errors

**Message Format**:
```python
{
    'timestamp': 1234567890.123,
    'role': 'user' | 'assistant' | 'system' | 'supervisor',
    'content': 'Message text',
    'metadata': {...}  # Optional extra data
}
```

**Key Methods**:
- `append_event(thread_id, role, content, metadata)` - Add message
- `get_context(thread_id, recent=N)` - Get last N messages
- `set_summary(thread_id, summary)` - Store conversation summary
- `cleanup()` - Clear all threads

**Usage**:
- Planner records plan creation
- Supervisor records decisions, health checks
- Decision engine reads context for informed decisions
- Allows multi-pass execution with memory

### 11. AccomplishmentStore (accomplishment_store.py)

**Purpose**: Shared cache of completed work across workers

**Session-scoped**:
- Each supervision session gets unique store
- All workers in same session share the store
- Prevents redundant actions

**Operations**:
- `record_accomplishment(action_type, target, metadata)` - Worker records action
- `get_accomplishments()` - Worker retrieves all accomplishments
- `has_accomplished(action_type, target)` - Check if already done

**Example**:
```python
# Worker A:
await store.record_accomplishment(
    action_type='click',
    target='Login button',
    metadata={'element_id': 1234}
)

# Worker B (later):
accomplishments = await store.get_accomplishments()
# Sees that login was already clicked
# Skips redundant login action
```

## Data Flow Example: "Search Google for Python"

```
1. User → MasterAgent.execute_goal("Search Google for Python", "google.com")

2. MasterAgent navigates to google.com

3. Planner.create_plan():
   - Explores page → finds search box, buttons
   - Calls Gemini planning_llm
   - Returns StructuredPlan:
     Step 1: Click search box
     Step 2: Type "Python"  
     Step 3: Press Enter
     Step 4: Verify results loaded

4. PlanToDAGConverter.convert():
   - Creates TaskDAG with 4 tasks
   - Task 2 depends on Task 1
   - Task 3 depends on Task 2
   - Task 4 depends on Task 3

5. AISupervisorAgent.supervise_execution(DAG):
   
   Iteration 1:
   - get_ready_tasks() → [Task 1: "Click search box"]
   - Spawn Worker A with Task 1
   
   Worker A:
   - ActionLoop iteration 1:
     * OBSERVE: Screenshot → OmniParser → [search_box, logo, buttons...]
     * DECIDE: Gemini action_llm → click(element_id=search_box)
     * ACT: ActionHandler.click(search_box.x, search_box.y)
     * Record accomplishment: clicked search box
   - Verify: Search box focused? Yes
   - Return TaskResult(success=True)
   
   - dag.mark_task_completed(Task 1)
   - Task 2 becomes ready
   
   Iteration 2:
   - get_ready_tasks() → [Task 2: "Type Python"]
   - Spawn Worker B with Task 2
   
   Worker B:
   - Check accomplishments → search box already focused
   - ActionLoop iteration 1:
     * OBSERVE: Screenshot → parse
     * DECIDE: Gemini → type(search_box, "Python")
     * ACT: ActionHandler.type("Python")
   - Verify: Text appears? Yes
   - Return TaskResult(success=True)
   
   - dag.mark_task_completed(Task 2)
   - Task 3 becomes ready
   
   Iteration 3:
   - get_ready_tasks() → [Task 3: "Press Enter"]
   - Spawn Worker C with Task 3
   
   Worker C:
   - ActionLoop iteration 1:
     * OBSERVE: Screenshot
     * DECIDE: Gemini → press_enter()
     * ACT: ActionHandler.press_key("Enter")
     * Wait for navigation
   - Return TaskResult(success=True)
   
   - dag.mark_task_completed(Task 3)
   - Task 4 becomes ready
   
   Iteration 4:
   - get_ready_tasks() → [Task 4: "Verify results"]
   - Spawn Worker D with Task 4
   
   Worker D:
   - ActionLoop iteration 1:
     * OBSERVE: Screenshot → parse → [result1, result2, ...]
     * DECIDE: Gemini → analyze_visual(result1)
     * Verify: Results contain "Python"? Yes
     * Mark complete: mark_complete("Search results loaded")
   - Return TaskResult(success=True)
   
   - dag.mark_task_completed(Task 4)
   - dag.is_complete() → True
   - Return SupervisionResult(success=True, 4/4 tasks)

6. MasterAgent._verify_final_goal():
   - Screenshot → parse → elements
   - TaskVerifier: "Are search results showing for Python?"
   - Gemini verification_llm → VerificationResult(completed=True, confidence=0.95)

7. DecisionEngine.should_continue():
   - execution_state: 4/4 complete, verification: 95% confident
   - Gemini continuation_llm → should_continue=False

8. Return ExecutionResult(
     success=True,
     confidence=1.0,
     completed_tasks=4,
     total_tasks=4
   )
```

## Key Design Principles

### 1. Separation of Concerns
- **Master** = High-level orchestration (planning, verification)
- **Supervisor** = Execution monitoring & recovery
- **Worker** = Single-task execution

### 2. Resource Sharing
- Single ScreenParser (expensive to create)
- Single GeminiAgent (API rate limits)
- Single BrowserController (one browser instance)
- Shared AccomplishmentStore (work deduplication)

### 3. Context Isolation
- Each worker gets unique `thread_id`
- Prevents Gemini context pollution
- Allows parallel execution
- Clean disposal after task

### 4. Fail-Safe Recovery
- AI-driven decisions (not hardcoded rules)
- Health monitoring (stuck, deadlock, success rate)
- Automatic replanning on mismatch
- Cooldowns prevent rapid thrashing

### 5. Memory Efficiency
- Screen cache (avoid redundant OmniParser calls)
- Redis conversation store (not in-memory)
- Aggressive cleanup (CUDA cache, GC, singleton reset)
- Immediate deletion of large objects (screenshots, DAGs)

### 6. Type Safety
- Pydantic models for all data structures
- LangChain structured outputs (not JSON parsing)
- Validated schemas at compile time
- No string-based magic

## Performance Characteristics

### Resource Usage

| Component | RAM | VRAM | CPU | Notes |
|-----------|-----|------|-----|-------|
| OmniParser | 2-3 GB | 4-6 GB | High | Cached via ScreenParser |
| Qwen2-VL | 2-3 GB | 3-4 GB | High | Called by OmniParser |
| Gemini API | Minimal | N/A | Low | Cloud-based (gemini-2.5-pro) |
| Browser | 500 MB | N/A | Medium | Single instance |
| Redis | 50-100 MB | N/A | Low | Optional (has in-memory fallback) |
| **Total** | **~6-8 GB** | **~8-10 GB** | **Medium** | With GPU |

### Latency Breakdown

Typical action iteration (observe→decide→act):
- Screenshot: 50-100ms
- OmniParser (cache miss): 2-4s
- OmniParser (cache hit): <10ms
- Gemini API call: 500-1500ms
- Action execution: 200-500ms
- **Total (cache miss)**: ~4-6s
- **Total (cache hit)**: ~1-2s

### Optimization Strategies

1. **Screen Caching**
   - 80%+ cache hit rate on repeated screens
   - Reduces latency from 4s to 1s per iteration

2. **Accomplishment Sharing**
   - Prevents redundant work across workers
   - 30-50% fewer actions on complex workflows

3. **Parallel Execution**
   - Up to 4 workers running simultaneously
   - 2-3x speedup on independent tasks

4. **Early Feasibility Checking**
   - Detects mismatches before wasted iterations
   - Triggers immediate replan (saves 5-10 iterations)

---

*This architecture enables robust, intelligent web automation with self-healing capabilities and efficient resource usage.*
