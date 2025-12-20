"""
Decision Engine

AI-powered decision making for supervisor actions.
"""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SupervisorAction(str, Enum):
    """Possible supervisor actions"""

    RETRY = "retry"
    SKIP = "skip"
    REPLAN = "replan"
    ABORT = "abort"
    WAIT = "wait"
    SIMPLIFY = "simplify"


@dataclass
class SupervisorDecision:
    """Supervisor decision result"""

    action: SupervisorAction
    reasoning: str
    confidence: float
    task_id: Optional[str] = None
    alternative: Optional[str] = None
    new_tasks: Optional[List[Dict]] = None


class DecisionRequest(BaseModel):
    """Input to decision engine"""

    goal: str
    failed_task: Dict
    execution_state: Dict
    downstream_tasks: List[Dict]
    failure_pattern: str
    current_url: str


class DecisionResponse(BaseModel):
    """Expected response from LLM"""

    action: SupervisorAction = Field(..., description="Chosen action")
    reasoning: str = Field(..., description="Detailed reasoning")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    task_id: Optional[str] = Field(None, description="Task ID to retry/skip")
    alternative: Optional[str] = Field(None, description="Backup plan")
    simplify_plan: Optional[bool] = Field(False, description="Simplify remaining tasks")
    # Optional suggestion from the LLM/decision process recommending how many
    # additional supervised execution attempts the agent should try.
    suggested_continuation_attempts: Optional[int] = Field(
        None, description="Suggested number of additional supervised execution attempts"
    )
    # Optional list of new tasks to add into the current DAG
    new_tasks: Optional[List[Dict]] = Field(
        None, description="List of new tasks to add to current DAG"
    )


