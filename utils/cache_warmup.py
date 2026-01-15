"""
Cache warmup system for rag - preload popular queries

Warms up:
- embedding model
- bm25 cache
- dense search cache
- hybrid search cache
- prefilter cache
"""

import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheWarmup:
    """
    Rag system cache warmup system

    Functions:
    - load embedding model into memory
    - precompute embeddings for popular queries
    - warm up all cache levels
    - warmup statistics and metrics
    """

    def __init__(self, hybrid_search, multilingual_manager=None):
        """
        Args:
            hybrid_search: hybridsearchengine instance
            multilingual_manager: multilingualmanager instance (optional)
        """
        self.hybrid_search = hybrid_search
        self.multilingual_manager = multilingual_manager

        self.warmup_completed = False
        self.warmup_metrics = {
            'total_time': 0.0,
            'model_load_time': 0.0,
            'queries_processed': 0,
            'queries_successful': 0,
            'queries_failed': 0,
            'caches_warmed': [],
            'success': False,
            'timestamp': None
        }

        logger.info("cachewarmup initialized")

    async def warmup_async(self,
                          test_queries: Optional[List[str]] = None,
                          languages: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Asynchronous system warmup

        args:
            test_queries: list of test queries (if none - uses defaults)
            languages: languages for multilingual warmup

        returns:
            dict with warmup metrics
        """
        if self.warmup_completed:
            logger.info("cache warmup already completed")
            return self.warmup_metrics

        logger.info("Starting cache warmup")

        start_time = time.time()

        try:
            # warmup embedding model
            logger.info("\n1. Warming up embedding model...")
            model_time = await self._warmup_model()
            self.warmup_metrics['model_load_time'] = model_time
            self.warmup_metrics['caches_warmed'].append('embedding_model')
            logger.info(f"   Model loaded in {model_time:.2f}s")

            # warmup with test queries
            logger.info("\n2. Processing warmup queries...")
            queries_time, queries_stats = await self._warmup_queries(test_queries)
            self.warmup_metrics['queries_processed'] = queries_stats['total']
            self.warmup_metrics['queries_successful'] = queries_stats['successful']
            self.warmup_metrics['queries_failed'] = queries_stats['failed']
            logger.info(f"   Queries processed: {queries_stats['successful']}/{queries_stats['total']}")

            # warmup multilingual if available
            if self.multilingual_manager and languages:
                logger.info("\n3. Warming up multilingual detection...")
                ml_time = await self._warmup_multilingual(languages)
                self.warmup_metrics['multilingual_time'] = ml_time
                self.warmup_metrics['caches_warmed'].append('multilingual')
                logger.info(f"   Multilingual warmed for {len(languages)} languages")

            # check cache stats
            logger.info("\n4. Checking cache statistics...")
            cache_stats = self._get_cache_stats()
            self.warmup_metrics['cache_stats'] = cache_stats

            # finish
            total_time = time.time() - start_time
            self.warmup_metrics['total_time'] = total_time
            self.warmup_metrics['success'] = queries_stats['successful'] > 0
            self.warmup_metrics['timestamp'] = datetime.now().isoformat()

            if self.warmup_metrics['success']:
                self.warmup_completed = True
                logger.info("\nCache warmup completed successfully!")
                logger.info(f"   Total time: {total_time:.2f}s")
                logger.info(f"   Queries: {queries_stats['successful']}/{queries_stats['total']}")
                logger.info(f"   Caches warmed: {', '.join(self.warmup_metrics['caches_warmed'])}")
            else:
                logger.warning("cache warmup completed with warnings")

            return self.warmup_metrics

        except Exception as e:
            logger.error(f"cache warmup error: {e}")
            self.warmup_metrics['success'] = False
            self.warmup_metrics['error'] = str(e)
            self.warmup_metrics['total_time'] = time.time() - start_time
            raise

    def warmup(self, test_queries: Optional[List[str]] = None,
              languages: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        synchronous wrapper for warmup_async
        """
        return asyncio.run(self.warmup_async(test_queries, languages))

    async def _warmup_model(self) -> float:
        """warmup embedding model"""
        start = time.time()

        try:
            # get model through property for loading
            if hasattr(self.hybrid_search, 'dense_engine'):
                _ = self.hybrid_search.dense_engine.model
                logger.info("   Dense engine model loaded")

            # warmup bm25 cache
            if hasattr(self.hybrid_search, 'bm25_engine'):
                logger.info("   Bm25 engine ready")
                self.warmup_metrics['caches_warmed'].append('bm25')

            # warmup prefilter cache
            if hasattr(self.hybrid_search, 'prefilter_engine'):
                logger.info("   Prefilter engine ready")
                self.warmup_metrics['caches_warmed'].append('prefilter')

        except Exception as e:
            logger.warning(f"model warmup warning: {e}")

        return time.time() - start

    async def _warmup_queries(self, test_queries: Optional[List[str]] = None) -> tuple:
        """
        warmup through test queries

        returns:
            (time, stats_dict)
        """
        if test_queries is None:
            # default queries in russian and english
            test_queries = [
                # russian
                "национальные парки Грузии",
                "крепость Нарикала",
                "Светицховели монастырь",
                "озеро Рица",
                "Тбилисский ботанический сад",

                # english
                "Tbilisi National Park",
                "Narikala Fortress",
                "Svetitskhoveli Cathedral",
                "Lake Ritsa",
                "Batumi Botanical Garden",

                # mixed popular
                "винный тур Кахетия",
                "mountain hiking Georgia",
                "старый город Тбилиси",
                "black sea resorts",
                "минеральные источники Боржоми"
            ]

        start = time.time()
        stats = {'total': len(test_queries), 'successful': 0, 'failed': 0}

        for i, query in enumerate(test_queries, 1):
            try:
                logger.info(f"   Query {i}/{len(test_queries)}: '{query[:50]}...'")

                # synchronous search call for warmup
                result = self.hybrid_search.search(query, top_k=5)

                if result and (isinstance(result, dict) and result.get('results') or
                              isinstance(result, list) and len(result) > 0):
                    stats['successful'] += 1
                    result_count = len(result['results']) if isinstance(result, dict) else len(result)
                    logger.info(f"   Found {result_count} results")
                else:
                    stats['failed'] += 1
                    logger.warning(f"   Empty result")

            except Exception as e:
                stats['failed'] += 1
                logger.warning(f"   Error: {e}")

        elapsed = time.time() - start
        return elapsed, stats

    async def _warmup_multilingual(self, languages: List[str]) -> float:
        """warmup multilingual detection"""
        start = time.time()

        # test phrases for different languages
        test_phrases = {
            'en': 'Tell me about Tbilisi',
            'ru': 'Расскажи о Тбилиси',
            'ka': 'მითხარი თბილისის შესახებ',
            'de': 'Erzählen Sie über Tiflis',
            'fr': 'Parlez-moi de Tbilissi',
            'es': 'Cuéntame sobre Tiflis',
            'it': 'Parlami di Tbilisi',
            'ja': 'トビリシについて',
            'ko': '트빌리시에 대해',
            'zh': '告诉我关于第比利斯',
            'ar': 'أخبرني عن تبليسي',
            'tr': 'Tiflis hakkında anlat',
            'az': 'Tiflisdə danış'
        }

        for lang in languages:
            if lang in test_phrases:
                try:
                    phrase = test_phrases[lang]
                    detected = await self.multilingual_manager.detect_language(phrase)
                    logger.info(f"   {lang}: '{phrase[:30]}...' -> {detected}")
                except Exception as e:
                    logger.warning(f"   {lang} detection error: {e}")

        return time.time() - start

    def _get_cache_stats(self) -> Dict[str, Any]:
        """get cache statistics"""
        stats = {}

        try:
            # bm25 cache stats
            if hasattr(self.hybrid_search, 'bm25_engine') and \
               hasattr(self.hybrid_search.bm25_engine, 'get_cache_stats'):
                stats['bm25'] = self.hybrid_search.bm25_engine.get_cache_stats()

            # dense cache stats
            if hasattr(self.hybrid_search, 'dense_engine') and \
               hasattr(self.hybrid_search.dense_engine, 'get_cache_stats'):
                stats['dense'] = self.hybrid_search.dense_engine.get_cache_stats()

            # hybrid cache stats
            if hasattr(self.hybrid_search, 'get_cache_health'):
                stats['hybrid'] = self.hybrid_search.get_cache_health()

        except Exception as e:
            logger.warning(f"cache stats error: {e}")

        return stats

    def get_metrics(self) -> Dict[str, Any]:
        """get warmup metrics"""
        return self.warmup_metrics.copy()

    def is_completed(self) -> bool:
        """check warmup completion"""
        return self.warmup_completed

    def reset(self):
        """reset warmup status"""
        self.warmup_completed = False
        self.warmup_metrics = {
            'total_time': 0.0,
            'model_load_time': 0.0,
            'queries_processed': 0,
            'queries_successful': 0,
            'queries_failed': 0,
            'caches_warmed': [],
            'success': False,
            'timestamp': None
        }
        logger.info("cache warmup reset")


async def warmup_system():
    """
    Standalone warmup script - can be run separately
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from core.clients import get_qdrant_client
    from config.settings import settings
    from search.HybridSearchEngine import HybridSearchEngine
    from multilingual.multilingual_manager import MultilingualManager

    print("\nRag system cache warmup")

    try:
        # initialize components
        print("\n1. Initializing components...")
        qdrant_client = get_qdrant_client()

        hybrid_search = HybridSearchEngine(
            qdrant_client=qdrant_client,
            collection_name=settings.qdrant.collection_name,
            embedding_model=settings.embedding.model_name,
            config={}
        )

        multilingual = MultilingualManager()

        print("   Components initialized")

        # create warmup instance
        print("\n2. Creating warmup instance...")
        warmup = CacheWarmup(hybrid_search, multilingual)

        # run warmup
        print("\n3. Running warmup...")
        languages = ['en', 'ru', 'ka', 'de', 'fr', 'es', 'ja', 'ko', 'zh', 'ar']

        metrics = await warmup.warmup_async(languages=languages)

        # show results
        print("\nWarmup results:")
        print(f"Total time: {metrics['total_time']:.2f}s")
        print(f"Model load: {metrics['model_load_time']:.2f}s")
        print(f"Queries: {metrics['queries_successful']}/{metrics['queries_processed']}")
        print(f"Caches warmed: {', '.join(metrics['caches_warmed'])}")
        print(f"Success: {'yes' if metrics['success'] else 'no'}")

        return metrics['success']

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(warmup_system())
    exit(0 if success else 1)