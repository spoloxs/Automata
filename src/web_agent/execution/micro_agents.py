"""
Micro-Agent Architecture for Reduced Hallucination

Specialized agents that handle single responsibilities:
- ElementIdentifierAgent: Finds elements matching descriptions
- ClickAgent: Executes verified clicks
- TypeAgent: Executes verified typing
- NavigationAgent: Handles URL navigation

Design principle: Each micro-agent has ONE job and does it well.
This reduces LLM hallucination by keeping prompts focused and simple.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from web_agent.util.logger import log_debug, log_info, log_success, log_warn, log_error


@dataclass
class AgentResult:
    """Result from micro-agent execution"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    confidence: float = 1.0
    reasoning: str = ""


class MicroAgentBase:
    """Base class for all micro-agents"""
    
    def __init__(self, name: str):
        self.name = name
    
    async def execute(self, instruction: Dict[str, Any]) -> AgentResult:
        """Execute the micro-agent's specialized task"""
        raise NotImplementedError(f"{self.name} must implement execute()")


class ElementIdentifierAgent(MicroAgentBase):
    """
    Specialized agent for identifying elements.
    
    SINGLE RESPONSIBILITY: Match descriptions to element IDs
    Simple prompt: "Which element matches this description?"
    """
    
    def __init__(self, gemini_agent):
        super().__init__("ElementIdentifier")
        self.gemini = gemini_agent
        self.cache = {}  # Simple in-memory cache: description -> element_id

    def _heuristic_match(self, description: str, elements: List[Any]) -> Optional[int]:
        """
        Attempt to find an element ID using simple string matching heuristics.
        Returns element_id if a strong match is found, None otherwise.
        """
        desc_lower = description.lower()
        
        # 1. Exact Content Match (Case-insensitive)
        for elem in elements:
            content = getattr(elem, 'content', '').lower()
            if content == desc_lower:
                return elem.id
        
        # 2. Strong Partial Match (e.g. "Submit Button" matches "Submit")
        # Only if description is short/specific enough to avoid false positives
        if len(desc_lower) > 3:
            for elem in elements:
                content = getattr(elem, 'content', '').lower()
                # Check if description contains the content (e.g. "Click Search" -> "Search")
                # or content contains description (e.g. "Submit" -> "Submit Request")
                if content and (desc_lower in content or content in desc_lower):
                    # Verify element type compatibility if mentioned
                    elem_type = getattr(elem, 'type', '').lower()
                    if 'button' in desc_lower and 'button' not in elem_type and 'clickable' not in elem_type:
                        continue
                    return elem.id

        # 3. DOM Attribute Match (if available)
        for elem in elements:
            dom_id = getattr(elem, 'dom_id', '').lower()
            dom_test = getattr(elem, 'dom_text', '').lower()
            dom_placeholder = getattr(elem, 'dom_placeholder', '').lower()
            
            if desc_lower in dom_id or desc_lower in dom_test or desc_lower in dom_placeholder:
                return elem.id
                
        return None

    async def execute(self, instruction: Dict[str, Any]) -> AgentResult:
        """
        Identify element matching description.
        
        Args:
            instruction: {
                "description": "Button with text 'Login'",
                "elements": [...],  # Current page elements
                "context": "I need to log in to the site"  # Optional
            }
        
        Returns:
            AgentResult with element_id if found
        """
        description = instruction.get("description", "")
        elements = instruction.get("elements", [])
        context = instruction.get("context", "")
        
        if not description:
            return AgentResult(
                success=False,
                error="Missing element description"
            )
        
        if not elements:
            return AgentResult(
                success=False,
                error="No elements provided"
            )
        
        log_info(f"   🔍 {self.name}: Finding element matching '{description}'")

        # --- OPTIMIZATION: Check Cache ---
        if description in self.cache:
            cached_id = self.cache[description]
            # Validate if cached element still exists and looks plausible
            # Simple check: does the ID exist in current elements?
            # A more robust check would verify content hasn't changed drastically
            if any(e.id == cached_id for e in elements):
                log_success(f"   ⚡ {self.name}: Cache hit for '{description}' -> {cached_id}")
                return AgentResult(
                    success=True,
                    data={"element_id": cached_id},
                    reasoning=f"Cached match found element {cached_id}"
                )
            else:
                # Element gone or ID changed, invalidate cache
                del self.cache[description]

        # --- OPTIMIZATION: Heuristic Fuzzy Match (Fast Path) ---
        # Try to find a strong match locally before calling LLM
        best_match_id = self._heuristic_match(description, elements)
        if best_match_id is not None:
            log_success(f"   ⚡ {self.name}: Found heuristic match {best_match_id} for '{description}'")
            # Cache the result
            self.cache[description] = best_match_id
            return AgentResult(
                success=True,
                data={"element_id": best_match_id},
                reasoning=f"Heuristic match found element {best_match_id} with high confidence"
            )
        # -------------------------------------------------------
        
        # Format elements for LLM
        from web_agent.perception.element_formatter import ElementFormatter
        elements_text = ElementFormatter.format_for_llm(elements, max_elements=50)
        
        # Simple, focused prompt
        prompt = f"""You are an element identifier. Your ONLY job is to find the element that matches a description.

DESCRIPTION TO MATCH: {description}

AVAILABLE ELEMENTS:
{elements_text}

{f"CONTEXT: {context}" if context else ""}

TASK:
- Find the element ID that best matches the description
- Return ONLY the element ID number
- If no match found, return "NOT_FOUND"
- Be precise: match text content, type, position

Return format:
- If found: Just the number (e.g., "15")
- If not found: "NOT_FOUND"

Answer:"""

        try:
            # Call LLM with simple prompt
            response = await self.gemini.action_llm.ainvoke([{
                "role": "user",
                "content": prompt
            }])
            
            answer = response.content.strip()
            
            # Parse response
            if answer == "NOT_FOUND":
                return AgentResult(
                    success=False,
                    error=f"No element found matching '{description}'",
                    reasoning="Element identifier could not find matching element"
                )
            
            try:
                element_id = int(answer)
                log_success(f"   ✅ {self.name}: Found element {element_id}")
                self.cache[description] = element_id  # Cache the result
                
                return AgentResult(
                    success=True,
                    data={"element_id": element_id},
                    reasoning=f"Identified element {element_id} as matching '{description}'"
                )
            except ValueError:
                # Try to extract number from response
                import re
                numbers = re.findall(r'\d+', answer)
                if numbers:
                    element_id = int(numbers[0])
                    log_success(f"   ✅ {self.name}: Found element {element_id}")
                    self.cache[description] = element_id  # Cache the result
                    return AgentResult(
                        success=True,
                        data={"element_id": element_id},
                        reasoning=f"Identified element {element_id}"
                    )
                
                return AgentResult(
                    success=False,
                    error=f"Could not parse element ID from response: {answer}",
                    reasoning="Failed to parse LLM response"
                )
                
        except Exception as e:
            log_error(f"   ❌ {self.name}: Error: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                reasoning=f"Exception during element identification: {e}"
            )


