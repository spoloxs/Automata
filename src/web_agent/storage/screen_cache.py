"""
Screen Analysis Cache - SQLite-based cache for visual analysis and ScreenParser results.

Uses perceptual hashing (pHash) to detect even tiny image changes (0.01% difference).
Caches are automatically invalidated when screen content changes.
"""

import hashlib
import io
import json
import pickle
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from web_agent.util.logger import log_debug, log_info, log_success, log_warn


class ScreenCache:
    """
    High-performance cache for screen analysis results.
    
    Uses SHA-256 hash of screenshot pixels as cache key.
    Even a single pixel change (0.01% difference) creates a different hash.
    """
    
    def __init__(self, cache_dir: Path = None, max_age_seconds: int = 3600):
        """
        Initialize screen cache.
        
        Args:
            cache_dir: Directory to store cache database (default: ./cache)
            max_age_seconds: Maximum age of cached entries in seconds (default: 1 hour)
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent.parent / "cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.cache_dir / "screen_analysis.db"
        self.max_age = max_age_seconds
        
        # Initialize database
        self._init_db()
        
        # Cache statistics
        self.stats = {
            "visual_hits": 0,
            "visual_misses": 0,
            "parser_hits": 0,
            "parser_misses": 0,
        }
        
        log_debug(f"ScreenCache initialized: {self.db_path}")
    
    def _init_db(self):
        """Initialize SQLite database with optimized schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Visual analysis cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS visual_analysis (
                image_hash TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                last_accessed INTEGER NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        
        # ScreenParser cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screen_parser (
                image_hash TEXT PRIMARY KEY,
                elements_pickle BLOB NOT NULL,
                created_at INTEGER NOT NULL,
                last_accessed INTEGER NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        
        # Indexes for fast lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_visual_created 
            ON visual_analysis(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_parser_created 
            ON screen_parser(created_at)
        """)
        
        conn.commit()
        conn.close()
    
    def _compute_image_hash(self, screenshot: Image.Image) -> str:
        """
        Compute SHA-256 hash of screenshot pixel data.
        
        Even 0.01% pixel change will produce a different hash.
        Fast and collision-resistant.
        
        Args:
            screenshot: PIL Image to hash
            
        Returns:
            Hex string of SHA-256 hash
        """
        # Convert image to bytes (RGB pixel data)
        img_bytes = screenshot.tobytes()
        
        # SHA-256 hash of pixel data
        hash_obj = hashlib.sha256(img_bytes)
        return hash_obj.hexdigest()
    
    def get_visual_analysis(
        self, screenshot: Image.Image, question: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached visual analysis result if available.
        
        Args:
            screenshot: Current screenshot
            question: Visual analysis question
            
        Returns:
            Cached result dict or None if not found/expired
        """
        image_hash = self._compute_image_hash(screenshot)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Query cache
            cursor.execute("""
                SELECT result_json, created_at, access_count
                FROM visual_analysis
                WHERE image_hash = ? AND question = ?
            """, (image_hash, question))
            
            row = cursor.fetchone()
            
            if row:
                result_json, created_at, access_count = row
                age = time.time() - created_at
                
                # Check if expired
                if age > self.max_age:
                    log_debug(f"   💨 Cache expired for visual analysis (age: {age:.1f}s)")
                    # Delete expired entry
                    cursor.execute("""
                        DELETE FROM visual_analysis
                        WHERE image_hash = ? AND question = ?
                    """, (image_hash, question))
                    conn.commit()
                    self.stats["visual_misses"] += 1
                    return None
                
                # Update access stats
                cursor.execute("""
                    UPDATE visual_analysis
                    SET last_accessed = ?, access_count = ?
                    WHERE image_hash = ? AND question = ?
                """, (int(time.time()), access_count + 1, image_hash, question))
                conn.commit()
                
                # Parse and return result
                result = json.loads(result_json)
                self.stats["visual_hits"] += 1
                log_success(f"   ✅ Cache HIT for visual analysis (age: {age:.1f}s, used {access_count} times)")
                return result
            else:
                self.stats["visual_misses"] += 1
                log_debug(f"   ❌ Cache MISS for visual analysis")
                return None
                
        finally:
            conn.close()
    
    def store_visual_analysis(
        self, screenshot: Image.Image, question: str, result: Dict[str, Any]
    ):
        """
        Store visual analysis result in cache.
        
        Args:
            screenshot: Screenshot that was analyzed
            question: Visual analysis question
            result: Analysis result to cache
        """
        image_hash = self._compute_image_hash(screenshot)
        result_json = json.dumps(result, ensure_ascii=False)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            now = int(time.time())
            
            # Insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO visual_analysis
                (image_hash, question, result_json, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (image_hash, question, result_json, now, now))
            
            conn.commit()
            log_debug(f"   💾 Cached visual analysis result (hash: {image_hash[:12]}...)")
            
        finally:
            conn.close()
    
    def get_screen_parser_result(
        self, screenshot: Image.Image
    ) -> Optional[List[Any]]:
        """
        Get cached ScreenParser result if available.
        
        Args:
            screenshot: Current screenshot
            
        Returns:
            Cached element list or None if not found/expired
        """
        image_hash = self._compute_image_hash(screenshot)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Query cache
            cursor.execute("""
                SELECT elements_pickle, created_at, access_count
                FROM screen_parser
                WHERE image_hash = ?
            """, (image_hash,))
            
            row = cursor.fetchone()
            
            if row:
                elements_pickle, created_at, access_count = row
                age = time.time() - created_at
                
                # Check if expired
                if age > self.max_age:
                    log_debug(f"   💨 Cache expired for ScreenParser (age: {age:.1f}s)")
                    # Delete expired entry
                    cursor.execute("""
                        DELETE FROM screen_parser
                        WHERE image_hash = ?
                    """, (image_hash,))
                    conn.commit()
                    self.stats["parser_misses"] += 1
                    return None
                
                # Update access stats
                cursor.execute("""
                    UPDATE screen_parser
                    SET last_accessed = ?, access_count = ?
                    WHERE image_hash = ?
                """, (int(time.time()), access_count + 1, image_hash))
                conn.commit()
                
                # Unpickle and return elements
                elements = pickle.loads(elements_pickle)
                self.stats["parser_hits"] += 1
                log_success(f"   ✅ Cache HIT for ScreenParser ({len(elements)} elements, age: {age:.1f}s, used {access_count} times)")
                return elements
            else:
                self.stats["parser_misses"] += 1
                log_debug(f"   ❌ Cache MISS for ScreenParser")
                return None
                
        finally:
            conn.close()
    
    def store_screen_parser_result(
        self, screenshot: Image.Image, elements: List[Any]
    ):
        """
        Store ScreenParser result in cache.
        
        Args:
            screenshot: Screenshot that was parsed
            elements: Parsed elements to cache
        """
        image_hash = self._compute_image_hash(screenshot)
        elements_pickle = pickle.dumps(elements, protocol=pickle.HIGHEST_PROTOCOL)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            now = int(time.time())
            
            # Insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO screen_parser
                (image_hash, elements_pickle, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, 1)
            """, (image_hash, elements_pickle, now, now))
            
            conn.commit()
            log_debug(f"   💾 Cached ScreenParser result ({len(elements)} elements, hash: {image_hash[:12]}...)")
            
        finally:
            conn.close()
    
    def cleanup_expired(self) -> Tuple[int, int]:
        """
        Remove expired cache entries.
        
        Returns:
            Tuple of (visual_deleted, parser_deleted) counts
        """
        cutoff = int(time.time() - self.max_age)
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Delete expired visual analysis
            cursor.execute("""
                DELETE FROM visual_analysis
                WHERE created_at < ?
            """, (cutoff,))
            visual_deleted = cursor.rowcount
            
            # Delete expired screen parser
            cursor.execute("""
                DELETE FROM screen_parser
                WHERE created_at < ?
            """, (cutoff,))
            parser_deleted = cursor.rowcount
            
            conn.commit()
            
            if visual_deleted + parser_deleted > 0:
                log_info(f"   🧹 Cleaned up {visual_deleted} visual + {parser_deleted} parser expired cache entries")
            
            return visual_deleted, parser_deleted
            
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Count entries
            cursor.execute("SELECT COUNT(*) FROM visual_analysis")
            visual_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM screen_parser")
            parser_count = cursor.fetchone()[0]
            
            # Calculate hit rates
            total_visual = self.stats["visual_hits"] + self.stats["visual_misses"]
            visual_hit_rate = (
                self.stats["visual_hits"] / total_visual * 100
                if total_visual > 0
                else 0
            )
            
            total_parser = self.stats["parser_hits"] + self.stats["parser_misses"]
            parser_hit_rate = (
                self.stats["parser_hits"] / total_parser * 100
                if total_parser > 0
                else 0
            )
            
            return {
                "visual_cached": visual_count,
                "parser_cached": parser_count,
                "visual_hits": self.stats["visual_hits"],
                "visual_misses": self.stats["visual_misses"],
                "visual_hit_rate": visual_hit_rate,
                "parser_hits": self.stats["parser_hits"],
                "parser_misses": self.stats["parser_misses"],
                "parser_hit_rate": parser_hit_rate,
            }
            
        finally:
            conn.close()
    
    def clear(self):
        """Clear all cache entries"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM visual_analysis")
            cursor.execute("DELETE FROM screen_parser")
            conn.commit()
            log_info("   🧹 Cleared all cache entries")
            
        finally:
            conn.close()


# Global cache instance (singleton)
_cache_instance: Optional[ScreenCache] = None


def get_screen_cache() -> ScreenCache:
    """Get global cache instance (singleton)"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ScreenCache()
    return _cache_instance
