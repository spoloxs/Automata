"""
Redis-backed conversation store for memory-efficient conversation history.

Uses Redis for persistent storage to avoid memory accumulation while maintaining
full conversation history. Automatically cleans up when done.
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


def _now_ts() -> float:
    return time.time()


@dataclass
class ConversationMessage:
    role: str
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMessage':
        return cls(
            role=data.get("role", "event"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", _now_ts()),
            metadata=data.get("metadata", {})
        )


class RedisConversationStore:
    """
    Redis-backed conversation store for memory efficiency.
    
    Stores conversations in Redis with automatic cleanup on shutdown.
    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "web_agent:conversation:",
        max_messages_before_summary: int = 100,
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_messages_before_summary = max_messages_before_summary
        self.redis_client: Optional[redis.Redis] = None
        self._fallback_store: Dict[str, List[Dict]] = {}  # Fallback if Redis unavailable
        self._use_redis = REDIS_AVAILABLE

    async def initialize(self):
        """Initialize Redis connection"""
        if not self._use_redis:
            print("⚠️ Redis not available, using in-memory fallback")
            return

        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            print("✅ Redis conversation store initialized")
        except Exception as e:
            print(f"⚠️ Redis connection failed: {e}, using in-memory fallback")
            self._use_redis = False
            self.redis_client = None

    async def append_event(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """Append message to conversation thread"""
        msg = ConversationMessage(
            role=role,
            content=content,
            timestamp=timestamp if timestamp is not None else _now_ts(),
            metadata=metadata or {},
        )

        if self._use_redis and self.redis_client:
            try:
                key = f"{self.key_prefix}{thread_id}:messages"
                await self.redis_client.rpush(key, json.dumps(msg.to_dict()))
                # Set expiry to 24 hours
                await self.redis_client.expire(key, 86400)
            except Exception as e:
                print(f"⚠️ Redis append failed: {e}, falling back")
                self._fallback_append(thread_id, msg)
        else:
            self._fallback_append(thread_id, msg)

    def _fallback_append(self, thread_id: str, msg: ConversationMessage):
        """Fallback to in-memory storage"""
        if thread_id not in self._fallback_store:
            self._fallback_store[thread_id] = []
        self._fallback_store[thread_id].append(msg.to_dict())

    async def get_recent(
        self,
        thread_id: str,
        n: int = 20,
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """Get recent messages from thread"""
        if self._use_redis and self.redis_client:
            try:
                msg_key = f"{self.key_prefix}{thread_id}:messages"
                summary_key = f"{self.key_prefix}{thread_id}:summary"
                
                # Get last n messages
                messages_json = await self.redis_client.lrange(msg_key, -n, -1)
                messages = [json.loads(m) for m in messages_json]
                
                summary = ""
                if include_summary:
                    summary = await self.redis_client.get(summary_key) or ""
                
                return {
                    "thread_id": thread_id,
                    "summary": summary,
                    "recent_messages": messages,
                    "metadata": {},
                    "message_count": await self.redis_client.llen(msg_key),
                }
            except Exception as e:
                print(f"⚠️ Redis get failed: {e}, using fallback")
                return self._fallback_get_recent(thread_id, n, include_summary)
        else:
            return self._fallback_get_recent(thread_id, n, include_summary)

    def _fallback_get_recent(self, thread_id: str, n: int, include_summary: bool) -> Dict[str, Any]:
        """Fallback to in-memory retrieval"""
        messages = self._fallback_store.get(thread_id, [])
        return {
            "thread_id": thread_id,
            "summary": "",
            "recent_messages": messages[-n:] if n > 0 else messages,
            "metadata": {},
            "message_count": len(messages),
        }

    async def set_summary(self, thread_id: str, summary: str) -> None:
        """Set thread summary"""
        if self._use_redis and self.redis_client:
            try:
                summary_key = f"{self.key_prefix}{thread_id}:summary"
                await self.redis_client.set(summary_key, summary)
                await self.redis_client.expire(summary_key, 86400)
            except Exception:
                pass

    async def clear_thread(self, thread_id: str) -> None:
        """Clear a specific thread"""
        if self._use_redis and self.redis_client:
            try:
                msg_key = f"{self.key_prefix}{thread_id}:messages"
                summary_key = f"{self.key_prefix}{thread_id}:summary"
                await self.redis_client.delete(msg_key, summary_key)
            except Exception:
                pass
        
        if thread_id in self._fallback_store:
            del self._fallback_store[thread_id]

    async def clear_all(self) -> None:
        """Clear all conversation threads"""
        if self._use_redis and self.redis_client:
            try:
                # Get all keys with our prefix
                pattern = f"{self.key_prefix}*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor, match=pattern, count=100
                    )
                    if keys:
                        await self.redis_client.delete(*keys)
                    if cursor == 0:
                        break
                print("✅ Cleared all Redis conversation data")
            except Exception as e:
                print(f"⚠️ Redis clear failed: {e}")
        
        self._fallback_store.clear()

    async def cleanup(self) -> None:
        """Cleanup resources and clear all data"""
        await self.clear_all()
        
        if self.redis_client:
            try:
                await self.redis_client.close()
                print("✅ Redis connection closed")
            except Exception:
                pass


class ConversationManager:
    """
    Lightweight wrapper for Redis conversation store.
    """

    def __init__(self, store: RedisConversationStore):
        self.store = store

    async def append_action(
        self,
        thread_id: str,
        actor: str,
        action_desc: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Append an action event"""
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
            pass

    async def append_decision(self, thread_id: str, decision: Dict[str, Any]):
        """Append a decision event"""
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
        """Append a plan"""
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
        """Append verification"""
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
        """Get recent context"""
        try:
            return await self.store.get_recent(
                thread_id, n=recent, include_summary=include_summary
            )
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
        """Summarize thread (placeholder for compatibility)"""
        return ""

    async def set_summary(self, thread_id: str, summary: str) -> None:
        """Set thread summary"""
        try:
            await self.store.set_summary(thread_id, summary)
        except Exception:
            pass
