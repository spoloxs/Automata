"""
SQLite-backed worker memory storage.
Provides namespaced key-value storage for worker tasks with disk persistence.
"""
from typing import Any, Dict, Optional, Type, TypeVar, Union
import json
import time
import sqlite3
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
from pathlib import Path

T = TypeVar('T')


class MemoryType(Enum):
    """Types of memory storage"""
    SHORT_TERM = "short_term"  # For current task context
    LONG_TERM = "long_term"    # For persistent storage
    SESSION = "session"        # For browser session data
    TASK = "task"             # For task-specific data


@dataclass
class MemoryEntry:
    """A single memory entry with metadata"""
    value: Any
    memory_type: MemoryType = MemoryType.SHORT_TERM
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    description: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'value': self.value,
            'memory_type': self.memory_type.value,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'expires_at': self.expires_at,
            'tags': self.tags,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        """Create from dictionary"""
        return cls(
            value=data['value'],
            memory_type=MemoryType(data['memory_type']) if 'memory_type' in data else MemoryType.SHORT_TERM,
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time()),
            expires_at=data.get('expires_at'),
            tags=data.get('tags', []),
            description=data.get('description')
        )


class WorkerMemory:
    """
    SQLite-backed key-value storage for worker memory.
    Provides isolation between different workers/tasks.
    Data stored on disk instead of RAM for memory efficiency.
    """
    
    def __init__(self, namespace: Optional[str] = None, db_path: Optional[str] = None):
        """
        Initialize worker memory with an optional namespace.
        
        Args:
            namespace: Namespace for this worker's memory. If None, a random UUID will be used.
            db_path: Path to SQLite database file. If None, uses default location.
        """
        self.namespace = namespace or f"worker_{uuid.uuid4().hex[:8]}"
        
        # Setup SQLite database
        if db_path is None:
            db_dir = Path(__file__).parent.parent.parent.parent / ".cache"
            db_dir.mkdir(exist_ok=True)
            db_path = str(db_dir / "worker_memory.db")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                expires_at REAL,
                tags TEXT,
                description TEXT,
                PRIMARY KEY (namespace, key)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_namespace ON memory(namespace)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires ON memory(expires_at)
        """)
        self.conn.commit()
    
    def _get_full_key(self, key: str) -> str:
        """Get fully qualified key with namespace"""
        return f"{self.namespace}:{key}"
    
    def store(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        ttl_seconds: Optional[float] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None
    ) -> None:
        """Store a value in memory"""
        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds is not None else None
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memory 
            (namespace, key, value, memory_type, created_at, updated_at, expires_at, tags, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.namespace,
            key,
            json.dumps(value),
            memory_type.value,
            now,
            now,
            expires_at,
            json.dumps(tags or []),
            description
        ))
        self.conn.commit()
    
    def retrieve(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from memory"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT value, expires_at FROM memory 
            WHERE namespace = ? AND key = ?
        """, (self.namespace, key))
        
        row = cursor.fetchone()
        if not row:
            return default
        
        # Check expiration
        if row['expires_at'] and time.time() > row['expires_at']:
            self.delete(key)
            return default
        
        return json.loads(row['value'])
    
    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Get the full MemoryEntry for a key"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory WHERE namespace = ? AND key = ?
        """, (self.namespace, key))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Check expiration
        if row['expires_at'] and time.time() > row['expires_at']:
            self.delete(key)
            return None
        
        return MemoryEntry(
            value=json.loads(row['value']),
            memory_type=MemoryType(row['memory_type']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            expires_at=row['expires_at'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            description=row['description']
        )
    
    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT expires_at FROM memory WHERE namespace = ? AND key = ?
        """, (self.namespace, key))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        if row['expires_at'] and time.time() > row['expires_at']:
            self.delete(key)
            return False
        
        return True
    
    def delete(self, key: str) -> bool:
        """Delete a key from memory"""
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM memory WHERE namespace = ? AND key = ?
        """, (self.namespace, key))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def clear(self, memory_type: Optional[MemoryType] = None) -> None:
        """Clear all or specific type of memory"""
        cursor = self.conn.cursor()
        if memory_type is None:
            cursor.execute("DELETE FROM memory WHERE namespace = ?", (self.namespace,))
        else:
            cursor.execute("""
                DELETE FROM memory WHERE namespace = ? AND memory_type = ?
            """, (self.namespace, memory_type.value))
        self.conn.commit()
    
    def get_all(self, memory_type: Optional[MemoryType] = None) -> Dict[str, Any]:
        """Get all key-value pairs, optionally filtered by memory type"""
        cursor = self.conn.cursor()
        now = time.time()
        
        if memory_type is None:
            cursor.execute("""
                SELECT key, value, expires_at FROM memory WHERE namespace = ?
            """, (self.namespace,))
        else:
            cursor.execute("""
                SELECT key, value, expires_at FROM memory 
                WHERE namespace = ? AND memory_type = ?
            """, (self.namespace, memory_type.value))
        
        result = {}
        expired_keys = []
        
        for row in cursor.fetchall():
            if row['expires_at'] and now > row['expires_at']:
                expired_keys.append(row['key'])
                continue
            result[row['key']] = json.loads(row['value'])
        
        # Clean up expired entries
        if expired_keys:
            cursor.execute(f"""
                DELETE FROM memory WHERE namespace = ? AND key IN ({','.join(['?']*len(expired_keys))})
            """, [self.namespace] + expired_keys)
            self.conn.commit()
        
        return result
    
    def find_by_tag(self, tag: str) -> Dict[str, Any]:
        """Find all memories with a specific tag"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT key, value, tags, expires_at FROM memory WHERE namespace = ?
        """, (self.namespace,))
        
        result = {}
        now = time.time()
        
        for row in cursor.fetchall():
            if row['expires_at'] and now > row['expires_at']:
                continue
            
            tags = json.loads(row['tags']) if row['tags'] else []
            if tag in tags:
                result[row['key']] = json.loads(row['value'])
        
        return result
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a memory entry"""
        entry = self.get_entry(key)
        if not entry:
            return None
        
        return {
            'memory_type': entry.memory_type.value,
            'created_at': entry.created_at,
            'updated_at': entry.updated_at,
            'expires_at': entry.expires_at,
            'tags': entry.tags,
            'description': entry.description
        }
    
    def update(
        self,
        key: str,
        value: Optional[Any] = None,
        memory_type: Optional[MemoryType] = None,
        ttl_seconds: Optional[float] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None
    ) -> bool:
        """Update an existing memory entry"""
        entry = self.get_entry(key)
        if not entry:
            return False
        
        cursor = self.conn.cursor()
        now = time.time()
        
        # Build update fields
        update_value = json.dumps(value) if value is not None else json.dumps(entry.value)
        update_type = memory_type.value if memory_type else entry.memory_type.value
        update_expires = now + ttl_seconds if ttl_seconds is not None else entry.expires_at
        update_tags = json.dumps(tags) if tags is not None else json.dumps(entry.tags)
        update_desc = description if description is not None else entry.description
        
        cursor.execute("""
            UPDATE memory 
            SET value = ?, memory_type = ?, updated_at = ?, expires_at = ?, tags = ?, description = ?
            WHERE namespace = ? AND key = ?
        """, (update_value, update_type, now, update_expires, update_tags, update_desc, self.namespace, key))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def to_dict(self) -> Dict[str, Dict]:
        """Convert all memories to a dictionary"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM memory WHERE namespace = ?
        """, (self.namespace,))
        
        result = {}
        now = time.time()
        
        for row in cursor.fetchall():
            if row['expires_at'] and now > row['expires_at']:
                continue
            
            result[row['key']] = {
                'value': json.loads(row['value']),
                'memory_type': row['memory_type'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'expires_at': row['expires_at'],
                'tags': json.loads(row['tags']) if row['tags'] else [],
                'description': row['description']
            }
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Dict], namespace: Optional[str] = None, db_path: Optional[str] = None) -> 'WorkerMemory':
        """Create a WorkerMemory instance from a dictionary"""
        memory = cls(namespace=namespace, db_path=db_path)
        
        for key, entry_data in data.items():
            try:
                entry = MemoryEntry.from_dict(entry_data)
                cursor = memory.conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO memory 
                    (namespace, key, value, memory_type, created_at, updated_at, expires_at, tags, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.namespace,
                    key,
                    json.dumps(entry.value),
                    entry.memory_type.value,
                    entry.created_at,
                    entry.updated_at,
                    entry.expires_at,
                    json.dumps(entry.tags),
                    entry.description
                ))
                memory.conn.commit()
            except (KeyError, ValueError):
                continue
        
        return memory
    
    def __del__(self):
        """Cleanup database connection"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except:
            pass
