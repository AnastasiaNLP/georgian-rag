"""
Georgian RAG FastAPI with Production Monitoring
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from contextlib import asynccontextmanager
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Monitoring imports
try:
    from utils.prometheus_exporter import (
        get_metrics,
        ERROR_COUNT,
        REQUEST_COUNT,
        REQUEST_DURATION,
        RESPONSE_LENGTH
    )
    PROMETHEUS_AVAILABLE = True
    print("Prometheus metrics imported successfully")
except ImportError as e:
    print(f"Prometheus exporter not available: {e}")
    PROMETHEUS_AVAILABLE = False
    # Create dummy metrics to avoid errors
    class DummyMetric:
        def labels(self, **kwargs):
            return self
        def inc(self): pass
        def observe(self, value): pass

    REQUEST_COUNT = DummyMetric()
    REQUEST_DURATION = DummyMetric()
    RESPONSE_LENGTH = DummyMetric()
    ERROR_COUNT = DummyMetric()

try:
    from utils.postgres_logger import PostgreSQLLogger
    postgres_logger = PostgreSQLLogger(
        os.getenv("POSTGRES_URL", "postgresql://raguser:ragpassword@localhost:5432/georgian_rag")
    ) if os.getenv("ENABLE_POSTGRES_LOGGING", "true").lower() == "true" else None
    if postgres_logger:
        print("PostgreSQL logger initialized")
except:
    postgres_logger = None

# core imports
from core.clients import get_qdrant_client
from config.settings import settings
from pipeline.rag import EnhancedGeorgianRAG
from api.models import Source

# models
class QueryRequest(BaseModel):
    query: str
    language: str = "en"
    top_k: int = 5

# source is imported from api.models

class QueryResponse(BaseModel):
    response: str
    language: str
    sources: List[Source]
    metadata: dict

# global state
rag_pipeline = None
query_cache = {}  # simple in-memory cache: {(query, language): result}

# lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan management"""
    global rag_pipeline  # noqa: PLW0603
    print("Starting Georgian RAG Api")

    try:
        print("Initializing components...")

        # api keys
        api_keys = {
            'anthropic_api_key': settings.claude.api_key,
            'groq_api_key': settings.groq.api_key,
            'langsmith_api_key': os.getenv('LANGSMITH_API_KEY', ''),
            'google_translate_api_key': os.getenv('GOOGLE_TRANSLATE_API_KEY', ''),
            'unsplash_access_key': os.getenv('UNSPLASH_ACCESS_KEY', ''),
            'serpapi_api_key': os.getenv('SERPAPI_API_KEY', ''),
            'upstash_url': os.getenv('UPSTASH_REDIS_REST_URL') or os.getenv('UPSTASH_REDIS_URL', ''),
            'upstash_token': os.getenv('UPSTASH_REDIS_REST_TOKEN') or os.getenv('UPSTASH_REDIS_TOKEN', ''),
            'redis_url': os.getenv('REDIS_URL', '')
        }

        # config
        rag_config = {
            'collection_name': settings.qdrant.collection_name,
            'embedding_model': settings.embedding.model_name
        }

        # get Qdrant client
        qdrant_client = get_qdrant_client()
        print("Qdrant client ready")

        # initialize components
        qdrant_system = None
        hybrid_search = None
        disclaimer_manager = None

        # qdrant system - doesn't exist as separate class, using None
        print("QdrantSystem not found (using None)")

        # HybridSearchEngine
        try:
            from search.HybridSearchEngine import HybridSearchEngine
            hybrid_search = HybridSearchEngine(
                qdrant_client=qdrant_client,
                collection_name=rag_config['collection_name'],
                embedding_model=rag_config['embedding_model']
            )
            print("HybridSearchEngine initialized")
        except Exception as e:
            print(f"HybridSearchEngine failed: {e}")
            import traceback
            traceback.print_exc()

        # DisclaimerManager
        try:
            from utils.disclaimer import DisclaimerManager
            disclaimer_manager = DisclaimerManager()
            print("DisclaimerManager initialized")
        except Exception as e:
            print(f"DisclaimerManager failed: {e}")

        print("\n Creating EnhancedGeorgianRAG...")

        # create RAG with components
        rag_pipeline = EnhancedGeorgianRAG(
            qdrant_system=qdrant_system,  # None
            hybrid_search_integrator=hybrid_search,
            disclaimer_manager=disclaimer_manager,
            api_keys=api_keys,
            config=rag_config
        )

        print("Initializing RAG pipeline...")
        success = await rag_pipeline.initialize()

        if success:
            print("EnhancedGeorgianRAG fully initialized!")
        else:
            print(" EnhancedGeorgianRAG initialization incomplete")
            print("\n Component status:")
            print(f"   multilingual_manager: {bool(rag_pipeline.multilingual_manager)}")
            print(f"   context_assembler: {bool(rag_pipeline.context_assembler)}")
            print(f"   response_generator: {bool(rag_pipeline.response_generator)}")
            print(f"   conversation_manager: {bool(rag_pipeline.conversation_manager)}")
            print(f"   hybrid_search: {bool(rag_pipeline.hybrid_search)}")

    except Exception as e:
        print(f" Initialization failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n Final Status:")
    print(f"   RAG Pipeline: {'✓' if rag_pipeline else '✗'}")
    print(f"   Initialized: {'✓' if rag_pipeline and getattr(rag_pipeline, 'is_initialized', False) else '✗'}")
    print(f"   PostgreSQL: {'✓' if postgres_logger else '✗'}")
    print(f"   Prometheus: {'✓' if PROMETHEUS_AVAILABLE else '✗'}")

    if rag_pipeline:
        print("\n Loaded Components:")
        print(f"   QdrantSystem: {bool(qdrant_system)}")
        print(f"   HybridSearch: {bool(hybrid_search)}")
        print(f"   DisclaimerManager: {bool(disclaimer_manager)}")

    yield

    print("\n🛑 Shutting down...")

