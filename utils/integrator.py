"""
Hybrid Search Integrator wrapper for backward compatibility.
NOTE: This is a simplified wrapper. Full version with PerformanceMonitor
"""

import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class HybridSearchIntegrator:
    """
    Main hybrid search integration class.

    Simplified wrapper for HybridSearchEngine with additional
    convenience methods and backward compatibility.
    """

    def __init__(self, config: Dict = None, existing_qdrant_client=None):
        """
        Initialize integrator.

        Args:
            config: Configuration dictionary
            existing_qdrant_client: Existing Qdrant client to reuse
        """
        self.config = config or {}
        self.qdrant_client = existing_qdrant_client
        self.hybrid_engine = None
        self.is_initialized = False

        # warm-up tracking
        self._local_warm_up_completed = False
        self._warm_up_metrics = {
            'total_time': 0.0,
            'model_load_time': 0.0,
            'test_queries_time': 0.0,
            'cache_init_time': 0.0,
            'test_queries_count': 0,
            'success': False
        }

        logger.info("HybridSearchIntegrator initialized")

    def initialize(self):
        """
        Initialize hybrid search engine.

        Returns:
            HybridSearchEngine instance
        """
        if self.is_initialized and self.hybrid_engine:
            logger.info("Already initialized, returning existing engine")
            return self.hybrid_engine

        logger.info("Initializing hybrid search...")

        try:
            # import here to avoid circular dependencies
            from search.hybrid import HybridSearchEngine

            # initialize engine
            self.hybrid_engine = HybridSearchEngine(
                qdrant_client=self.qdrant_client,
                collection_name=self.config.get('collection_name', 'georgian_attractions'),
                embedding_model=self.config.get('embedding_model', 'intfloat/multilingual-e5-small'),
                config=self.config.get('search_config', {})
            )

            self.hybrid_engine.initialize()
            self.is_initialized = True

            logger.info("Hybrid search initialized successfully")
            return self.hybrid_engine

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self.is_initialized = False
            self.hybrid_engine = None
            raise

    def warm_up(self, test_queries: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Warm up system with test queries.

        Args:
            test_queries: Optional list of test queries

        Returns:
            Warm-up metrics
        """
        if self._local_warm_up_completed:
            logger.info("Already warmed up")
            return self._warm_up_metrics

        logger.info("Starting system warm-up...")
        start_time = time.time()

        try:
            # initialize if needed
            if not self.is_initialized:
                self.initialize()

            # default test queries
            if test_queries is None:
                test_queries = [
                    "Светицховели церковь",
                    "крепости Тбилиси",
                    "музеи Грузии"
                ]

            # run test queries
            successful_queries = 0
            for query in test_queries:
                try:
                    result = self.search(query, top_k=3)
                    if isinstance(result, dict) and 'results' in result:
                        successful_queries += 1
                except Exception as e:
                    logger.warning(f"Test query failed: {e}")

            # update metrics
            total_time = time.time() - start_time
            self._warm_up_metrics.update({
                'total_time': total_time,
                'test_queries_count': len(test_queries),
                'success': successful_queries > 0
            })

            self._local_warm_up_completed = True
            logger.info(f"Warm-up complete in {total_time:.2f}s")

            return self._warm_up_metrics

        except Exception as e:
            logger.error(f"Warm-up failed: {e}")
            self._warm_up_metrics['success'] = False
            raise

    def search(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """
        Search with hybrid engine.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            Search results dictionary
        """
        if not self.is_initialized or not self.hybrid_engine:
            self.initialize()

        return self.hybrid_engine.search(query, top_k or 10)

    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        if not self.is_initialized:
            return {"status": "Not initialized"}

        return {
            'initialization_status': self.is_initialized,
            'warm_up_completed': self._local_warm_up_completed,
            'warm_up_metrics': self._warm_up_metrics,
            'config': self.config
        }

    def get_warm_up_metrics(self) -> Dict[str, Any]:
        """Get warm-up metrics"""
        return {
            'local_metrics': self._warm_up_metrics.copy(),
            'local_completed': self._local_warm_up_completed
        }

    def clear_caches(self):
        """Clear all caches"""
        if self.hybrid_engine:
            self.hybrid_engine.clear_caches()
            self._local_warm_up_completed = False
            logger.info("Caches cleared, warm-up status reset")

    def is_ready(self) -> bool:
        """Check if system is ready"""
        return self.is_initialized and self.hybrid_engine is not None

    def health_check(self) -> Dict[str, Any]:
        """System health check"""
        health = {
            'status': 'unknown',
            'initialized': self.is_initialized,
            'warmed_up': self._local_warm_up_completed,
            'components': {},
            'issues': []
        }

        if not self.is_initialized:
            health['status'] = 'not_initialized'
            health['issues'].append('System not initialized')
            return health

        if not self._local_warm_up_completed:
            health['issues'].append('System not warmed up')

        # check components
        if self.hybrid_engine:
            components = [
                ('query_analyzer', self.hybrid_engine.query_analyzer),
                ('bm25_engine', self.hybrid_engine.bm25_engine),
                ('dense_engine', self.hybrid_engine.dense_engine),
                ('rrf_engine', self.hybrid_engine.rrf_engine)
            ]

            for name, component in components:
                health['components'][name] = component is not None
                if component is None:
                    health['issues'].append(f'{name} not available')

        # determine status
        if not health['issues']:
            health['status'] = 'healthy'
        elif len(health['issues']) <= 2:
            health['status'] = 'warning'
        else:
            health['status'] = 'critical'

        return health