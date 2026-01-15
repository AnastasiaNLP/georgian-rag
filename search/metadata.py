"""
Metadata filters for search with filter hierarchy.
"""

import time
import logging
from typing import Dict, Any, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from core.types import QueryAnalysis, SearchResult

logger = logging.getLogger(__name__)


class MetadataFilters:
    """
    Metadata filtering with filter hierarchy.

    Filter types:
    - Hard filters: Mandatory (language, quality)
    - User filters: User-defined (type, location)
    - Boost filters: Soft score improvements
    """

    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        self.client = qdrant_client
        self.collection_name = collection_name

        # filter hierarchy
        self.filter_hierarchy = {
            'hard_filters': {
                'quality_threshold': 0.3,
                'has_description': True
            },
            'user_filters': {
                'attraction_type': None,
                'location': None,
                'has_images': None,
                'language': None
            },
            'boost_filters': {
                'georgian_entities': 1.2,
                'high_quality': 1.1,
                'complete_data': 1.1,
                'tbilisi_related': 1.15
            }
        }

    def _extract_dynamic_filters(self, query_analysis: QueryAnalysis) -> Dict[str, Any]:
        """Extract dynamic filters from query analysis"""
        filters = {}

        # base filters from analysis
        filters.update(query_analysis.implicit_filters)

        # language filters
        if query_analysis.language in ['ru', 'en']:
            filters['language_preference'] = query_analysis.language.upper()

        # geographic filters
        locations = query_analysis.entities.get('locations', [])
        if locations:
            filters['mentioned_locations'] = locations

        # category filters
        categories = query_analysis.entities.get('categories', [])
        if categories:
            filters['mentioned_categories'] = categories

        return filters

    def _build_qdrant_filter(self, filters: Dict[str, Any]) -> Optional[Filter]:
        """Build Qdrant filter from conditions dictionary"""
        conditions = []

        if filters.get('has_description'):
            conditions.append(
                FieldCondition(
                    key="has_description",
                    match=MatchValue(value=True)
                )
            )

        # user filters
        if filters.get('language_preference'):
            conditions.append(
                FieldCondition(
                    key="language",
                    match=MatchValue(value=filters['language_preference'])
                )
            )

        if filters.get('has_images') is not None:
            conditions.append(
                FieldCondition(
                    key="has_images",
                    match=MatchValue(value=filters['has_images'])
                )
            )

        # religious filters
        if filters.get('has_religion_tags'):
            conditions.append(
                FieldCondition(
                    key="is_religious_site",
                    match=MatchValue(value=True)
                )
            )

        # nature filters
        if filters.get('has_nature_tags'):
            conditions.append(
                FieldCondition(
                    key="is_nature_tourism",
                    match=MatchValue(value=True)
                )
            )

        # historical filters
        if filters.get('is_historical_site'):
            conditions.append(
                FieldCondition(
                    key="is_historical_site",
                    match=MatchValue(value=True)
                )
            )

        return Filter(must=conditions) if conditions else None

    def search(self, query_analysis: QueryAnalysis, top_k: int = 20) -> List[SearchResult]:
        """
        Search with metadata filtering.

        Args:
            query_analysis: Query analysis result
            top_k: Number of results

        Returns:
            List[SearchResult]: Filtered results
        """
        start_time = time.time()

        # extract dynamic filters
        dynamic_filters = self._extract_dynamic_filters(query_analysis)

        # combine with base filters
        all_filters = {**self.filter_hierarchy['hard_filters'], **dynamic_filters}

        # build Qdrant filter
        qdrant_filter = self._build_qdrant_filter(all_filters)

        try:
            # search by metadata (without vector search)
            search_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
                with_vectors=False
            )

            # transform results and apply boost filters
            results = []
            boost_filters = self.filter_hierarchy['boost_filters']

            for point in search_result[0]:  # scroll returns tuple (points, next_page_offset)
                base_score = 1.0  # base score for metadata

                # apply boost filters
                metadata = point.payload

                if metadata.get('has_georgian_entities', False):
                    base_score *= boost_filters['georgian_entities']

                if metadata.get('is_fully_enriched', False):
                    base_score *= boost_filters['complete_data']
                result = SearchResult(
                    doc_id=str(point.id),
                    score=float(base_score),
                    source='metadata',
                    metadata=metadata,
                    content=metadata.get('description', '')
                )
                results.append(result)

            # sort by score
            results.sort(key=lambda x: x.score, reverse=True)

            logger.info(f"Metadata search completed in {time.time() - start_time:.3f}s: {len(results)} results")
            return results[:top_k]

        except Exception as e:
            logger.error(f"Metadata search failed: {e}")
            return []