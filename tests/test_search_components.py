"""
test script for search components (phase 2).

tests:
1. configuration loading
2. qdrant client connection
3. queryanalyzer
4. densesearchengine
5. bm25engine
6. rrffusionengine

requirements:
- qdrant running and accessible
- embedding model downloadable
- no google translate api required
"""

import sys
import os
from pathlib import Path
# add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import config
from core.clients import get_qdrant_client
from core.types import QueryType, QueryAnalysis, SearchResult
from search.query_analyzer import QueryAnalyzer
from search.dense import DenseSearchEngine
from search.bm25 import BM25Engine
from search.rrf import RRFFusionEngine
from utils.logger_setup import setup_logging, get_logger

# setup logging
setup_logging()
logger = get_logger(__name__)


def test_config():
    """test 1: configuration loading"""
    print("\nTest 1: Configuration loading")

    try:
        config.validate()
        config.print_status()
        print("Configuration loaded successfully")
        return True
    except Exception as e:
        print(f"Configuration test failed: {e}")
        return False


def test_qdrant_connection():
    """test 2: qdrant connection"""
    print("\nTest 2: Qdrant connection")

    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        print(f"Connected to qdrant")
        print(f"   Collections: {[c.name for c in collections.collections]}")

        # check if our collection exists
        collection_name = config.qdrant.collection_name
        if any(c.name == collection_name for c in collections.collections):
            collection_info = client.get_collection(collection_name)
            print(f"   Collection '{collection_name}' found:")
            print(f"   - Points count: {collection_info.points_count}")
            print(f"   - Vector size: {collection_info.config.params.vectors.size}")
            return True
        else:
            print(f"   Collection '{collection_name}' not found")
            print(f"   Available collections: {[c.name for c in collections.collections]}")
            return False

    except Exception as e:
        print(f"Qdrant connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_analyzer():
    """test 3: queryanalyzer"""
    print("\nTest 3: Query analyzer")

    try:
        analyzer = QueryAnalyzer()
        print("Queryanalyzer initialized")

        # test queries in different languages
        test_queries = [
            "церкви в Тбилиси",
            "churches in Tbilisi",
            "Svetitskhoveli Cathedral",
            "лучшие достопримечательности Грузии"
        ]

        for query in test_queries:
            print(f"\n   Query: '{query}'")
            analysis = analyzer.analyze(query)
            print(f"   - Language: {analysis.language}")
            print(f"   - Intent: {analysis.intent_type.value}")
            print(f"   - Entities: {analysis.entities}")
            print(f"   - Filters: {len(analysis.qdrant_filters)} filter(s)")
            print(f"   - Strategy: {analysis.filter_strategy}")
            print(f"   - Keywords: {analysis.keywords[:5]}")

        print("\nQueryanalyzer test passed")
        return True

    except Exception as e:
        print(f"Queryanalyzer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dense_search():
    """test 4: densesearchengine"""
    print("\nTest 4: Dense search engine")

    try:
        client = get_qdrant_client()
        collection_name = config.qdrant.collection_name

        dense_engine = DenseSearchEngine(
            client=client,
            collection_name=collection_name
        )
        print("Densesearchengine initialized")

        # test search
        test_query = "beautiful churches in Tbilisi"
        print(f"\n   Testing search: '{test_query}'")

        results = dense_engine.search(
            dense_query=test_query,
            top_k=5
        )

        print(f"   Results: {len(results)} documents found")
        for i, result in enumerate(results[:3], 1):
            print(f"   {i}. {result.metadata.get('name', 'Unknown')} (score: {result.score:.4f})")

        # test cache
        stats = dense_engine.get_search_stats()
        print(f"\n   Cache stats:")
        print(f"   - Searches: {stats['total_searches']}")
        print(f"   - Cache size: {stats['cache_stats']['cache_size']}")
        print(f"   - Hit rate: {stats['cache_stats']['hit_rate']}%")

        print("\nDensesearchengine test passed")
        return True

    except Exception as e:
        print(f"Densesearchengine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bm25_search():
    """test 5: bm25engine"""
    print("\nTest 5: Bm25 search engine")

    try:
        client = get_qdrant_client()
        collection_name = config.qdrant.collection_name

        bm25_engine = BM25Engine()
        print("Bm25engine initialized")

        # get some candidates first
        dense_engine = DenseSearchEngine(client=client, collection_name=collection_name)
        candidates = dense_engine.search("churches", top_k=50)

        if not candidates:
            print("   No candidates found, skipping bm25 test")
            return True

        print(f"   Testing with {len(candidates)} candidates")

        # test bm25 search
        keywords = ["church", "cathedral", "tbilisi"]
        results = bm25_engine.search_within_candidates(
            keywords=keywords,
            candidate_docs=candidates,
            language='en',
            top_k=5,
            semantic_query="churches in tbilisi"
        )

        print(f"   Results: {len(results)} documents found")
        for i, result in enumerate(results[:3], 1):
            print(f"   {i}. {result.metadata.get('name', 'Unknown')} (score: {result.score:.4f})")

        # test cache
        stats = bm25_engine.get_cache_stats()
        print(f"\n   Cache stats:")
        print(f"   - Cache size: {stats['cache_size']}")
        print(f"   - Hit rate: {stats['hit_rate']}%")

        print("\nBm25engine test passed")
        return True

    except Exception as e:
        print(f"Bm25engine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rrf_fusion():
    """test 6: rrffusionengine"""
    print("\nTest 6: Rrf fusion engine")

    try:
        rrf_engine = RRFFusionEngine(k=3)
        print("Rrffusionengine initialized")

        # create mock results for testing
        mock_results = {
            'dense': [
                SearchResult(
                    doc_id='1',
                    score=0.95,
                    source='dense',
                    metadata={'name': 'Test 1', 'language': 'EN'},
                    content='Test content 1'
                ),
                SearchResult(
                    doc_id='2',
                    score=0.85,
                    source='dense',
                    metadata={'name': 'Test 2', 'language': 'EN'},
                    content='Test content 2'
                )
            ],
            'bm25': [
                SearchResult(
                    doc_id='2',
                    score=12.5,
                    source='bm25',
                    metadata={'name': 'Test 2', 'language': 'EN'},
                    content='Test content 2'
                ),
                SearchResult(
                    doc_id='3',
                    score=8.3,
                    source='bm25',
                    metadata={'name': 'Test 3', 'language': 'EN'},
                    content='Test content 3'
                )
            ]
        }

        # create mock query analysis
        mock_analysis = QueryAnalysis(
            original_query="test query",
            language='en',
            detected_language='en',
            intent_type=QueryType.EXPLORATORY,
            entities={},
            query_complexity='simple',
            suggested_weights={'bm25': 0.4, 'dense': 0.5, 'metadata': 0.1},
            enhanced_query="test query",
            implicit_filters={},
            semantic_query="test query",
            keywords=['test', 'query'],
            qdrant_filters=[],
            filter_strategy='loose',
            dense_query="test query"
        )

        # test fusion
        fused_results = rrf_engine.fuse_results(
            results_dict=mock_results,
            query_analysis=mock_analysis,
            top_k=5
        )

        print(f"   Fused results: {len(fused_results)} documents")
        for i, result in enumerate(fused_results, 1):
            fusion_info = result.metadata.get('fusion_info', {})
            print(f"   {i}. {result.metadata.get('name')} (score: {result.score:.4f})")
            print(f"      Sources: {fusion_info.get('sources_used', [])}")

        # test stats
        stats = rrf_engine.get_fusion_stats()
        print(f"\n   Fusion stats:")
        print(f"   - Total fusions: {stats['total_fusions']}")
        print(f"   - Clean fusions: {stats['clean_fusions']}")
        print(f"   - Legacy fusions: {stats['legacy_fusions']}")

        print("\nRrffusionengine test passed")
        return True

    except Exception as e:
        print(f"Rrffusionengine test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """run all tests"""
    print("\nGeorgian rag - phase 2 tests")
    print("Testing search components")

    results = {
        'Configuration': test_config(),
        'Qdrant Connection': test_qdrant_connection(),
        'Query Analyzer': test_query_analyzer(),
        'Dense Search': test_dense_search(),
        'BM25 Search': test_bm25_search(),
        'RRF Fusion': test_rrf_fusion()
    }

    # summary
    print("\nTest summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "Passed" if result else "Failed"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)