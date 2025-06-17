import asyncio
import json
import time
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import hashlib
import logging

logger = logging.getLogger(__name__)

class CacheService:
    """In-memory cache service with TTL support for improved performance"""
    
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate a cache key from prefix and parameters"""
        # Create a deterministic key from the parameters
        key_data = json.dumps(kwargs, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"{prefix}:{key_hash}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry["expires_at"] < time.time():
                del self._cache[key]
                return None
            
            entry["last_accessed"] = time.time()
            logger.debug(f"Cache hit for key: {key}")
            return entry["value"]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        if ttl is None:
            ttl = self.default_ttl
        
        async with self._lock:
            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": time.time() + ttl,
                "last_accessed": time.time()
            }
            logger.debug(f"Cache set for key: {key}, TTL: {ttl}s")
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted for key: {key}")
                return True
            return False
    
    async def clear_expired(self) -> int:
        """Clear expired cache entries"""
        current_time = time.time()
        expired_keys = []
        
        async with self._lock:
            for key, entry in self._cache.items():
                if entry["expires_at"] < current_time:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleared {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self._lock:
            total_entries = len(self._cache)
            current_time = time.time()
            
            active_entries = sum(1 for entry in self._cache.values() 
                               if entry["expires_at"] > current_time)
            
            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": total_entries - active_entries,
                "cache_size_mb": len(str(self._cache)) / (1024 * 1024)
            }
    
    # Convenience methods for common cache patterns
    async def cache_search_results(self, query: str, provider: str, results: List[Dict], ttl: int = 180):
        """Cache search results"""
        key = self._generate_key("search", query=query, provider=provider)
        await self.set(key, results, ttl)
    
    async def get_cached_search_results(self, query: str, provider: str) -> Optional[List[Dict]]:
        """Get cached search results"""
        key = self._generate_key("search", query=query, provider=provider)
        return await self.get(key)
    
    async def cache_ai_response(self, messages: List[Dict], provider: str, response: str, ttl: int = 300):
        """Cache AI responses"""
        key = self._generate_key("ai_response", 
                                messages=messages[-3:],  # Only use last 3 messages for key
                                provider=provider)
        await self.set(key, response, ttl)
    
    async def get_cached_ai_response(self, messages: List[Dict], provider: str) -> Optional[str]:
        """Get cached AI response"""
        key = self._generate_key("ai_response", 
                                messages=messages[-3:],  # Only use last 3 messages for key
                                provider=provider)
        return await self.get(key)
    
    async def cache_product_data(self, product_id: str, product_data: Dict, ttl: int = 600):
        """Cache product data"""
        key = f"product:{product_id}"
        await self.set(key, product_data, ttl)
    
    async def get_cached_product_data(self, product_id: str) -> Optional[Dict]:
        """Get cached product data"""
        key = f"product:{product_id}"
        return await self.get(key)

# Global cache instance
_cache_service = None

def get_cache_service() -> CacheService:
    """Get the global cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service

# Cleanup task
async def start_cache_cleanup_task():
    """Start background task to clean up expired cache entries"""
    cache_service = get_cache_service()
    
    while True:
        try:
            await asyncio.sleep(60)  # Clean up every minute
            await cache_service.clear_expired()
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}") 