class ClickAgent(MicroAgentBase):
    """
    Specialized agent for clicking elements.
    
    SINGLE RESPONSIBILITY: Click verified element IDs
    No complex reasoning - just execute the click
    """
    
    def __init__(self, action_handler):
        super().__init__("ClickAgent")
        self.action_handler = action_handler
    
    async def execute(self, instruction: Dict[str, Any]) -> AgentResult:
        """
        Click verified element.
        
        Args:
            instruction: {
                "element_id": 15,
                "reason": "To open login form"  # Optional
            }
        
        Returns:
            AgentResult with click outcome
        """
        element_id = instruction.get("element_id")
        reason = instruction.get("reason", "")
        
        if element_id is None:
            return AgentResult(
                success=False,
                error="Missing element_id"
            )
        
        log_info(f"   🖱️  {self.name}: Clicking element {element_id}")
        if reason:
            log_debug(f"      Reason: {reason}")
        
        try:
            # Use action handler to click
            from web_agent.execution.action_handler import BrowserAction, ActionType
            
            action = BrowserAction(
                action_type=ActionType.CLICK,
                parameters={"element_id": element_id},
                reasoning=reason
            )
            
            result = await self.action_handler.handle_action(
                action,
                elements=self.action_handler.current_elements
            )
            
            if result.success:
                log_success(f"   ✅ {self.name}: Click succeeded")
                return AgentResult(
                    success=True,
                    data={"clicked": True, "element_id": element_id},
                    reasoning=f"Successfully clicked element {element_id}"
                )
            else:
                log_error(f"   ❌ {self.name}: Click failed: {result.error}")
                return AgentResult(
                    success=False,
                    error=result.error,
                    reasoning=f"Click failed for element {element_id}"
                )
                
        except Exception as e:
            log_error(f"   ❌ {self.name}: Error: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                reasoning=f"Exception during click: {e}"
            )


