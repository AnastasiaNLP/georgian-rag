# RAG Pipeline

Core Retrieval-Augmented Generation pipeline orchestrating the entire system.

## Files

### `rag.py`

**EnhancedGeorgianRAG** - Main RAG pipeline class.

## Architecture
```
User Query
    ↓
[1. Language Detection]
    ↓
[2. Query Analysis]
    ↓
[3. Hybrid Search] (BM25 + Dense + Filters)
    ↓
[4. Result Formatting]
    ↓
[5. Web Enrichment] (optional)
    ↓
[6. Image Collection]
    ↓
[7. LLM Response Generation] (Claude)
    ↓
[8. Conversation Context] (if multi-turn)
    ↓
Response
```

## Features

- **Hybrid search** - BM25 + Dense semantic search with RRF fusion
- **18 languages** - Auto-detection and multilingual support
- **Smart caching** - Multiple cache layers (query, search, translation)
- **Web enrichment** - Wikipedia, Unsplash (optional)
- **Conversation memory** - Redis-backed multi-turn dialogues
- **Comprehensive logging** - PostgreSQL + Prometheus metrics
- **Async/await** - Non-blocking operations
- **Error handling** - Graceful degradation

## Usage
```python
from pipeline.rag import EnhancedGeorgianRAG
from core.clients import get_qdrant_client
from search.HybridSearchEngine import HybridSearchEngine

# Initialize components
qdrant_client = get_qdrant_client()
hybrid_search = HybridSearchEngine(
    qdrant_client=qdrant_client,
    collection_name="georgian_attractions",
    embedding_model="paraphrase-multilingual-MiniLM-L12-v2"
)

# API keys
api_keys = {
    'anthropic_api_key': 'sk-ant-...',
    'groq_api_key': 'gsk_...',
    'langsmith_api_key': 'lsv2_...',
    'upstash_url': 'https://...',
    'upstash_token': 'AZCn...'
}

# Initialize RAG
rag = EnhancedGeorgianRAG(
    qdrant_system=qdrant_client,
    hybrid_search_integrator=hybrid_search,
    api_keys=api_keys,
    config={}
)

# Initialize all components
await rag.initialize()

# Query
result = await rag.answer_question(
    query="What are the best places in Tbilisi?",
    target_language="en",
    top_k=5,
    conversation_id="conv_123"  # optional
)
```

## Response Format
```python
{
    "response": "Here are the top attractions in Tbilisi...",
    "language": "en",
    "sources": [
        {
            "id": "abc123",
            "name": "Narikala Fortress",
            "location": "Tbilisi",
            "category": "Historical Site",
            "score": 0.95,
            "description": "Ancient fortress...",
            "image_url": "https://res.cloudinary.com/..."
        }
    ],
    "metadata": {
        "total_results": 5,
        "search_time": 0.523,
        "llm_time": 3.245,
        "total_time": 3.768,
        "language_detected": "en",
        "cache_used": False,
        "enrichment_applied": False,
        "conversation_context_used": False
    }
}
```

## Pipeline Stages

### 1. Language Detection
```python
# Auto-detect query language
detected_lang = self.multilingual.detect_language(query)
# Fallback to target_language if specified
```

**Supported:** 18 languages with auto-detection

### 2. Query Analysis
```python
# Analyze query intent and extract entities
analysis = self.hybrid_search.analyze_query(
    query=query,
    language=detected_lang
)
```

**Returns:** QueryAnalysis with:
- intent_type (factual, exploratory, etc.)
- entities (locations, categories)
- keywords (for BM25)
- semantic_query (for dense search)
- suggested_weights (BM25/dense/metadata)

### 3. Hybrid Search
```python
# Multi-stage search
search_results = await self.hybrid_search.search(
    query=query,
    top_k=top_k,
    query_analysis=analysis
)
```

**Three components:**
- **BM25Search** - Keyword matching
- **DenseSearch** - Semantic similarity
- **RRFFusion** - Reciprocal Rank Fusion

**Returns:** Ranked results with scores

### 4. Result Formatting
```python
formatted = self._format_search_results(search_results)
```

**Extracts:**
- name, description, category, location
- image_url (Cloudinary)
- relevance score
- Additional metadata

### 5. Web Enrichment (Optional)
```python
if self.web_enrichment:
    enrichment = await self.web_enrichment.enrich_content(
        search_results, 
        analysis
    )
```

**Adds:**
- Wikipedia descriptions
- Unsplash images
- SerpAPI practical info

**Status:** Currently disabled

### 6. Image Collection
```python
images = self._collect_images(
    search_results, 
    enrichment
)
```

**Sources:**
- Database (Cloudinary URLs)
- Enrichment (Wikipedia, Unsplash)

**Priority:** Database images first

### 7. LLM Response Generation
```python
result = await self.response_generator.generate_response({
    "query_info": analysis,
    "search_results": formatted_results,
    "enrichment": enrichment,
    "images": images
})
```

**LLM:** Claude Sonnet 4 (AsyncAnthropic)
**Features:**
- Direct multilingual generation
- Optimized prompts
- 4 intent-based templates
- max_tokens=800

### 8. Conversation Context (Optional)
```python
if conversation_id and self.conversation_manager:
    # Get history
    context = self.conversation_manager.get_context_window(
        conversation_id, 
        max_tokens=2000
    )
    
    # Add messages
    self.conversation_manager.add_message(
        conversation_id, 
        role="user", 
        content=query
    )
    self.conversation_manager.add_message(
        conversation_id, 
        role="assistant", 
        content=response
    )
```

