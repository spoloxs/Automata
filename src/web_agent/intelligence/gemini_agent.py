"""
Gemini Agent - Handles all LLM interactions using Gemini 2.5 Pro.
WITH LANGCHAIN STRUCTURED OUTPUTS (PROPERLY!)
"""

import base64
import io
import time
import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InternalServerError
from PIL import Image
from pydantic import BaseModel, Field

from web_agent.config.settings import GEMINI_API_KEY
from web_agent.intelligence.prompt_builder import PromptBuilder
from web_agent.intelligence.tool_definitions import get_browser_tools
from web_agent.util.logger import log_debug, log_error, log_info, log_success, log_warn


# Pydantic Models for Structured Outputs
class VerificationOutput(BaseModel):
    completed: bool = Field(description="Whether the task is completed")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(description="Explanation of why task is/isn't complete")
    evidence: List[str] = Field(default_factory=list, description="Supporting evidence")
    issues: List[str] = Field(default_factory=list, description="Problems found")


class ContextoGameState(BaseModel):
    """Structured analysis of Contexto game state for strategic guessing."""
    best_guess: str = Field(description="The word with the lowest position number found so far")
    best_position: int = Field(description="The position number of the best guess")
    recent_guesses: List[str] = Field(description="List of recent guesses and their positions", default_factory=list)
    semantic_direction: str = Field(description="What semantic category/direction to explore next based on feedback")
    next_guess: str = Field(description="The strategic next word to guess")
    reasoning: str = Field(description="Detailed reasoning for the next guess")


class FoundElement(BaseModel):
    """Individual element found during visual analysis"""
    id: int = Field(description="Sequential ID starting from 1")
    description: str = Field(description="What this element is")
    center_coordinates: List[float] = Field(description="[x, y] pixel coordinates of element center point")
    bbox: List[float] = Field(description="[x1, y1, x2, y2] pixel bounding box")
    element_type: str = Field(description="Type: button, link, input, image, text, icon, etc")
    content: Optional[str] = Field(None, description="Visible text or label if any")
    is_primary_target: bool = Field(False, description="Whether this is the primary target of the question")


class VisualAnalysisOutput(BaseModel):
    answer: str = Field(description="Answer to the question")
    target_element_id: Optional[int] = Field(None, description="Element ID if found")
    target_coordinates: Optional[List[float]] = Field(
        None, description="[x, y] coordinates if found"
    )
    target_bbox: Optional[List[float]] = Field(
        None, description="[x1, y1, x2, y2] bounding box if found"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in answer")
    cursor_position: Optional[List[float]] = Field(
        None, description="[x, y] cursor position if visible on screen"
    )
    all_elements_found: List[FoundElement] = Field(
        default_factory=list, 
        description="All significant elements found on screen with their coordinates and bboxes"
    )


class PlanStep(BaseModel):
    number: int = Field(description="Step number")
    name: str = Field(description="Short step name")
    description: str = Field(description="Detailed description")
    type: str = Field(description="Step type: 'direct' or 'delegate'")
    dependencies: List[int] = Field(
        default_factory=list, description="Step numbers this depends on"
    )
    estimated_time_seconds: int = Field(description="Estimated time in seconds")


class PlanOutput(BaseModel):
    steps: List[PlanStep] = Field(description="List of plan steps")
    complexity: str = Field(description="Plan complexity: simple/moderate/complex")
    estimated_total_time: int = Field(description="Total estimated time in seconds")


class ContinueDecision(BaseModel):
    """
    Structured model for a simple continue/stop decision returned by the LLM.

    Note: We use the field alias "continue" so the LLM JSON may use that key,
    while the Python attribute name is `should_continue`.
    """

    should_continue: bool = Field(
        ..., alias="continue", description="Whether to continue supervised execution"
    )
    reason: Optional[str] = Field(
        None, description="One-line rationale for the decision"
    )


class DecisionOutput(BaseModel):
    """Structured decision output for supervisor decisions returned by the LLM."""

    action: str = Field(
        ..., description="Chosen action: retry|skip|replan|abort|wait|simplify"
    )
    reasoning: str = Field(..., description="Short explanation of the decision")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0-1")
    task_id: Optional[str] = Field(None, description="Task ID to retry/skip")
    alternative: Optional[str] = Field(
        None, description="Backup plan / alternative action"
    )
    simplify_plan: Optional[bool] = Field(
        False, description="Whether to simplify remaining plan"
    )
    suggested_continuation_attempts: Optional[int] = Field(
        None, description="Optional suggestion for additional supervised attempts"
    )


class HealthAssessmentOutput(BaseModel):
    """Structured health assessment output returned by the LLM."""

    assessment: str = Field(..., description="One-line assessment of execution health")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in assessment"
    )


