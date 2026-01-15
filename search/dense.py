"""
Dense semantic search engine with smart caching.
"""

import time
import logging
import hashlib
from typing import Dict, List, Optional, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny, HasIdCondition

from config.settings import config
from core.types import SearchResult
from utils.model_manager import model_manager

logger = logging.getLogger(__name__)


class DenseSearchEngine:
    """
    Dense vector search with smart caching.

    Features:
    - Cache key based on dense_query only (without candidate_ids)
    - TTL for cache entries (1 hour)
    - LRU eviction when cache is full
    - Cache works across different candidate sets
    """

    def __init__(self, client: QdrantClient, collection_name: str, embedding_model: str = None):
        self.client = client
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        self._search_count = 0
        self._model = None
        self._model_name = embedding_model or config.embedding.model_name

        self._results_cache = {}
        self._cache_max_size = 500
        self._cache_ttl = 3600  # 1 hour TTL
        self._cache_hits = 0
        self._cache_misses = 0

        logger.info("DenseSearchEngine initialized with smart caching")

    @property
    def model(self):
        """Lazy loading of embedding model"""
        if self._model is None:
            logger.info(f"Loading model with caching: {self._model_name}")
            self._model = model_manager.get_model(self._model_name)
        return self._model

    def _create_cache_key(self, dense_query: str, top_k: int, metadata_filter: Optional = None) -> str:
        """Create cache key without candidate_ids"""
        normalized_query = dense_query.strip().lower()

        key_parts = [
            normalized_query,
            str(top_k),
            str(hash(str(metadata_filter))) if metadata_filter else "no_filter"
        ]

        key_string = "|".join(key_parts)
        cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()

        return f"dense:{cache_key}"

    def _get_from_cache(self, cache_key: str) -> Optional[List]:
        """Get from cache with TTL check"""
        if cache_key not in self._results_cache:
            self._cache_misses += 1
            return None

        cached_data = self._results_cache[cache_key]

        if time.time() - cached_data['timestamp'] > self._cache_ttl:
            del self._results_cache[cache_key]
            self._cache_misses += 1
            logger.debug(f"Dense cache entry expired: {cache_key[:16]}")
            return None

        self._cache_hits += 1
        logger.debug(f"Dense cache HIT: {cache_key[:16]}...")
        return cached_data['results']

    def _save_to_cache(self, cache_key: str, results: List):
        """Save to cache with LRU eviction"""
        if len(self._results_cache) >= self._cache_max_size:
            oldest_key = min(
                self._results_cache.keys(),
                key=lambda k: self._results_cache[k]['timestamp']
            )
            del self._results_cache[oldest_key]
            logger.debug("Dense: Evicted oldest cache entry")

        self._results_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }
        logger.debug(f"Dense cached: {cache_key[:16]}... ({len(results)} results)")

    def search(self,
               dense_query: str,
               candidate_ids: Optional[List[str]] = None,
               top_k: int = 10,
               metadata_filter: Optional = None) -> List[SearchResult]:
        """
        Universal dense search with smart caching.
        """
        if not dense_query.strip():
            logger.warning("Empty dense_query provided")
            return []

        start_time = time.time()
        self._search_count += 1

        cache_key = self._create_cache_key(dense_query, top_k, metadata_filter)
        cached_results = self._get_from_cache(cache_key)

        if cached_results is not None:
            logger.info(f"Dense cache HIT: {dense_query[:50]}...")

            if candidate_ids:
                candidate_ids_set = set(candidate_ids)
                filtered_results = [
                    r for r in cached_results
                    if r.doc_id in candidate_ids_set
                ]
                logger.debug(f"Filtered {len(cached_results)} -> {len(filtered_results)} by candidates")
                return filtered_results[:top_k]

            return cached_results[:top_k]

        logger.info(f"Dense cache MISS: {dense_query[:50]}...")

        try:
            query_vector = self.model.encode(dense_query).tolist()
            ids_filter, field_filter = self._build_combined_filter(candidate_ids, metadata_filter)
            search_params = {
                "collection_name":self.collection_name,
                "query_vector":query_vector,
                "limit":top_k * 2,
                "with_payload":True
            }
            if ids_filter:
                # using HasIdCondition to filter by ID
                from qdrant_client.models import HasIdCondition, Filter
                search_params["query_filter"] = Filter(
                    must=[HasIdCondition(has_id=ids_filter)]
                )
                logger.debug(f"Using HasIdCondition with {len(ids_filter)} IDs")
            elif field_filter:
                # using metadata filters
                search_params["query_filter"] = field_filter
                logger.debug("Using metadata filter")

        # performing a search
            search_result = self.client.search(**search_params)
            results = []

            for point in search_result:
                if point.score > 0.05:
                    results.append(SearchResult(
                        doc_id=str(point.id),
                        score=float(point.score),
                        source='dense_focused' if candidate_ids else 'dense_standard',
                        metadata=point.payload,
                        content=point.payload.get('description', '')
                    ))

            if results:
                self._save_to_cache(cache_key, results)

            search_time = time.time() - start_time
            search_type = "focused" if candidate_ids else "standard"
            logger.info(f"Dense {search_type} search completed in {search_time:.3f}s: {len(results)} results")

            return results[:top_k]

        except Exception as e:
            logger.error(f"Dense search failed for query '{dense_query[:50]}...': {e}")
            import traceback
            traceback.print_exc()
            return []

    def search_within_candidates(self, dense_query: str, candidate_ids: List[str], top_k: int = 10) -> List[SearchResult]:
        """Wrapper for search within candidates"""
        return self.search(dense_query=dense_query, candidate_ids=candidate_ids, top_k=top_k)

    def _build_combined_filter(self,
                              candidate_ids: Optional[List],
                              metadata_filter: Optional) -> tuple:
        """Build combined filter for search"""
        ids_to_filter = None
        if candidate_ids:
            try:
                ids_to_filter = []
                for cid in candidate_ids:
                    if isinstance(cid, int):
                        ids_to_filter.append(cid)
                    elif isinstance(cid, str):
                        if cid.isdigit():
                            ids_to_filter.append(int(cid))
                        else:
                            # Если UUID string, оставляем как есть
                            ids_to_filter.append(cid)
                    else:
                        ids_to_filter.append(cid)

                if ids_to_filter:
                    logger.debug(f"Filtering by {len(ids_to_filter)} IDs")
            except Exception as e:
                logger.warning(f"Failed to process candidate IDs: {e}")
                ids_to_filter = None

    # metadata filters remain as is
        return ids_to_filter, metadata_filter

    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics with cache metrics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        try:
            model_info = model_manager.get_stats()
        except:
            model_info = {}

        return {
            'total_searches': self._search_count,
            'cache_stats': {
                'cache_type': 'results_cache',
                'cache_size': len(self._results_cache),
                'max_size': self._cache_max_size,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'hit_rate': round(hit_rate, 2),
                'total_requests': total_requests,
                'ttl_seconds': self._cache_ttl
            },
            'model_manager_stats': model_info,
            'optimization_enabled': True
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get separate cache statistics"""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'cache_type': 'results_cache',
            'cache_size': len(self._results_cache),
            'max_cache_size': self._cache_max_size,
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests,
            'ttl_seconds': self._cache_ttl
        }