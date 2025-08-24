# Auto-generated cachehantering
from typing import Optional, Dict
import time

class MerinfoCache:
    """Enkel cache för att minska antal förfrågningar"""
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        if len(self.cache) >= self.max_size:
            # Ta bort äldsta
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][-1])
            del self.cache[oldest_key]
        
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()

