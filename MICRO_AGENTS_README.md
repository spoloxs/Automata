# Micro-Agent Delegation Architecture

## Overview

The micro-agent architecture reduces LLM hallucination by separating complex tasks into simple, focused subtasks. Each micro-agent has ONE responsibility and uses simple prompts.

## Benefits

### 🎯 Reduced Hallucination
**Before (Single-Phase):**
```
Worker: "Click the login button"
↓
LLM must:
1. Understand what "login button" means
2. Find it in 50+ elements
3. Get correct element ID
4. Generate click action
↓
High complexity = High hallucination risk
```

**After (Two-Phase with Micro-Agents):**
```
Worker: identify_and_click(description="Button with text 'Login'")
↓
Phase 1: ElementIdentifier
├─ Simple prompt: "Which element matches 'Button with text Login'?"
├─ ONLY job: match description to ID
└─ Returns: element_id = 15
↓
Phase 2: ClickAgent
├─ Simple task: Click element 15
└─ Executes click
↓
Low complexity = Low hallucination
```

### ✅ Additional Benefits
- **Separation of Concerns** - Planning vs. execution separated
- **Better Element Identification** - Dedicated agent for matching
- **Reusable Specialists** - Each micro-agent optimized for ONE task
- **Optional Usage** - Workers can still use direct actions when element ID is known

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ WorkerAgent (High-Level Planner)                        │
│ - Decides WHAT to do                                    │
│ - Can delegate to micro-agents OR use direct actions    │
└─────────────┬───────────────────────────────────────────┘
              │
              ├──→ Direct Actions (when element ID known)
              │    └─ click(element_id=15)
              │    └─ type(element_id=20, text="hello")
              │
              └──→ Micro-Agent Delegation (description-based)
                   └─ MicroAgentCoordinator
                      ├─ Phase 1: ElementIdentifier
                      │   └─ Finds element matching description
                      │   └─ Returns element_id
                      │
                      └─ Phase 2: Execution Agent
                          ├─ ClickAgent
                          ├─ TypeAgent
                          └─ NavigationAgent
```

## Components

### 1. MicroAgentBase
Base class for all micro-agents with standard interface.

### 2. ElementIdentifierAgent
**Responsibility:** Match element descriptions to element IDs

**Simple Prompt:**
```
Which element matches "Button with text 'Login'"?

Available elements:
[ID 1] Button: "Submit"
[ID 15] Button: "Login"
[ID 20] Link: "Register"

Return: element ID or "NOT_FOUND"
```

**Usage:**
```python
result = await element_identifier.execute({
    "description": "Button with text 'Login'",
    "elements": current_elements,
    "context": "Need to log in to site"
})
# Returns: {"element_id": 15}
```

### 3. ClickAgent
**Responsibility:** Click verified element IDs

**Simple Task:** Just click, no complex reasoning needed

**Usage:**
```python
result = await click_agent.execute({
    "element_id": 15,
    "reason": "To open login form"
})
```

### 4. TypeAgent
**Responsibility:** Type text into verified element IDs

**Usage:**
```python
result = await type_agent.execute({
    "element_id": 20,
    "text": "username@example.com",
    "reason": "Enter email for login"
})
```

### 5. NavigationAgent
**Responsibility:** Navigate to URLs

**Usage:**
```python
result = await navigation_agent.execute({
    "url": "https://example.com",
    "reason": "To access login page"
})
```

### 6. MicroAgentCoordinator
**Responsibility:** Orchestrate two-phase actions

**Two-Phase Click:**
```python
result = await coordinator.click_element_by_description(
    description="Button with text 'Login'",
    elements=current_elements,
    context="Need to log in"
)
# Phase 1: Identifies element → ID 15
# Phase 2: Clicks element 15
```

**Two-Phase Type:**
```python
result = await coordinator.type_into_element_by_description(
    description="Email input field",
    text="user@example.com",
    elements=current_elements
)
# Phase 1: Identifies element → ID 20
# Phase 2: Types into element 20
```

## New Tools

### identify_and_click
```json
{
  "name": "identify_and_click",
  "description": "TWO-PHASE: Identify element by description, then click it",
  "parameters": {
    "description": "Element description (e.g., 'Button with text Login')",
    "context": "Why you need this element (optional)",
    "reasoning": "Why using two-phase instead of direct click"
  }
}
```

**Example:**
```python
# LLM decides to use two-phase click
await action_handler.handle_action(BrowserAction(
    action_type=ActionType.IDENTIFY_AND_CLICK,
    parameters={
        "description": "Red submit button",
        "reasoning": "Not sure of exact element ID"
    }
))
```

### identify_and_type
```json
{
  "name": "identify_and_type",
  "description": "TWO-PHASE: Identify element by description, then type into it",
  "parameters": {
    "description": "Element description (e.g., 'Email input field')",
    "text": "Text to type once identified",
    "context": "Why you need this element (optional)",
    "reasoning": "Why using two-phase instead of direct type"
  }
}
```

**Example:**
```python
# LLM decides to use two-phase type
await action_handler.handle_action(BrowserAction(
    action_type=ActionType.IDENTIFY_AND_TYPE,
    parameters={
        "description": "Password field",
        "text": "secret123",
        "reasoning": "Need to find password input first"
    }
))
```

## When to Use Each Approach

### Use Direct Actions When:
- ✅ Element ID is known from previous step
- ✅ Element was just found via visual analysis
- ✅ Working with stable, numbered elements

**Example:**
```python
# Element ID already known from element list
click(element_id=15, reasoning="Click login button")
```

### Use Micro-Agent Delegation When:
- ✅ Describing element by appearance/text
- ✅ Element ID uncertain
- ✅ Need to find element first
- ✅ Reduce hallucination risk

**Example:**
```python
# Description-based, let micro-agent find it
identify_and_click(
    description="Green button with text 'Next'",
    reasoning="Need to find Next button to proceed"
)
```

## Configuration

### Enable/Disable Micro-Agents

**In GeminiAgent:**
```python
gemini_agent = GeminiAgent(
    enable_micro_agents=True  # Enable delegation tools
)
```

**In tool_definitions.py:**
```python
tools = get_browser_tools(
    enable_visual_analysis=True,
    enable_micro_agents=True  # Include delegation tools
)
```

## Error Handling

Each micro-agent returns `AgentResult`:

```python
@dataclass
class AgentResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    confidence: float = 1.0
    reasoning: str = ""
