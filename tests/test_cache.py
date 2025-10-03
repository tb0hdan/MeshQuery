"""Tests for cache utility functions."""

import pytest
import time
import threading
from unittest.mock import patch
from src.malla.utils.cache import SimpleCache, get_analytics_cache


class TestSimpleCache:
    """Test cases for SimpleCache class."""

    def test_init_default_ttl(self):
        """Test cache initialization with default TTL."""
        cache = SimpleCache()
        assert cache.default_ttl == 300

    def test_init_custom_ttl(self):
        """Test cache initialization with custom TTL."""
        cache = SimpleCache(default_ttl=600)
        assert cache.default_ttl == 600

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = SimpleCache()
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = SimpleCache()
        assert cache.get("nonexistent") is None

    def test_set_with_custom_ttl(self):
        """Test setting value with custom TTL."""
        cache = SimpleCache(default_ttl=300)
        cache.set("test_key", "test_value", ttl=600)
        assert cache.get("test_key") == "test_value"

    def test_expiration(self):
        """Test that expired entries are removed."""
        cache = SimpleCache()

        # Set with very short TTL
        cache.set("test_key", "test_value", ttl=1)
        assert cache.get("test_key") == "test_value"

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("test_key") is None

    @patch('time.time')
    def test_expiration_mock(self, mock_time):
        """Test expiration using mocked time."""
        cache = SimpleCache()

        # Set initial time
        mock_time.return_value = 1000
        cache.set("test_key", "test_value", ttl=10)

        # Before expiration
        mock_time.return_value = 1005
        assert cache.get("test_key") == "test_value"

        # After expiration
        mock_time.return_value = 1015
        assert cache.get("test_key") is None

    def test_clear_specific_key(self):
        """Test clearing a specific key."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_clear_all(self):
        """Test clearing all keys."""
        cache = SimpleCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_clear_nonexistent_key(self):
        """Test clearing a key that doesn't exist."""
        cache = SimpleCache()
        cache.clear("nonexistent")  # Should not raise an error

    @patch('time.time')
    def test_cleanup_expired(self, mock_time):
        """Test cleanup of expired entries."""
        cache = SimpleCache()

        # Set initial time and add entries
        mock_time.return_value = 1000
        cache.set("key1", "value1", ttl=10)
        cache.set("key2", "value2", ttl=20)
        cache.set("key3", "value3", ttl=30)

        # Move time forward to expire some entries
        mock_time.return_value = 1025
        removed_count = cache.cleanup_expired()

        assert removed_count == 2  # key1 and key2 should be expired
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    @patch('time.time')
    def test_get_stats(self, mock_time):
        """Test cache statistics."""
        cache = SimpleCache()

        # Set initial time
        mock_time.return_value = 1000
        cache.set("active1", "value1", ttl=20)
        cache.set("active2", "value2", ttl=30)
        cache.set("expired1", "value3", ttl=5)

        # Move time forward to expire one entry
        mock_time.return_value = 1010
        stats = cache.get_stats()

        assert stats["total_entries"] == 3
        assert stats["active_entries"] == 2
        assert stats["expired_entries"] == 1

    def test_thread_safety(self):
        """Test that cache operations are thread-safe."""
        cache = SimpleCache()
        results = []

        def worker(thread_id):
            for i in range(100):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"
                cache.set(key, value)
                retrieved = cache.get(key)
                if retrieved == value:
                    results.append(True)
                else:
                    results.append(False)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should have succeeded
        assert all(results)
        assert len(results) == 500  # 5 threads * 100 operations

    def test_complex_data_types(self):
        """Test caching complex data types."""
        cache = SimpleCache()

        # Test list
        test_list = [1, 2, 3, {"nested": "dict"}]
        cache.set("list_key", test_list)
        assert cache.get("list_key") == test_list

        # Test dict
        test_dict = {"key": "value", "nested": [1, 2, 3]}
        cache.set("dict_key", test_dict)
        assert cache.get("dict_key") == test_dict

        # Test None
        cache.set("none_key", None)
        assert cache.get("none_key") is None


class TestGetAnalyticsCache:
    """Test cases for get_analytics_cache function."""

    def test_get_analytics_cache_returns_instance(self):
        """Test that get_analytics_cache returns a SimpleCache instance."""
        cache = get_analytics_cache()
        assert isinstance(cache, SimpleCache)

    def test_get_analytics_cache_singleton(self):
        """Test that get_analytics_cache returns the same instance."""
        cache1 = get_analytics_cache()
        cache2 = get_analytics_cache()
        assert cache1 is cache2

    def test_analytics_cache_default_ttl(self):
        """Test that analytics cache has correct default TTL."""
        cache = get_analytics_cache()
        assert cache.default_ttl == 300  # 5 minutes

    def test_analytics_cache_functionality(self):
        """Test that analytics cache works correctly."""
        cache = get_analytics_cache()

        # Clear any existing data
        cache.clear()

        # Test basic functionality
        cache.set("test_analytics", {"data": "test"})
        result = cache.get("test_analytics")
        assert result == {"data": "test"}

        # Clean up
        cache.clear()