## Components Initialized

**Core:**
- `qdrant_system` - Vector database client
- `hybrid_search` - Hybrid search engine
- `multilingual` - Language manager (Groq)

**Optional:**
- `conversation_manager` - Redis/in-memory (if Redis available)
- `web_enrichment` - Web enrichment engine (currently disabled)
- `disclaimer_manager` - Disclaimer system

**Always:**
- `response_generator` - Claude API (EnhancedResponseGenerator)
- `prometheus_exporter` - Metrics tracking
- `postgres_logger` - Request logging (if PostgreSQL available)

## Caching Layers

**Multiple cache levels:**

1. **Query cache** (in-memory, FastAPI level)
   - Key: (query, language, top_k)
   - TTL: Session-based
   - Hit rate: ~75%

2. **Search cache** (HybridSearchEngine)
   - BM25 cache
   - Dense cache
   - TTL: 24 hours

3. **Translation cache** (MultilingualManager)
   - Groq translations
   - TTL: 24 hours (temp), permanent (system)

## Logging & Monitoring

**PostgreSQL logging:**
```python
self.postgres_logger.log_request(
    query=query,
    language=target_language,
    response=result['response'],
    num_sources=len(result['sources']),
    duration_total=total_time,
    duration_search=search_time,
    duration_llm=llm_time,
    status="success",
    cache_hit=cache_hit
)
```

**Prometheus metrics:**
```python
self.prometheus.track_request(
    duration=total_time,
    language=target_language,
    status="success",
    cache_hit=cache_hit
)
```

## Error Handling

**Graceful degradation:**
```python
try:
    result = await self.answer_question(...)
except SearchError as e:
    # Return error with fallback message
    return {
        "response": error_message,
        "error": str(e),
        "sources": []
    }
except Exception as e:
    # Log and return generic error
    logger.error(f"Pipeline error: {e}")
    return fallback_response
```

**Monitored by:**
- Prometheus alerts
- PostgreSQL error logging
- Telegram notifications (via Alertmanager)

## Performance

**Typical timings:**

- Language detection: < 0.01s
- Query analysis: ~0.05s
- Hybrid search: ~0.5-1s
  - BM25: ~0.15s
  - Dense: ~0.3-0.5s
  - RRF fusion: ~0.05s
- LLM generation: ~2-5s
- **Total (uncached):** ~3-7s
- **Total (cached):** ~0.001s

**Bottlenecks:**
- Dense search (embedding)
- LLM API call (Claude)

**Optimizations:**
- Async operations
- Caching at multiple levels
- Batching where possible
- Connection pooling

## Configuration

**From `config/settings.py`:**
```python
# Qdrant
qdrant.url
qdrant.collection_name

# Embedding
embedding.model_name
embedding.vector_size

# Claude
claude.api_key
claude.model

# Groq
groq.api_key

# Redis (optional)
redis.url
redis.token

# Search
search.max_results
search.use_hybrid
search.dense_weight
search.bm25_weight
```

## Integration

**Used by:**

- `fastapi_dashboard.py` - Main API endpoint
- Direct Python usage (scripts, notebooks)

**Uses:**
- `search/HybridSearchEngine.py` - Search
- `llm/generator.py` - Response generation
- `multilingual/multilingual_manager.py` - Languages
- `conversation/manager.py` - Conversations
- `core/clients.py` - Qdrant, Cloudinary
- `utils/*` - Logging, monitoring, caching

## Initialization

**Two-stage init:**
```python
# Stage 1: Create instance
rag = EnhancedGeorgianRAG(...)

# Stage 2: Initialize components (async)
success = await rag.initialize()
```

**Initialization checks:**
- Qdrant connection
- Redis availability (optional)
- API key validation
- Component initialization

**Startup time:** ~2-5 seconds

## Multi-turn Conversations

**Enable conversation context:**
```python
# First message
result1 = await rag.answer_question(
    query="Tell me about Tbilisi",
    conversation_id="conv_abc123"
)

# Follow-up (uses context)
result2 = await rag.answer_question(
    query="What about nearby attractions?",
    conversation_id="conv_abc123"  # Same ID
)
```

**Context window:** Max 2000 tokens (~8000 chars)

**History limit:** Last 20 messages

**TTL:** 24 hours

## Advanced Features

### Custom Weights
```python
# Override search weights
result = await rag.answer_question(
    query="...",
    weights={
        'bm25': 0.5,
        'dense': 0.4,
        'metadata': 0.1
    }
)
```

### Filters
```python
# Category filter
result = await rag.answer_question(
    query="...",
    filters={"category": "Historical Site"}
)
```

### Debug Mode
```python
# Get detailed debug info
rag.debug = True
result = await rag.answer_question(...)
# result['debug'] contains timing breakdown
```

## Testing

**Unit tests:** `tests/test_rag_simple.py`

**Integration tests:** `tests/test_all_components.py`

**Run tests:**
```bash
pytest tests/test_rag_simple.py -v
```

## Notes

- Main orchestrator of entire RAG system
- All async operations for performance
- Graceful degradation on component failures
- Comprehensive logging and monitoring
- Production-ready error handling
- Multi-language support (18 languages)
- Optimized for Georgian tourism domain
