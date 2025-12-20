"""
Task verification using Gemini.
"""

from typing import Any, Dict, List

from web_agent.core.result import VerificationResult
from web_agent.intelligence.gemini_agent import GeminiAgent
from web_agent.perception.element_formatter import ElementFormatter


class TaskVerifier:
    """
    Verifies task completion using Gemini.
    """

    def __init__(self, gemini_agent: GeminiAgent):
        """
        Initialize verifier.

        Args:
            gemini_agent: GeminiAgent instance
        """
        self.gemini = gemini_agent

    async def verify_task_completion(
        self,
        task: str,
        elements: List[Any],
        url: str,
        storage_data: Dict[str, Any],
        action_history: List[Dict] = None,
        thread_id: str = None,
        screenshot: Any = None,
    ) -> VerificationResult:
        """
        Verify if task has been completed.

        Args:
            task: Task description
            elements: Current page elements
            url: Current URL
            storage_data: Extracted data
            action_history: Actions executed
            thread_id: Thread ID for context
            screenshot: Optional screenshot for visual verification

        Returns:
            VerificationResult
        """
        # Format elements
        # elements_text = ElementFormatter.format_for_llm(elements)

        # Call Gemini verification
        result = await self.gemini.verify_task_completion(
            task=task,
            elements=elements,
            url=url,
            storage_data=storage_data,
            action_history=action_history or [],
            thread_id=thread_id or "verification",
            screenshot=screenshot,
        )

        # Convert to VerificationResult
        return VerificationResult(
            completed=result.get("completed", False),
            confidence=result.get("confidence", 0.0),
            reasoning=result.get("reasoning", ""),
            evidence=result.get("evidence", []),
            issues=result.get("issues", []),
        )
