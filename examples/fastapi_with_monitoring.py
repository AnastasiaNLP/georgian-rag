"""
Georgian RAG FastAPI with Production Monitoring

Features:
- Prometheus metrics endpoint
- PostgreSQL logging
- Request tracking
- Error monitoring
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import time
import os
from dotenv import load_dotenv

# loading .env
load_dotenv()

# monitoring Imports
from utils.prometheus_exporter import (
    track_request,
    track_cache_hit,
    track_cache_miss,
    get_metrics,
    get_metrics_summary,
    ERROR_COUNT
)

from utils.postgres_logger import PostgreSQLLogger

# RAG system imports
from core.clients import get_qdrant_client
from config.settings import settings
from rag.RAGPipeline import RAGPipeline

# config
app = FastAPI(
    title="Georgian RAG API with Monitoring",
    description="RAG system with Prometheus and PostgreSQL monitoring",
    version="2.0.0"
)

# cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PostgreSQL Logger
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://raguser:ragpassword@localhost:5432/georgian_rag")
ENABLE_POSTGRES = os.getenv("ENABLE_POSTGRES_LOGGING", "true").lower() == "true"

if ENABLE_POSTGRES:
    try:
        postgres_logger = PostgreSQLLogger(POSTGRES_URL)
        print("PostgreSQL logger initialized")
    except Exception as e:
        print(f"PostgreSQL logger failed: {e}")
        postgres_logger = None
else:
    postgres_logger = None

# RAG Pipeline
rag_pipeline = None

# models
class QueryRequest(BaseModel):
    query: str
    language: str = "en"
    top_k: int = 5


class Source(BaseModel):
    name: str
    location: str
    category: str
    score: float
    image_url: Optional[str] = None
    has_image: bool = False


class QueryResponse(BaseModel):
    response: str
    language: str
    sources: List[Source]
    metadata: dict

# startup

@app.on_event("startup")
async def startup_event():
    """Initialization at startup"""
    global rag_pipeline
    print("STARTING GEORGIAN RAG API")
    # RAG initialization
    try:
        client = get_qdrant_client()
        rag_pipeline = RAGPipeline(
            qdrant_client=client,
            collection_name=settings.qdrant.collection_name,
            llm_api_key=settings.groq.api_key,
            embedding_model=settings.embedding.model_name
        )
        print("RAG Pipeline initialized")
    except Exception as e:
        print(f"RAG Pipeline initialization failed: {e}")
        raise

    print("\n Monitoring:")
    print(f"   Prometheus: http://localhost:9090")
    print(f"   Grafana: http://localhost:3000")
    print(f"   Metrics endpoint: http://localhost:8000/metrics")

    if postgres_logger:
        print(f"   PostgreSQL: Enabled")
    else:
        print(f"   PostgreSQL: Disabled")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("\n Shutting down Georgian RAG API...")

# request Tracking

@app.middleware("http")
async def track_requests_middleware(request: Request, call_next):
    """Middleware for tracking all requests"""
    start_time = time.time()

    # request processing
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # logging in PostgreSQL (/query only)
        if postgres_logger and request.url.path == "/query":
            # logging occurs within the endpoint
            pass

        return response

    except Exception as e:
        duration = time.time() - start_time
        ERROR_COUNT.labels(error_type=type(e).__name__).inc()
        raise

# endpoints

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "healthy",
        "service": "Georgian RAG API",
        "version": "2.0.0",
        "monitoring": {
            "prometheus": "http://localhost:9090",
            "grafana": "http://localhost:3000",
            "metrics": "http://localhost:8000/metrics"
        }
    }


@app.get("/health")
async def health():
    """Detailed health check"""

    health_status = {
        "status": "healthy",
        "components": {
            "rag_pipeline": rag_pipeline is not None,
            "postgres_logger": postgres_logger is not None,
            "prometheus": True
        }
    }

    # checking Qdrant
    try:
        client = get_qdrant_client()
        collection = client.get_collection(settings.qdrant.collection_name)
        health_status["components"]["qdrant"] = True
        health_status["qdrant_points"] = collection.points_count
    except:
        health_status["components"]["qdrant"] = False
        health_status["status"] = "degraded"

    return health_status


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    Exports metrics in Prometheus format
    """
    metrics_data = get_metrics()
    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4"
    )


@app.get("/metrics/summary")
async def metrics_summary():
    """
    Readable metrics summary (for debugging)
    """
    return get_metrics_summary()


@app.post("/query", response_model=QueryResponse)
@track_request(endpoint="query")
async def query(request: QueryRequest):
    """
    Primary endpoint for RAG requests
    With full monitoring and logging
    """
    start_time = time.time()

    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG Pipeline not initialized")

    try:
        # we execute a RAG query
        result = rag_pipeline.query(
            query=request.query,
            language=request.language,
            top_k=request.top_k
        )

        duration = time.time() - start_time

        # forming a response
        sources = []
        for source in result.get('sources', []):
            sources.append(Source(
                name=source.name,
                location=source.location,
                category=getattr(source, 'category', 'N/A'),
                score=source.score,
                image_url=getattr(source, 'image_url', None),
                has_image=bool(getattr(source, 'image_url', None))
            ))

        response_data = QueryResponse(
            response=result['response'],
            language=request.language,
            sources=sources,
            metadata={
                'duration': round(duration, 2),
                'num_sources': len(sources),
                'timestamp': time.time()
            }
        )

        # logging in PostgreSQL
        if postgres_logger:
            try:
                postgres_logger.log_request(
                    query=request.query,
                    language=request.language,
                    response=result['response'],
                    num_sources=len(sources),
                    duration_total=duration,
                    status='success',
                    top_k=request.top_k
                )
            except Exception as e:
                print(f"PostgreSQL logging failed: {e}")

        return response_data

    except Exception as e:
        duration = time.time() - start_time

        # logging the error
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

        ERROR_COUNT.labels(error_type=type(e).__name__).inc()

        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@app.get("/stats")
async def stats():
    """
    statistics from PostgreSQL
    """
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

# main

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )