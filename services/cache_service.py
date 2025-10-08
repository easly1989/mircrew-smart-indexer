"""
Cache service for in-memory caching (no external dependencies).
"""
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from config.settings import settings


class CacheService:
    """Service for in-memory caching operations."""

    def __init__(self):
        self.cache = {}  # key -> {'data': data, 'expires': timestamp}

    def _get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key not in self.cache:
            return None
        entry = self.cache[key]
        if time.time() > entry['expires']:
            del self.cache[key]
            return None
        return entry['data']

    def _set(self, key: str, data: Any, ttl: int) -> None:
        """Set cached data with TTL."""
        self.cache[key] = {
            'data': data,
            'expires': time.time() + ttl
        }

    def _delete(self, key: str) -> None:
        """Delete cached data."""
        if key in self.cache:
            del self.cache[key]

    def _incr(self, key: str) -> int:
        """Increment counter, return new value."""
        current = self._get(key) or 0
        new_value = current + 1
        self._set(key, new_value, settings.like_counts_ttl)
        return new_value

    def _decr(self, key: str) -> int:
        """Decrement counter, return new value."""
        current = self._get(key) or 0
        new_value = current - 1
        self._set(key, new_value, settings.like_counts_ttl)
        return new_value

    def get_thread_status(self, thread_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get cached thread status."""
        key = f"thread:status:{thread_id}"
        data = self._get(key)
        if data:
            status = json.loads(data)
            # Add user-specific like status if user provided
            if user_id:
                like_key = f"thread:like:{thread_id}:{user_id}"
                user_liked = self._get(like_key) is not None
                status['user_liked'] = user_liked
            return status
        return None

    def set_thread_status(self, thread_id: str, status: Dict) -> None:
        """Cache thread status."""
        key = f"thread:status:{thread_id}"
        self._set(key, json.dumps(status), settings.thread_metadata_ttl)

    def get_like_count(self, thread_id: str) -> Optional[int]:
        """Get cached like count."""
        key = f"thread:likes:{thread_id}"
        count = self._get(key)
        return int(count) if count else None

    def set_like_count(self, thread_id: str, count: int) -> None:
        """Cache like count."""
        key = f"thread:likes:{thread_id}"
        self._set(key, str(count), settings.like_counts_ttl)

    def increment_like_count(self, thread_id: str) -> int:
        """Increment like count and return new value."""
        key = f"thread:likes:{thread_id}"
        return self._incr(key)

    def decrement_like_count(self, thread_id: str) -> int:
        """Decrement like count and return new value."""
        key = f"thread:likes:{thread_id}"
        return self._decr(key)

    def set_user_like(self, thread_id: str, user_id: str) -> None:
        """Mark that user has liked thread."""
        key = f"thread:like:{thread_id}:{user_id}"
        self._set(key, "1", settings.user_like_status_ttl)

    def remove_user_like(self, thread_id: str, user_id: str) -> None:
        """Remove user's like mark."""
        key = f"thread:like:{thread_id}:{user_id}"
        self._delete(key)

    def get_search_results(self, query: str, season: Optional[int] = None) -> Optional[Dict]:
        """Get cached search results."""
        key = f"search:{query}:{season or ''}"
        data = self._get(key)
        return json.loads(data) if data else None

    def set_search_results(self, query: str, season: Optional[int], results: Dict) -> None:
        """Cache search results."""
        key = f"search:{query}:{season or ''}"
        self._set(key, json.dumps(results), settings.search_results_ttl)

    def invalidate_thread_cache(self, thread_id: str) -> None:
        """Invalidate all cache entries for a thread."""
        keys_to_delete = []
        for key in self.cache.keys():
            if key.startswith(f"thread:") and (f":status:{thread_id}" in key or f":metadata:{thread_id}" in key or f":like:{thread_id}:" in key):
                keys_to_delete.append(key)
        for key in keys_to_delete:
            self._delete(key)

    def invalidate_user_likes_cache(self, user_id: str) -> None:
        """Invalidate user's like status cache."""
        keys_to_delete = []
        for key in self.cache.keys():
            if key.startswith("thread:like:") and key.endswith(f":{user_id}"):
                keys_to_delete.append(key)
        for key in keys_to_delete:
            self._delete(key)

    def get_cached_metadata(self, thread_id: str) -> Optional[Dict]:
        """Get cached thread metadata."""
        key = f"thread:metadata:{thread_id}"
        data = self._get(key)
        return json.loads(data) if data else None

    def set_cached_metadata(self, thread_id: str, metadata: Dict) -> None:
        """Cache thread metadata."""
        key = f"thread:metadata:{thread_id}"
        self._set(key, json.dumps(metadata), settings.thread_metadata_ttl)