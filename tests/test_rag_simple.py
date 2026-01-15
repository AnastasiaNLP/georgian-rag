"""
simple rag system test with automatic language detection and groq translation
"""
import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

async def test_rag_simple():
    print("\nRag system test with auto language detection")

    try:
        # 1. connect to qdrant
        print("\n1. Connecting to qdrant...")
        from core.clients import get_qdrant_client
        from config.settings import settings

        qdrant_client = get_qdrant_client()
        collection_info = qdrant_client.get_collection(settings.qdrant.collection_name)
        print(f"   Connected: {collection_info.points_count} documents")

        # 2. initialize hybrid search
        print("\n2. Initializing hybrid search...")
        from search.HybridSearchEngine import HybridSearchEngine

        hybrid_search = HybridSearchEngine(
            qdrant_client=qdrant_client,
            collection_name=settings.qdrant.collection_name,
            embedding_model=settings.embedding.model_name,
            config={}
        )
        print("   Hybrid search ready")

        # 3. search test
        print("\n3. Search test...")

        # ask for test query
        test_search_query = input("   Test search query (enter = 'national parks of Georgia'): ").strip()
        if not test_search_query:
            test_search_query = "national parks of Georgia"

        # synchronous call for python 3.8
        search_results = hybrid_search.search(test_search_query, 5)

        results_list = search_results['results'] if isinstance(search_results, dict) else search_results
        print(f"   Found results: {len(results_list)}")

        if results_list:
            print(f"\n   First result:")
            first = results_list[0]
            payload = first.payload if hasattr(first, 'payload') else first
            print(f"      Name: {payload.get('name', 'N/A')[:60]}")
            print(f"      Category: {payload.get('category', 'N/A')}")
            print(f"      Score: {first.score if hasattr(first, 'score') else 'N/A'}")
            print(f"      Tags: {payload.get('tags', [])[:3]}")
            print(f"      Image url: {'yes' if payload.get('image_url') else 'no'}")

        # 4. initialize rag
        print("\n4. Initializing rag system...")
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

        # show available keys
        print("   Available api keys:")
        for key_name, key_value in api_keys.items():
            if key_value:
                masked = f"{str(key_value)[:8]}..." if len(str(key_value)) > 8 else "***"
                print(f"      {key_name}: {masked}")
            else:
                print(f"      {key_name} (not set)")

        # check groq api key
        groq_key = os.getenv('GROQ_API_KEY')
        if groq_key:
            print(f"      Groq_api_key: {groq_key[:8]}... (free translation enabled!)")
        else:
            print(f"      Groq_api_key (not set - translation unavailable)")

        rag = EnhancedGeorgianRAG(
            qdrant_system=qdrant_client,
            hybrid_search_integrator=hybrid_search,
            api_keys=api_keys,
            config={}
        )

        print("\n   Initializing components...")
        success = await rag.initialize()

        if not success:
            print("   Initialization failed!")
            return False

        print("   Rag system ready")

        # 5. check components
        print("\n5. Component check:")
        status = rag.get_system_status()
        for component, state in status['components'].items():
            icon = "yes" if state else "no"
            print(f"   {component}: {icon}")

        print("\nAll basic checks passed!")

        # 6. real query test
        print("\nTest with real claude request?")
        print("   This will call claude api (~$0.01)")
        print("   Groq api is used for free translation")
        print("   See trace in langsmith")

        user_input = input("\n   Continue? (y/n): ").strip()

        if user_input.lower() == 'y':
            print("\n6. Real query test...")

            print("\n   Enter query in any of 18 languages:")
            print("      (en, ru, ka, de, fr, es, it, nl, pl, cs, zh, ja, ko, ar, tr, hi, hy, az)")

            test_query = input("\n   Your query (enter = 'national parks of Georgia'): ").strip()
            if not test_query:
                test_query = "national parks of Georgia"

            print(f"\n   Query: '{test_query}'")
            print("   Detecting language...")

            # without target_language - system will auto-detect!
            result = await rag.answer_question(
                query=test_query,
                enable_web_enrichment=False,
                top_k=3
            )

            # show what happened
            print(f"\n   Detected language: {result['metadata'].get('detected_language')}")

            if result['metadata'].get('query_was_translated'):
                print(f"   Query translated via groq (free):")
                print(f"      '{test_query[:50]}...'")
                print(f"      ->")
                print(f"      '{result['metadata'].get('search_query', '')[:50]}...'")
            else:
                print(f"   Query not translated (already en/ru or close language)")

            print(f"   Response generated in: {result.get('language')}")

            print("\n   Result:")
            response_text = result['response']
            print(f"   {response_text[:500]}{'...' if len(response_text) > 500 else ''}")

            print(f"\n   Statistics:")
            print(f"   Sources: {len(result.get('sources', []))}")
            print(f"   Query language: {result['metadata'].get('detected_language')}")
            print(f"   Response language: {result.get('language')}")
            print(f"   Translated via groq: {'yes' if result['metadata'].get('query_was_translated') else 'no'}")
            print(f"   Tokens: {result['metadata'].get('total_tokens', 'N/A')}")
            print(f"   Time: {result['metadata'].get('processing_time', 'N/A'):.2f}s")

            if result['metadata'].get('translation_service'):
                print(f"   Translation service: {result['metadata'].get('translation_service')} (free)")

            if result.get('sources'):
                print(f"\n   Sources:")
                for i, source in enumerate(result['sources'][:5], 1):
                    print(f"      {i}. {source.name[:60]}")
                    print(f"         Location: {source.location}")
                    print(f"         Category: {source.category if hasattr(source, 'category') else 'N/A'}")
                    print(f"         Image: {'yes' if source.image_url else 'no'}")
                    if source.image_url:
                        print(f"         Url: {source.image_url[:60]}...")
                    print(f"         Score: {source.score:.3f}")

        else:
            print("\n   Real query test skipped")

        print("\nTest completed successfully!")

        print("\nExample queries in different languages:")
        print("   🇬🇧 en: Tell me about Tbilisi National Park")
        print("   🇷🇺 ru: Расскажи о Тбилисском национальном парке")
        print("   🇬🇪 ka: მითხარი თბილისის ეროვნული პარკის შესახებ")
        print("   🇰🇷 ko: 트빌리시 국립공원에 대해 알려주세요")
        print("   🇯🇵 ja: トビリシ国立公園について教えてください")
        print("   🇨🇳 zh: 告诉我关于第比利斯国家公园")
        print("   🇸🇦 ar: أخبرني عن حديقة تبليسي الوطنية")
        print("   🇩🇪 de: Erzählen Sie mir über den Nationalpark Tiflis")
        print("   🇫🇷 fr: Parlez-moi du parc national de Tbilissi")
        print("   🇪🇸 es: Cuéntame sobre el parque nacional de Tiflis")
        print("   🇮🇹 it: Parlami del parco nazionale di Tbilisi")
        print("   🇳🇱 nl: Vertel me over het nationale park van Tbilisi")
        print("   🇵🇱 pl: Opowiedz mi o parku narodowym w Tbilisi")
        print("   🇹🇷 tr: Tiflis milli parkı hakkında anlat")
        print("   🇦🇿 az: Tiflisdə milli parklar haqqında danış")

        return True

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_rag_simple())
    sys.exit(0 if success else 1)