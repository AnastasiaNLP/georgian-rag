"""
Pre-filtering engine for candidate retrieval.
"""

import time
import logging
import random
from typing import Dict, List, Any, Optional
from copy import deepcopy

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

from config.settings import config
from core.types import QueryAnalysis
from utils.model_manager import model_manager

logger = logging.getLogger(__name__)


class PreFilterEngine:
    """
    Pre-Filtering Engine for quality candidate retrieval.

    Features:
    - Case-insensitive search for attraction names
    - Adaptive filtering strategies (strict/moderate/loose)
    - Multilingual logic (OR for text, AND for boolean)
    - Uses stable .search() API

    Architecture Step 1:
    Query - PreFilter - Candidates (200-300 documents)
    """

    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        self.client = qdrant_client
        self.collection_name = collection_name

        self._candidates_cache = {}
        self._cache_hits = 0
        self._total_requests = 0

        self.model_name = config.embedding.model_name
        self._embedding_model = None

        logger.info("PreFilterEngine initialized with case-insensitive search")

    @property
    def embedding_model(self):
        """Lazy loading embedding model"""
        if self._embedding_model is None:
            self._embedding_model = model_manager.get_model(self.model_name)
        return self._embedding_model

    def _normalize_text(self, text: str) -> str:
        """Normalize text for case-insensitive search"""
        if not text:
            return ""
        return text.strip().lower()

    def _create_case_insensitive_variants(self, text: str) -> List[str]:
        """
        Create text variants with different cases.

        For "Svetitskhoveli" creates:
        - svetitskhoveli (lowercase)
        - Svetitskhoveli (original)
        - SVETITSKHOVELI (uppercase)
        """
        if not text:
            return []

        variants = [
            text.lower(),
            text.title(),
            text.upper(),
        ]

        return list(set(variants))

    def get_filtered_candidates(self, query_analysis: QueryAnalysis,
                               max_candidates: int = 200) -> Dict[str, Any]:
        """Returns list of candidate document IDs with diagnostic information"""
        start_time = time.time()
        self._total_requests += 1
        cache_key = self._create_cache_key(query_analysis, max_candidates)

        if cache_key in self._candidates_cache:
            self._cache_hits += 1
            logger.info(f"Cache hit for prefilter (hit rate: {self._cache_hits/self._total_requests:.2%})")
            return self._candidates_cache[cache_key]

        logger.info(f"Starting PreFilter with strategy: {query_analysis.filter_strategy}")

        try:
            qdrant_filter = self._create_adaptive_filter(query_analysis)

            candidates_result = self._execute_candidate_search(
                query_analysis, qdrant_filter, max_candidates
            )

            result = {
                'candidates': candidates_result['candidates'],
                'count': len(candidates_result['candidates']),
                'strategy_used': query_analysis.filter_strategy,
                'filters_applied': len(query_analysis.qdrant_filters),
                'search_time': time.time() - start_time,
                'filter_details': self._get_filter_summary(query_analysis),
                'fallback_used': candidates_result.get('fallback_used', False),
                'original_count': candidates_result.get('original_count', 0),
                'case_insensitive': True
            }

            if len(result['candidates']) == 0 and query_analysis.filter_strategy != 'loose':
                logger.warning("No candidates found, applying fallback strategy")
                result = self._apply_fallback_strategy(query_analysis, max_candidates, result)
            elif len(result['candidates']) >= 1:
                logger.info(f"Found {len(result['candidates'])} candidates")

            self._candidates_cache[cache_key] = result

            logger.info(f"PreFilter completed: {result['count']} candidates in {result['search_time']:.3f}s")
            return result

        except Exception as e:
            logger.error(f"PreFilter error: {e}", exc_info=True)
            return {
                'candidates': [],
                'count': 0,
                'strategy_used': 'error',
                'filters_applied': 0,
                'search_time': time.time() - start_time,
                'error': str(e),
                'fallback_used': False,
                'case_insensitive': True
            }

    def _create_adaptive_filter(self, query_analysis: QueryAnalysis) -> Optional[Filter]:
        """
        Create adaptive filter with case-insensitive search.

        Logic:
        - Text filters (names) -> OR (MatchAny with case variants)
        - Boolean filters (metadata) -> AND
        """

        if not query_analysis.qdrant_filters:
            return None

        text_filters = []
        boolean_filters = []

        for filter_obj in query_analysis.qdrant_filters:
            if hasattr(filter_obj, 'match') and hasattr(filter_obj.match, 'text'):
                original_text = filter_obj.match.text

                text_variants = self._create_case_insensitive_variants(original_text)

                case_insensitive_filter = FieldCondition(
                    key=filter_obj.key,
                    match=MatchAny(any=text_variants)
                )

                text_filters.append(case_insensitive_filter)
                logger.debug(f"Case-insensitive filter for '{original_text}': {text_variants}")

            else:
                boolean_filters.append(filter_obj)

        strategy = query_analysis.filter_strategy
        selected_text_filters = []
        selected_boolean_filters = []

        if strategy == 'strict':
            selected_text_filters = text_filters
            selected_boolean_filters = boolean_filters
        elif strategy == 'moderate':
            selected_text_filters = text_filters
            priority_keys = {'is_religious_site', 'is_nature_tourism', 'is_historical_site', 'language'}
            selected_boolean_filters = [f for f in boolean_filters
                                       if hasattr(f, 'key') and f.key in priority_keys]
        else:  # loose
            selected_text_filters = text_filters
            priority_keys = {'is_religious_site', 'language'}
            selected_boolean_filters = [f for f in boolean_filters
                                       if hasattr(f, 'key') and f.key in priority_keys]

        if selected_text_filters and selected_boolean_filters:
            combined_filter = Filter(
                should=selected_text_filters,
                must=selected_boolean_filters
            )
            logger.info(f"Combined filter: {len(selected_text_filters)} text (OR) + {len(selected_boolean_filters)} boolean (AND)")
        elif selected_text_filters:
            combined_filter = Filter(should=selected_text_filters)
            logger.info(f"Text-only filter: {len(selected_text_filters)} filters with OR logic")
        elif selected_boolean_filters:
            combined_filter = Filter(must=selected_boolean_filters)
            logger.info(f"Boolean-only filter: {len(selected_boolean_filters)} filters with AND logic")
        else:
            logger.info("No filters selected for the current strategy")
            return None

        logger.info(f"Selected filters for '{strategy}' strategy: {len(selected_text_filters + selected_boolean_filters)} total")
        return combined_filter

    def _execute_candidate_search(self, query_analysis: QueryAnalysis,
                                 qdrant_filter: Optional[Filter],
                                 max_candidates: int) -> Dict[str, Any]:
        """Execute candidate search using stable .search() API"""
        try:
            search_vector = self._get_search_vector(query_analysis.semantic_query)

            search_result =self.client.search(
                collection_name=self.collection_name,
                query_vector=search_vector,
                query_filter=qdrant_filter,
                limit=max_candidates,
                with_payload=False
            )

            candidates = [point.id for point in search_result]

            logger.debug(f"Search returned {len(candidates)} candidates (types: {type(candidates[0]) if candidates else 'empty'})")

            return {
                'candidates': candidates,
                'original_count': len(search_result),
                'fallback_used': False
            }

        except Exception as e:
            logger.error(f"Candidate search failed: {e}")
            raise

    def _get_search_vector(self, query: str) -> List[float]:
        """Create embedding vector for query"""
        try:
            embedding = self.embedding_model.encode(query)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Vector creation failed: {e}")
            return [random.random() for _ in range(384)]

    def _apply_fallback_strategy(self, query_analysis: QueryAnalysis,
                                max_candidates: int, original_result: Dict) -> Dict[str, Any]:
        """Apply fallback strategy with insufficient candidates"""
        logger.info("Applying fallback strategy: switching to 'loose'")

        try:
            fallback_analysis = deepcopy(query_analysis)
            fallback_analysis.filter_strategy = 'loose'

            fallback_filter = self._create_adaptive_filter(fallback_analysis)
            fallback_result_data = self._execute_candidate_search(
                fallback_analysis, fallback_filter, max_candidates
            )

            if len(fallback_result_data['candidates']) < 2:
                logger.info("Fallback 'loose' yielded few results. Searching without filters")
                fallback_result_data = self._execute_candidate_search(
                    fallback_analysis, None, max_candidates
                )
                final_strategy = 'no_filters_fallback'
                filters_applied_count = 0
            else:
                final_strategy = 'loose_fallback'
                if fallback_filter:
                    filters_applied_count = len(fallback_filter.must or []) + len(fallback_filter.should or [])
                else:
                    filters_applied_count = 0

            return {
                'candidates': fallback_result_data['candidates'],
                'count': len(fallback_result_data['candidates']),
                'strategy_used': final_strategy,
                'filters_applied': filters_applied_count,
                'search_time': original_result['search_time'],
                'filter_details': self._get_filter_summary(fallback_analysis),
                'fallback_used': True,
                'original_count': original_result['count'],
                'case_insensitive': True
            }

        except Exception as e:
            logger.error(f"Fallback strategy failed: {e}", exc_info=True)
            return original_result

    def _create_cache_key(self, query_analysis: QueryAnalysis, max_candidates: int) -> str:
        """Create cache key for query"""
        key_components = (
            query_analysis.original_query,
            query_analysis.filter_strategy,
            max_candidates,
            tuple(sorted(str(f) for f in query_analysis.qdrant_filters))
        )
        return str(hash(key_components))

    def _get_filter_summary(self, query_analysis: QueryAnalysis) -> Dict[str, Any]:
        """Create summary of applied filters"""
        summary = {}
        for f in query_analysis.qdrant_filters:
            if hasattr(f, 'match'):
                if hasattr(f.match, 'any'):
                    summary[f.key] = f"any({f.match.any})"
                elif hasattr(f.match, 'value'):
                    summary[f.key] = f.match.value
                elif hasattr(f.match, 'text'):
                    summary[f.key] = f.match.text
            elif hasattr(f, 'range'):
                summary[f.key] = f"range(gte={f.range.gte}, lte={f.range.lte})"
        return summary

    def clear_cache(self):
        """Clear PreFilter cache"""
        self._candidates_cache.clear()
        self._cache_hits = 0
        self._total_requests = 0
        logger.info("PreFilter cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get PreFilter cache statistics"""
        hit_rate = self._cache_hits / self._total_requests if self._total_requests > 0 else 0

        return {
            'cache_size': len(self._candidates_cache),
            'cache_hits': self._cache_hits,
            'total_requests': self._total_requests,
            'hit_rate': hit_rate,
            'hit_rate_percent': round(hit_rate * 100, 2),
            'cache_enabled': True
        }

    def reset_cache_stats(self):
        """Reset cache statistics"""
        self._cache_hits = 0
        self._total_requests = 0
        logger.info("PreFilter cache statistics reset")