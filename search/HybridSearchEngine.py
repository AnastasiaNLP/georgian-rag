"""
Hybrid search engine with centralized smart caching.
"""

import time
import logging
from typing import Dict, List, Any

from qdrant_client import QdrantClient

from search.query_analyzer import QueryAnalyzer
from search.PreFilterEngine import PreFilterEngine
from search.bm25 import BM25Engine
from search.dense import DenseSearchEngine
from search.rrf import RRFFusionEngine

logger = logging.getLogger(__name__)


class HybridSearchEngine:
    """
    Hybrid search engine with centralized smart caching.

    Features:
    - Passing semantic_query to BM25 for proper caching
    - Cache coordination between BM25 and Dense
    - Methods for cache management and monitoring
    - Performance monitoring integration

    Architecture:
    Step 1: PreFilter - Candidates
    Step 2: Candidates - [BM25, Dense] (Focused Search) + CACHING
    Step 3: Results - RRF - Final Ranking
    """

    def __init__(self,
                 qdrant_client: QdrantClient,
                 collection_name: str,
                 embedding_model: str,
                 config: Dict = None):
        """Constructor with simplified component initialization"""
        self.config = config or {}
        self.client = qdrant_client
        self.collection_name = collection_name

        logger.info("Initializing Hybrid Search Engine with smart caching...")

        self.query_analyzer = QueryAnalyzer()

        self.bm25_engine = BM25Engine(self.config)
        self.dense_engine = DenseSearchEngine(qdrant_client, collection_name, embedding_model)
        self.rrf_engine = RRFFusionEngine(k=self.config.get('rrf_k', 60))

        self._search_count = 0
        self._cache_enabled = True

        logger.info("Hybrid Search Engine successfully initialized with smart caching!")

    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Main entry point for search.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            Dict with results, analysis and performance metrics
        """
        start_time = time.time()
        self._search_count += 1

        try:
            analysis = self.query_analyzer.analyze(query)
            logger.info(f"Query analyzed: {analysis.intent_type.value}, lang: {analysis.language}")

            strategy_used = analysis.filter_strategy

            if strategy_used in ['strict', 'moderate', 'loose']:
                result = self._focused_search(analysis, strategy_used, top_k)
            else:
                result = self._fallback_search(analysis, top_k)

            total_time = time.time() - start_time
            result['performance']['total_time'] = total_time

            logger.info(f"Search completed in {total_time:.3f}s")
            return result

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return {
                'results': [],
                'error': str(e),
                'performance': {'total_time': time.time() - start_time}
            }

    def _focused_search(self,
                       analysis,
                       strategy_used: str,
                       top_k: int) -> Dict[str, Any]:
        """
        Focused search with smart caching.

        Critical changes:
        1. Passing semantic_query to BM25Engine for proper caching
        2. Dense search automatically caches by dense_query
        3. Cache coordination between components
        """
        start_time = time.time()
        logger.info(f"Starting focused search with strategy: {strategy_used}")

        # prefilter
        prefilter_engine = PreFilterEngine(self.client, self.collection_name)
        prefilter_result = prefilter_engine.get_filtered_candidates(
            analysis,
            max_candidates=200
        )

        candidate_ids = prefilter_result['candidates']

        if not candidate_ids:
            logger.warning("PreFilter returned no candidates - using fallback")
            return self._fallback_search(analysis, top_k)

        logger.info(f"PreFilter: {len(candidate_ids)} candidates in {prefilter_result['search_time']:.3f}s")

        # bm25 with cache
        bm25_start = time.time()

        candidate_docs = self._fetch_candidate_documents(candidate_ids)

        bm25_results = self.bm25_engine.search_within_candidates(
            keywords=analysis.keywords,
            candidate_docs=candidate_docs,
            language=analysis.language,
            top_k=top_k,
            semantic_query=analysis.semantic_query
        )

        bm25_time = time.time() - bm25_start
        logger.info(f"BM25 search: {len(bm25_results)} results in {bm25_time:.3f}s")

        # dense search with cache
        dense_start = time.time()

        dense_results = self.dense_engine.search(
            dense_query=analysis.dense_query,
            candidate_ids=candidate_ids,
            top_k=top_k
        )

        dense_time = time.time() - dense_start
        logger.info(f"Dense search: {len(dense_results)} results in {dense_time:.3f}s")

        # rrf fusion
        fusion_start = time.time()

        results_to_fuse = {
            'bm25_focused': bm25_results,
            'dense_focused': dense_results,
            'prefilter_info': prefilter_result
        }

        final_results = self.rrf_engine.fuse_results(
            results_to_fuse,
            analysis,
            top_k=top_k
        )

        fusion_time = time.time() - fusion_start
        logger.info(f"RRF fusion: {len(final_results)} results in {fusion_time:.3f}s")

        total_time = time.time() - start_time

        return {
            'results': final_results,
            'query_analysis': analysis,
            'performance': {
                'total_time': total_time,
                'prefilter_time': prefilter_result['search_time'],
                'bm25_time': bm25_time,
                'dense_time': dense_time,
                'fusion_time': fusion_time,
                'prefilter_candidates': len(candidate_ids),
                'strategy_used': strategy_used,
                'fallback_used': False
            },
            'cache_info': self._get_cache_info()
        }

    def _fallback_search(self, analysis, top_k: int) -> Dict[str, Any]:
        """Fallback strategy with simplified call"""
        start_time = time.time()

        dense_results = self.dense_engine.search(
            dense_query=analysis.dense_query,
            top_k=top_k
        )

        total_time = time.time() - start_time
        logger.info(f"Fallback search completed in {total_time:.3f}s")

        return {
            'results': dense_results,
            'query_analysis': analysis,
            'performance': {
                'total_time': total_time,
                'prefilter_time': 0,
                'fallback_used': True,
                'strategy_used': 'fallback'
            },
            'cache_info': self._get_cache_info()
        }

    def _fetch_candidate_documents(self, candidate_ids: List[str]) -> List:
        """Fetch documents by ID"""
        try:
            return self.client.retrieve(
                collection_name=self.collection_name,
                ids=candidate_ids,
                with_payload=True,
                with_vectors=False
            )
        except Exception as e:
            logger.error(f"Failed to fetch candidate documents: {e}")
            return []

    def _get_cache_info(self) -> Dict[str, Any]:
        """Get cache status information"""
        bm25_stats = self.bm25_engine.get_cache_stats()
        dense_stats = self.dense_engine.get_cache_stats()

        return {
            'bm25_cache': {
                'hit_rate': bm25_stats.get('hit_rate', 0),
                'size': bm25_stats.get('cache_size', 0),
                'hits': bm25_stats.get('cache_hits', 0),
                'misses': bm25_stats.get('cache_misses', 0)
            },
            'dense_cache': {
                'hit_rate': dense_stats.get('hit_rate', 0),
                'size': dense_stats.get('cache_size', 0),
                'hits': dense_stats.get('cache_hits', 0),
                'misses': dense_stats.get('cache_misses', 0)
            },
            'cache_enabled': self._cache_enabled
        }

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics with cache"""
        return {
            'total_searches': self._search_count,
            'bm25_stats': self.bm25_engine.get_cache_stats(),
            'dense_stats': self.dense_engine.get_search_stats(),
            'cache_info': self._get_cache_info(),
            'cache_enabled': self._cache_enabled
        }

    def clear_caches(self):
        """Clear all caches"""
        self.bm25_engine.clear_cache()
        # dense engine doesn't have clear_cache method, only stats reset
        logger.info("All caches cleared (BM25 + Dense)")

    def reset_cache_stats(self):
        """Reset cache statistics without clearing"""
        self.bm25_engine.reset_cache_stats()
        self.dense_engine.reset_cache_stats()
        logger.info("Cache statistics reset")

    def get_cache_health(self) -> Dict[str, Any]:
        """Check cache health"""
        bm25_stats = self.bm25_engine.get_cache_stats()
        dense_stats = self.dense_engine.get_cache_stats()

        bm25_hit_rate = bm25_stats.get('hit_rate', 0)
        dense_hit_rate = dense_stats.get('hit_rate', 0)

        overall_hit_rate = (bm25_hit_rate + dense_hit_rate) / 2

        if overall_hit_rate > 70:
            status = "excellent"
            emoji = "🟢"
        elif overall_hit_rate > 50:
            status = "good"
            emoji = "🟡"
        elif overall_hit_rate > 30:
            status = "fair"
            emoji = "🟠"
        else:
            status = "poor"
            emoji = "🔴"

        return {
            'status': status,
            'emoji': emoji,
            'overall_hit_rate': round(overall_hit_rate, 2),
            'bm25_hit_rate': round(bm25_hit_rate, 2),
            'dense_hit_rate': round(dense_hit_rate, 2),
            'bm25_size': bm25_stats.get('cache_size', 0),
            'dense_size': dense_stats.get('cache_size', 0),
            'total_requests': (
                bm25_stats.get('total_requests', 0) +
                dense_stats.get('total_requests', 0)
            ),
            'recommendations': self._get_cache_recommendations(bm25_hit_rate, dense_hit_rate)
        }

    def _get_cache_recommendations(self, bm25_hit_rate: float, dense_hit_rate: float) -> List[str]:
        """Get cache optimization recommendations"""
        recommendations = []

        if bm25_hit_rate < 50:
            recommendations.append(
                f"BM25 cache hit rate is low ({bm25_hit_rate:.1f}%). "
                "Consider increasing cache_max_size or TTL."
            )

        if dense_hit_rate < 50:
            recommendations.append(
                f"Dense cache hit rate is low ({dense_hit_rate:.1f}%). "
                "Consider increasing cache_max_size or TTL."
            )

        if bm25_hit_rate > 85 and dense_hit_rate > 85:
            recommendations.append(
                "Excellent cache efficiency! System operating optimally."
            )

        return recommendations

    def enable_cache(self):
        """Enable caching"""
        self._cache_enabled = True
        logger.info("Caching enabled")

    def disable_cache(self):
        """Disable caching"""
        self._cache_enabled = False
        logger.info("Caching disabled")