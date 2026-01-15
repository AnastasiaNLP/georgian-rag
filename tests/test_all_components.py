"""
complete test of all performance components:
1. cache warmup
2. performance monitoring
3. performance dashboard

tests integration with rag system
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# add project to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_all_components():
    print("\nTesting all performance components")

    try:
        print("\nStep 1: Initialize rag system")

        from core.clients import get_qdrant_client
        from config.settings import settings
        from search.HybridSearchEngine import HybridSearchEngine
        from multilingual.multilingual_manager import MultilingualManager

        print("\n1. Connecting to qdrant...")
        qdrant_client = get_qdrant_client()
        collection_info = qdrant_client.get_collection(settings.qdrant.collection_name)
        print(f"   Connected: {collection_info.points_count} documents")

        print("\n2. Initializing hybrid search...")
        hybrid_search = HybridSearchEngine(
            qdrant_client=qdrant_client,
            collection_name=settings.qdrant.collection_name,
            embedding_model=settings.embedding.model_name,
            config={}
        )
        print("   Hybrid search ready")

        print("\n3. Initializing multilingual manager...")
        multilingual = MultilingualManager()
        print("   Multilingual manager ready")

        print("\nStep 2: Initialize performance components")

        # import components we created
        # files are in monitoring/ directory
        from utils.performance_monitoring import PerformanceMonitor, track_performance
        from utils.performance_dashboard import CacheAnalytics, PerformanceDashboard

        print("\n1. Creating performance monitor...")
        monitor = PerformanceMonitor()
        print("   Performancemonitor initialized")

        print("\n2. Creating cache analytics...")
        cache_analytics = CacheAnalytics()
        print("   Cacheanalytics initialized")

        print("\n3. Creating performance dashboard...")
        dashboard = PerformanceDashboard(monitor, cache_analytics)
        print("   Performancedashboard initialized")

        print("\nStep 3: Cache warmup")

        from utils.cache_warmup import CacheWarmup

        print("\n1. Creating cache warmup instance...")
        warmup = CacheWarmup(hybrid_search, multilingual)

        print("\n2. Running warmup (this will take ~30 seconds)...")
        warmup_start = time.time()

        # warmup with subset of languages
        warmup_languages = ['en', 'ru', 'ka', 'de', 'fr', 'es']

        warmup_metrics = await warmup.warmup_async(languages=warmup_languages)

        warmup_time = time.time() - warmup_start

        print(f"\nWarmup completed!")
        print(f"   Total time: {warmup_metrics['total_time']:.2f}s")
        print(f"   Model load: {warmup_metrics['model_load_time']:.2f}s")
        print(f"   Queries: {warmup_metrics['queries_successful']}/{warmup_metrics['queries_processed']}")
        print(f"   Caches warmed: {', '.join(warmup_metrics['caches_warmed'])}")
        print(f"   Success: {'yes' if warmup_metrics['success'] else 'no'}")

        print("\nStep 4: Performance monitoring test")

        print("\n1. Running test queries with performance tracking...")

        test_queries = [
            "национальные парки Грузии",
            "Narikala Fortress",
            "Svetitskhoveli Cathedral",
            "озеро Рица",
            "Tbilisi restaurants"
        ]

        for i, query in enumerate(test_queries, 1):
            print(f"\n   Query {i}/{len(test_queries)}: '{query}'")

            # track full search
            search_start = time.time()

            try:
                # track components
                with track_performance(monitor, "QueryAnalysis"):
                    time.sleep(0.05)  # simulate analysis

                with track_performance(monitor, "PreFilter"):
                    time.sleep(0.1)  # simulate prefilter

                with track_performance(monitor, "BM25Search"):
                    time.sleep(0.15)  # simulate bm25

                with track_performance(monitor, "DenseSearch"):
                    # actual search
                    result = hybrid_search.search(query, top_k=5)

                with track_performance(monitor, "RRFFusion"):
                    time.sleep(0.05)  # simulate fusion

                search_time = time.time() - search_start

                # track search
                monitor.track_search(search_time, success=True)

                result_count = len(result['results']) if isinstance(result, dict) else len(result)
                print(f"      Found {result_count} results in {search_time:.3f}s")

            except Exception as e:
                search_time = time.time() - search_start
                monitor.track_search(search_time, success=False)
                print(f"      Error: {e}")

        print("\n2. Performance monitor summary:")
        monitor.print_summary()

        print("\nStep 5: Cache analytics test")

        print("\n1. Collecting cache statistics...")

        # register caches
        cache_analytics.register_cache("bm25_cache", max_size=1000)
        cache_analytics.register_cache("dense_cache", max_size=500)
        cache_analytics.register_cache("translation_cache")

        # update with mock stats (in real scenario, collect from components)
        cache_analytics.update_cache_stats("bm25_cache", {
            'hits': 12,
            'misses': 3,
            'size': 450,
            'memory_mb': 25.5
        })

        cache_analytics.update_cache_stats("dense_cache", {
            'hits': 10,
            'misses': 5,
            'size': 300,
            'memory_mb': 18.2
        })

        cache_analytics.update_cache_stats("translation_cache", {
            'hits': 8,
            'misses': 2,
            'size': 50
        })

        print("\n2. Cache analytics summary:")
        cache_analytics.print_summary()

        print("\nStep 6: Performance dashboard test")

        print("\n1. Quick stats:")
        dashboard.print_quick_stats()

        print("\n2. Generating html report...")
        html_file = dashboard.save_html_report("performance_report.html")
        print(f"   Html report saved: {html_file}")

        print("\n3. Exporting json metrics...")
        json_file = "../docs/performance_metrics.json"
        dashboard.export_to_json(json_file)
        print(f"   Json metrics saved: {json_file}")

        print("\n4. Testing snapshots...")
        snapshot1 = dashboard.save_snapshot()
        print(f"   Snapshot 1 saved")

        # simulate some changes
        for i in range(3):
            monitor.track_component("TestComponent", 0.5 + i * 0.1)
            monitor.track_search(1.0 + i * 0.1, success=True)

        snapshot2 = dashboard.save_snapshot()
        print(f"   Snapshot 2 saved")

        print("\n5. Comparing snapshots...")
        comparison = dashboard.compare_snapshots()
        if comparison:
            dashboard.print_comparison(comparison)

        print("\nStep 7: Integration test with real rag")

        print("\n1. Initializing rag with monitoring...")

        from pipeline.rag import EnhancedGeorgianRAG

        api_keys = {
            'anthropic_api_key': settings.claude.api_key,
            'langsmith_api_key': os.getenv('LANGSMITH_API_KEY', ''),
            'google_translate_api_key': settings.translation.api_key,
            'unsplash_access_key': settings.unsplash.access_key,
            'serpapi_api_key': os.getenv('SERPAPI_API_KEY'),
            'redis_url': settings.redis.url,
            'upstash_url': settings.redis.url,
            'upstash_token': settings.redis.token,
        }

        rag = EnhancedGeorgianRAG(
            qdrant_system=qdrant_client,
            hybrid_search_integrator=hybrid_search,
            api_keys=api_keys,
            config={}
        )

        await rag.initialize()
        print("   Rag initialized")

        print("\n2. Testing rag with monitoring...")
        test_query = "Tell me about beautiful places in Tbilisi"

        print(f"   Query: '{test_query}'")
        print(f"   Tracking performance...")

        # track the entire rag process
        rag_start = time.time()

        with track_performance(monitor, "RAG_FullPipeline"):
            result = await rag.answer_question(
                query=test_query,
                enable_web_enrichment=False,
                top_k=3
            )

        rag_time = time.time() - rag_start
        monitor.track_search(rag_time, success=True)

        print(f"\n   Rag response generated!")
        print(f"   Total time: {rag_time:.2f}s")
        print(f"   Language: {result.get('language')}")
        print(f"   Sources: {len(result.get('sources', []))}")
        print(f"   Response length: {len(result['response'])} chars")

        print("\n3. Final performance summary:")
        monitor.print_summary()

        print("\n4. Final cache summary:")
        cache_analytics.print_summary()

        print("\n5. Generating final report...")
        final_html = dashboard.save_html_report("final_performance_report.html")
        final_json = dashboard.export_to_json("final_metrics.json")
        print(f"   Html: {final_html}")
        print(f"   Json: {final_json}")

        print("\nAll tests completed successfully!")

        print("\nSummary:")
        print(f"   1. Cache warmup: {'yes' if warmup_metrics['success'] else 'no'}")
        print(f"   2. Performance monitoring: {monitor.search_metrics['total_searches']} searches tracked")
        print(f"   3. Cache analytics: {len(cache_analytics.caches)} caches monitored")
        print(f"   4. Performance dashboard: {len(dashboard.reports_history)} snapshots saved")
        print(f"   5. Rag integration: successfully integrated and tested")

        print("\nGenerated files (in current directory):")
        print(f"   - performance_report.html")
        print(f"   - performance_metrics.json")
        print(f"   - final_performance_report.html")
        print(f"   - final_metrics.json")

        print("\nNext steps:")
        print("   1. Open html reports in browser to see visualizations")
        print("   2. Review json metrics for detailed statistics")
        print("   3. Integrate monitoring into production rag")
        print("   4. Set up continuous monitoring and alerting")

        return True

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nComplete performance components test")
    print("\nThis will test:")
    print("  1. Cache warmup system")
    print("  2. Performance monitoring")
    print("  3. Cache analytics")
    print("  4. Performance dashboard")
    print("  5. Integration with rag")

    user_input = input("\nProceed with full test? (y/n): ").strip().lower()

    if user_input == 'y':
        success = asyncio.run(test_all_components())
        sys.exit(0 if success else 1)
    else:
        print("\nTest cancelled.")
        sys.exit(0)