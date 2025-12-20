"""
SQLite-backed Accomplishment Store - Tracks what has been accurately accomplished.

This store prevents agents from redoing work by maintaining a structured
record of completed goals, actions, and state changes on disk instead of RAM.
"""

import asyncio
import time
import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from web_agent.intelligence.gemini_agent import GeminiAgent


class AccomplishmentType(str, Enum):
    """Types of accomplishments that can be recorded"""
    NAVIGATION = "navigation"
    DATA_EXTRACTION = "data_extraction"
    FORM_SUBMISSION = "form_submission"
    SEARCH = "search"
    CLICK = "click"
    INPUT = "input"
    STATE_CHANGE = "state_change"
    GOAL_COMPLETION = "goal_completion"


@dataclass
class Accomplishment:
    """Structured record of something accomplished"""
    type: AccomplishmentType
    description: str
    timestamp: float
    agent_id: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    structural_key: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": self.type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "evidence": self.evidence,
            "context": self.context,
            "structural_key": self.structural_key,
        }


class AccomplishmentStore:
    """
    SQLite-backed store for tracking accomplished work.
    Data stored on disk instead of RAM for memory efficiency.
    
    Design principles:
    - Small and accurate: Only store verified accomplishments
    - Agent-filled: Agents write their successes with evidence
    - Queryable: Other agents can check before acting
    - Scoped: Per-session to avoid stale data
    - Structural keys: Deterministic, no fuzzy matching
    """
    
    def __init__(self, session_id: str, gemini_agent: Optional["GeminiAgent"] = None, db_path: Optional[str] = None):
        self.session_id = session_id
        self.gemini_agent = gemini_agent
        
        # Setup SQLite database
        if db_path is None:
            db_dir = Path(__file__).parent.parent.parent.parent / ".cache"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "accomplishments.db")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        
        # LLM-based summarization (optional optimization)
        self._llm_summary: Optional[str] = None
        self._llm_summary_count: int = 0
        self._summary_task: Optional[asyncio.Task] = None
        self._summary_threshold: int = 10
    
    def _init_db(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accomplishments (
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp REAL NOT NULL,
                agent_id TEXT NOT NULL,
                evidence TEXT,
                context TEXT,
                structural_key TEXT,
                PRIMARY KEY (session_id, structural_key)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session ON accomplishments(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_type ON accomplishments(session_id, type)
        """)
        self.conn.commit()
    
    def _generate_key(self, type: AccomplishmentType, evidence: Dict, context: Dict) -> str:
        """Generate deterministic structural key from evidence and context"""
        if type == AccomplishmentType.NAVIGATION:
            url = context.get("url", "")
            return f"nav:{url}"
        
        elif type == AccomplishmentType.INPUT:
            element_id = evidence.get("element_id", "")
            text = evidence.get("text", "")
            return f"input:elem{element_id}:{text}"
        
        elif type == AccomplishmentType.CLICK:
            element_id = evidence.get("element_id", "")
            return f"click:elem{element_id}"
        
        elif type == AccomplishmentType.DATA_EXTRACTION:
            key = context.get("key", "")
            return f"extract:{key}"
        
        elif type == AccomplishmentType.GOAL_COMPLETION:
            return f"goal:{context.get('goal', '')}".lower()
        
        elif type == AccomplishmentType.FORM_SUBMISSION:
            form_id = evidence.get("form_id", "")
            return f"submit:form{form_id}"
        
        else:
            return f"{type.value}:{hash(str(evidence))}"
    
    def record(
        self,
        type: AccomplishmentType,
        description: str,
        agent_id: str,
        evidence: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a verified accomplishment with structural key"""
        evidence = evidence or {}
        context = context or {}
        
        structural_key = self._generate_key(type, evidence, context)
        
        # Check if already recorded
        if self.is_accomplished_by_key(structural_key):
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO accomplishments 
            (session_id, type, description, timestamp, agent_id, evidence, context, structural_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.session_id,
            type.value,
            description,
            time.time(),
            agent_id,
            json.dumps(evidence),
            json.dumps(context),
            structural_key
        ))
        self.conn.commit()
    
    def is_accomplished_by_key(self, structural_key: str) -> bool:
        """Check if accomplishment exists by structural key"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM accomplishments 
            WHERE session_id = ? AND structural_key = ?
        """, (self.session_id, structural_key))
        return cursor.fetchone()['count'] > 0
    
    def check_input(self, element_id: int, text: str) -> bool:
        """Check if specific input has been entered"""
        key = f"input:elem{element_id}:{text}"
        return self.is_accomplished_by_key(key)
    
    def check_click(self, element_id: int) -> bool:
        """Check if specific element has been clicked"""
        key = f"click:elem{element_id}"
        return self.is_accomplished_by_key(key)
    
    def check_navigation(self, url: str) -> bool:
        """Check if navigation to URL has occurred"""
        key = f"nav:{url}"
        return self.is_accomplished_by_key(key)
    
    def get_recent(self, type: Optional[AccomplishmentType] = None, limit: int = 10) -> List[Accomplishment]:
        """Get recent accomplishments, optionally filtered by type"""
        cursor = self.conn.cursor()
        
        if type:
            cursor.execute("""
                SELECT * FROM accomplishments 
                WHERE session_id = ? AND type = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (self.session_id, type.value, limit))
        else:
            cursor.execute("""
                SELECT * FROM accomplishments 
                WHERE session_id = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (self.session_id, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append(Accomplishment(
                type=AccomplishmentType(row['type']),
                description=row['description'],
                timestamp=row['timestamp'],
                agent_id=row['agent_id'],
                evidence=json.loads(row['evidence']) if row['evidence'] else {},
                context=json.loads(row['context']) if row['context'] else {},
                structural_key=row['structural_key']
            ))
        
        return list(reversed(results))  # Return oldest first
    
    def has_visited_url(self, url: str) -> bool:
        """Check if we've already navigated to a URL"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM accomplishments 
            WHERE session_id = ? AND type = ? AND structural_key = ?
        """, (self.session_id, AccomplishmentType.NAVIGATION.value, f"nav:{url}"))
        return cursor.fetchone()['count'] > 0
    
    def has_extracted(self, key: str) -> Optional[Any]:
        """Check if data has been extracted and return it if so"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT evidence FROM accomplishments 
            WHERE session_id = ? AND type = ? AND structural_key = ?
        """, (self.session_id, AccomplishmentType.DATA_EXTRACTION.value, f"extract:{key}"))
        
        row = cursor.fetchone()
        if row:
            evidence = json.loads(row['evidence']) if row['evidence'] else {}
            return evidence.get('value')
        return None
    
    def has_completed_goal(self, goal: str) -> bool:
        """Check if a goal has been marked complete"""
        key = f"goal:{goal.lower()}"
        return self.is_accomplished_by_key(key)
    
    async def _generate_llm_summary_async(self) -> None:
        """Background task: Generate intelligent LLM summary of all accomplishments"""
        if not self.gemini_agent:
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT type, description FROM accomplishments 
                WHERE session_id = ?
                ORDER BY timestamp
            """, (self.session_id,))
            
            raw_data = []
            for row in cursor.fetchall():
                raw_data.append(f"[{row['type']}] {row['description']}")
            
            if not raw_data:
                return
            
            raw_text = "\n".join(raw_data)
            
            prompt = f"""You are summarizing a session's accomplishments for a web automation agent.

Raw accomplishment log ({len(raw_data)} items):
{raw_text}

Generate a concise, intelligent summary that highlights:
1. **Key patterns** - What actions were repeated? What was being tried?
2. **Progress made** - What worked? What got closer to the goal?
3. **What's been attempted** - List unique inputs/attempts to avoid duplicates
4. **Current state** - Where are we now?

Format as clear bullet points. Be specific about actual values (e.g., "tried words: flower, rose, tulip").
Focus on actionable information the agent can use to avoid repeating work."""

            response = await self.gemini_agent.action_llm.ainvoke(prompt)
            
            if hasattr(response, 'content') and response.content:
                self._llm_summary = str(response.content).strip()
                self._llm_summary_count = len(raw_data)
                print(f"      🤖 Generated LLM summary ({len(raw_data)} accomplishments)")
            
        except Exception as e:
            print(f"      ⚠️ LLM summary generation failed: {e}")
    
    def _trigger_summary_regeneration(self) -> None:
        """Trigger background summary regeneration if needed"""
        if not self.gemini_agent:
            return
        
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM accomplishments WHERE session_id = ?
        """, (self.session_id,))
        current_count = cursor.fetchone()['count']
        
        new_count = current_count - self._llm_summary_count
        if new_count >= self._summary_threshold:
            if self._summary_task and not self._summary_task.done():
                self._summary_task.cancel()
            
            try:
                self._summary_task = asyncio.create_task(self._generate_llm_summary_async())
            except RuntimeError:
                pass
    
    def get_summary(self) -> str:
        """Get intelligent summary of accomplishments"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM accomplishments WHERE session_id = ?
        """, (self.session_id,))
        total_count = cursor.fetchone()['count']
        
        if total_count == 0:
            return "No accomplishments recorded yet."
        
        # Trigger regeneration if needed
        self._trigger_summary_regeneration()
        
        # If we have an LLM summary and it's reasonably fresh, use it
        staleness = total_count - self._llm_summary_count
        if self._llm_summary and staleness < 20:
            return f"{self._llm_summary}\n\n[{staleness} new items since summary, total: {total_count}]"
        
        # Otherwise, return complete raw data
        cursor.execute("""
            SELECT type, description FROM accomplishments 
            WHERE session_id = ?
            ORDER BY timestamp
        """, (self.session_id,))
        
        by_type: Dict[str, List[str]] = {}
        for row in cursor.fetchall():
            acc_type = row['type']
            if acc_type not in by_type:
                by_type[acc_type] = []
            by_type[acc_type].append(row['description'])
        
        lines = [f"All accomplishments ({total_count} total):"]
        for acc_type, descriptions in by_type.items():
            lines.append(f"  {acc_type}: {len(descriptions)} items")
            for desc in descriptions:
                lines.append(f"    - {desc}")
        
        return "\n".join(lines)
    
    def clear(self) -> None:
        """Clear all accomplishments for this session"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accomplishments WHERE session_id = ?", (self.session_id,))
        self.conn.commit()
    
    @property
    def accomplishments(self) -> List[Accomplishment]:
        """Get all accomplishments (for backward compatibility)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM accomplishments 
            WHERE session_id = ?
            ORDER BY timestamp
        """, (self.session_id,))
        
        results = []
        for row in cursor.fetchall():
            results.append(Accomplishment(
                type=AccomplishmentType(row['type']),
                description=row['description'],
                timestamp=row['timestamp'],
                agent_id=row['agent_id'],
                evidence=json.loads(row['evidence']) if row['evidence'] else {},
                context=json.loads(row['context']) if row['context'] else {},
                structural_key=row['structural_key']
            ))
        return results
    
    def __del__(self):
        """Cleanup database connection"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except:
            pass
