"""
Conversation store and manager for threaded conversation history.

Responsibilities:
- Maintain append-only conversations for different threads (planner, supervisor, workers).
- Provide safe async append / read operations (uses asyncio locks).
- Offer a summarization hook (sync or async callable) to compress history when it grows.
- Optional persistence (simple JSON dump/load) for debugging and post-mortem analysis.

Design notes:
- This component is intentionally LLM-agnostic: it does not call any LLM itself.
  Instead, a summarizer callable may be passed in (sync or async) that accepts text
  and returns a short summary string.
- Conversation messages are kept in-memory. Summaries are persisted as part of the
  conversation and can be written to disk via `save_thread_to_disk`.
- Thread safety: each thread gets its own asyncio.Lock and operations are awaited.

Usage example (conceptual):
    store = ConversationStore(base_dir=Path("/tmp/conv_store"))
    await store.append_event(thread_id="supervisor_abc", role="system", content="Start")
    await store.append_event(thread_id="supervisor_abc", role="event", content="Task X failed")
    # Get last 10 messages + summary
    ctx = await store.get_recent(thread_id="supervisor_abc", n=10)
    # Summarize using an async summarizer
    async def my_summarizer(text): return "short summary"
    summary = await store.summarize_thread("supervisor_abc", summarizer=my_summarizer)
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# Message role types (free-form strings are allowed)
DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY = 50  # Reduced from 200 to trigger summarization sooner
DEFAULT_MAX_RECENT_MESSAGES = 20
DEFAULT_MAX_MESSAGES_TO_KEEP = 30  # Maximum messages to keep in memory per thread


def _now_ts() -> float:
    return time.time()


@dataclass
class ConversationMessage:
    role: str  # e.g., "system", "assistant", "user", "event", "action", "verification"
    content: str
    timestamp: float = field(default_factory=_now_ts)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ConversationThread:
    thread_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    summary: str = ""  # Condensed textual summary of earlier messages
    created_at: float = field(default_factory=_now_ts)
    last_updated: float = field(default_factory=_now_ts)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }


class ConversationStore:
    """
    In-memory conversation store with async-safe operations and optional persistence.

    Key methods:
    - append_event(thread_id, role, content, metadata)
    - get_recent(thread_id, n, include_summary)
    - summarize_thread(thread_id, summarizer)  # summarizer can be sync or async
    - save_thread_to_disk(thread_id, path)
    - load_thread_from_disk(path) -> ConversationThread
    """

    def __init__(
        self,
        base_dir: Optional[Union[str, Path]] = None,
        max_messages_before_summary: int = DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY,
    ):
        self._threads: Dict[str, ConversationThread] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
        self.base_dir: Optional[Path] = Path(base_dir) if base_dir else None
        if self.base_dir:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_messages_before_summary = max_messages_before_summary

    # -------------------------
    # Internal helpers
    # -------------------------
    async def _get_lock_for(self, thread_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if thread_id not in self._locks:
                self._locks[thread_id] = asyncio.Lock()
            return self._locks[thread_id]

    async def _ensure_thread(self, thread_id: str) -> ConversationThread:
        async with self._global_lock:
            if thread_id not in self._threads:
                self._threads[thread_id] = ConversationThread(thread_id=thread_id)
            return self._threads[thread_id]

    # -------------------------
    # Public API
    # -------------------------
    async def append_event(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Append an event/message to the specified thread. Creates the thread if it
        does not exist.

        Args:
            thread_id: identifier for the conversation thread
            role: role string (system, assistant, event, action, verification, etc.)
            content: textual content of the message/event
            metadata: optional dictionary with additional structured info
            timestamp: optional epoch timestamp; defaults to now
        """
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            msg = ConversationMessage(
                role=role,
                content=content,
                timestamp=timestamp if timestamp is not None else _now_ts(),
                metadata=metadata or {},
            )
            thread.messages.append(msg)
            thread.last_updated = _now_ts()

            # If the thread has grown too big, leave summarization to explicit call,
            # but the store can optionally mark it for future compaction.
            # We do not perform auto-summarize here to avoid hidden LLM costs.

    async def get_recent(
        self,
        thread_id: str,
        n: int = DEFAULT_MAX_RECENT_MESSAGES,
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Return a dictionary with:
            - thread_id
            - summary (optional)
            - recent_messages: list of last `n` messages (oldest -> newest)
            - metadata

        If the thread does not exist, returns an empty structure.
        """
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            msgs = thread.messages[-n:] if n > 0 else []
            return {
                "thread_id": thread.thread_id,
                "summary": thread.summary if include_summary else "",
                "recent_messages": [m.to_dict() for m in msgs],
                "metadata": thread.metadata,
                "created_at": thread.created_at,
                "last_updated": thread.last_updated,
                "message_count": len(thread.messages),
            }

    async def get_all_messages(self, thread_id: str) -> List[Dict[str, Any]]:
        """
        Return all messages for the thread as list of dicts.
        """
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            return [m.to_dict() for m in thread.messages]

    async def set_thread_metadata(
        self, thread_id: str, metadata: Dict[str, Any]
    ) -> None:
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            thread.metadata.update(metadata)
            thread.last_updated = _now_ts()

    async def get_thread_metadata(self, thread_id: str) -> Dict[str, Any]:
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            return dict(thread.metadata)

    # -------------------------
    # Summarization
    # -------------------------
    async def summarize_thread(
        self,
        thread_id: str,
        summarizer: Optional[Callable[[str], Union[str, Awaitable[str]]]] = None,
        *,
        max_messages_to_include: int = DEFAULT_MAX_RECENT_MESSAGES,
        force: bool = False,
    ) -> str:
        """
        Summarize the thread's history and update the thread.summary.

        Args:
            thread_id: conversation thread id
            summarizer: optional callable that accepts a single string (text) and returns
                        a summary string. The callable may be sync or async.
                        If None, a lightweight heuristic summarizer is used.
            max_messages_to_include: number of recent messages to include in the summary prompt
            force: if True, force summarization even if message count is below threshold

        Returns:
            The summary string (newly set).
        """
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            total_msgs = len(thread.messages)
            if not force and total_msgs < self.max_messages_before_summary:
                # No need to summarize yet; return existing summary
                return thread.summary

            # Build text to summarize: existing summary + all messages up to the tail
            head_summary = thread.summary.strip()
            # Include all but the most recent max_messages_to_include messages in the long-form context
            head_msgs = thread.messages[: max(0, total_msgs - max_messages_to_include)]
            tail_msgs = thread.messages[-max_messages_to_include:]

            def _format_msgs(msgs: List[ConversationMessage]) -> str:
                return "\n".join(
                    [
                        f"[{m.role}] {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m.timestamp))}: {m.content}"
                        for m in msgs
                    ]
                )

            long_context = ""
            if head_summary:
                long_context += f"PREVIOUS_SUMMARY:\n{head_summary}\n\n"
            if head_msgs:
                long_context += f"EARLIER_EVENTS:\n{_format_msgs(head_msgs)}\n\n"

            tail_text = _format_msgs(tail_msgs) if tail_msgs else ""

            # Build candidate summary text
            if summarizer:
                # Provide a concise prompt-like input to the summarizer.
                prompt_text = f"{long_context}\nRECENT_EVENTS:\n{tail_text}\n\nSummarize progress, failures, and outstanding issues in 4-8 bullets."
                # Call provided summarizer (may be async)
                if asyncio.iscoroutinefunction(summarizer):
                    new_summary = await summarizer(prompt_text)
                else:
                    # callable sync
                    new_summary = summarizer(prompt_text)
            else:
                # Lightweight heuristic summarizer:
                # - keep previous summary bullets if present
                # - produce a few bullets from the last messages
                bullets = []
                if head_summary:
                    bullets.append(f"(Previously) {head_summary.strip()}")
                # Take the last few important messages (prioritize events/actions/verifications)
                for msg in tail_msgs[-8:]:
                    snippet = msg.content.strip().replace("\n", " ")
                    if len(snippet) > 200:
                        snippet = snippet[:197] + "..."
                    bullets.append(f"[{msg.role}] {snippet}")
                new_summary = "\n".join(bullets[:12])

            # Update thread summary and prune older messages if desired to keep memory bounded.
            thread.summary = new_summary
            thread.last_updated = _now_ts()

            # Optional pruning: keep only summary + last N messages in memory to bound growth.
            # We preserve the last max_messages_to_include messages.
            thread.messages = tail_msgs.copy()
            return thread.summary

    # -------------------------
    # Persistence helpers
    # -------------------------
    async def save_thread_to_disk(
        self, thread_id: str, path: Optional[Union[str, Path]] = None
    ) -> Path:
        """
        Save a thread to disk as JSON. If `path` is None and store was created with base_dir,
        the file will be written to base_dir/{thread_id}.json. Returns the path written.
        """
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            if path:
                p = Path(path)
            elif self.base_dir:
                p = self.base_dir / f"{thread_id}.json"
            else:
                raise ValueError(
                    "No path provided and ConversationStore has no base_dir configured."
                )

            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8") as fh:
                json.dump(thread.to_dict(), fh, ensure_ascii=False, indent=2)
            return p

    async def load_thread_from_disk(self, path: Union[str, Path]) -> ConversationThread:
        """
        Load a thread JSON exported by save_thread_to_disk and register it in the store.
        Returns the loaded ConversationThread object.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{p} does not exist")
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        thread_id = data.get("thread_id") or p.stem
        thread = ConversationThread(thread_id=thread_id)
        thread.summary = data.get("summary", "")
        thread.created_at = data.get("created_at", _now_ts())
        thread.last_updated = data.get("last_updated", _now_ts())
        thread.metadata = data.get("metadata", {})
        thread.messages = [
            ConversationMessage(
                role=m.get("role", "event"),
                content=m.get("content", ""),
                timestamp=m.get("timestamp", _now_ts()),
                metadata=m.get("metadata", {}),
            )
            for m in data.get("messages", [])
        ]
        async with self._global_lock:
            self._threads[thread_id] = thread
            if thread_id not in self._locks:
                self._locks[thread_id] = asyncio.Lock()
        return thread

    # -------------------------
    # Utility / housekeeping
    # -------------------------
    async def clear_thread(self, thread_id: str) -> None:
        """
        Clear a thread's messages and summary.
        """
        async with self._global_lock:
            if thread_id in self._threads:
                del self._threads[thread_id]
            if thread_id in self._locks:
                del self._locks[thread_id]

    async def list_threads(self) -> List[str]:
        """
        Return list of known thread ids.
        """
        async with self._global_lock:
            return list(self._threads.keys())

    # Simple token estimate heuristic (useful for determining when to summarize)
    @staticmethod
    def estimate_tokens_from_text(text: str) -> int:
        # Rough heuristic: 1 token per ~4 characters
        return max(1, len(text) // 4)

    async def estimate_thread_tokens(self, thread_id: str) -> int:
        thread = await self._ensure_thread(thread_id)
        lock = await self._get_lock_for(thread_id)
        async with lock:
            text = (
                thread.summary + "\n" + "\n".join([m.content for m in thread.messages])
            )
            return self.estimate_tokens_from_text(text)


# ---------------------------------------------------------------------------
# ConversationManager - lightweight helper wrapper used by higher-level code
# ---------------------------------------------------------------------------
class ConversationManager:
    """
    Lightweight wrapper exposing helpful helpers used throughout the agent:
      - append_action
      - append_decision
      - append_plan
      - append_verification
      - get_context (recent messages + summary)
      - summarize_thread (delegates to ConversationStore.summarize_thread)
      - set_summary (explicitly set the thread summary)
    """

    def __init__(self, store: ConversationStore):
        self.store = store

    async def append_action(
        self,
        thread_id: str,
        actor: str,
        action_desc: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Append an action event.

        actor: identifier of who performed the action (worker id, planner, etc.)
        action_desc: human readable description of the action
        success: boolean result
        details: optional structured details (e.g., element id, error)
        """
        payload = {
            "action": action_desc,
            "success": bool(success),
            "details": details or {},
        }
        try:
            await self.store.append_event(
                thread_id=thread_id,
                role=actor,
                content=json.dumps(payload, ensure_ascii=False),
                metadata=details or {},
            )
        except Exception:
            # best-effort: do not raise to avoid breaking execution
            pass

    async def append_decision(self, thread_id: str, decision: Dict[str, Any]):
        """
        Append a decision/result produced by the decision engine or supervisor.
        """
        try:
            await self.store.append_event(
                thread_id=thread_id,
                role="decision",
                content=json.dumps(decision, ensure_ascii=False),
                metadata=decision,
            )
        except Exception:
            pass

    async def append_plan(self, thread_id: str, plan: Dict[str, Any]):
        """
        Append a plan object (structured) to the conversation for traceability.
        """
        try:
            await self.store.append_event(
                thread_id=thread_id,
                role="planner",
                content=json.dumps(plan, ensure_ascii=False),
                metadata={"plan_steps": len(plan.get("steps", []))},
            )
        except Exception:
            pass

    async def append_verification(self, thread_id: str, verification: Dict[str, Any]):
        """
        Append verification output (from verifier) to the conversation thread.
        """
        try:
            await self.store.append_event(
                thread_id=thread_id,
                role="verifier",
                content=json.dumps(verification, ensure_ascii=False),
                metadata=verification,
            )
        except Exception:
            pass

    async def get_context(
        self, thread_id: str, recent: int = 20, include_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Return the recent context for use in LLM prompts:
          { "summary": str, "recent_messages": [...], "metadata": {...} }
        """
        try:
            ctx = await self.store.get_recent(
                thread_id, n=recent, include_summary=include_summary
            )
            return ctx
        except Exception:
            return {
                "thread_id": thread_id,
                "summary": "",
                "recent_messages": [],
                "metadata": {},
            }

    async def summarize_thread(
        self,
        thread_id: str,
        summarizer: Optional[Callable[[str], Any]] = None,
        max_messages_to_include: int = 20,
        force: bool = False,
    ) -> str:
        """
        Trigger summarization for a thread. The summarizer callable (if provided)
        should accept a single string (prompt/context) and return a summary string.
        If summarizer is None, a lightweight heuristic summary will be used.
        """
        try:
            summary = await self.store.summarize_thread(
                thread_id,
                summarizer,
                max_messages_to_include=max_messages_to_include,
                force=force,
            )
            return summary
        except Exception:
            return ""

    async def set_summary(self, thread_id: str, summary: str) -> None:
        """
        Explicitly set the summary for a conversation thread.

        This calls the store.summarize_thread helper with a small summarizer that
        returns the provided summary string. It's a best-effort helper that does not
        raise if the underlying store operation fails.
        """
        try:
            # Define a simple synchronous summarizer that ignores input and returns the desired summary
            def _return_summary(_: str) -> str:
                return summary

            # Force the store to update the summary and prune older messages if configured
            await self.store.summarize_thread(
                thread_id,
                summarizer=_return_summary,
                max_messages_to_include=0,
                force=True,
            )
        except Exception:
            # best-effort: do not raise
            pass
