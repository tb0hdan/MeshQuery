"""
Simple in-memory cache for analytics data to improve performance.
"""

import logging
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if time.time() > entry["expires_at"]:
                del self._cache[key]
                return None

            return entry["value"]

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
                "created_at": time.time(),
            }

    def clear(self, key: str | None = None) -> None:
        """Clear cache entry or all entries."""
        with self._lock:
            if key is None:
                self._cache.clear()
            elif key in self._cache:
                del self._cache[key]

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed entries."""
        current_time = time.time()
        removed_count = 0

        with self._lock:
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]

            for key in expired_keys:
                del self._cache[key]
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired cache entries")

        return removed_count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            current_time = time.time()
            active_entries = sum(
                1
                for entry in self._cache.values()
                if current_time <= entry["expires_at"]
            )

            return {
                "total_entries": len(self._cache),
                "active_entries": active_entries,
                "expired_entries": len(self._cache) - active_entries,
            }


# Global cache instance
_analytics_cache = SimpleCache(default_ttl=300)  # 5 minutes TTL


def get_analytics_cache() -> SimpleCache:
    """Get the global analytics cache instance."""
    return _analytics_cache


def cache_key_for_traceroute_analytics(hours: int) -> str:
    """Generate cache key for traceroute analytics."""
    return f"traceroute_analytics_{hours}h"


def cache_key_for_node_stats() -> str:
    """Generate cache key for node statistics."""
    return "node_stats"


def cache_key_for_packet_stats() -> str:
    """Generate cache key for packet statistics."""
    return "packet_stats"
