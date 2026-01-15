"""
Web enrichment engine with Wikipedia, Unsplash, and SerpAPI.
"""

import asyncio
import logging
import hashlib
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import aiohttp
import requests

logger = logging.getLogger(__name__)


@dataclass
class WebEnrichmentResult:
    """Result of web enrichment"""
    wikipedia_content: str = ""
    wikipedia_images: List[str] = None
    unsplash_images: List[Dict] = None
    serpapi_results: List[Dict] = None
    enrichment_sources: List[str] = None
    cache_key: str = None

    def __post_init__(self):
        if self.wikipedia_images is None:
            self.wikipedia_images = []
        if self.unsplash_images is None:
            self.unsplash_images = []
        if self.serpapi_results is None:
            self.serpapi_results = []
        if self.enrichment_sources is None:
            self.enrichment_sources = []


class WebEnrichmentEngine:
    """
    Web enrichment with permanent caching and background Qdrant updates.

    Features:
    - Wikipedia API integration
    - Unsplash image search
    - SerpAPI for practical info
    - Permanent caching (NO TTL - never expires)
    - Background Qdrant updates (non-blocking)
    """

    def __init__(
        self,
        api_keys: Dict[str, str],
        cache_manager=None,
        enrichment_persister=None,
        redis_client=None
    ):
        """
        Initialize WebEnrichmentEngine.

        Args:
            api_keys: API keys for external services
            cache_manager: CacheManager instance (preferred)
            enrichment_persister: EnrichmentPersister for Qdrant updates
            redis_client: Redis client (backward compatibility)
        """
        self.wikipedia_api_key = api_keys.get('wikipedia_api_key')
        self.unsplash_key = api_keys.get('unsplash_access_key')
        self.serpapi_key = api_keys.get('serpapi_api_key')

        self.cache_manager = cache_manager
        self.enrichment_persister = enrichment_persister
        self.redis = redis_client

        if self.cache_manager:
            logger.info("WebEnrichmentEngine using CacheManager")
            if self.enrichment_persister:
                logger.info("WebEnrichmentEngine with background Qdrant updates")
        elif self.redis:
            logger.info("WebEnrichmentEngine using legacy redis_client")

        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def enrich_content(
        self,
        search_results: List,
        query_analysis
    ) -> WebEnrichmentResult:
        """
        Main enrichment method with TWO-level storage strategy.

        LEVEL 1: Check permanent cache (Redis NO TTL)
        LEVEL 2: Check Qdrant metadata

        If not found:
        - Fetch from Web APIs
        - Save to permanent cache (IMMEDIATE, NO TTL)
        - Queue Qdrant update (BACKGROUND, non-blocking)
        - Return data to user
        """

        # normalize input data
        if isinstance(search_results, dict):
            if 'results' in search_results:
                search_results_list = search_results['results']
            else:
                search_results_list = []
        elif isinstance(search_results, list):
            search_results_list = search_results
        else:
            search_results_list = []

        # check if enrichment is needed
        needs_description = any(self._needs_more_description(result) for result in search_results_list[:3])
        needs_images = any(self._needs_more_images(result) for result in search_results_list[:3])

        if not (needs_description or needs_images):
            return WebEnrichmentResult()

        # create cache key
        place_names = [self._extract_place_name(result) for result in search_results_list[:3]]
        cache_key = hashlib.md5('|'.join(place_names).encode()).hexdigest()
        primary_place = place_names[0] if place_names else query_analysis.original_query

        # permanent cache
        if self.cache_manager:
            cached = self.cache_manager.get('enrichment:permanent', cache_key)
            if cached:
                logger.info(f"PERMANENT CACHE HIT: {primary_place}")
                return WebEnrichmentResult(**cached) if isinstance(cached, dict) else cached

        # qdrant metadata
        document_id = search_results_list[0].get('id') if search_results_list and isinstance(search_results_list[0], dict) else None
        if not document_id and search_results_list and hasattr(search_results_list[0], 'id'):
            document_id = search_results_list[0].id

        if document_id and self.enrichment_persister:
            if self.enrichment_persister.is_enriched(document_id):
                enriched_data = self._get_from_qdrant(document_id)
                if enriched_data:
                    logger.info(f"QDRANT METADATA HIT: {primary_place}")

                    # promote to permanent cache for faster access
                    if self.cache_manager:
                        self.cache_manager.set_permanent('enrichment:permanent', cache_key, enriched_data)

                    return WebEnrichmentResult(**enriched_data) if isinstance(enriched_data, dict) else enriched_data

        # fallback for redis client
        if self.redis and not self.cache_manager:
            try:
                redis_key = f"enrichment:{cache_key}"
                cached = self.redis.get(redis_key)
                if cached:
                    cached_data = json.loads(cached.decode('utf-8'))
                    logger.info(f"Legacy Redis HIT: {primary_place}")
                    return WebEnrichmentResult(**cached_data)
            except Exception as e:
                logger.warning(f"Legacy Redis error: {e}")

        # fetch from web
        logger.info(f"Fetching enrichment from web for: {primary_place}")

        tasks = []

        if needs_description:
            tasks.append(self._search_wikipedia(primary_place))
            tasks.append(self._search_serpapi(primary_place, query_analysis.detected_language))

        if needs_images:
            tasks.append(self._search_unsplash_images(primary_place))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            enrichment = WebEnrichmentResult()
            sources = []

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Enrichment task {i} failed: {result}")
                    continue

                if i == 0 and needs_description:  # wikipedia
                    enrichment.wikipedia_content = result.get('content')
                    enrichment.wikipedia_images = result.get('images', [])
                    if result.get('content'):
                        sources.append('wikipedia')

                elif i == 1 and needs_description:  # serpAPI
                    enrichment.serpapi_results = result
                    if result:
                        sources.append('serpapi')

                elif needs_images:  # unsplash
                    enrichment.unsplash_images = result
                    if result:
                        sources.append('unsplash')

            enrichment.enrichment_sources = sources
            enrichment.cache_key = cache_key

            # only permanent
            if sources:
                enrichment_dict = asdict(enrichment)

                # only permanent
                if self.cache_manager:
                    self.cache_manager.set_permanent('enrichment:permanent', cache_key, enrichment_dict)
                    logger.info(f"Saved to PERMANENT cache: {primary_place}")

                # queue Qdrant update
                if document_id and self.enrichment_persister:
                    self.enrichment_persister.persist_enrichment_async(document_id, enrichment_dict)
                    logger.info(f"Queued Qdrant update for {document_id} (background)")

                # fallback to redis_client
                elif self.redis and not self.cache_manager:
                    try:
                        redis_key = f"enrichment:{cache_key}"
                        self.redis.setex(redis_key, 86400, json.dumps(enrichment_dict, ensure_ascii=False))
                    except Exception as e:
                        logger.warning(f"Legacy Redis save error: {e}")

            logger.info(f"Enrichment complete for {primary_place}")
            return enrichment

        return WebEnrichmentResult()

    def _get_from_qdrant(self, document_id: str) -> Optional[Dict]:
        """Get enriched data from Qdrant metadata"""
        try:
            if not self.enrichment_persister:
                return None

            docs = self.enrichment_persister.qdrant.retrieve(
                collection_name=self.enrichment_persister.collection_name,
                ids=[document_id]
            )

            if not docs:
                return None

            payload = docs[0].payload if hasattr(docs[0], 'payload') else docs[0]

            if not payload.get('is_enriched'):
                return None

            return {
                'wikipedia_content': payload.get('description_enriched'),
                'wikipedia_images': payload.get('images_wikipedia', []),
                'unsplash_images': payload.get('images_unsplash', []),
                'enrichment_sources': payload.get('enrichment_sources', []),
                'cache_key': None
            }

        except Exception as e:
            logger.error(f"Error getting from Qdrant: {e}")
            return None

    def _needs_more_description(self, result) -> bool:
        """Check if result needs more description"""
        if hasattr(result, 'payload') and result.payload:
            description = result.payload.get('description', '')
            return len(description.strip()) < 300
        elif isinstance(result, dict):
            description = result.get('description', '')
            return len(description.strip()) < 300
        return True

    def _needs_more_images(self, result) -> bool:
        """Check if result needs more images"""
        if hasattr(result, 'payload') and result.payload:
            has_image = result.payload.get('has_processed_image', False)
            has_cloudinary = bool(result.payload.get('image_url'))
            return not (has_image or has_cloudinary)
        elif isinstance(result, dict):
            has_image = result.get('has_processed_image', False)
            has_cloudinary = bool(result.get('image_url'))
            return not (has_image or has_cloudinary)
        return True

    def _extract_place_name(self, result) -> str:
        """Extract place name from search result"""
        if hasattr(result, 'payload') and result.payload:
            return result.payload.get('name')
        elif isinstance(result, dict):
            return result.get('name')
        return 'Unknown'

    async def _search_wikipedia(self, place_name: str) -> Dict:
        """Search Wikipedia for additional information"""
        try:
            search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + place_name.replace(' ', '_')

            headers = {
                'User-Agent': 'Georgian-Tourism-Bot/1.0 (https://example.com/contact)'
            }

            response = requests.get(search_url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return {
                    'content': data.get('extract', ''),
                    'images': [data.get('thumbnail', {}).get('source', '')] if data.get('thumbnail') else [],
                    'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                    'source': 'wikipedia'
                }
            else:
                logger.warning(f"Wikipedia search failed for {place_name}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Wikipedia request failed for {place_name}: {e}")
        except Exception as e:
            logger.error(f"Wikipedia search failed for {place_name}: {e}")

        return {'content': '', 'images': [], 'url': '', 'source': 'wikipedia'}

    async def _search_unsplash_images(self, place_name: str) -> List[Dict]:
        """Search Unsplash for high-quality images"""
        if not self.unsplash_key:
            return []

        try:
            headers = {'Authorization': f'Client-ID {self.unsplash_key}'}
            search_url = f"https://api.unsplash.com/search/photos"
            params = {
                'query': f"{place_name} Georgia tourism",
                'per_page': 5,
                'orientation': 'landscape'
            }

            async with self.session.get(search_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    images = []
                    for photo in data.get('results', []):
                        images.append({
                            'url': photo['urls']['regular'],
                            'thumbnail': photo['urls']['thumb'],
                            'description': photo.get('description', ''),
                            'photographer': photo['user']['name'],
                            'source': 'unsplash',
                            'urls': photo['urls'],
                            'user': photo['user'],
                            'alt_description': photo.get('alt_description')
                        })
                    return images
        except Exception as e:
            logger.error(f"Unsplash search failed for {place_name}: {e}")

        return []

    async def _search_serpapi(self, place_name: str, language: str) -> List[Dict]:
        """Search for practical information using SerpAPI"""
        if not self.serpapi_key:
            return []

        try:
            search_url = "https://serpapi.com/search"
            params = {
                'api_key': self.serpapi_key,
                'engine': 'google',
                'q': f"{place_name} Georgia tourism opening hours tickets",
                'hl': language,
                'num': 5
            }

            async with self.session.get(search_url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('organic_results', [])
        except Exception as e:
            logger.error(f"SerpAPI search failed for {place_name}: {e}")

        return []