```

**Success:**
```python
AgentResult(
    success=True,
    data={"element_id": 15},
    reasoning="Identified login button"
)
```

**Failure:**
```python
AgentResult(
    success=False,
    error="No element found matching 'Login button'",
    reasoning="Element identifier could not find match"
)
```

## Integration with Hierarchical History

Micro-agent actions are recorded in **both** stores:

### ActionHistoryStore (Technical Audit)
```python
{
    "action_type": "identify_and_click",
    "target": "Button with text 'Login'",
    "success": True,
    "before_context": {...},
    "after_context": {...},
    "changes_observed": ["URL changed to /dashboard"]
}
```

### AccomplishmentStore (Agent Learning)
```python
"✓ Two-phase click: Button with text 'Login' → navigated to /dashboard"
```

## Testing

**Test Element Identification:**
```python
async def test_element_identifier():
    identifier = ElementIdentifierAgent(gemini_agent)
    result = await identifier.execute({
        "description": "Button with text 'Submit'",
        "elements": test_elements
    })
    assert result.success
    assert result.data["element_id"] == expected_id
```

**Test Two-Phase Action:**
```python
async def test_identify_and_click():
    coordinator = MicroAgentCoordinator(gemini_agent, action_handler)
    result = await coordinator.click_element_by_description(
        description="Login button",
        elements=test_elements
    )
    assert result.success
    assert result.data["clicked"] == True
```

## Performance Considerations

**Micro-agent delegation adds:**
- 1 additional LLM call (ElementIdentifier)
- ~1-2 seconds latency for identification
- Reduced overall failure rate (fewer retries needed)

**Trade-off:**
- Slightly slower per action
- Much higher success rate
- Fewer failed attempts = faster overall task completion

## Best Practices

1. **Use delegation for ambiguous elements**
   ```python
   # Good: Description-based when unsure
   identify_and_click(description="Red submit button")
   
   # Good: Direct when ID known
   click(element_id=15)
   ```

2. **Provide context to help identification**
   ```python
   identify_and_type(
       description="Email field",
       text="user@example.com",
       context="Need to log in to account"  # Helps narrow search
   )
   ```

3. **Be specific in descriptions**
   ```python
   # Better: Specific
   "Blue button with text 'Next Step'"
   
   # Worse: Vague
   "Next button"
   ```

4. **Monitor accomplishments to see what works**
   ```python
   # Accomplishment shows full outcome
   "✓ Two-phase click: Blue Next button → form submitted, 5 new fields visible"
   ```

## Example Workflow

```python
# Worker decides action sequence
actions = [
    # Use delegation when finding element
    identify_and_click(
        description="Login link in top right",
        reasoning="Need to find login link first"
    ),
    
    # Use delegation for form fields
    identify_and_type(
        description="Email or username input",
        text="user@example.com",
        reasoning="Description-based field identification"
    ),
    
    identify_and_type(
        description="Password input field",
        text="secret123",
        reasoning="Find password field by description"
    ),
    
    # Direct action when element ID known
    click(
        element_id=25,  # Submit button found in previous observation
        reasoning="Click submit button to login"
    )
]
```

## Summary

The micro-agent architecture provides:
- ✅ **Reduced hallucination** through focused, simple prompts
- ✅ **Better element identification** with dedicated agent
- ✅ **Flexibility** - use delegation OR direct actions
- ✅ **Complete tracking** - all actions recorded with outcomes
- ✅ **Production-ready** - all files tested and validated

Use micro-agents when element identification is uncertain. Use direct actions when element IDs are known. The LLM chooses the best approach based on context.
