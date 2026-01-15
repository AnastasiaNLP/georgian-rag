"""
Reciprocal Rank Fusion engine for combining search results.
"""

import time
import math
import logging
from typing import Dict, List, Any

from core.types import SearchResult, QueryAnalysis, QueryType

logger = logging.getLogger(__name__)


class RRFFusionEngine:
    """
    Reciprocal Rank Fusion for combining results with Clean Fusion.

    Features:
    - Score normalization from different sources
    - Adaptive weights based on query analysis
    - Contextual boosts
    - Duplicate elimination
    - Clean Fusion for prefiltered results
    - Improved normalization for consistent results
    - Special weights for focused search
    """

    def __init__(self, k: int = 3):
        self.k = k
        self.score_ranges = {
            'bm25': (0, 20),
            'dense': (0.3, 0.9),
            'metadata': (0.5, 2.0),
            'bm25_focused': (0, 15),
            'dense_focused': (0.4, 0.95)
        }

        self._fusion_stats = {
            'clean_fusions': 0,
            'legacy_fusions': 0,
            'avg_clean_time': 0.0,
            'avg_legacy_time': 0.0
        }

    def fuse_results(self, results_dict: Dict[str, List[SearchResult]],
                query_analysis: QueryAnalysis, top_k: int = 20) -> List[SearchResult]:
        """Fuse results from multiple sources"""
        start_time = time.time()

        use_clean_fusion = self._should_use_clean_fusion(results_dict)

        try:
            if use_clean_fusion:
                logger.info("Using Clean Fusion for prefiltered results")
                final_results = self._clean_fusion_pipeline(results_dict, query_analysis, top_k)
                self._fusion_stats['clean_fusions'] += 1
                self._fusion_stats['avg_clean_time'] = (
                    (self._fusion_stats['avg_clean_time'] * (self._fusion_stats['clean_fusions'] - 1) +
                     (time.time() - start_time)) / self._fusion_stats['clean_fusions']
                )
            else:
                logger.info("Using Legacy Fusion for mixed results")
                final_results = self._legacy_fusion_pipeline(results_dict, query_analysis, top_k)
                self._fusion_stats['legacy_fusions'] += 1
                self._fusion_stats['avg_legacy_time'] = (
                    (self._fusion_stats['avg_legacy_time'] * (self._fusion_stats['legacy_fusions'] - 1) +
                     (time.time() - start_time)) / self._fusion_stats['legacy_fusions']
                )

            if final_results is None:
                logger.error("Fusion pipeline returned None, returning empty list")
                final_results = []

            if not isinstance(final_results, list):
                logger.error(f"Fusion pipeline returned {type(final_results)}, converting to list")
                final_results = list(final_results) if final_results else []

            total_time = time.time() - start_time
            fusion_type = "clean" if use_clean_fusion else "legacy"
            logger.info(f"RRF {fusion_type} fusion completed in {total_time:.3f}s: {len(final_results)} results")

            return final_results

        except Exception as e:
            logger.error(f"Critical error in fusion pipeline: {e}", exc_info=True)
            return []

    def _should_use_clean_fusion(self, results_dict: Dict[str, List[SearchResult]]) -> bool:
        """Determine if Clean Fusion should be used"""
        focused_sources = []
        for source in results_dict.keys():
             if source in ['bm25_focused', 'dense_focused'] and results_dict[source]:
                 focused_sources.append(source)

        has_prefilter_info = 'prefilter_info' in results_dict

        has_main_results = any(source in results_dict and results_dict[source]
                              for source in ['bm25', 'bm25_focused', 'dense', 'dense_focused'])

        use_clean = (len(focused_sources) > 0 or has_prefilter_info) and has_main_results

        logger.info(f"Clean Fusion decision: {use_clean} (focused_sources: {len(focused_sources)}, prefilter: {has_prefilter_info}, main_results: {has_main_results})")

        return use_clean

    def _clean_fusion_pipeline(self, results_dict: Dict[str, List[SearchResult]],
                              query_analysis: QueryAnalysis, top_k: int) -> List[SearchResult]:
        """Clean Fusion pipeline for prefiltered results"""
        logger.info("Starting Clean Fusion pipeline for prefiltered results")

        weights = self._calculate_focused_weights(results_dict)
        normalized_results = self._normalize_focused_scores(results_dict)
        doc_scores = self._calculate_focused_rrf_scores(normalized_results, weights)
        doc_scores = self._apply_focused_contextual_boosts(doc_scores, query_analysis)

        return self._assemble_final_results(doc_scores, top_k, fusion_type='clean')

    def _calculate_focused_weights(self, results_dict: Dict[str, List[SearchResult]]) -> Dict[str, float]:
        """Calculate weights for focused search components"""
        base_weights = {
            'bm25': 0.4,
            'bm25_focused': 0.45,
            'dense': 0.5,
            'dense_focused': 0.55,
            'metadata': 0.1
        }

        available_sources = set(results_dict.keys()) - {'prefilter_info'}
        final_weights = {}

        for source in available_sources:
            if source in base_weights:
                final_weights[source] = base_weights[source]
            else:
                final_weights[source] = 0.3

        total_weight = sum(final_weights.values())
        if total_weight > 0:
            final_weights = {k: v/total_weight for k, v in final_weights.items()}

        logger.info(f"Focused weights: {final_weights}")
        return final_weights

    def _normalize_focused_scores(self, results_dict: Dict[str, List[SearchResult]]) -> Dict[str, List[SearchResult]]:
        """Improved normalization without strong score reduction"""
        normalized_dict = {}

        for source, results in results_dict.items():
            if source == 'prefilter_info' or not results:
                normalized_dict[source] = results
                continue

            if not results:
                normalized_dict[source] = []
                continue

            original_scores = [r.score for r in results]
            logger.info(f"[DIAG] {source} original scores: {[f'{s:.4f}' for s in original_scores]}")

            normalized_results = []

            if 'bm25' in source:
                max_bm25_score = max(r.score for r in results) if results else 1.0

                for result in results:
                    new_result = SearchResult(
                        doc_id=result.doc_id,
                        score=0.2 + 0.8 * (result.score / max_bm25_score) if result.score > 0 else 0.0,
                        source=result.source,
                        metadata=result.metadata.copy(),
                        content=result.content
                    )
                    normalized_results.append(new_result)

            elif 'dense' in source:
                scores = [r.score for r in results if r.score > 0]
                if scores:
                    max_score = max(scores)
                    min_score = min(scores)

                    if max_score > min_score:
                        for result in results:
                            if result.score > 0:
                                normalized_score = 0.3 + 0.7 * ((result.score - min_score) / (max_score - min_score))
                            else:
                                normalized_score = 0.0

                            new_result = SearchResult(
                                doc_id=result.doc_id,
                                score=normalized_score,
                                source=result.source,
                                metadata=result.metadata.copy(),
                                content=result.content
                            )
                            normalized_results.append(new_result)
                    else:
                        for result in results:
                            new_result = SearchResult(
                                doc_id=result.doc_id,
                                score=0.8 if result.score > 0 else 0.0,
                                source=result.source,
                                metadata=result.metadata.copy(),
                                content=result.content
                            )
                            normalized_results.append(new_result)
                else:
                    normalized_results = results.copy()
            else:
                scores = [r.score for r in results if r.score > 0]
                if scores:
                    max_score = max(scores)
                    for result in results:
                        normalized_score = 0.1 + 0.9 * (result.score / max_score) if result.score > 0 and max_score > 0 else 0.0
                        new_result = SearchResult(
                            doc_id=result.doc_id,
                            score=normalized_score,
                            source=result.source,
                            metadata=result.metadata.copy(),
                            content=result.content
                        )
                        normalized_results.append(new_result)
                else:
                    normalized_results = results.copy()

            normalized_scores = [r.score for r in normalized_results]
            logger.info(f"[DIAG] {source} normalized scores: {[f'{s:.4f}' for s in normalized_scores]}")

            normalized_dict[source] = normalized_results

        return normalized_dict

    def _calculate_focused_rrf_scores(self, normalized_results: Dict[str, List[SearchResult]],
                                    weights: Dict[str, float]) -> Dict[str, Dict]:
        """RRF with higher final scores"""
        doc_scores = {}

        for source, results in normalized_results.items():
            if source == 'prefilter_info' or not results:
                continue

            weight = weights.get(source, 0.5)

            for rank, result in enumerate(results, 1):
                doc_id = result.doc_id

                base_rrf = 1.0 / (self.k + rank)
                final_score = weight * base_rrf * result.score * 10.0

                if rank == 1:
                    final_score *= 3.0
                elif rank == 2:
                    final_score *= 2.0
                elif rank == 3:
                    final_score *= 1.5

                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        'total_score': 0.0,
                        'source_scores': {},
                        'rank_info': {},
                        'result': result
                    }

                doc_scores[doc_id]['total_score'] += final_score
                doc_scores[doc_id]['source_scores'][source] = final_score
                doc_scores[doc_id]['rank_info'][source] = rank

                if rank <= 3:
                    logger.info(f"[DIAG] {source} rank={rank}, weight={weight:.3f}, "
                              f"norm_score={result.score:.4f}, base_rrf={base_rrf:.6f}, final={final_score:.6f}")

        return doc_scores

    def _apply_focused_contextual_boosts(self, doc_scores: Dict[str, Dict],
                                       query_analysis: QueryAnalysis) -> Dict[str, Dict]:
        """More significant boosts for better discrimination"""
        for doc_id, score_data in doc_scores.items():
            result = score_data['result']
            metadata = result.metadata
            boost_factor = 1.0

            if metadata.get('language') == query_analysis.language.upper():
                boost_factor *= 1.2

            source_count = len(score_data['source_scores'])
            if source_count >= 2:
                boost_factor *= (1.0 + 0.3 * (source_count - 1))

            top_ranks = sum(1 for rank in score_data['rank_info'].values() if rank <= 3)
            if top_ranks >= 2:
                boost_factor *= 1.5

            if metadata.get('is_fully_enriched', False):
                boost_factor *= 1.1

            first_place_count = sum(1 for rank in score_data['rank_info'].values() if rank == 1)
            if first_place_count >= 1:
                boost_factor *= 1.8

            old_score = score_data['total_score']
            score_data['total_score'] *= boost_factor
            score_data['boost_factor'] = boost_factor

            if boost_factor > 1.5:
                logger.info(f"[DIAG] Significant boost for {doc_id}: {old_score:.6f} -> {score_data['total_score']:.6f} (x{boost_factor:.2f})")

        return doc_scores

    def _legacy_fusion_pipeline(self, results_dict: Dict[str, List[SearchResult]],
                               query_analysis: QueryAnalysis, top_k: int) -> List[SearchResult]:
        """Legacy fusion pipeline for mixed results"""
        weights = getattr(query_analysis, 'suggested_weights', self._get_default_weights(results_dict))
        normalized_results = self._normalize_scores(results_dict)
        doc_scores = self._calculate_rrf_scores(normalized_results, weights)
        doc_scores = self._apply_contextual_boosts(doc_scores, query_analysis)

        return self._assemble_final_results(doc_scores, top_k, fusion_type='legacy')

    def _get_default_weights(self, results_dict: Dict[str, List[SearchResult]]) -> Dict[str, float]:
        """Get default weights for sources"""
        default_weights = {
            'bm25': 0.4,
            'bm25_focused': 0.4,
            'dense': 0.5,
            'dense_focused': 0.5,
            'metadata': 0.1
        }

        available_sources = set(results_dict.keys()) - {'prefilter_info'}
        weights = {source: default_weights.get(source, 0.3) for source in available_sources}

        total = sum(weights.values())
        if total > 0:
            weights = {k: v/total for k, v in weights.items()}

        return weights

    def _normalize_scores(self, results_dict: Dict[str, List[SearchResult]]) -> Dict[str, List[SearchResult]]:
        """Normalize scores preserving discriminability"""
        normalized_results = {}

        for source, results in results_dict.items():
            if source == 'prefilter_info':
                continue

            if not results:
                normalized_results[source] = []
                continue

            if 'bm25' in source:
                for result in results:
                    if result.score > 0:
                        result.score = math.log(1 + result.score) / math.log(1 + 60)
                    else:
                        result.score = 0.0

            elif 'dense' in source:
                scores = [r.score for r in results]
                if scores:
                    max_score = max(scores)
                    min_score = min(scores)

                    if max_score > min_score:
                        for result in results:
                            result.score = (result.score - min_score) / (max_score - min_score)
                            result.score = result.score * 0.9 + 0.1

            normalized_results[source] = results

        for source, results in normalized_results.items():
            if results:
                scores = [r.score for r in results[:3]]
                logger.info(f"Legacy {source} normalized scores: {[f'{s:.4f}' for s in scores]}")

        return normalized_results

    def _calculate_rrf_scores(self, results_dict: Dict[str, Dict],
                            weights: Dict[str, float]) -> Dict[str, Dict]:
        """Calculate RRF scores with weights"""
        doc_scores = {}

        for source, results in results_dict.items():
            weight = weights.get(source, 0.0)

            for rank, result in enumerate(results, 1):
                doc_id = result.doc_id

                rrf_score = weight / (self.k + rank)
                if rank <= 3:
                    logger.info(f"Legacy RRF: {source} rank={rank}, weight={weight:.3f}, "
                              f"score={result.score:.4f} -> rrf={rrf_score:.6f}")

                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {
                        'total_score': 0.0,
                        'source_scores': {},
                        'result': result
                    }

                doc_scores[doc_id]['total_score'] += rrf_score
                doc_scores[doc_id]['source_scores'][source] = rrf_score

        return doc_scores

    def _apply_contextual_boosts(self, doc_scores: Dict[str, Dict],
                               query_analysis: QueryAnalysis) -> Dict[str, Dict]:
        """Apply contextual boosts based on query analysis"""
        for doc_id, score_data in doc_scores.items():
            result = score_data['result']
            metadata = result.metadata
            boost_factor = 1.0

            if metadata.get('language') == query_analysis.language.upper():
                boost_factor *= 1.1

            if (query_analysis.intent_type == QueryType.EXPLORATORY and
                metadata.get('has_georgian_entities', False)):
                boost_factor *= 1.15

            if metadata.get('is_fully_enriched', False):
                boost_factor *= 1.03

            mentioned_categories = query_analysis.entities.get('categories', [])
            if mentioned_categories:
                doc_categories = metadata.get('category', '').lower()
                if any(cat in doc_categories for cat in mentioned_categories):
                    boost_factor *= 1.2

            score_data['total_score'] *= boost_factor
            score_data['boost_factor'] = boost_factor

        return doc_scores

    def _assemble_final_results(self, doc_scores: Dict[str, Dict], top_k: int,
                              fusion_type: str) -> List[SearchResult]:
        """Assemble final results from scores"""
        sorted_docs = sorted(doc_scores.items(),
                           key=lambda x: x[1]['total_score'],
                           reverse=True)

        top_scores = [f"{item[1]['total_score']:.6f}" for item in sorted_docs[:3]]
        logger.info(f"[DIAG] Top 3 final scores: {top_scores}")

        final_results = []
        for doc_id, score_data in sorted_docs[:top_k]:
            original_result = score_data['result']
            final_score = score_data['total_score']

            if not isinstance(original_result, SearchResult):
                 logger.error(f"Unexpected object type in doc_scores['result']: {type(original_result)}. Skipping.")
                 continue

            final_result = SearchResult(
                doc_id=original_result.doc_id,
                score=final_score,
                source=original_result.source,
                metadata=original_result.metadata.copy(),
                content=original_result.content
            )

            fusion_info = {
                'source_scores': score_data['source_scores'],
                'boost_factor': score_data.get('boost_factor', 1.0),
                'sources_used': list(score_data['source_scores'].keys()),
                'fusion_type': fusion_type
            }

            if 'rank_info' in score_data:
                fusion_info['rank_info'] = score_data['rank_info']

            final_result.metadata['fusion_info'] = fusion_info
            final_results.append(final_result)

        if not final_results:
            logger.warning("_assemble_final_results returning empty list")
            return []

        return final_results

    def get_fusion_stats(self) -> Dict[str, Any]:
        """Get fusion operation statistics"""
        total_fusions = self._fusion_stats['clean_fusions'] + self._fusion_stats['legacy_fusions']

        return {
        'clean_fusions': self._fusion_stats['clean_fusions'],
        'legacy_fusions': self._fusion_stats['legacy_fusions'],
        'total_fusions': total_fusions,
        'clean_fusion_ratio': (
            self._fusion_stats['clean_fusions'] / total_fusions
            if total_fusions > 0 else 0
        ),
        'avg_clean_time': self._fusion_stats['avg_clean_time'],
        'avg_legacy_time': self._fusion_stats['avg_legacy_time']
         }

    def reset_fusion_stats(self):
        """Reset fusion operation statistics"""
        self._fusion_stats = {
            'clean_fusions': 0,
            'legacy_fusions': 0,
            'avg_clean_time': 0.0,
            'avg_legacy_time': 0.0
        }
        logger.info("Fusion statistics reset")