class TypeAgent(MicroAgentBase):
    """
    Specialized agent for typing text.
    
    SINGLE RESPONSIBILITY: Type text into verified element IDs
    No complex reasoning - just execute the typing
    """
    
    def __init__(self, action_handler):
        super().__init__("TypeAgent")
        self.action_handler = action_handler
    
    async def execute(self, instruction: Dict[str, Any]) -> AgentResult:
        """
        Type text into verified element.
        
        Args:
            instruction: {
                "element_id": 15,
                "text": "username@example.com",
                "reason": "Enter email for login"  # Optional
            }
        
        Returns:
            AgentResult with typing outcome
        """
        element_id = instruction.get("element_id")
        text = instruction.get("text", "")
        reason = instruction.get("reason", "")
        
        if element_id is None:
            return AgentResult(
                success=False,
                error="Missing element_id"
            )
        
        if not text:
            return AgentResult(
                success=False,
                error="Missing text to type"
            )
        
        log_info(f"   ⌨️  {self.name}: Typing '{text}' into element {element_id}")
        if reason:
            log_debug(f"      Reason: {reason}")
        
        try:
            # Use action handler to type
            from web_agent.execution.action_handler import BrowserAction, ActionType
            
            action = BrowserAction(
                action_type=ActionType.TYPE,
                parameters={"element_id": element_id, "text": text},
                reasoning=reason
            )
            
            result = await self.action_handler.handle_action(
                action,
                elements=self.action_handler.current_elements
            )
            
            if result.success:
                log_success(f"   ✅ {self.name}: Type succeeded")
                return AgentResult(
                    success=True,
                    data={"typed": True, "element_id": element_id, "text": text},
                    reasoning=f"Successfully typed into element {element_id}"
                )
            else:
                log_error(f"   ❌ {self.name}: Type failed: {result.error}")
                return AgentResult(
                    success=False,
                    error=result.error,
                    reasoning=f"Type failed for element {element_id}"
                )
                
        except Exception as e:
            log_error(f"   ❌ {self.name}: Error: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                reasoning=f"Exception during type: {e}"
            )


