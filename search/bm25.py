"""
BM25 search engine with smart result caching.
"""

import re
import time
import logging
import hashlib
import numpy as np
from typing import Dict, List, Any
from rank_bm25 import BM25Okapi

from core.types import SearchResult

logger = logging.getLogger(__name__)


class BM25Engine:
    """
    BM25 search engine with smart result caching.

    Features:
    - Result caching (not indexes)
    - Stable cache key based on semantic query
    - TTL and LRU eviction for memory management
    - Independence from candidate sets
    """

    def __init__(self, config_dict: Dict = None):
        """Constructor with new result caching system"""
        self.config = config_dict or {}
        self.k1 = self.config.get('bm25_k1', 1.2)
        self.b = self.config.get('bm25_b', 0.75)

        self.field_weights = {
            'name': 3.0,
            'description': 1.0,
            'location': 2.0,
            'category': 1.5
        }

        self._results_cache = {}
        self._cache_max_size = 500
        self._cache_ttl = 3600  # 1 hour TTL
        self._cache_hits = 0
        self._cache_misses = 0

        self._init_tokenizers()
        logger.info("BM25Engine initialized with smart result caching")

    def _init_tokenizers(self):
        """Initialize tokenizers for different languages"""
        try:
            import inspect
            if not hasattr(inspect, 'getargspec'):
                def getargspec(func):
                    spec = inspect.getfullargspec(func)
                    return (spec.args, spec.varargs, spec.varkw, spec.defaults)
                inspect.getargspec = getargspec

            import pymorphy2
            from nltk.stem import SnowballStemmer
            from nltk.corpus import stopwords

            self.morph_ru = pymorphy2.MorphAnalyzer()
            self.stemmer_en = SnowballStemmer("english")
            self.stop_words_ru = set(stopwords.words('russian'))
            self.stop_words_en = set(stopwords.words('english'))

        except Exception as e:
            logger.warning(f"Failed to initialize tokenizers: {e}")
            self.morph_ru = None
            self.stemmer_en = None
            self.stop_words_ru = set()
            self.stop_words_en = set()

    def _create_weighted_text(self, payload: Dict) -> str:
        """Create search text with field weights"""
        parts = []
        for field, weight in self.field_weights.items():
            content = payload.get(field, '')
            if content:
                parts.extend([content] * int(weight))
        return ' '.join(parts)

    def _tokenize_russian(self, text: str) -> List[str]:
        """Tokenize Russian text"""
        if not text or not self.morph_ru:
            return text.lower().split()
        tokens = []
        for word in re.findall(r'\b\w+\b', text.lower()):
            if len(word) > 2 and word not in self.stop_words_ru:
                tokens.append(self.morph_ru.parse(word)[0].normal_form)
        return tokens

    def _tokenize_english(self, text: str) -> List[str]:
        """Tokenize English text"""
        if not text or not self.stemmer_en:
            return text.lower().split()
        tokens = []
        for word in re.findall(r'\b\w+\b', text.lower()):
            if len(word) > 2 and word not in self.stop_words_en:
                tokens.append(self.stemmer_en.stem(word))
        return tokens

    def _tokenize_mixed(self, text: str) -> List[str]:
        """Tokenize mixed language text"""
        return [word for word in text.lower().split() if len(word) > 2]

    def _simple_keyword_match(self, keywords: List[str], candidate_docs: List, top_k: int) -> List[SearchResult]:
        """Simple keyword matching for small corpora"""
        results = []

        for doc in candidate_docs:
            search_text = self._create_weighted_text(doc.payload).lower()
            matches = 0
            total_keywords = len(keywords)

            for keyword in keywords:
                if keyword.lower() in search_text:
                    matches += 1

            if matches > 0:
                simple_score = (matches / total_keywords) * 10.0

                result = SearchResult(
                    doc_id=str(doc.id),
                    score=float(simple_score),
                    source='bm25_simple_match',
                    metadata=doc.payload,
                    content=doc.payload.get('description', '')
                )
                results.append(result)

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    def _create_cache_key(self, semantic_query: str, keywords: List[str], language: str) -> str:
        """Create cache key using semantic query"""
        normalized_query = semantic_query.lower().strip()
        key_string = f"bm25:{normalized_query}"
        cache_key = hashlib.md5(key_string.encode('utf-8')).hexdigest()
        return f"bm25:{cache_key}"

    def _get_from_cache(self, cache_key: str) -> List:
        """Get results from cache with TTL check"""
        if cache_key not in self._results_cache:
            self._cache_misses += 1
            return None

        cached_data = self._results_cache[cache_key]

        if time.time() - cached_data['timestamp'] > self._cache_ttl:
            del self._results_cache[cache_key]
            self._cache_misses += 1
            return None

        self._cache_hits += 1
        logger.debug(f"BM25 cache HIT: {cache_key[:16]}...")
        return cached_data['results']

    def _save_to_cache(self, cache_key: str, results: List):
        """Save results to cache with LRU eviction"""
        if len(self._results_cache) >= self._cache_max_size:
            oldest_key = min(
                self._results_cache.keys(),
                key=lambda k: self._results_cache[k]['timestamp']
            )
            del self._results_cache[oldest_key]
            logger.debug(f"Evicted oldest cache entry: {oldest_key[:16]}")

        self._results_cache[cache_key] = {
            'results': results,
            'timestamp': time.time()
        }
        logger.debug(f"BM25 cached: {cache_key[:16]}... ({len(results)} results)")

    def search_within_candidates(self,
                                 keywords: List[str],
                                 candidate_docs: List,
                                 language: str,
                                 top_k: int,
                                 semantic_query: str = None) -> List[SearchResult]:
        """
        BM25 search with smart result caching.

        Args:
            keywords: Search keywords
            candidate_docs: Candidate documents to search within
            language: Query language (ru/en/mixed)
            top_k: Number of results to return
            semantic_query: Semantic query for cache key creation
        """
        if not candidate_docs or not keywords:
            return []

        if semantic_query:
            cache_key = self._create_cache_key(semantic_query, keywords, language)

            cached_results = self._get_from_cache(cache_key)
            if cached_results is not None:
                logger.info(f"BM25 cache HIT - returning {len(cached_results)} cached results")
                return cached_results

            logger.info("BM25 cache MISS - executing search")
        else:
            cache_key = None
            logger.debug("No semantic_query provided - cache disabled for this search")

        # create temporary corpus from candidates
        temp_corpus = []
        doc_mapping = []

        for doc in candidate_docs:
            search_text = self._create_weighted_text(doc.payload)

            if language == 'ru':
                tokens = self._tokenize_russian(search_text)
            elif language == 'en':
                tokens = self._tokenize_english(search_text)
            else:
                tokens = self._tokenize_mixed(search_text)

            if tokens:
                temp_corpus.append(tokens)
                doc_mapping.append(doc)

        if not temp_corpus:
            logger.warning("Failed to create BM25 corpus from candidates")
            return []

        # handle small corpora
        if len(temp_corpus) <= 5:
            logger.info(f"Small corpus ({len(temp_corpus)} documents), using simple matching")
            return self._simple_keyword_match(keywords, candidate_docs, top_k)

        # create temporary BM25 index
        try:
            bm25_index = BM25Okapi(temp_corpus, k1=self.k1, b=self.b)
            scores = bm25_index.get_scores(keywords)
            top_indices = np.argsort(scores)[::-1][:top_k]

            # adaptive threshold
            if len(temp_corpus) <= 20:
                score_threshold = -0.5
            else:
                score_threshold = 0.0

            # form SearchResult objects
            results = []

            for idx in top_indices:
                if scores[idx] > score_threshold:
                    original_doc = doc_mapping[idx]
                    result = SearchResult(
                        doc_id=str(original_doc.id),
                        score=float(scores[idx]),
                        source='bm25_focused',
                        metadata=original_doc.payload,
                        content=original_doc.payload.get('description', '')
                    )
                    results.append(result)

            # fallback if no results
            if not results:
                logger.info("BM25 gave no results, fallback to simple matching")
                results = self._simple_keyword_match(keywords, candidate_docs, top_k)

            # save results to cache
            if cache_key and results:
                self._save_to_cache(cache_key, results)

            return results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return self._simple_keyword_match(keywords, candidate_docs, top_k)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
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

    def clear_cache(self):
        """Clear results cache"""
        self._results_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("BM25 results cache cleared")

    def reset_cache_stats(self):
        """Reset cache statistics without clearing cache"""
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("BM25 cache stats reset")