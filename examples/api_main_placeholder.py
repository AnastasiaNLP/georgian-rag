"""
FastAPI old application
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from typing import Optional

from api.models import (
    ChatRequest, ChatResponse, HealthResponse,
    StatsResponse, ClearCacheRequest, ErrorResponse,
    LanguageCode, Source
)

# will be initialized in lifespan
rag_system = None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global rag_system, hybrid_search, qdrant_client

    logger.info("Starting Georgian RAG API...")

    try:
        # initialize Qdrant client
        from core.clients import get_qdrant_client
        from config.settings import settings

        logger.info("Connecting to Qdrant...")
        qdrant_client = get_qdrant_client()
        logger.info("Qdrant connected")

        # initialize Hybrid Search
        from search.hybrid import HybridSearchEngine

        logger.info("Initializing Hybrid Search...")
        hybrid_search = HybridSearchEngine(
            qdrant_client=qdrant_client,
            collection_name=settings.qdrant.collection_name,
            embedding_model=settings.qdrant.embedding_model,
            config={}
        )
        logger.info("Hybrid Search initialized")

        # initialize RAG system
        from pipeline.rag import EnhancedGeorgianRAG

        logger.info("Initializing RAG system...")

        api_keys = {
            'anthropic_api_key': settings.anthropic_api_key,
            'langsmith_api_key': settings.langsmith_api_key,
            'google_translate_api_key': getattr(settings, 'google_translate_api_key', None),
            'unsplash_access_key': getattr(settings, 'unsplash_access_key', None),
            'serpapi_api_key': getattr(settings, 'serpapi_api_key', None),
            'redis_url': getattr(settings, 'redis_url', None),
            'upstash_url': getattr(settings, 'upstash_url', None),
            'upstash_token': getattr(settings, 'upstash_token', None),
        }

        rag_system = EnhancedGeorgianRAG(
            qdrant_system=qdrant_client,
            hybrid_search_integrator=hybrid_search,
            api_keys=api_keys,
            config={}
        )

        success = await rag_system.initialize()

        if success:
            logger.info("RAG system initialized successfully")
        else:
            logger.error("RAG system initialization failed")
            rag_system = None

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        import traceback
        traceback.print_exc()
        rag_system = None

    logger.info("Georgian RAG API started")

    yield

    logger.info("Shutting down Georgian RAG API...")
# create FastAPI app
app = FastAPI(
    title="Georgian Attractions RAG API",
    description="Semantic search and chat for Georgian attractions",
    version="1.0.0",
    lifespan=lifespan
)

# add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_rag_system():
    """Dependency to get RAG system"""
    if rag_system is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized")
    return rag_system


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Georgian Attractions RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    rag: Optional[object] = Depends(get_rag_system)
):
    """
    Main chat endpoint
    """
    try:
        # placeholder response
        return ChatResponse(
            response=f"Query received: {request.query}",
            language=request.target_language.value,
            sources=[],
            conversation_id=request.conversation_id,
            metadata={"status": "placeholder"}
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if rag_system else "initializing",
        timestamp=datetime.now(),
        components={
            "rag_system": "ready" if rag_system else "not_initialized"
        },
        initialized=rag_system is not None,
        warmed_up=False
    )


@app.get("/stats", response_model=StatsResponse)
async def stats():
    """System statistics"""
    return StatsResponse(
        cache_stats={},
        search_stats={},
        system_info={"status": "operational"}
    )


@app.post("/cache/clear")
async def clear_cache(request: ClearCacheRequest):
    """Clear cache"""
    return {"status": "ok", "message": "Cache clear requested"}


@app.get("/cache/stats")
async def cache_stats(namespace: Optional[str] = None):
    """Get cache statistics"""
    return {"namespace": namespace, "stats": {}}


@app.get("/languages")
async def languages():
    """List supported languages"""
    return {
        "languages": [
            {"code": lang.value, "name": lang.name}
            for lang in LanguageCode
        ]
    }


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket, client_id: str):
    """WebSocket endpoint"""
    await handle_websocket(websocket, client_id, rag_system)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(
        error="Internal server error",
        detail=str(exc),
        timestamp=datetime.now()
    )