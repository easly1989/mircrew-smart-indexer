"""
Cache service for Redis-based caching.
"""
import json
import redis
from typing import Optional, Dict, Any
from datetime import datetime

from config.settings import settings


class CacheService:
    """Service for Redis caching operations."""

    def __init__(self):
        self.redis = redis.from_url(settings.redis_url)

    def get_thread_status(self, thread_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get cached thread status."""
        key = f"thread:status:{thread_id}"
        data = self.redis.get(key)
        if data:
            status = json.loads(data)
            # Add user-specific like status if user provided
            if user_id:
                like_key = f"thread:like:{thread_id}:{user_id}"
                user_liked = self.redis.exists(like_key)
                status['user_liked'] = user_liked
            return status
        return None

    def set_thread_status(self, thread_id: str, status: Dict) -> None:
        """Cache thread status."""
        key = f"thread:status:{thread_id}"
        self.redis.setex(key, settings.thread_metadata_ttl, json.dumps(status))

    def get_like_count(self, thread_id: str) -> Optional[int]:
        """Get cached like count."""
        key = f"thread:likes:{thread_id}"
        count = self.redis.get(key)
        return int(count) if count else None

    def set_like_count(self, thread_id: str, count: int) -> None:
        """Cache like count."""
        key = f"thread:likes:{thread_id}"
        self.redis.setex(key, settings.like_counts_ttl, str(count))

    def increment_like_count(self, thread_id: str) -> int:
        """Increment like count and return new value."""
        key = f"thread:likes:{thread_id}"
        return self.redis.incr(key)

    def decrement_like_count(self, thread_id: str) -> int:
        """Decrement like count and return new value."""
        key = f"thread:likes:{thread_id}"
        return self.redis.decr(key)

    def set_user_like(self, thread_id: str, user_id: str) -> None:
        """Mark that user has liked thread."""
        key = f"thread:like:{thread_id}:{user_id}"
        self.redis.setex(key, settings.user_like_status_ttl, "1")

    def remove_user_like(self, thread_id: str, user_id: str) -> None:
        """Remove user's like mark."""
        key = f"thread:like:{thread_id}:{user_id}"
        self.redis.delete(key)

    def get_search_results(self, query: str, season: Optional[int] = None) -> Optional[Dict]:
        """Get cached search results."""
        key = f"search:{query}:{season or ''}"
        data = self.redis.get(key)
        return json.loads(data) if data else None

    def set_search_results(self, query: str, season: Optional[int], results: Dict) -> None:
        """Cache search results."""
        key = f"search:{query}:{season or ''}"
        self.redis.setex(key, settings.search_results_ttl, json.dumps(results))

    def invalidate_thread_cache(self, thread_id: str) -> None:
        """Invalidate all cache entries for a thread."""
        pattern = f"thread:*:{thread_id}*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    def invalidate_user_likes_cache(self, user_id: str) -> None:
        """Invalidate user's like status cache."""
        pattern = f"thread:like:*:{user_id}"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    def get_cached_metadata(self, thread_id: str) -> Optional[Dict]:
        """Get cached thread metadata."""
        key = f"thread:metadata:{thread_id}"
        data = self.redis.get(key)
        return json.loads(data) if data else None

    def set_cached_metadata(self, thread_id: str, metadata: Dict) -> None:
        """Cache thread metadata."""
        key = f"thread:metadata:{thread_id}"
        self.redis.setex(key, settings.thread_metadata_ttl, json.dumps(metadata))