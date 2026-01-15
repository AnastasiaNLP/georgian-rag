"""
Model Manager for caching embedding models.
"""

import threading
import time
import logging
from typing import Dict, Optional, Any
from sentence_transformers import SentenceTransformer
from config.settings import config

logger = logging.getLogger(__name__)


class ModelManager:
    """
    Singleton manager for caching embedding models.
    Thread-safe model loading with caching.
    """

    _instance: Optional['ModelManager'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'ModelManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._models: Dict[str, SentenceTransformer] = {}
        self._model_stats: Dict[str, Dict[str, Any]] = {}
        self._loading_locks: Dict[str, threading.Lock] = {}
        self._total_loads = 0
        self._cache_hits = 0
        self._initialized = True

        logger.info("ModelManager initialized")

    def get_model(self, model_name: str = None) -> SentenceTransformer:
        """Get model with caching"""
        if model_name is None:
            model_name = config.embedding.model_name

        if model_name in self._models:
            self._cache_hits += 1
            logger.debug(f"Cache hit for model: {model_name}")
            return self._models[model_name]

        if model_name not in self._loading_locks:
            with self._lock:
                if model_name not in self._loading_locks:
                    self._loading_locks[model_name] = threading.Lock()

        with self._loading_locks[model_name]:
            if model_name in self._models:
                self._cache_hits += 1
                return self._models[model_name]

            logger.info(f"Loading embedding model: {model_name}")
            start_time = time.time()

            try:
                model = SentenceTransformer(model_name, device=config.embedding.device)
                load_time = time.time() - start_time

                self._models[model_name] = model
                self._model_stats[model_name] = {
                    'load_time': load_time,
                    'loaded_at': time.time(),
                    'use_count': 0,
                    'dimension': model.get_sentence_embedding_dimension(),
                }
                self._total_loads += 1

                logger.info(f"Model {model_name} loaded in {load_time:.2f}s")
                return model

            except Exception as e:
                logger.error(f"Error loading model {model_name}: {e}")
                raise RuntimeError(f"Failed to load embedding model: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        total_requests = self._cache_hits + self._total_loads
        cache_hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'loaded_models': list(self._models.keys()),
            'total_models': len(self._models),
            'total_loads': self._total_loads,
            'cache_hits': self._cache_hits,
            'cache_hit_rate': f"{cache_hit_rate:.1f}%"
        }


# global model manager instance
model_manager = ModelManager()