class GeminiAgent:
    """
    Gemini-powered decision making agent using LangChain.
    Uses Gemini 2.5 Pro for all interactions with proper structured outputs.
    """

    def __init__(self, api_key: str = GEMINI_API_KEY, use_cache: bool = True, enable_micro_agents: bool = True):
        self.api_key = api_key
        self.model_name = "gemini-2.5-pro"
        self.use_cache = use_cache
        self.enable_micro_agents = enable_micro_agents
        
        # Initialize cache if enabled
        if self.use_cache:
            from web_agent.storage.screen_cache import get_screen_cache
            self.cache = get_screen_cache()
        else:
            self.cache = None
        
        self.action_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=2048,
        )
        from langchain_core.utils.function_calling import convert_to_openai_tool

        tools_schema = [convert_to_openai_tool(tool) for tool in get_browser_tools(
            enable_micro_agents=enable_micro_agents
        )]
        # Enable parallel tool calling by binding tools with proper configuration
        self.action_llm_with_tools = self.action_llm.bind_tools(
            tools_schema,
            tool_choice="auto"  # Allow model to choose which tools to call
        )
        self.verification_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=1024,
        ).with_structured_output(VerificationOutput)
        self.vision_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=1024,
        ).with_structured_output(VisualAnalysisOutput)
        self.planning_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.3,
            max_output_tokens=4096,
        ).with_structured_output(PlanOutput)

        # Continuation LLM: structured output used to ask the model whether to continue
        # supervised execution. This uses langchain's with_structured_output to ensure
        # we receive a typed response we can depend on rather than ad-hoc JSON parsing.
        # Continuation LLM: structured output used to ask the model whether to continue
        # supervised execution. Use langchain's with_structured_output to receive typed output.
        self.continuation_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.0,
            max_output_tokens=256,
        ).with_structured_output(ContinueDecision)

        # Decision LLM: structured output for supervisor decisions (retry/skip/replan/abort).
        # This gives DecisionEngine a typed response instead of relying on ad-hoc JSON extraction.
        self.decision_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.05,
            max_output_tokens=1024,
        ).with_structured_output(DecisionOutput)

        # Health assessment LLM: structured output for execution health analysis
        self.health_llm = ChatGoogleGenerativeAI(
            model=self.model_name,
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=512,
        ).with_structured_output(HealthAssessmentOutput)

        self.chat_histories: Dict[str, List] = {}
        log_info(f"🤖 GeminiAgent initialized with {self.model_name} (LangChain)")

    async def decide_action(
        self,
        task: str,
        elements: List[Any],
        url: str,
        thread_id: str,
        storage_data: Dict[str, Any],
        viewport_size: tuple,
        accomplishment_summary: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        log_info(f"\n      🤔 Gemini deciding action for thread {thread_id}...")
        log_debug(f"      Task: {task}")

        prompt = PromptBuilder.build_action_prompt(
            task=task,
            elements_text=str(elements),
            url=url,
            storage_data=storage_data,
            viewport_size=viewport_size,
            accomplishment_summary=accomplishment_summary,
        )
        
        # Structured logging: show first/last lines instead of arbitrary truncation
        prompt_lines = prompt.split('\n')
        if len(prompt_lines) > 20:
            log_preview = '\n'.join(prompt_lines[:10] + ['...'] + prompt_lines[-5:])
        else:
            log_preview = prompt
        
        log_debug("--- PROMPT SENT TO GEMINI ---")
        log_debug(log_preview)
        log_debug("-----------------------------")
        if thread_id not in self.chat_histories:
            self.chat_histories[thread_id] = []
        history = self.chat_histories[thread_id]
        
        # Context window management: keep only last 4 exchanges to prevent bloat
        # This dramatically reduces token count and decision latency
        MAX_HISTORY_PAIRS = 4  # Last 4 human-AI exchange pairs
        if len(history) > MAX_HISTORY_PAIRS * 2:
            # Keep only recent history
            history = history[-(MAX_HISTORY_PAIRS * 2):]
            self.chat_histories[thread_id] = history
            log_debug(f"      🧹 Trimmed history to last {MAX_HISTORY_PAIRS} exchanges")
        
        try:
            messages = history + [HumanMessage(content=prompt)]
            
            # Retry logic for transient API errors
            max_retries = 3
            base_delay = 2
            
            for attempt in range(max_retries):
                try:
                    response = await self.action_llm_with_tools.ainvoke(messages)
                    break
                except (ResourceExhausted, ServiceUnavailable, InternalServerError) as e:
                    if attempt == max_retries - 1:
                        raise e
                    
                    delay = base_delay * (2 ** attempt)
                    log_warn(f"      ⚠️ Gemini API error (attempt {attempt+1}/{max_retries}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)

            log_debug("--- RAW RESPONSE FROM GEMINI ---")
            log_debug(str(response)[:300] + "...")  # Truncate log
            log_debug("--------------------------------")

            # Check for malformed function call
            finish_reason = None
            if hasattr(response, "response_metadata"):
                finish_reason = response.response_metadata.get("finish_reason")
            
            if finish_reason == "MALFORMED_FUNCTION_CALL":
                log_warn(f"      ⚠️  MALFORMED_FUNCTION_CALL detected - falling back to single action")
                # Clear history to reset context and try again with simpler prompt
                # Ask for just ONE action to avoid complexity
                simple_prompt = prompt.replace(
                    "You can call **multiple tools in one decision**",
                    "Call ONLY ONE tool per decision for reliability"
                )
                simple_messages = [HumanMessage(content=simple_prompt)]
                response = await self.action_llm_with_tools.ainvoke(simple_messages)
                log_info(f"      🔄 Retry response: {str(response)[:200]}")

            history.append(HumanMessage(content=prompt))
            history.append(response)
            
            actions = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    log_info(
                        f"      🛠️ Tool Call: {tool_call['name']} args={tool_call['args']}"
                    )
                    actions.append(
                        {"tool": tool_call["name"], "parameters": tool_call["args"]}
                    )
            if not actions and response.content:
                log_info(f"      💬 Gemini response (no tool call): {response.content[:200]}")
            
            # CRITICAL: Store pending tool calls for later result attachment
            # This allows action_loop to add ToolMessages after execution
            self._pending_tool_calls = response.tool_calls if hasattr(response, "tool_calls") else []
            
            return actions
        except Exception as e:
            log_error(f"      ❌ Gemini API error in decide_action: {e}")
            import traceback

            traceback.print_exc()
            return []

    async def verify_task_completion(
        self,
        task: str,
        elements: List[Any],
        url: str,
        storage_data: Dict[str, Any],
        action_history: List[Dict],
        thread_id: str,
        screenshot: Optional[Image.Image] = None,
    ) -> Dict[str, Any]:
        prompt = PromptBuilder.build_verification_prompt(
            task=task,
            elements_text=str(elements),
            url=url,
            storage_data=storage_data,
            action_history=action_history,
        )
        try:
            if screenshot:
                buffered = io.BytesIO()
                screenshot.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                # CRITICAL: Free buffer immediately
                buffered.close()
                del buffered
                
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ]
                )
                result: VerificationOutput = await self.verification_llm.ainvoke(
                    [message]
                )
                # Free base64 after sending
                del img_base64, message
            else:
                result: VerificationOutput = await self.verification_llm.ainvoke(prompt)

            return {
                "completed": result.completed,
                "confidence": result.confidence,
                "reasoning": result.reasoning,
                "evidence": result.evidence,
                "issues": result.issues,
            }
        except Exception as e:
            log_error(f"      ❌ Verification error: {e}")
            import traceback

            traceback.print_exc()
            return {
                "completed": False,
                "confidence": 0.0,
                "reasoning": f"Verification error: {str(e)}",
                "evidence": [],
                "issues": [str(e)],
            }

    async def analyze_visual(
        self, screenshot: Image.Image, question: str, context: Optional[str] = None,
        viewport_size: Optional[tuple] = None
    ) -> Dict[str, Any]:
        """
        Async visual analysis using Gemini Vision.
        Returns results after awaiting the API call.
        
        Args:
            screenshot: PIL Image to analyze
            question: Question about the image
            context: Additional context
            viewport_size: (width, height) for coordinate normalization
        """
        # Try cache first
        if self.cache:
            cached_result = self.cache.get_visual_analysis(screenshot, question)
            if cached_result is not None:
                return cached_result
        
        prompt = PromptBuilder.build_visual_analysis_prompt(
            question=question, context=context, viewport_size=viewport_size
        )
        try:
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            # CRITICAL: Free buffer immediately
            buffered.close()
            del buffered
            
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    },
                ]
            )
            # Use async ainvoke and await the result
            result: VisualAnalysisOutput = await self.vision_llm.ainvoke([message])
            # Free base64 after sending
            del img_base64, message
            
            log_success(f"      ✅ Visual analysis complete: {result.answer[:100]}")
            log_info(f"      🔍 Found {len(result.all_elements_found)} elements on screen")
            
            # CRITICAL: Normalize pixel coordinates to 0-1 range for ALL elements
            # Gemini returns pixels, we need to normalize to match OmniParser
            normalized_coords = None
            if result.target_coordinates and viewport_size:
                try:
                    x_pixel, y_pixel = result.target_coordinates[0], result.target_coordinates[1]
                    width, height = viewport_size
                    normalized_coords = [x_pixel / width, y_pixel / height]
                    log_debug(f"      📍 Normalized coords: pixel ({x_pixel}, {y_pixel}) → [{normalized_coords[0]:.3f}, {normalized_coords[1]:.3f}]")
                except Exception as e:
                    log_warn(f"      ⚠️  Coordinate normalization failed: {e}")
                    normalized_coords = result.target_coordinates  # Use as-is if normalization fails
            else:
                normalized_coords = result.target_coordinates
            
            # Normalize coordinates for all found elements
            normalized_elements = []
            if viewport_size:
                width, height = viewport_size
                for elem in result.all_elements_found:
                    try:
                        x_pixel, y_pixel = elem.center_coordinates[0], elem.center_coordinates[1]
                        normalized_center = [x_pixel / width, y_pixel / height]
                        
                        # Also normalize bbox if present
                        normalized_bbox = None
                        if elem.bbox and len(elem.bbox) >= 4:
                            x1, y1, x2, y2 = elem.bbox
                            normalized_bbox = [x1/width, y1/height, x2/width, y2/height]
                        
                        normalized_elements.append({
                            "id": elem.id,
                            "description": elem.description,
                            "center_coordinates": normalized_center,
                            "center_coordinates_pixels": elem.center_coordinates,  # Keep original
                            "bbox": normalized_bbox,
                            "bbox_pixels": elem.bbox,  # Keep original
                            "element_type": elem.element_type,
                            "content": elem.content,
                            "is_primary_target": elem.is_primary_target
                        })
                    except Exception as e:
                        # If normalization fails for this element, include it as-is
                        normalized_elements.append({
                            "id": elem.id,
                            "description": elem.description,
                            "center_coordinates": elem.center_coordinates,  # Use pixel coords if normalization fails
                            "bbox": elem.bbox,
                            "element_type": elem.element_type,
                            "content": elem.content,
                            "is_primary_target": elem.is_primary_target
                        })
            else:
                # No viewport size - return pixel coordinates as-is
                normalized_elements = [
                    {
                        "id": elem.id,
                        "description": elem.description,
                        "center_coordinates": elem.center_coordinates,
                        "bbox": elem.bbox,
                        "element_type": elem.element_type,
                        "content": elem.content,
                        "is_primary_target": elem.is_primary_target
                    }
                    for elem in result.all_elements_found
                ]
            
            final_result = {
                "answer": result.answer,
                "target_element_id": result.target_element_id,
                "target_coordinates": normalized_coords,
                "confidence": result.confidence,
                "all_elements": normalized_elements,  # NEW: Comprehensive element list
                "elements_count": len(normalized_elements)
            }
            
            # Store in cache
            if self.cache:
                self.cache.store_visual_analysis(screenshot, question, final_result)
            
            return final_result
            
        except Exception as e:
            log_error(f"      ❌ Visual analysis error: {e}")
            import traceback

            traceback.print_exc()
            return {
                "answer": f"Error: {str(e)}",
                "target_element_id": None,
                "target_coordinates": None,
                "confidence": 0.0,
            }

    async def create_plan(
        self,
        goal: str,
        url: str,
        elements_text: str,
        exploration_history: List[str] = None,
        visual_insights: Optional[Dict] = None,
        accomplishment_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = PromptBuilder.build_planning_prompt(
            goal=goal,
            url=url,
            elements_text=elements_text,
            exploration_history=exploration_history or [],
            visual_insights=visual_insights,
            accomplishment_summary=accomplishment_summary,
        )
        try:
            result: PlanOutput = await self.planning_llm.ainvoke(prompt)
            return {
                "steps": [
                    {
                        "number": step.number,
                        "name": step.name,
                        "description": step.description,
                        "type": step.type,
                        "dependencies": step.dependencies,
                        "estimated_time_seconds": step.estimated_time_seconds,
                    }
                    for step in result.steps
                ],
                "complexity": result.complexity,
                "estimated_total_time": result.estimated_total_time,
            }
        except Exception as e:
            log_error(f"      ❌ Planning error: {e}")
            import traceback

            traceback.print_exc()
            return {
                "steps": [
                    {
                        "number": 1,
                        "name": "Execute goal",
                        "description": goal,
                        "type": "direct",
                        "dependencies": [],
                        "estimated_time_seconds": 30,
                    }
                ],
                "complexity": "simple",
                "estimated_total_time": 30,
            }

    async def summarize_history(
        self, thread_id: str, conversation: Dict[str, Any], max_tokens: int = 512
    ) -> str:
        """
        Summarize a conversation context (summary + recent_messages).

        Args:
            thread_id: identifier for the conversation (for logging/debug only)
            conversation: dict with keys "summary" (str) and "recent_messages" (list of dicts)
            max_tokens: soft token budget hint (unused in heuristic fallback)

        Returns:
            A concise summary string. If the LLM call fails, returns the existing summary.
        """
        try:
            existing_summary = conversation.get("summary", "") or ""
            recent_messages = conversation.get("recent_messages", []) or []

            # Build a compact recent-events text
            recent_text_lines = []
            for m in recent_messages:
                role = m.get("role", "event")
                content = m.get("content", "")
                # Keep content short per message
                snippet = content.replace("\n", " ")
                if len(snippet) > 400:
                    snippet = snippet[:397] + "..."
                recent_text_lines.append(f"[{role}] {snippet}")

            recent_text = "\n".join(recent_text_lines[:20])

            prompt = (
                "You are a concise summarization assistant for a web-automation supervisor. "
                "Given an existing short summary and the most recent events, produce a short, "
                "useful summary (4-8 bullets) describing:\n"
                "- overall progress\n"
                "- repeated failures or persistent issues\n"
                "- outstanding tasks or next hypotheses for the agent\n\n"
                f"Existing summary:\n{existing_summary}\n\n"
                f"Recent events:\n{recent_text}\n\n"
                "Return the summary as plain text (4-8 bullets)."
            )

            # Prefer deterministic, low-temperature output from the LLM.
            # Use action_llm (available) for simple text generation; fall back to returning existing summary.
            if hasattr(self, "action_llm") and getattr(
                self.action_llm, "ainvoke", None
            ):
                # some langchain wrappers accept either a list of messages or directly a string;
                # we try both patterns, preferring structured messages for compatibility.
                try:
                    # Try structured call first
                    response = await self.action_llm.ainvoke(
                        [{"role": "user", "content": prompt}]
                    )
                    # Many wrappers provide `.content`, but fall back to str(response)
                    if hasattr(response, "content") and response.content:
                        return str(response.content).strip()
                    elif isinstance(response, str) and response:
                        return response.strip()
                except Exception:
                    # Try a fallback invocation form
                    try:
                        response2 = await self.action_llm.ainvoke(prompt)
                        if hasattr(response2, "content") and response2.content:
                            return str(response2.content).strip()
                        elif isinstance(response2, str) and response2:
                            return response2.strip()
                    except Exception as e:
                        log_warn(f"      ❌ Summarization LLM fallback error: {e}")

            # If LLM not available or failed, produce a lightweight heuristic summary
            bullets = []
            if existing_summary:
                bullets.append(f"(Prev) {existing_summary.strip()}")
            for line in recent_text_lines[-6:]:
                bullets.append(line)
            if not bullets:
                return "No significant events to summarize."
            return "\n".join(bullets[:8])

        except Exception as e:
            log_warn(f"      ❌ Summarization error for thread {thread_id}: {e}")
            return conversation.get("summary", "") or ""

    def append_tool_results(self, thread_id: str, tool_results: List[Dict[str, Any]]):
        """
        Append tool execution results to chat history.
        
        CRITICAL: This allows the AI to remember what tools returned!
        Without this, visual analysis results are lost between iterations.
        
        Args:
            thread_id: Thread to update
            tool_results: List of dicts with 'tool_call_id', 'name', 'content'
        """
        from langchain_core.messages import ToolMessage
        
        if thread_id not in self.chat_histories:
            return
        
        history = self.chat_histories[thread_id]
        
        # Append ToolMessage for each result
        for result in tool_results:
            tool_call_id = result.get('tool_call_id', '')
            content = result.get('content', '')
            
            # Create ToolMessage with the result
            tool_msg = ToolMessage(
                content=str(content),
                tool_call_id=tool_call_id
            )
            history.append(tool_msg)
            
        log_debug(f"      📝 Added {len(tool_results)} tool result(s) to history")
    
    def clear_context(self, thread_id: str):
        if thread_id in self.chat_histories:
            del self.chat_histories[thread_id]
            log_debug(f"   🧹 Cleared context for thread {thread_id[:12]}")

    def get_active_sessions(self) -> int:
        return len(self.chat_histories)