class NavigationAgent(MicroAgentBase):
    """
    Specialized agent for navigation.
    
    SINGLE RESPONSIBILITY: Navigate to URLs
    Handles URL validation and navigation
    """
    
    def __init__(self, action_handler):
        super().__init__("NavigationAgent")
        self.action_handler = action_handler
    
    async def execute(self, instruction: Dict[str, Any]) -> AgentResult:
        """
        Navigate to URL.
        
        Args:
            instruction: {
                "url": "https://example.com",
                "reason": "To access the login page"  # Optional
            }
        
        Returns:
            AgentResult with navigation outcome
        """
        url = instruction.get("url", "")
        reason = instruction.get("reason", "")
        
        if not url:
            return AgentResult(
                success=False,
                error="Missing URL"
            )
        
        log_info(f"   🌐 {self.name}: Navigating to {url}")
        if reason:
            log_debug(f"      Reason: {reason}")
        
        try:
            # Use action handler to navigate
            from web_agent.execution.action_handler import BrowserAction, ActionType
            
            action = BrowserAction(
                action_type=ActionType.NAVIGATE,
                parameters={"url": url},
                reasoning=reason
            )
            
            result = await self.action_handler.handle_action(
                action,
                elements=self.action_handler.current_elements
            )
            
            if result.success:
                log_success(f"   ✅ {self.name}: Navigation succeeded")
                return AgentResult(
                    success=True,
                    data={"navigated": True, "url": url},
                    reasoning=f"Successfully navigated to {url}"
                )
            else:
                log_error(f"   ❌ {self.name}: Navigation failed: {result.error}")
                return AgentResult(
                    success=False,
                    error=result.error,
                    reasoning=f"Navigation failed to {url}"
                )
                
        except Exception as e:
            log_error(f"   ❌ {self.name}: Error: {e}")
            return AgentResult(
                success=False,
                error=str(e),
                reasoning=f"Exception during navigation: {e}"
            )


class MicroAgentCoordinator:
    """
    Coordinates micro-agents for complex actions.
    
    Implements two-phase pattern:
    1. Identify element (using ElementIdentifierAgent)
    2. Execute action (using ClickAgent/TypeAgent/etc.)
    """
    
    def __init__(self, gemini_agent, action_handler):
        self.element_identifier = ElementIdentifierAgent(gemini_agent)
        self.click_agent = ClickAgent(action_handler)
        self.type_agent = TypeAgent(action_handler)
        self.navigation_agent = NavigationAgent(action_handler)
    
    async def click_element_by_description(
        self,
        description: str,
        elements: List,
        context: str = ""
    ) -> AgentResult:
        """
        Two-phase click: Identify → Click
        
        Args:
            description: Element description ("Button with text 'Login'")
            elements: Current page elements
            context: Optional context
        
        Returns:
            AgentResult with final outcome
        """
        log_info(f"   🎯 Coordinator: Click element by description")
        
        # Phase 1: Identify
        identify_result = await self.element_identifier.execute({
            "description": description,
            "elements": elements,
            "context": context
        })
        
        if not identify_result.success:
            return AgentResult(
                success=False,
                error=f"Could not identify element: {identify_result.error}",
                reasoning=identify_result.reasoning
            )
        
        element_id = identify_result.data["element_id"]
        
        # Phase 2: Click
        click_result = await self.click_agent.execute({
            "element_id": element_id,
            "reason": f"Click {description}"
        })
        
        return click_result
    
    async def type_into_element_by_description(
        self,
        description: str,
        text: str,
        elements: List,
        context: str = ""
    ) -> AgentResult:
        """
        Two-phase type: Identify → Type
        
        Args:
            description: Element description ("Email input field")
            text: Text to type
            elements: Current page elements
            context: Optional context
        
        Returns:
            AgentResult with final outcome
        """
        log_info(f"   🎯 Coordinator: Type into element by description")
        
        # Phase 1: Identify
        identify_result = await self.element_identifier.execute({
            "description": description,
            "elements": elements,
            "context": context
        })
        
        if not identify_result.success:
            return AgentResult(
                success=False,
                error=f"Could not identify element: {identify_result.error}",
                reasoning=identify_result.reasoning
            )
        
        element_id = identify_result.data["element_id"]
        
        # Phase 2: Type
        type_result = await self.type_agent.execute({
            "element_id": element_id,
            "text": text,
            "reason": f"Type into {description}"
        })
        
        return type_result