class DecisionEngine:
    """
    AI Decision Engine for Supervisor Agent.

    Uses structured LLM calls to make intelligent decisions about:
    - Task failures
    - Deadlocks
    - Execution health
    - Strategy changes
    """

    def __init__(self, gemini_agent):
        self.gemini = gemini_agent
        self.supervisor_thread_id = "supervisor_decision_engine"

    async def decide_failure_action(
        self, goal: str, failed_task: Dict, execution_state: Dict, dag_state: Dict
    ) -> SupervisorDecision:
        """
        Decide what to do when a task fails.
        """

        # Normalize execution state to a stable schema for LLM prompts
        normalized_state = self._normalize_execution_state(execution_state)
        request = DecisionRequest(
            goal=goal,
            failed_task=failed_task,
            execution_state=normalized_state,
            downstream_tasks=dag_state.get("downstream_tasks", []),
            failure_pattern=dag_state.get("failure_pattern", "unknown"),
            current_url=dag_state.get("current_url", ""),
        )

        # Get AI decision
        decision = await self._call_decision_llm(request)

        print(f"\n🧠 AI Decision: {decision.action.value}")
        print(f"   Confidence: {decision.confidence:.1%}")
        print(f"   Reasoning: {decision.reasoning[:100]}...")

        return SupervisorDecision(
            action=decision.action,
            reasoning=decision.reasoning,
            confidence=decision.confidence,
            task_id=decision.task_id,
            alternative=decision.alternative,
            new_tasks=getattr(decision, "new_tasks", None),
        )

    async def decide_deadlock_resolution(
        self, goal: str, blocked_tasks: List[Dict], dag_state: Dict
    ) -> SupervisorDecision:
        """
        Decide how to resolve execution deadlock.
        """

        prompt = self._build_deadlock_prompt(goal, blocked_tasks, dag_state)
        response = await self.gemini.action_llm.ainvoke(
            [{"role": "user", "content": prompt}]
        )

        return self._parse_decision_response(response.content)

    def _build_deadlock_prompt(
        self, goal: str, blocked_tasks: List[Dict], dag_state: Dict
    ) -> str:
        """Builds the prompt for resolving a deadlock."""
        task_list = "\n".join(
            [f"  - {task.id}: {task.description}" for task in blocked_tasks[:5]]
        )

        return f"""You are an AI Supervisor responsible for unblocking execution.

**SITUATION:** Execution is DEADLOCKED. No tasks can run.

**GOAL:** {goal}

**BLOCKED TASKS:**
{task_list}

**ANALYSIS:**
1. Identify which task, if skipped, would unblock the most other tasks.
2. Determine if skipping it compromises the goal.
3. If no single skippable task resolves the issue, consider a replan.

**DECISION REQUIRED:**
Choose ONE action to resolve the deadlock. Respond in VALID JSON.

{self._decision_schema()}
"""

    async def health_assessment(self, execution_state: Dict) -> Dict:
        """
        Get AI assessment of execution health using the structured health LLM.
        Returns a dict containing 'assessment', 'confidence' and a computed
        'suggested_continuation_attempts' heuristic.
        """
        try:
            # Normalize state first to handle varied input shapes
            norm = self._normalize_execution_state(execution_state)

            # Prepare state for prompt (combine raw fields like 'goal' with normalized counts)
            prompt_state = norm["raw"].copy()
            prompt_state.update(norm)

            prompt = self._build_health_prompt(prompt_state)

            # Use the structured health LLM exposed on the GeminiAgent
            if hasattr(self.gemini, "health_llm"):
                result = await self.gemini.health_llm.ainvoke(prompt)
                base_assessment = {
                    "assessment": getattr(result, "assessment", ""),
                    "confidence": float(getattr(result, "confidence", 0.0)),
                }
            else:
                # Fallback to the generic action_llm only if structured LLM is unavailable
                response = await self.gemini.action_llm.ainvoke(
                    [{"role": "user", "content": prompt}]
                )
                try:
                    data = json.loads(response.content)
                    base_assessment = {
                        "assessment": data.get("assessment", ""),
                        "confidence": float(data.get("confidence", 0.0)),
                    }
                except Exception:
                    base_assessment = {
                        "assessment": "Failed to assess",
                        "confidence": 0.0,
                    }

            # Heuristic suggestion calculation using normalized state
            suggested_attempts = 0
            try:
                completed = norm["completed"]
                total = norm["total"] or 1
                failed = norm["failed"]
                elapsed = norm["elapsed_time"]

                remaining = max(0, total - completed)

                # If nothing remains, don't continue.
                if remaining == 0:
                    suggested_attempts = 0
                else:
                    frac_remaining = remaining / float(max(1, total))
                    attempts = int(round(frac_remaining * 3)) + (1 if failed > 0 else 0)

                    if elapsed and elapsed > 600:
                        attempts = max(0, attempts - 1)

                    suggested_attempts = max(0, min(5, attempts))
            except Exception:
                suggested_attempts = 0

            result = base_assessment.copy()
            result["suggested_continuation_attempts"] = suggested_attempts
            return result
        except Exception:
            # Conservative fallback
            return {
                "assessment": "Failed to run health assessment",
                "confidence": 0.0,
                "suggested_continuation_attempts": 0,
            }

    async def should_continue(
        self,
        execution_state: Dict,
        verification: Optional[Dict] = None,
        conversation_context: Optional[Dict] = None,
    ) -> bool:
        """
        Decide whether the master should continue running supervised execution passes.

        Enhancements:
        - Accepts an optional `conversation_context` dict with keys:
            { "thread_id": str, "summary": str, "recent_messages": [dict,...] }
          If provided, the decision prompt will include the conversation summary and recent events.
        - If the DAG (execution_state) is complete and a conversation_context is provided,
          the method will call the GeminiAgent summarizer to produce an updated concise
          summary for the conversation (automatic summarization after a whole DAG run).
        """
        try:
            # If a conversation context is provided and the execution indicates the DAG is complete,
            # produce an updated summary (automatic summarization after whole DAG completion).
            if conversation_context and isinstance(conversation_context, dict):
                try:
                    # Determine completion: prefer explicit verification, otherwise use completed == total
                    completed_flag = False
                    if verification is not None:
                        # verification may be either a dict or an object; try to interpret both
                        if isinstance(verification, dict):
                            completed_flag = bool(verification.get("completed", False))
                        else:
                            completed_flag = bool(
                                getattr(verification, "completed", False)
                            )
                    else:
                        completed_flag = (
                            execution_state.get("completed") is not None
                            and execution_state.get("total") is not None
                            and execution_state.get("completed")
                            >= execution_state.get("total")
                        )

                    # If the DAG / run completed, ask Gemini to produce a concise summary for later decisions
                    if completed_flag and hasattr(self.gemini, "summarize_history"):
                        # Provide conversation content (summary + recent messages) to Gemini summarizer
                        conv_payload = {
                            "summary": (
                                conversation_context.get("summary", "")
                                if conversation_context
                                else ""
                            ),
                            "recent_messages": (
                                conversation_context.get("recent_messages", [])
                                if conversation_context
                                else []
                            ),
                        }
                        try:
                            new_summary = await self.gemini.summarize_history(
                                conversation_context.get("thread_id", "unknown"),
                                conv_payload,
                            )
                            # update conversation_context in-place to pass forward the improved summary
                            conversation_context["summary"] = (
                                new_summary or conversation_context.get("summary", "")
                            )
                        except Exception:
                            # Don't let summarization failures block decision making
                            pass
                except Exception:
                    # Non-fatal; continue to decision logic
                    pass

            # Prefer LangChain structured output if GeminiAgent exposes it
            if hasattr(self.gemini, "continuation_llm"):
                # Build a concise prompt describing the execution state, verification, and optionally conversation context.
                # Include conversation summary and the last few recent events for context if available.
                conv_summary = ""
                conv_events = ""
                if conversation_context and isinstance(conversation_context, dict):
                    conv_summary = conversation_context.get("summary", "") or ""
                    recent = conversation_context.get("recent_messages", []) or []
                    # Build a compact recent-events string
                    lines = []
                    for m in recent[-10:]:
                        role = m.get("role", "event")
                        content = m.get("content", "")
                        snippet = content.replace("\n", " ")
                        if len(snippet) > 300:
                            snippet = snippet[:297] + "..."
                        lines.append(f"[{role}] {snippet}")
                    conv_events = "\n".join(lines)

                prompt = (
                    "You are an AI Supervisor Decision Engine.\n\n"
                    "Given the execution state, the verifier assessment, and a short conversation summary\n"
                    "with recent events, return a structured response indicating whether the master should\n"
                    "run another supervised execution pass. The structured model will be provided by the system.\n\n"
                    f"Execution state: {execution_state}\n\nVerification: {verification}\n\n"
                    f"Conversation summary: {conv_summary}\n\nRecent events:\n{conv_events}\n\n"
                    "Return only the structured response."
                )
                # The continuation_llm is configured with a Pydantic model (ContinueDecision)
                result = await self.gemini.continuation_llm.ainvoke(prompt)
                # result is a validated structured output object; access the boolean field
                return bool(getattr(result, "should_continue", False))

            # Backwards-compatible: if the agent exposes a helper method, call it
            if hasattr(self.gemini, "decide_continue"):
                decision_obj = await self.gemini.decide_continue(
                    execution_state=execution_state, verification=verification
                )
                return bool(
                    getattr(decision_obj, "should_continue", False)
                    or getattr(decision_obj, "do_continue", False)
                )

            # Fallback to the older action_llm JSON response parsing if structured interface missing
            # Include conversation context in the fallback prompt if available to improve decision-making.
            conv_section = ""
            if conversation_context and isinstance(conversation_context, dict):
                conv_section_lines = []
                if conversation_context.get("summary"):
                    conv_section_lines.append(
                        f"Conversation summary:\n{conversation_context.get('summary')}\n"
                    )
                recent_msgs = conversation_context.get("recent_messages", []) or []
                for m in recent_msgs[-10:]:
                    r = m.get("role", "event")
                    c = m.get("content", "")
                    snippet = c.replace("\n", " ")
                    if len(snippet) > 300:
                        snippet = snippet[:297] + "..."
                    conv_section_lines.append(f"[{r}] {snippet}")
                conv_section = "\n".join(conv_section_lines)

            prompt = f"""You are an AI Supervisor Decision Engine.

Given the following execution state and the verifier's assessment, decide whether the
master should run additional supervised execution passes to try to complete the goal.

If available, a compact supervision summary is included below to help you understand
how the previous supervised pass ended (stop reason, decisions taken, and basic progress).
Supervision summary (if present): {execution_state.get("supervision", {})}

Return a structured response with fields:
- continue: true|false
- reason: one-line rationale

Execution state:
{execution_state}

Verification:
{verification}

{conv_section}

Be conservative: prefer false when unsure.
"""
            # Prefer structured continuation LLM when available
            try:
                if hasattr(self.gemini, "continuation_llm"):
                    result = await self.gemini.continuation_llm.ainvoke(prompt)
                    return bool(getattr(result, "should_continue", False))
                else:
                    # As a last-resort fallback, call action_llm and attempt to parse JSON content
                    response = await self.gemini.action_llm.ainvoke(
                        [{"role": "user", "content": prompt}]
                    )
                    try:
                        data = json.loads(response.content)
                        return bool(data.get("continue", False))
                    except Exception:
                        return False
            except Exception:
                # Fallback heuristic: continue only if verifier confidence is low and tasks remain.
                try:
                    conf = 0.0
                    if verification is not None:
                        conf = float(
                            getattr(
                                verification,
                                "confidence",
                                verification.get("confidence", 0.0),
                            )
                        )
                except Exception:
                    conf = 0.0
                remaining = execution_state.get("total", 1) - execution_state.get(
                    "completed", 0
                )
                if conf < 0.95 and remaining > 0:
                    return True
                return False

        except Exception:
            # Fallback heuristic: continue only if verifier confidence is low and tasks remain.
            try:
                conf = 0.0
                if verification is not None:
                    conf = float(
                        getattr(
                            verification,
                            "confidence",
                            verification.get("confidence", 0.0),
                        )
                    )
            except Exception:
                conf = 0.0
            remaining = execution_state.get("total", 1) - execution_state.get(
                "completed", 0
            )
            if conf < 0.95 and remaining > 0:
                return True
            return False

    def _build_health_prompt(self, execution_state: Dict) -> str:
        """Builds the prompt for a health assessment."""
        # Handle various shapes of execution_state (dict vs object access for health)
        health_obj = execution_state.get("health", {})

        def get_val(obj, attr, default):
            return (
                getattr(obj, attr, default)
                if not isinstance(obj, dict)
                else obj.get(attr, default)
            )

        status = get_val(
            health_obj, "status", execution_state.get("health_status", "Unknown")
        )
        success_rate = get_val(
            health_obj, "success_rate", execution_state.get("success_rate", 0.0)
        )
        concerns = get_val(health_obj, "concerns", execution_state.get("concerns", []))

        # Safe progress calc
        try:
            completed = execution_state.get("completed", 0)
            total = execution_state.get("total", 1) or 1
            progress = completed / total if total > 0 else 0
        except Exception:
            progress = 0

        prompt = f"""You are an AI Supervisor Health Analyst.

**EXECUTION HEALTH SUMMARY:**
- **Goal**: {execution_state.get('goal', 'N/A')}
- **Status**: {status}
- **Progress**: {progress:.0%}
- **Success Rate**: {success_rate:.0%}
- **Concerns**: {', '.join(concerns) if concerns else 'None'}

**ASSESSMENT REQUIRED:**
Provide a brief, one-sentence assessment of the current execution health and a confidence score.

**RESPONSE FORMAT (JSON):**
{{
  "assessment": "The execution is proceeding well despite minor issues.",
  "confidence": 0.85
}}
"""
        return prompt

    def _parse_health_assessment(self, content: str) -> Dict:
        """Parse health assessment from LLM response."""
        try:
            assessment_json = self._extract_json_from_response(content)
            data = json.loads(assessment_json)
            return {
                "assessment": data.get("assessment", "Could not parse assessment."),
                "confidence": data.get("confidence", 0.0),
            }
        except Exception:
            return {
                "assessment": "Failed to parse health assessment.",
                "confidence": 0.0,
            }

    async def _call_decision_llm(self, request: DecisionRequest) -> DecisionResponse:
        """Call the structured decision LLM and return a validated DecisionResponse."""

        # Import the structured error classifier
        from web_agent.core.error_types import ErrorClassifier
        
        failed_task_dict = request.failed_task if isinstance(request.failed_task, dict) else {}
        error_message = failed_task_dict.get("error", "")
        
        # Extract progress metrics from recent history
        progress_metrics_dict = None
        recent_history = request.execution_state.get('raw', {}).get('recent_history', [])
        if recent_history:
            last_run = recent_history[-1]
            result = last_run.get('result', {})
            extracted_data = result.get('extracted_data', {})
            progress_metrics_dict = extracted_data.get('progress_metrics')
        
        # Classify the error using structured system
        structured_error = ErrorClassifier.classify(error_message, progress_metrics_dict)
        
        # Build detailed progress information using structured data
        progress_info = ""
        if structured_error.progress_metrics:
            metrics = structured_error.progress_metrics
            progress_info = f"""
STRUCTURED ERROR ANALYSIS:
Error Category: {structured_error.category.value}
{f"Timeout Reason: {structured_error.timeout_reason.value}" if structured_error.timeout_reason else ""}
Suggested Action: {structured_error.suggested_action}
Is Recoverable: {structured_error.is_recoverable}

DETAILED PROGRESS METRICS:
- Actions executed: {metrics.actions_executed}
- Successful actions: {metrics.successful_actions} 
- Failed actions: {metrics.failed_actions}
- Success rate: {metrics.success_rate:.1%}
- State changes: {metrics.state_changes}
- Unique states visited: {metrics.unique_states_visited}
- Has meaningful progress: {metrics.has_meaningful_progress}
{f"- Convergence detected: {metrics.convergence_detected}" if metrics.convergence_detected else ""}
{f"- Convergence metric: {metrics.convergence_metric} = {metrics.convergence_value}" if metrics.convergence_metric else ""}

Recent Actions Pattern:
{self._format_action_pattern(metrics.last_10_actions)}

RECOMMENDATION:
{self._generate_recommendation(structured_error)}
"""

        prompt = f"""You are an AI Supervisor Decision Engine for web automation.

CRITICAL RESPONSIBILITIES:
1. Detect iterative tasks that need continuation (not retry)
2. Analyze task failure impact on overall goal
3. Choose optimal recovery strategy
4. Be pragmatic - prefer completion over perfection

GOAL: {request.goal}

FAILED TASK:
{self._format_failed_task(request.failed_task)}
{progress_info}

EXECUTION STATE:
- Progress: {request.execution_state.get('completed', 0)} / {request.execution_state.get('total', request.execution_state.get('all_tasks', 0))}
- Failed: {request.execution_state.get('failed', 0)}
- Time elapsed: {request.execution_state.get('elapsed_time', 0):.0f}s
- Current URL: {request.current_url}

RECENT HISTORY:
{self._format_recent_history(request.execution_state.get('raw', {}).get('recent_history', []))}

DOWNSTREAM IMPACT:
- {request.execution_state.get('downstream_count', (len(request.downstream_tasks) if isinstance(request.downstream_tasks, list) else (request.downstream_tasks or 0)))} tasks blocked
{self._format_downstream_tasks(request.downstream_tasks)}

FAILURE PATTERN: {request.failure_pattern}

DECISION REQUIRED:
Choose ONE action and return a structured response.

RULES:
- RETRY: First failure, temporary issue, critical task
- SKIP: Non-critical verification, goal still achievable without it  
- REPLAN: Task made PROGRESS but needs continuation
  * Use new_tasks field to create continuation task(s)
  * Continuation should resume the iterative process
  * Example: "Continue trying guesses until position #1 is found"
- ABORT: Goal unreachable, repeated critical failures, cost too high

SPECIAL CASE - ITERATIVE TASKS:
If a task shows progress but timed out (see PROGRESS DETECTED above):
1. Action should be REPLAN (not RETRY or SKIP)
2. Create continuation task(s) in new_tasks field
3. Continuation description should capture the iterative nature
4. Do NOT treat timeout with progress as failure

PRIORITIZE GOAL COMPLETION above perfect task execution.
"""

        messages = [
            {
                "role": "system",
                "content": """You are a production-grade AI supervisor for web automation.

CRITICAL RULES:
1. ALWAYS respond with a structured DecisionOutput
2. Prioritize GOAL COMPLETION over individual task success
3. Verification tasks are often skippable
4. Repeated failures of same task type = systemic issue
5. Be decisive - no "maybe" decisions
""",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            # Use the structured decision LLM exposed by GeminiAgent
            if hasattr(self.gemini, "decision_llm"):
                result = await self.gemini.decision_llm.ainvoke(messages)
                # Map structured fields into DecisionResponse
                action_str = getattr(result, "action", None)
                reasoning = getattr(result, "reasoning", "")
                confidence = float(getattr(result, "confidence", 0.0))
                task_id = getattr(result, "task_id", None)
                alternative = getattr(result, "alternative", None)
                simplify_plan = getattr(result, "simplify_plan", False)
                suggested = getattr(result, "suggested_continuation_attempts", None)
                new_tasks = getattr(result, "new_tasks", None)

                # Validate / coerce action into SupervisorAction
                try:
                    action_enum = SupervisorAction(action_str)
                except Exception:
                    action_enum = SupervisorAction.SKIP

                return DecisionResponse(
                    action=action_enum,
                    reasoning=reasoning,
                    confidence=confidence,
                    task_id=task_id,
                    alternative=alternative,
                    simplify_plan=bool(simplify_plan),
                    suggested_continuation_attempts=suggested,
                    new_tasks=new_tasks if isinstance(new_tasks, list) else None,
                )
            else:
                # As a conservative fallback (should be rare), call action_llm and parse JSON
                response = await self.gemini.action_llm.ainvoke(messages)
                # Validate directly from the LLM response content (expected JSON string).
                # Avoid double json.dumps which can corrupt already-serialized content.
                try:
                    return DecisionResponse.model_validate_json(response.content)
                except Exception:
                    data = json.loads(response.content)
                    return DecisionResponse(
                        action=SupervisorAction(data.get("action", "skip")),
                        reasoning=data.get("reasoning", ""),
                        confidence=float(data.get("confidence", 0.0)),
                        task_id=data.get("task_id"),
                        alternative=data.get("alternative"),
                        simplify_plan=bool(data.get("simplify_plan", False)),
                        new_tasks=(
                            data.get("new_tasks")
                            if isinstance(data.get("new_tasks"), list)
                            else None
                        ),
                    )

        except Exception as e:
            print(f"⚠️  Decision engine fallback: {e}")
            return DecisionResponse(
                action=SupervisorAction.SKIP,
                reasoning="Decision engine error - defaulting to skip",
                confidence=0.5,
            )

    def _normalize_execution_state(self, state: Dict) -> Dict:
        """Normalize execution_state to a stable schema the decision engine expects.

        Ensures the following keys are present and typed:
        - completed (int)
        - failed (int)
        - total (int)  (if total not present, will try 'all_tasks' or derive from collections)
        - all_tasks (int) (alias of total)
        - elapsed_time (float)
        - downstream_count (int)
        - downstream_tasks (List[Dict]) (ensure list if possible)
        """
        if not isinstance(state, dict):
            state = {}

        normalized = dict(state)  # shallow copy to avoid mutating caller data

        def to_int(val, default=0):
            if isinstance(val, int):
                return val
            try:
                if val is None:
                    return default
                # If it's a collection, treat its length as the count
                if isinstance(val, (list, tuple, set, dict)):
                    return len(val)
                # Try numeric conversion otherwise
                return int(val)
            except Exception:
                return default

        # Normalize primary counts
        normalized["completed"] = to_int(
            state.get("completed", state.get("completed_count", 0)), 0
        )
        normalized["failed"] = to_int(
            state.get("failed", state.get("failed_count", 0)), 0
        )

        # Determine total / all_tasks
        normalized["total"] = to_int(
            state.get("total", state.get("all_tasks", state.get("total_tasks", None))),
            0,
        )
        normalized["all_tasks"] = normalized["total"]

        # If total wasn't provided, derive it from completed + failed + remaining (if available)
        if normalized["total"] == 0:
            remaining = to_int(state.get("remaining", None), 0)
            derived_total = normalized["completed"] + normalized["failed"] + remaining
            normalized["total"] = derived_total
            normalized["all_tasks"] = derived_total

        # Elapsed time normalization
        try:
            normalized["elapsed_time"] = float(
                state.get("elapsed_time", state.get("elapsed", 0)) or 0.0
            )
        except Exception:
            normalized["elapsed_time"] = 0.0

        # Downstream tasks normalization: prefer an explicit list, otherwise store a numeric count
        downstream = state.get("downstream_tasks", state.get("downstream", []))
        if isinstance(downstream, list):
            normalized["downstream_tasks"] = downstream
            normalized["downstream_count"] = len(downstream)
        else:
            # If downstream is an int-like count or other, try to coerce to int
            normalized["downstream_tasks"] = []
            normalized["downstream_count"] = to_int(downstream, 0)

        # Preserve raw input for downstream formatting (e.g., recent_history)
        try:
            normalized["raw"] = dict(state)
        except Exception:
            normalized["raw"] = {"state": state}

        return normalized

    def _decision_schema(self) -> str:
        """Return JSON schema for decision"""
        schema = """```
        {
        "action": "retry|skip|replan|abort",
        "reasoning": "Your reasoning here",
        "confidence": 0.95,
        "task_id": "abc123def" (optional),
        "alternative": "Backup plan (optional)",
        "simplify_plan": true/false,
        "new_tasks": [
            {"description": "Describe the recovery step succinctly"}
        ]
        }
        ```"""
        return schema

    def _format_failed_task(self, task: Dict) -> str:
        """Format failed task info"""
        return f"""Description: {task.get('description', 'N/A')}
            Error: {task.get('error', 'Unknown')}
            Duration: {task.get('duration', 0):.1f}s
            Actions: {len(task.get('action_history', []))}
            """

    def _format_recent_history(self, recent: Optional[List[Dict]]) -> str:
        """Format a compact recent-history section for the LLM prompt.

        Expected each recent entry to be a dict with keys like:
        - timestamp, task_id, description, action_summary (or action_history), result/error, worker_id
        We include up to the last 5 events (most recent last) and truncate long fields.
        """
        if not recent:
            return "No recent execution history available."

        lines: List[str] = []
        # Keep order from oldest->newest for readability; take last up to 5
        items = recent[-5:] if len(recent) > 5 else recent
        for e in items:
            try:
                task_id = e.get("task_id", "unknown")
                desc = e.get("description") or e.get("task_desc") or "(no desc)"
                # result may be a dict or fields at top-level
                res_msg = None
                if e.get("error"):
                    res_msg = e.get("error")
                else:
                    r = e.get("result") or {}
                    if isinstance(r, dict):
                        res_msg = r.get("error") or r.get("message")
                if not res_msg:
                    res_msg = "success" if e.get("success") else "failed"
                actions = e.get("action_summary") or e.get("action_history") or []
                act_summ: List[str] = []
                for a in actions[:5]:
                    if isinstance(a, dict):
                        act_summ.append(
                            a.get("action_type") or a.get("type") or str(a)[:40]
                        )
                    else:
                        # fallback for action objects
                        try:
                            act_summ.append(str(getattr(a, "action_type", a))[:40])
                        except Exception:
                            act_summ.append(str(a)[:40])
                lines.append(
                    f"- {task_id}: {desc} -> {res_msg}; actions: {', '.join(act_summ)}"
                )
            except Exception:
                # Resilient fallback for malformed entries
                try:
                    lines.append(
                        f"- {e.get('task_id', 'unknown')}: (malformed history entry)"
                    )
                except Exception:
                    lines.append("- unknown: (malformed history entry)")

        return "Recent events (oldest → newest):\n" + "\n".join(lines)

    def _format_downstream_tasks(self, tasks: Any) -> str:
        """Format downstream impact

        This method is intentionally robust: `tasks` may be a list of task dicts,
        a numeric count, or another type. Return a short summary with a numeric
        count and (when available) up to a few brief descriptions.
        """
        if not tasks:
            return "No downstream tasks affected"

        count = 0
        bullets: List[str] = []

        # If it's a real list of task dicts, build bullets from descriptions
        if isinstance(tasks, list):
            count = len(tasks)
            bullets = [f"  • {t.get('description', 'N/A')[:100]}..." for t in tasks[:5]]
        else:
            # Try to coerce non-list values to an integer count (e.g. upstream may provide an int)
            try:
                count = int(tasks)
            except Exception:
                # As a last resort, see if the object exposes a length
                try:
                    count = len(tasks)  # type: ignore
                except Exception:
                    count = 0

        out = f"- {count} tasks blocked\n"
        if bullets:
            out += "\n" + "\n".join(bullets)
        return out

    def _extract_json_from_response(self, text: str) -> str:
        """Deprecated: JSON extraction by regex removed in favor of structured LLM outputs.

        This function is retained for compatibility but will attempt a simple json.loads()
        parse and otherwise raise a ValueError to avoid silent regex parsing.
        """
        if not isinstance(text, str):
            raise ValueError("Expected text string for JSON extraction")

        try:
            return json.dumps(json.loads(text))
        except Exception:
            # If the content is not a strict JSON string, signal failure explicitly.
            raise ValueError(
                "Unable to extract JSON via strict parsing. Use structured LLMs instead."
            )

    def _format_action_pattern(self, actions: List[Dict[str, Any]]) -> str:
        """Format action pattern analysis"""
        if not actions:
            return "No actions recorded"
        
        lines = []
        for i, action in enumerate(actions, 1):
            action_type = action.get('type', 'unknown')
            success = action.get('success', False)
            iteration = action.get('iteration', '?')
            status = "✓" if success else "✗"
            lines.append(f"  {i}. [{status}] {action_type} (iter {iteration})")
        
        return "\n".join(lines) if lines else "No pattern detected"
    
    def _generate_recommendation(self, structured_error) -> str:
        """Generate structured recommendation based on error analysis"""
        from web_agent.core.error_types import ErrorCategory, TimeoutReason
        
        if structured_error.category == ErrorCategory.TIMEOUT:
            if structured_error.progress_metrics and structured_error.progress_metrics.has_meaningful_progress:
                return (
                    "This is an ITERATIVE TASK making measurable progress. "
                    "Recommend REPLAN with continuation task to resume from current state. "
                    "Do NOT treat as failure - the agent is converging on the goal."
                )
            elif structured_error.timeout_reason == TimeoutReason.MAX_ITERATIONS:
                return "Task hit iteration limit without progress. Consider RETRY with simplified approach."
            else:
                return "Task timed out without progress. Recommend SKIP or RETRY based on criticality."
        
        elif structured_error.category == ErrorCategory.VERIFICATION_FAILED:
            return "Verification failure - typically safe to SKIP as verifications are non-critical."
        
        elif structured_error.is_recoverable:
            return f"Error is recoverable. Suggested action: {structured_error.suggested_action.upper()}"
        
        else:
            return "Unrecoverable error - recommend ABORT."
    
    def _parse_decision_response(self, content: Any) -> SupervisorDecision:
        """Parse structured decision response or fallback JSON content.

        Prefer structured DecisionOutput objects; if given raw content, attempt strict JSON parse.
        """
        try:
            # If we received a structured object (from langchain with_structured_output), it will
            # already expose attributes we can read.
            if not isinstance(content, str) and hasattr(content, "action"):
                action_val = getattr(content, "action", None)
                reasoning = getattr(content, "reasoning", "")
                confidence = float(getattr(content, "confidence", 0.0))
                try:
                    action_enum = SupervisorAction(action_val)
                except Exception:
                    action_enum = SupervisorAction.SKIP
                return SupervisorDecision(
                    action=action_enum, reasoning=reasoning, confidence=confidence
                )
            # Otherwise, try to parse JSON string strictly
            data = json.loads(content) if isinstance(content, str) else dict(content)
            try:
                action_enum = SupervisorAction(data.get("action"))
            except Exception:
                action_enum = SupervisorAction.SKIP
            return SupervisorDecision(
                action=action_enum,
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception:
            return SupervisorDecision(
                action=SupervisorAction.SKIP,
                reasoning="Parse error - default skip",
                confidence=0.3,
            )
