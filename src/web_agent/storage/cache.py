"""
Caching utilities for LLM responses and DOM states.
"""
from typing import Optional, Any, Dict
import time
import hashlib
import json


class LRUCache:
    """Simple LRU cache implementation"""
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, tuple] = {}
        self.access_order = []
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)
            return None
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        return value
    
    def set(self, key: str, value: Any):
        if len(self.cache) >= self.max_size and key not in self.cache:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        self.cache[key] = (value, time.time())
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
    
    def clear(self):
        self.cache.clear()
        self.access_order.clear()


class LLMCache:
    """Cache for LLM responses"""
    
    def __init__(self, ttl: int = 3600):
        self.cache = LRUCache(max_size=200, ttl=ttl)
    
    def _make_key(self, prompt: str, model: str = "") -> str:
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, prompt: str, model: str = "") -> Optional[Any]:
        key = self._make_key(prompt, model)
        return self.cache.get(key)
    
    def set(self, prompt: str, response: Any, model: str = ""):
        key = self._make_key(prompt, model)
        self.cache.set(key, response)
    
    def clear(self):
        self.cache.clear()


class DOMCache:
    """Cache for DOM states"""
    
    def __init__(self, ttl: int = 30):
        self.cache = LRUCache(max_size=50, ttl=ttl)
    
    def get(self, url: str) -> Optional[Dict]:
        return self.cache.get(url)
    
    def set(self, url: str, dom_state: Dict):
        self.cache.set(url, dom_state)
    
    def clear(self):
        self.cache.clear()