#app
app = FastAPI(
    title="Georgian RAG API",
    description="RAG система для грузинских достопримечательностей",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# endpoints
@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Georgian RAG API",
        "version": "2.0.0",
        "rag_available": rag_pipeline is not None,
        "rag_initialized": getattr(rag_pipeline, 'is_initialized', False) if rag_pipeline else False
    }

@app.get("/health")
async def health():
    health_status = {
        "status": "healthy",
        "components": {
            "rag_pipeline": rag_pipeline is not None,
            "rag_initialized": getattr(rag_pipeline, 'is_initialized', False) if rag_pipeline else False,
            "postgres": postgres_logger is not None,
            "prometheus": PROMETHEUS_AVAILABLE
        }
    }

    try:
        client = get_qdrant_client()
        collection = client.get_collection(settings.qdrant.collection_name)
        health_status["components"]["qdrant"] = True
        health_status["qdrant_points"] = collection.points_count
    except Exception as e:
        health_status["components"]["qdrant"] = False
        health_status["error"] = str(e)

    return health_status

@app.get("/metrics")
async def metrics():
    if not PROMETHEUS_AVAILABLE:
        return Response(content="# Metrics not available\n", media_type="text/plain")
    return Response(content=get_metrics(), media_type="text/plain")

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    start_time = time.time()

    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG Pipeline not available")

    if not getattr(rag_pipeline, 'is_initialized', False):
        raise HTTPException(status_code=503, detail="RAG Pipeline not fully initialized")

    try:
        #convert empty string to None for auto-detection
        target_lang = request.language if request.language else None

        # simple cache key
        cache_key = (request.query.lower().strip(), target_lang or 'auto', request.top_k)
        cache_hit = False

        # Check cache
        if cache_key in query_cache:
            print(f"CACHE HIT for query: {request.query[:50]}...")
            result = query_cache[cache_key]
            cache_hit = True
        else:
            print(f" CACHE MISS for query: {request.query[:50]}...")
            result = await rag_pipeline.answer_question(
                query=request.query,
                target_language=target_lang,
                top_k=request.top_k
            )
            # store in cache (limit cache size to 100 entries)
            if len(query_cache) > 100:
                # remove oldest entry (simple FIFO)
                query_cache.pop(next(iter(query_cache)))
            query_cache[cache_key] = result

        duration = time.time() - start_time

        if result.get('error'):
            raise HTTPException(status_code=500, detail=result.get('response', 'Unknown error'))

        # sources are already api.models
        sources = result.get('sources', [])

        response_data = QueryResponse(
            response=result['response'],
            language=request.language,
            sources=sources,
            metadata={
                'duration': round(duration, 2),
                'num_sources': len(sources),
                'timestamp': time.time(),
                **result.get('metadata', {})
            }
        )

        if postgres_logger:
            try:
                postgres_logger.log_request(
                    query=request.query,
                    language=request.language,
                    response=result['response'],
                    num_sources=len(sources),
                    duration_total=duration,
                    status='success',
                    top_k=request.top_k,
                    cache_hit=cache_hit
                )
            except Exception as e:
                print(f"  PostgreSQL logging failed: {e}")

        # track Prometheus metrics
        if PROMETHEUS_AVAILABLE:
            try:
                # track request
                REQUEST_COUNT.labels(
                    endpoint='query',
                    language=target_lang or 'auto',
                    status='success'
                ).inc()

                # track duration
                REQUEST_DURATION.labels(
                    endpoint='query',
                    language=target_lang or 'auto'
                ).observe(duration)

                # track response length
                RESPONSE_LENGTH.observe(len(result['response']))

                print(f"Prometheus metrics recorded: duration={duration:.2f}s, length={len(result['response'])}")
            except Exception as e:
                print(f"Prometheus tracking failed: {e}")
                import traceback
                traceback.print_exc()

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time

        if postgres_logger:
            try:
                postgres_logger.log_request(
                    query=request.query,
                    language=request.language,
                    duration_total=duration,
                    status='error',
                    error_message=str(e),
                    error_type=type(e).__name__,
                    top_k=request.top_k
                )
            except:
                pass

        if PROMETHEUS_AVAILABLE:
            try:
                ERROR_COUNT.labels(error_type=type(e).__name__).inc()
            except:
                pass

        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/stats")
async def stats():
    if not postgres_logger:
        return {"error": "PostgreSQL logging disabled"}
    try:
        recent = postgres_logger.get_recent_requests(limit=10)
        perf_stats = postgres_logger.get_performance_stats(hours=24)
        errors = postgres_logger.get_error_summary(hours=24)
        return {
            "recent_requests": recent,
            "performance_24h": perf_stats,
            "errors_24h": errors
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/system-status")
async def system_status():
    if not rag_pipeline:
        return {"error": "RAG pipeline not available"}
    try:
        return rag_pipeline.get_system_status()
    except Exception as e:
        return {"error": str(e)}
# main
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    print(f"\n Starting server on {host}:{port}")

    uvicorn.run(app, host=host, port=port, log_level="info")

