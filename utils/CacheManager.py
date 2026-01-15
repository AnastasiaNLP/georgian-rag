"""
Cache manager with two-level strategy (temporary + permanent).
"""

import json
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Enhanced Cache Manager with Two-Level Strategy.

    LEVEL 1: Temporary Cache (with TTL)
    - Translations (temporary)
    - Embeddings
    - Search results
    - Purpose: SPEED (1-2ms vs 100-500ms)

    LEVEL 2: Permanent Storage (NO TTL)
    - Enrichment data (Wikipedia, photos)
    - Important translations (attraction names)
    - Location data, prices
    - Purpose: NEVER lose expensive API data

    Namespaces:
    TEMPORARY (with TTL):
    - translation:temp
    - enrichment:temp
    - search:dense:embeddings
    - search:dense:results
    - search:bm25:results
    - search:hybrid:final
    - search:prefilter

    PERMANENT (NO TTL):
    - enrichment:permanent
    - translation:permanent
    """

    def __init__(self, redis_client=None, default_ttl: int = 86400):
        """
        Initialize CacheManager.

        Args:
            redis_client: Redis client instance (optional)
            default_ttl: Default time-to-live in seconds (default: 24 hours)
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.memory_cache = {}

        self.stats = {
            'global': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0, 'deletes': 0},
            'permanent_sets': 0,
            'temporary_sets': 0,

            # temporary namespaces
            'translation:temp': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'enrichment:temp': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'search:dense:embeddings': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'search:dense:results': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'search:bm25:results': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'search:hybrid:final': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'search:prefilter': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},

            # permanent namespaces
            'enrichment:permanent': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
            'translation:permanent': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0}
        }

        logger.info(f"CacheManager initialized (Redis: {'available' if redis_client else 'memory only'})")
        logger.info("Two-level caching: Temporary (TTL) + Permanent (NO TTL)")

    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced cache key"""
        return f"{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            namespace: Cache namespace (e.g., 'translation:temp', 'enrichment:permanent')
            key: Cache key (usually hash of parameters)

        Returns:
            Cached value or None if not found
        """
        cache_key = self._make_key(namespace, key)

        if self.redis:
            try:
                value = self.redis.get(cache_key)
                if value:
                    self._increment_stat(namespace, 'hits')
                    self.stats['global']['hits'] += 1
                    logger.debug(f"Cache HIT [{namespace}]: {cache_key[:50]}...")

                    if isinstance(value, bytes):
                        value = value.decode('utf-8')
                    return json.loads(value)
                else:
                    self._increment_stat(namespace, 'misses')
                    self.stats['global']['misses'] += 1
            except Exception as e:
                self._increment_stat(namespace, 'errors')
                self.stats['global']['errors'] += 1
                logger.warning(f"Redis get error: {e}")

        if cache_key in self.memory_cache:
            self._increment_stat(namespace, 'hits')
            self.stats['global']['hits'] += 1
            logger.debug(f"Memory cache HIT [{namespace}]: {cache_key[:50]}...")
            return self.memory_cache[cache_key]

        self._increment_stat(namespace, 'misses')
        self.stats['global']['misses'] += 1
        return None

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value with TTL (TEMPORARY storage).

        Use for:
        - Search results (expire after 1h)
        - Embeddings (expire after 24h)
        - Temporary translations

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            Success boolean
        """
        cache_key = self._make_key(namespace, key)
        ttl = ttl or self.default_ttl

        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)

            if self.redis:
                try:
                    self.redis.setex(cache_key, ttl, serialized)
                    logger.debug(f"TEMP Cache SET [{namespace}]: {cache_key[:50]}... (TTL: {ttl}s)")
                except Exception as e:
                    self._increment_stat(namespace, 'errors')
                    self.stats['global']['errors'] += 1
                    logger.warning(f"Redis set error: {e}")

            self.memory_cache[cache_key] = value

            self._increment_stat(namespace, 'sets')
            self.stats['global']['sets'] += 1
            self.stats['temporary_sets'] += 1
            return True

        except Exception as e:
            self._increment_stat(namespace, 'errors')
            self.stats['global']['errors'] += 1
            logger.error(f"Cache set error: {e}")
            return False

    def set_permanent(self, namespace: str, key: str, value: Any) -> bool:
        """
        Set value WITHOUT TTL (PERMANENT storage).

        CRITICAL: Data will NEVER expire automatically!

        Use for:
        - Wikipedia enrichment (expensive API calls)
        - Unsplash photos (expensive API calls)
        - Important translations (attraction names)
        - Location data, prices

        Args:
            namespace: Should be 'enrichment:permanent' or 'translation:permanent'
            key: Cache key (usually hash)
            value: Value to store permanently

        Returns:
            Success boolean
        """
        cache_key = self._make_key(namespace, key)

        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)

            if self.redis:
                try:
                    self.redis.set(cache_key, serialized)
                    logger.info(f"PERMANENT save [{namespace}]: {cache_key[:50]}...")
                except Exception as e:
                    self._increment_stat(namespace, 'errors')
                    self.stats['global']['errors'] += 1
                    logger.warning(f"Redis permanent set error: {e}")

            self.memory_cache[cache_key] = value

            self._increment_stat(namespace, 'sets')
            self.stats['global']['sets'] += 1
            self.stats['permanent_sets'] += 1

            logger.info(f"Permanently saved in namespace '{namespace}'")
            return True

        except Exception as e:
            self._increment_stat(namespace, 'errors')
            self.stats['global']['errors'] += 1
            logger.error(f"Permanent cache set error: {e}")
            return False

    def has_permanent(self, namespace: str, key: str) -> bool:
        """
        Check if value exists in permanent storage.

        Args:
            namespace: Permanent namespace
            key: Cache key

        Returns:
            True if exists, False otherwise
        """
        value = self.get(namespace, key)
        return value is not None

    def delete(self, namespace: str, key: str) -> bool:
        """
        Delete specific key from cache.

        Args:
            namespace: Cache namespace
            key: Cache key

        Returns:
            Success boolean
        """
        cache_key = self._make_key(namespace, key)

        if self.redis:
            try:
                self.redis.delete(cache_key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")

        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]

        self.stats['global']['deletes'] += 1
        return True

    def clear_namespace(self, namespace: str) -> int:
        """
        Clear all keys in a namespace.

        Args:
            namespace: Namespace to clear (e.g., 'translation:temp')

        Returns:
            Number of keys deleted
        """
        count = 0

        if self.redis:
            try:
                pattern = f"{namespace}:*"
                keys = self.redis.keys(pattern)
                if keys:
                    count = self.redis.delete(*keys)
                    logger.info(f"Cleared {count} keys from Redis namespace '{namespace}'")
            except Exception as e:
                logger.warning(f"Redis clear namespace error: {e}")

        prefix = f"{namespace}:"
        memory_keys = [k for k in list(self.memory_cache.keys()) if k.startswith(prefix)]
        for k in memory_keys:
            del self.memory_cache[k]
            count += 1

        logger.info(f"Cleared total {count} keys from namespace '{namespace}'")
        return count

    def get_stats(self, namespace: Optional[str] = None) -> dict:
        """
        Get cache statistics.

        Args:
            namespace: Specific namespace or None for global stats

        Returns:
            Dictionary with statistics
        """
        if namespace:
            ns_stats = self.stats.get(namespace, {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0})
            total = ns_stats['hits'] + ns_stats['misses']
            hit_rate = (ns_stats['hits'] / total * 100) if total > 0 else 0

            return {
                'hits': ns_stats['hits'],
                'misses': ns_stats['misses'],
                'sets': ns_stats.get('sets', 0),
                'errors': ns_stats.get('errors', 0),
                'total_requests': total,
                'hit_rate_percent': round(hit_rate, 2),
                'is_permanent': ':permanent' in namespace
            }
        else:
            global_stats = self.stats['global']
            total = global_stats['hits'] + global_stats['misses']
            hit_rate = (global_stats['hits'] / total * 100) if total > 0 else 0

            temp_namespaces = {
                ns: self.get_stats(ns)
                for ns in ['translation:temp', 'enrichment:temp', 'search:dense:embeddings',
                          'search:dense:results', 'search:bm25:results',
                          'search:hybrid:final', 'search:prefilter']
            }

            perm_namespaces = {
                ns: self.get_stats(ns)
                for ns in ['enrichment:permanent', 'translation:permanent']
            }

            return {
                'hits': global_stats['hits'],
                'misses': global_stats['misses'],
                'sets': global_stats['sets'],
                'errors': global_stats['errors'],
                'deletes': global_stats['deletes'],
                'total_requests': total,
                'hit_rate_percent': round(hit_rate, 2),
                'memory_cache_size': len(self.memory_cache),
                'redis_connected': self.redis is not None,
                'permanent_sets': self.stats['permanent_sets'],
                'temporary_sets': self.stats['temporary_sets'],
                'temporary_namespaces': temp_namespaces,
                'permanent_namespaces': perm_namespaces
            }

    def reset_stats(self, namespace: Optional[str] = None):
        """
        Reset statistics.

        Args:
            namespace: Specific namespace or None for all
        """
        if namespace:
            if namespace in self.stats:
                self.stats[namespace] = {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0}
            logger.info(f"Stats reset for namespace '{namespace}'")
        else:
            self.stats = {
                'global': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0, 'deletes': 0},
                'permanent_sets': 0,
                'temporary_sets': 0,
                'translation:temp': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'enrichment:temp': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'search:dense:embeddings': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'search:dense:results': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'search:bm25:results': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'search:hybrid:final': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'search:prefilter': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'enrichment:permanent': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0},
                'translation:permanent': {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0}
            }
            logger.info("All cache stats reset")

    def _increment_stat(self, namespace: str, stat: str):
        """
        Internal: increment statistic counter.

        Args:
            namespace: Namespace to update
            stat: Statistic name (hits, misses, sets, errors)
        """
        if namespace not in self.stats:
            self.stats[namespace] = {'hits': 0, 'misses': 0, 'sets': 0, 'errors': 0}
        self.stats[namespace][stat] = self.stats[namespace].get(stat, 0) + 1