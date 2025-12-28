"""
Prompt builder for Gemini interactions.
Constructs prompts for action decisions and verification.
"""

from typing import Any, Dict, List, Optional


class PromptBuilder:
    """Builds prompts for different Gemini interactions"""

    @staticmethod
    def build_action_prompt(
        task: str,
        elements_text: str,
        url: str,
        storage_data: Dict[str, Any],
        viewport_size: tuple,
        accomplishment_summary: Optional[str] = None,
    ) -> str:
        """
        Build prompt for action decision.

        Args:
            task: Task description
            elements_text: Formatted elements string
            url: Current URL
            storage_data: Data in worker memory
            viewport_size: Browser viewport dimensions
            accomplishment_summary: Summary of what's already been done

        Returns:
            Formatted prompt string
        """
        # Build accomplishment section if provided
        accomplishments_section = ""
        if accomplishment_summary:
            accomplishments_section = f"""
**What You've Already Accomplished:**
{accomplishment_summary}

"""
        
        prompt = f"""You are a web automation agent executing a specific task.

**Current Task:**
{task}

**Current Page:**
URL: {url}
Viewport: {viewport_size[0]}x{viewport_size[1]}

**Available Elements:**
{elements_text}

**Stored Data:**
{storage_data if storage_data else "No data stored yet"}
{accomplishments_section}
**CRITICAL DECISION RULES - 100% Confidence Required:**

⚠️ **NEVER ACT ON UNCERTAINTY** ⚠️
1. If you're NOT 100% certain what to click/type → STOP and use analyze_visual_content
2. If you can't find an element → STOP and use analyze_visual_content  
3. If the task is unclear → STOP and ask for ALL details via analyze_visual_content
4. If you're guessing → STOP, you're doing it wrong!

**When to Use Deep Visual Analysis:**
- "Play the game" → Ask: "What button starts the game? Where is it? What are ALL interactive elements?"
- "Click start" but no start button visible → Ask: "Find ALL buttons and clickable elements with coordinates"
- "Fill the form" but unsure which fields → Ask: "Find ALL input fields with their labels and coordinates"
- ANY uncertainty → Ask comprehensive question to get COMPLETE info

**Instructions:**
1. Analyze the current page state and task objective
2. **IF UNCERTAIN:** Use analyze_visual_content with comprehensive question to get ALL info
3. **IF CERTAIN:** Decide the NEXT action(s) using exact coordinates/data
4. Use the provided tools to interact with the page
5. **ONLY call mark_task_complete when:**
   - You have EXECUTED all required actions (not just planned them!)
   - You can SEE concrete evidence of task completion on the current page
   - The task's success criteria are visibly met
   - ⚠️ **NEVER mark complete based on what you THINK happened - only based on what you SEE!**

**Important Guidelines:**
- If the current URL is `about:blank` or does not match the target URL, your first action MUST be to use the 'navigate' tool to go to the correct URL. The user's goal is "{task}". The target URL is likely mentioned in the goal.
- Only interact with elements that are visible and interactivity=True
- **Use COORDINATES for interactions**: Each element shows its center position (x, y) in pixels
- **Click/Type using x, y coordinates**: Use click(x=640, y=360) and type(x=640, y=360, text="...")
- Example: If you see "Submit button at (640, 360)", use click(x=640, y=360, reasoning="Click submit button")
- **Use EXACT pixel coordinates** from the element list - don't guess or estimate
- Break complex actions into simple steps
- Call mark_task_complete ONLY when task is fully accomplished
- Be precise and deliberate with each action
- **You have a time limit of ~2 minutes per task** - work efficiently and strategically
- You can call **multiple tools in one decision** to be more efficient (e.g., type + press_enter together)
- Use get_accomplishments tool if you need to check what's been tried before

**⚠️ About Visual Analysis Tool (analyze_visual_content):**

This tool uses Gemini Vision API and is **SLOW (5-10 seconds) and EXPENSIVE (API costs)**. 

**Recommended workflow - try these steps FIRST:**

1. **Check Available Elements list thoroughly**
   - Read through ALL elements in the list
   - Look for keywords, descriptions that match what you need
   - Element list already has most interactive elements!

2. **Try scrolling if element not visible**
   - Many elements are off-screen
   - Scroll down/up to reveal more elements
   - Check element list again after scrolling

3. **Use get_element_details for more info**
   - Get coordinates, colors, DOM info for specific elements
   - Helps verify you have the right element

4. **Try navigation or exploration**
   - Check menus, navigate to related pages
   - Explore semantically related areas

**When visual analysis makes sense:**
- Element genuinely NOT in list after thorough checking and scrolling
- Complex visual patterns (grids, game boards) that OmniParser missed
- Overlays/modals not parsed properly
- Need to understand overall page structure

**If you decide to use visual analysis:**
- Ask comprehensive questions to get ALL info in ONE call
- ❌ Inefficient: "Where is button?" then later "Where is cell 1?" (2 calls = 10-20 seconds)
- ✅ Efficient: "Find ALL interactive elements: buttons, grid cells, inputs with coordinates" (1 call = 5-10 seconds)

Remember: Element list already has most elements - check it first!

**SEMANTIC EXPLORATION GUIDANCE:**
When looking for specific content, explore semantically related areas FIRST:

- **Looking for games/puzzles (crossword, wordle, etc.)?** → Check:
  * Navigation menus: "Games", "Puzzles", "Entertainment", "Play"
  * Footer sections: "More from...", "Features"
  * Header sections: Common placement for game links
  * Try navigate tool if you know direct URL patterns

- **Looking for login/account features?** → Check:
  * Top-right corner (common web pattern)
  * Navigation menu: "Sign In", "Account", "Profile", "My Account"
  * Footer: "Customer Service", "Help"

- **Looking for specific articles/content?** → Check:
  * Search functionality FIRST (fastest path)
  * Category/section navigation matching topic
  * Related content sections/sidebars
  * Homepage links if on subpage

**Strategy:**
1. Think WHERE this content would logically be placed
2. Check those semantic areas FIRST before random exploration
3. Use navigate tool if you know the likely URL structure
4. Use analyze_visual_content if not in obvious semantic locations

**CRITICAL: Tool Selection Strategy**

1. **PREFERRED: Use Two-Phase Actions (identify_and_click / identify_and_type)**
   - These tools are safest and most robust.
   - You provide a description (e.g., "Submit button"), and the system finds and clicks it.
   - Use this when:
     - You know what you want but coordinates are cluttered
     - You want to be sure you hit the right thing
     - Element ID might be unstable

2. **Direct Coordinates (click / type)**
   - Use ONLY if you see the EXACT element in the "Available Elements" list.
   - **ONLY use coordinates from the list** - NEVER guess or estimate.
   - **Use x, y parameters**: click(x=640, y=360) NOT element_id
   - **Coordinates are in pixels**: (0, 0) is top-left, values shown in element list
   - **Use EXACT coordinates**: Don't round or approximate - use what's shown

**Preventing Hallucination & Ensuring Accuracy:**
- ❌ NEVER guess coordinates - only use coordinates you see in the element list
- ❌ NEVER skip elements - if you got 10 cells, interact with all 10
- ❌ NEVER make up coordinates - use analyze_visual_content if element not in list
- ✅ ALWAYS verify coordinates exist before interacting
- ✅ ALWAYS use ALL elements returned from visual analysis
- ✅ ALWAYS use x, y parameters: click(x=640, y=360) NOT element_id
- If visual analysis returns 10 elements with coordinates, interact with ALL using those exact coordinates

**Using Your Memory (store_data tool):**
- **Actively use store_data** to remember important things YOU discover
- Store patterns you observe (e.g., "pattern_guess_feedback": "green=close, red=far")
- Store failed attempts (e.g., "failed_guesses": ["word1", "word2"])
- Store working strategies (e.g., "working_approach": "semantic similarity from flower")
- Store page quirks/behaviors you learn
- **This is YOUR memory** - use it proactively to avoid repeating work and to build understanding

What action(s) should you take next?"""

        return prompt

    @staticmethod
    def build_verification_prompt(
        task: str,
        elements_text: str,
        url: str,
        storage_data: Dict[str, Any],
        action_history: List[Dict],
    ) -> str:
        """
        Build prompt for task verification.

        Args:
            task: Original task description
            elements_text: Current page elements
            url: Current URL
            storage_data: Extracted data
            action_history: Actions that were executed

        Returns:
            Formatted prompt string
        """
        action_summary = "\n".join(
            [
                f"- {action.action_type}: {action.success}"
                for action in action_history[-10:]  # Last 10 actions
            ]
        )

        prompt = f"""You are verifying whether a task has been completed successfully.

**Original Task:**
{task}

**Actions Taken:**
{action_summary}

**Current Page State:**
URL: {url}

**Visible Elements:**
{elements_text}

**Extracted Data:**
{storage_data if storage_data else "No data extracted"}

**Your Task:**
Determine if the original task's GOAL has been completed successfully.

**CRITICAL VERIFICATION RULES:**
1. **Focus on GOAL, not element presence**: If the task was "click CONTINUE button", success means the button was clicked and the page progressed - NOT that the button is still visible!
2. **Element IDs are EPHEMERAL**: Element IDs from the task description (e.g., "click element 12") may not exist on current page - this is NORMAL after page changes
3. **Page changes indicate progress**: If task was to interact with an overlay/modal/dialog and it's now GONE, that's SUCCESS, not failure
4. **Verify OUTCOME, not process**: 
   - Task: "Dismiss cookie banner" → Success: banner is gone
   - Task: "Click Continue on overlay" → Success: overlay disappeared, main content visible
   - Task: "Submit form" → Success: confirmation message or next page loaded
5. **Use the screenshot**: Visual confirmation is more reliable than element lists

Return a JSON object with:
{{
    "completed": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation of why task is/isn't complete",
    "evidence": ["list", "of", "supporting", "evidence"],
    "issues": ["list", "of", "problems", "if", "any"]
}}

**Guidelines:**
- Verify the task's INTENDED OUTCOME was achieved
- Missing task elements after interaction = likely SUCCESS (they were removed/hidden)
- Check if the page STATE matches expected post-task state
- Only mark failed if clear evidence goal was NOT achieved
- Provide clear reasoning for your decision"""

        return prompt

    @staticmethod
    def build_planning_prompt(
        goal: str, url: str, elements_text: str, exploration_history: List[str],
        visual_insights: Optional[Dict] = None,
        accomplishment_summary: Optional[str] = None
    ) -> str:
        """
        Build prompt for task planning/decomposition.

        Args:
            goal: High-level goal
            url: Starting URL
            elements_text: Initial page elements
            exploration_history: Previous exploration actions
            visual_insights: Deep visual analysis from Gemini Vision
            accomplishment_summary: What has already been accomplished

        Returns:
            Formatted prompt string
        """
        exploration_summary = (
            "\n".join(exploration_history)
            if exploration_history
            else "No exploration yet"
        )
        
        # Include accomplishment history to prevent repetition
        accomplishment_section = ""
        if accomplishment_summary:
            accomplishment_section = f"""
**WHAT HAS ALREADY BEEN ACCOMPLISHED:**
The following actions have already been completed successfully. DO NOT repeat these in your plan:

{accomplishment_summary}

⚠️ CRITICAL: Review this list carefully before planning!
- If a step has been completed, DON'T plan it again
- Build on what's already done
- Only plan NEW actions that haven't been tried yet
- If stuck repeating, try a different approach
"""

        prompt_template = """You are a TASK PLANNING AGENT for a web automation system. Your job is to create a CONCRETE, SPECIFIC plan for the NEXT PHASE of work based on what is CURRENTLY VISIBLE on the page.

        ⚠️  **CRITICAL: RESPECT EXPLORATION HISTORY** ⚠️
        - Review the **Exploration Summary** carefully.
        - Actions listed there have **ALREADY BEEN PERFORMED** (e.g., dismissing popups, clicking buttons).
        - **DO NOT** create steps for actions that were already successful in the exploration phase.
        - If the exploration summary says "Dismissed cookie popup", do NOT plan to dismiss it again.
        - If exploration failed to do something, ONLY THEN should you plan to try it again (perhaps differently).

        ⚠️  **CRITICAL: ITERATIVE PLANNING PHILOSOPHY** ⚠️
        
        - You are creating a plan for the IMMEDIATE next steps only
        - Plan ONLY for elements and actions that are VISIBLE RIGHT NOW
        - DO NOT plan for future pages, hidden elements, or content that doesn't exist yet
        - After your plan completes, the system will AUTOMATICALLY REPLAN based on the new page state
        - Think "What can I do NOW?" not "What's the complete solution?"
        - Keep plans SHORT (2-7 steps typically) and focused on visible next actions
        
        **Example:**
        - Goal: "Play the Contexto game and find the secret word"
        - Current page: Shows input field and submit button
        - ❌ BAD: Plan 50 steps to solve the entire game
        - ✅ GOOD: Plan to (1) type first guess, (2) submit, (3) observe feedback
        - After those 3 steps, the system will REPLAN based on what feedback appears!

        ⚠️  **CRITICAL: NO VAGUE TASKS - BE SPECIFIC** ⚠️
        
        - EVERY task must reference SPECIFIC, VISIBLE elements from the Available Elements list
        - NEVER create tasks for things you can't find in the current page state
        - If something isn't visible now, create a task to FIND it first (scroll, navigate, search)
        - Use EXACT element descriptions from the list
        
        **Bad vs Good task examples:**
        - ❌ BAD: "Navigate to the crossword section" (how? where is it?)
        - ✅ GOOD: "Click the 'Games' link in the top navigation menu at coordinates [X, Y]"
        - ❌ BAD: "Play the game" (which game? how?)
        - ✅ GOOD: "Click the 'Start Game' button visible in the center panel"
        - ❌ BAD: "Find the video player" (not a task, no action)
        - ✅ GOOD: "Scroll down to reveal more content and locate video elements"

        You DO NOT execute actions yourself. You ONLY design the plan for the CURRENT phase.

        ==================== INPUT CONTEXT ====================

        **Goal (overall objective):**
        <GOAL>

        **Starting Page:**
        URL: <URL>

        **Available Elements on the page (parsed UI):**
        <ELEMENTS>

        **Exploration Summary (what has already been done / observed):**
        <EXPLORATION>

        ======================================================

        Your job is to output a CLEAR, CONCRETE PLAN that a separate execution agent can follow step-by-step.

        ### General Planning Principles

        - Think like a senior automation engineer designing a workflow for a web macro.
        - Steps must be grounded in what is actually visible or interactable on the page (from `Available Elements`).
        - Prefer a SMALL number of meaningful steps over dozens of tiny ones, but:
          - Each step MUST be *atomic* and *verifiable* (the executor can clearly tell if it succeeded).
          - Each step MUST be *actionable* using typical browser actions (click, type, press_enter, scroll, wait_for, etc.).
        - Respect dependencies: do not plan to use data or UI that does not exist yet.
        - Avoid assumptions about hidden pages or magical navigation; if a URL or button is not present, do not plan to use it.

        ### Step Design Requirements

        For EACH step you create:

        1. **Single clear objective**
           - Example: "Type 'thing' into the input field labeled 'type a word'".
           - Not allowed: "Type a query, press Enter, and analyze results" (that is multiple steps).

        2. **Atomic and verifiable**
           - The executor should be able to answer "Did this succeed?" using page state.
           - Good: "Click the button with text 'Submit'."
           - Good: "Confirm that a result list appears containing at least one item."
           - Avoid vague goals like "Understand the page better".

        3. **Grounded in current UI - DESCRIPTIVE ONLY**
           - **NEVER use Element IDs (e.g., [12]) or Coordinates in the plan steps.**
           - Elements change IDs and positions constantly. Your plan must be robust to these changes.
           - Describe elements by their **visual properties, text labels, and context**.
           - The Worker Agent will resolve the specific ID/coordinate at runtime.
           
           Examples:
           - ✅ GOOD: "Click the 'Submit' button visible in the form area"
           - ✅ GOOD: "Type into the input field next to the 'Email' label"
           - ❌ BAD: "Click element [12]" (IDs change!)
           - ❌ BAD: "Click at (500, 300)" (Coordinates change!)
           
           **If an element you need is NOT in the Available Elements list:**
           - Create a task to scroll/explore to find it
           - OR create a task to use visual analysis to locate it
           - OR use navigate tool to go directly to where it should be

        4. **Dependency-aware**
           - Use `dependencies` to specify which earlier steps must complete before this one.
           - If a step requires a prior search, login, or navigation, mark that dependency explicitly.

        5. **Loop / iterative behavior**
           - If the goal requires repetition (e.g., “keep guessing until you find the secret word”):
             - Do NOT explode this into hundreds of steps.
             - Instead, create ONE higher-level “delegate” step that describes the loop logic in detail.
             - Example: “Analyze the feedback for each guess and iteratively submit new guesses until the target condition (position #1) is met.”
           - Mark such steps with `"type": "delegate"`.

        6. **Types of steps**
           - `"direct"`: Can be executed with a short, deterministic sequence of browser actions (e.g., click, type, press_enter).
           - `"delegate"`: Requires iterative reasoning, exploration, or multiple internal actions (e.g., playing a game until a condition is met, multi-step semantic refinement).
           - Prefer `direct` where possible; use `delegate` when the number of internal actions is unknown or open-ended.

        7. **Time estimates**
           - `estimated_time_seconds` should be a rough guess, not exact.
           - Simple direct steps: 5–20 seconds.
           - Complex delegate steps: 60–300 seconds or more, depending on the goal.

        ### Special Considerations for Web Tasks

        - If the current URL does not match the goal’s target domain or path, include an early step to navigate there.
        - If essential elements (inputs, buttons, forms) are missing from `Available Elements`, include a step to scroll, open menus, or otherwise expose them.
        - If user authentication, cookie banners, or modals are likely required, add steps to handle them explicitly (e.g., “Close cookie consent dialog if visible”).

        ### Output Format (IMPORTANT)

        Return a single JSON object with this exact structure and keys:

        {
          "steps": [
            {
              "number": 1,
              "name": "Short step name",
              "description": "Precise, detailed description of what the executor should do and what success looks like.",
              "type": "direct or delegate",
              "dependencies": [],
              "estimated_time_seconds": 15
            },
            {
              "number": 2,
              "name": "Next step name",
              "description": "Describe the concrete browser-level interactions or iterative behavior.",
              "type": "direct or delegate",
              "dependencies": [1],
              "estimated_time_seconds": 30
            }
          ],
          "complexity": "simple | moderate | complex",
          "estimated_total_time": 120
        }

        ### Additional Requirements

        - Step numbers MUST be consecutive integers starting from 1.
        - `dependencies` MUST refer only to previous step numbers.
        - `complexity` reflects the overall plan difficulty:
          - `"simple"`: 1–3 steps, minimal branching.
          - `"moderate"`: 3–7 steps, some dependencies.
          - `"complex"`: Many steps, loops, or multi-page flows.
        - Make sure the plan is COMPLETE enough that, if all steps succeed, the original goal will be satisfied.

        Now, using the context above, generate the JSON plan.
        """

        # Use safe, unique placeholders in the template above and then replace them so we
        # avoid f-string formatting conflicts with braces in the JSON example.
        prompt = (
            prompt_template.replace("<GOAL>", goal)
            .replace("<URL>", url)
            .replace("<ELEMENTS>", elements_text)
            .replace("<EXPLORATION>", exploration_summary)
        )

        return prompt

    @staticmethod
    def build_visual_analysis_prompt(
        question: str, context: Optional[str] = None, viewport_size: Optional[tuple] = None
    ) -> str:
        """
        Build prompt for visual analysis using Gemini Vision.

        Args:
            question: Specific question about the image
            context: Additional context
            viewport_size: (width, height) for coordinate normalization

        Returns:
            Formatted prompt string
        """
        # Build coordinate instruction based on viewport
        coord_instruction = ""
        if viewport_size:
            coord_instruction = f"""
**CRITICAL - Coordinate System:**
The viewport is {viewport_size[0]}x{viewport_size[1]} pixels.
Return coordinates as PIXEL values (not normalized!)
- Simply identify the pixel position on the screen where the element is located
- Example: if element is in center of {viewport_size[0]}x{viewport_size[1]} screen, return [640, 360]
- The system will automatically normalize these to match OmniParser's coordinate system
"""
        
        prompt = f"""Analyze this screenshot COMPREHENSIVELY and provide COMPLETE information:

**Question/Task:**
{question}

**Context:**
{context if context else "This is a web page screenshot. The worker agent needs complete information to act accurately."}
{coord_instruction}
**CRITICAL INSTRUCTIONS - Comprehensive Analysis:**

1. **Examine EVERYTHING visible** - Don't just answer the question minimally
2. **Detect the RED ARROW CURSOR** - Track where the agent is currently pointing
3. **Find ALL related elements** - If asked about a grid, return ALL cells. If asked about buttons, return ALL buttons
4. **Provide exact coordinates** - Center point AND bounding box for every element
5. **Group related elements** - If there's a pattern (grid, list, menu), identify all members
6. **Be exhaustive, not minimal** - The worker needs ALL the information in ONE response

**Examples of GOOD comprehensive responses:**

❌ BAD (minimal): "The start button is at [100, 200]"
✅ GOOD (comprehensive): Returns coordinates for start button, all grid cells, input fields, and any other interactive elements visible

❌ BAD (single item): "Cell at row 1, col 1 is at [150, 150]"  
✅ GOOD (complete set): Returns ALL cells in the grid with their coordinates in a structured list

**What to identify and return:**
- ALL buttons (with exact coordinates)
- ALL input fields (with exact coordinates)
- ALL clickable items (with exact coordinates)
- Grid/table structures (ALL cells with coordinates)
- Lists (ALL items with coordinates)
- Forms (ALL fields with coordinates)
- The cursor position if visible


Return a JSON object with COMPREHENSIVE data:
{{
    "answer": "your detailed answer to the question",
    "target_element_id": element_id_if_question_asks_for_one or null,
    "target_coordinates": [x_pixels, y_pixels] or null,
    "target_bbox": [x1_pixels, y1_pixels, x2_pixels, y2_pixels] or null,
    "confidence": 0.0-1.0,
    "cursor_position": [x_pixels, y_pixels] if you see a cursor/pointer on screen,
    "all_elements_found": [
        {{
            "id": sequential_number_starting_from_1,
            "description": "what this element is (e.g., 'Submit button', 'Email input field', 'Logo image')",
            "center_coordinates": [x_pixels, y_pixels],
            "bbox": [x1_pixels, y1_pixels, x2_pixels, y2_pixels],
            "element_type": "button|link|input|image|text|icon|etc",
            "content": "visible text or label if any",
            "is_primary_target": true/false
        }}
    ]
}}

**IMPORTANT**: The all_elements_found array should include EVERY significant element you can see on screen, not just the target. This provides comprehensive context for navigation and interaction planning.

Answer the question now with full element details."""

        return prompt
