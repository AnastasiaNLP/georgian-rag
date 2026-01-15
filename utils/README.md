# Utilities

Comprehensive utility modules for caching, logging, monitoring, and system operations.

## Files Overview

### Caching & Performance

- **CacheManager.py** - Two-level cache system (temporary + permanent)
- **cache_warmup.py** - Cache preloading for popular queries
- **model_manager.py** - Embedding model caching

### Monitoring & Logging

- **prometheus_exporter.py** - Prometheus metrics export
- **postgres_logger.py** - PostgreSQL request logging
- **logger_setup.py** - Logging configuration
- **performance_monitoring.py** - Performance tracking & bottleneck detection
- **performance_dashboard.py** - HTML visualization & reporting

### Search & Data

- **adapter.py** - Data adapter for hybrid search
- **integrator.py** - HybridSearch wrapper (backward compatibility)
- **disclaimer.py** - Multilingual disclaimers (18 languages)

### Background Tasks

- **background_queue.py** - Async task queue for Qdrant updates

---

## Detailed Documentation

### CacheManager.py

**Two-level caching system** with temporary and permanent storage.

**Features:**
- **Temporary cache** - TTL-based (24h default)
- **Permanent cache** - No expiration
- **Redis-first** - With in-memory fallback
- **Namespace support** - Organize by category
- **Statistics tracking** - Hit rates, usage

**Usage:**
```python
from utils.CacheManager import CacheManager
from core.clients import get_redis_client

# Initialize
redis = get_redis_client()
cache = CacheManager(redis_client=redis)

# Temporary cache (24h TTL)
cache.set('temp', 'query_123', result_data)
cached = cache.get('temp', 'query_123')

# Permanent cache (no TTL)
cache.set_permanent('perm', 'lang_instruction_ru', instruction)
cached = cache.get('perm', 'lang_instruction_ru')

# Statistics
stats = cache.get_stats('temp')
# Returns: {hits, misses, hit_rate, size}
```

**Cache Namespaces:**

- `query:*` - Query results
- `bm25:*` - BM25 search cache
- `dense:*` - Dense search cache
- `translation:*` - Translation cache
- `enrichment:permanent` - Web enrichment (permanent)
- `embedding:*` - Embedding vectors

**Performance:**
- Redis get: < 5ms
- In-memory get: < 0.1ms
- Typical hit rate: 70-90%

---

### cache_warmup.py

**Cache preloading system** for popular queries.

**Features:**
- **Embedding model** warmup
- **BM25 cache** preloading
- **Dense search** cache
- **Hybrid search** results
- **PreFilter** cache
- **Popular queries** list

**Usage:**
```python
from utils.cache_warmup import CacheWarmup

# Initialize
warmup = CacheWarmup(
    rag_pipeline=rag,
    popular_queries_file='popular_queries.json'
)

# Warm up all caches
await warmup.warm_all_caches()

# Warm specific cache
await warmup.warm_embedding_cache()
await warmup.warm_bm25_cache()
await warmup.warm_dense_cache()
```

**Popular Queries Format:**
```json
{
  "queries": [
    {"query": "Tbilisi attractions", "language": "en", "priority": 1},
    {"query": "Батуми отели", "language": "ru", "priority": 2}
  ]
}
```

**Benefits:**
- Faster first queries
- Reduced API calls
- Better user experience
- Lower latency

**Typical Warmup Time:**
- 10 queries: ~30 seconds
- 50 queries: ~2 minutes
- 100 queries: ~4 minutes

---

### model_manager.py

**Embedding model caching** and lazy loading.

**Features:**
- **Lazy initialization** - Load on first use
- **Model caching** - Reuse instances
- **Device management** - CPU/CUDA
- **Memory optimization** - Shared instances

**Usage:**
```python
from utils.model_manager import ModelManager

# Initialize
manager = ModelManager()

# Get model (lazy load)
model = manager.get_model(
    model_name='paraphrase-multilingual-MiniLM-L12-v2',
    device='cpu'
)

# Encode
embeddings = model.encode(["query text"])

# Statistics
stats = manager.get_stats()
# Returns: {models_loaded, cache_hits, total_requests}
```

**Supported Models:**
- `paraphrase-multilingual-MiniLM-L12-v2` (384d)
- `sentence-transformers/all-MiniLM-L6-v2` (384d)
- Custom SentenceTransformer models

**Memory Usage:**
- Model size: ~120MB (MiniLM)
- Singleton pattern: 1 instance per model
- GPU memory: ~500MB (if CUDA)

---

### prometheus_exporter.py

**Prometheus metrics exporter** for monitoring.

**Features:**
- **Request counter** - Total requests by status
- **Duration histogram** - Response time percentiles
- **Cache metrics** - Hit/miss counters
- **Error counter** - Errors by type
- **Active requests** - Current concurrent requests

**Usage:**
```python
from utils.prometheus_exporter import PrometheusExporter

# Initialize
exporter = PrometheusExporter()

# Track request
exporter.track_request(
    duration=2.5,
    status='success',
    language='en',
    cache_hit=True
)

# Track error
exporter.track_error('search_error')

# Get metrics (for /metrics endpoint)
metrics = exporter.get_metrics()
```

**Exported Metrics:**
```promql
# Request counter
rag_requests_total{status="success",language="en"} 150

# Response time histogram
rag_request_duration_seconds_bucket{le="1.0"} 80
rag_request_duration_seconds_bucket{le="5.0"} 140
rag_request_duration_seconds_bucket{le="10.0"} 148

# Cache metrics
rag_cache_hits_total{cache="bm25"} 120
rag_cache_misses_total{cache="bm25"} 30

# Errors
rag_errors_total{error_type="search_error"} 5

# Active requests
rag_active_requests 3
```

**Integration:**
- FastAPI `/metrics` endpoint
- Scraped by Prometheus every 15s
- Visualized in Grafana

---

### postgres_logger.py

**PostgreSQL request logger** for long-term analytics.

**Features:**
- **Full request logging** - Query, response, metadata
- **Performance metrics** - Duration breakdown
- **Cache tracking** - Hit/miss status
- **Error logging** - Stack traces
- **Async logging** - Non-blocking

**Usage:**
```python
from utils.postgres_logger import PostgresLogger

# Initialize
logger = PostgresLogger(
    connection_url="postgresql://user:pass@localhost:5432/db"
)

# Log request
logger.log_request(
    query="What to see in Tbilisi?",
    language="en",
    response="Here are top attractions...",
    num_sources=5,
    duration_total=3.5,
    duration_search=0.8,
    duration_llm=2.5,
    status="success",
    cache_hit=False
)

# Log error
logger.log_error(
    query="...",
    error_message="Connection timeout",
    error_type="TimeoutError"
)
```

**Database Schema:**
```sql
CREATE TABLE request_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    query TEXT NOT NULL,
    language VARCHAR(10),
    response TEXT,
    num_sources INTEGER,
    duration_total FLOAT,
    duration_search FLOAT,
    duration_llm FLOAT,
    status VARCHAR(20),
    error_message TEXT,
    error_type VARCHAR(100),
    cache_hit BOOLEAN DEFAULT FALSE,
    top_k INTEGER,
    model_used VARCHAR(50),
    total_tokens INTEGER
);
```

**Queries:**
```sql
-- Average response time
SELECT AVG(duration_total) FROM request_logs 
WHERE timestamp > NOW() - INTERVAL '24 hours';

-- Cache hit rate
SELECT 
  COUNT(*) FILTER (WHERE cache_hit) * 100.0 / COUNT(*) 
FROM request_logs;

-- Errors
SELECT error_type, COUNT(*) 
FROM request_logs 
WHERE status = 'error' 
GROUP BY error_type;
```

---

### logger_setup.py

**Centralized logging configuration.**

**Features:**
- **Colored output** - Easy reading
- **File rotation** - 10MB per file, 5 backups
- **Multiple levels** - DEBUG, INFO, WARNING, ERROR
- **Structured format** - Timestamp, module, level, message

**Usage:**
```python
from utils.logger_setup import setup_logging

# Setup logging
setup_logging(level='INFO')

# Use logger
import logging
logger = logging.getLogger(__name__)

logger.info("System started")
logger.warning("Cache miss")
logger.error("API call failed")
```

**Configuration:**
```python
LOG_LEVEL='INFO'  # From .env
LOG_FILE='logs/georgian_rag.log'
MAX_BYTES=10485760  # 10MB
BACKUP_COUNT=5
```

**Log Format:**
```
2026-01-10 14:30:15,123 - pipeline.rag - INFO - RAG initialized successfully
2026-01-10 14:30:20,456 - search.dense - WARNING - Dense cache miss for query
2026-01-10 14:30:25,789 - llm.generator - ERROR - Claude API timeout
```

---

### performance_monitoring.py

**Performance tracking and bottleneck detection.**

**Features:**
- **Component timing** - Track every stage
- **Bottleneck detection** - Identify slow components
- **Trend analysis** - Performance over time
- **Anomaly detection** - Unusual slowdowns
- **Degradation alerts** - Performance decline

**Usage:**
```python
from utils.performance_monitoring import PerformanceMonitor

# Initialize
monitor = PerformanceMonitor()

# Track component
with monitor.track('query_analysis'):
    analysis = analyzer.analyze(query)

with monitor.track('bm25_search'):
    results = bm25.search(query)

# Get report
report = monitor.get_report()
# Returns: {
#   'query_analysis': {'avg': 0.05, 'calls': 10, 'total': 0.5},
#   'bm25_search': {'avg': 0.15, 'calls': 10, 'total': 1.5}
# }

# Detect bottlenecks
bottlenecks = monitor.detect_bottlenecks(threshold=1.0)
# Returns: [{'component': 'dense_search', 'avg_time': 0.95, 'severity': 30}]
```

**Tracked Components:**
- QueryAnalysis
- PreFilter
- BM25Search
- DenseSearch
- RRFFusion
- LLMGeneration
- RAG_FullPipeline

**Metrics:**
- Average time
- Total time
- Call count
- Trend (improving/stable/degrading)
- Percentiles (50th, 95th, 99th)

---

### performance_dashboard.py

**HTML dashboard generator** for performance visualization.

**Features:**
- **HTML reports** - Visual dashboards
- **Charts & graphs** - Performance trends
- **Export options** - JSON, CSV
- **Comparison** - Between runs
- **Cache analytics** - Hit rates, efficiency

**Usage:**
```python
from utils.performance_dashboard import PerformanceDashboard

# Initialize
dashboard = PerformanceDashboard(monitor)

# Generate report
dashboard.generate_html_report('performance_report.html')

# Export data
dashboard.export_json('metrics.json')
dashboard.export_csv('metrics.csv')
```

**Report Sections:**
1. **System Health** - Overall status
2. **Key Metrics** - Total searches, avg time, cache hit rate
3. **Component Performance** - Timing breakdown
4. **Cache Statistics** - Hit rates by cache type
5. **Bottlenecks** - Slow components
6. **Recommendations** - Optimization suggestions

**Generated Files:**
- `performance_report.html` - Visual dashboard
- `performance_metrics.json` - Raw data
- `performance_metrics.csv` - Spreadsheet format

---

### adapter.py

**Data adapter** for hybrid search compatibility.

**Features:**
- **Format conversion** - Qdrant → SearchResult
- **Payload extraction** - Universal accessor
- **Score normalization** - Consistent scoring
- **Field mapping** - Old → New structure

**Usage:**
```python
from utils.adapter import GeorgianDataAdapter

# Initialize
adapter = GeorgianDataAdapter()

# Convert Qdrant results
search_results = adapter.adapt_results(
    qdrant_results,
    source='qdrant'
)

# Each result becomes SearchResult object:
# SearchResult(
#     doc_id='abc123',
#     score=0.95,
#     source='qdrant',
#     metadata={'name': '...', 'category': '...'},
#     content='...'
# )
```

**Supported Sources:**
- Qdrant vector search results
- BM25 search results
- Dense search results
- Legacy formats

---

### integrator.py

**HybridSearch wrapper** for backward compatibility.

**Features:**
- **Unified interface** - Single entry point
- **Backward compatible** - Legacy code support
- **Performance monitoring** - Built-in tracking
- **Error handling** - Graceful degradation

**Usage:**
```python
from utils.integrator import HybridSearchIntegrator

# Initialize
integrator = HybridSearchIntegrator(
    qdrant_client=qdrant,
    collection_name='georgian_attractions'
)

# Search
results = await integrator.search(
    query="Tbilisi attractions",
    top_k=5
)
```

**Note:** This is a compatibility wrapper. For new code, use `search.HybridSearchEngine` directly.

---

### disclaimer.py

**Multilingual disclaimer system** (18 languages).

**Features:**
- **18 languages** - Full multilingual support
- **Content detection** - Auto-detect disclaimer type
- **Smart placement** - Contextual disclaimers
- **Frequency control** - 100% for specific, 30% for general

**Usage:**
```python
from utils.disclaimer import DisclaimerManager

# Initialize
manager = DisclaimerManager()

# Add disclaimers (auto-detect language)
response_with_disclaimers = manager.add_disclaimers(
    answer="Visit from 9 AM to 6 PM. Entry costs 10 GEL.",
    language='en'
)
```

**Supported Languages:**

English (EN), Russian (RU), Georgian (KA), German (DE), French (FR), Spanish (ES), Italian (IT), Dutch (NL), Polish (PL), Czech (CS), Chinese (ZH), Japanese (JA), Korean (KO), Arabic (AR), Turkish (TR), Hindi (HI), Armenian (HY), Azerbaijani (AZ)

**Disclaimer Types:**

1. **price** - Price information
   - Keywords: price, cost, fee, free, лари, цена
   - Example: "⚠️ Prices may change. Verify before visiting."

2. **schedule** - Opening hours
   - Keywords: hours, schedule, open, closed, время работы
   - Example: "🕒 Hours may vary by season and holidays."

3. **seasonal** - Weather/season dependent
   - Keywords: winter, snow, mountain, hiking, зима, горы
   - Example: "🌨️ Mountain access depends on weather and season."

4. **transport** - Transportation info
   - Keywords: route, transport, bus, train, маршрут
   - Example: "🚌 Public transport routes may change."

5. **general** - Default disclaimer
   - Example: "🗺️ Information may be incomplete or outdated."

**Detection Logic:**
- Scans response for keywords
- Adds specific disclaimers (100%)
- Adds general disclaimer (30% if no specific)
- Combines multiple types if applicable

**Example Output:**
```
Response: "Visit Narikala Fortress from 9 AM to 6 PM. Entry is free."

With Disclaimers (EN):
Visit Narikala Fortress from 9 AM to 6 PM. Entry is free.

---

### ⚠️ Important Information:

⚠️ **Note**: Prices may change. Please verify current costs before visiting.

🕒 **Note**: Opening hours may vary by season and holidays. Please check current schedule.
```

**Same in Russian:**
```
### ⚠️ Важная информация:

⚠️ **Внимание**: Цены могут изменяться. Рекомендуем уточнить актуальную стоимость перед посещением.

🕒 **Примечание**: Время работы может изменяться в зависимости от сезона и праздников.
```

---

### background_queue.py

**Async task queue** for non-blocking operations.

**Features:**
- **Non-blocking** - Async execution
- **Queue management** - FIFO processing
- **Error handling** - Retry logic
- **Status tracking** - Task completion
- **Background updates** - Qdrant enrichment

**Usage:**
```python
from utils.background_queue import BackgroundQueue

# Initialize
queue = BackgroundQueue()

# Add task
task_id = await queue.add_task(
    func=update_qdrant_metadata,
    args=(doc_id, enrichment_data)
)

# Check status
status = queue.get_task_status(task_id)
# Returns: 'pending' | 'running' | 'completed' | 'failed'

# Wait for completion
await queue.wait_for_task(task_id)
```

**Use Cases:**
- Qdrant metadata updates
- Cache preloading
- Image processing
- External API calls
- Log aggregation

**Benefits:**
- User doesn't wait
- Better responsiveness
- Parallel processing
- Error isolation

---

## Integration

### FastAPI Application
```python
# In fastapi_dashboard.py

from utils.CacheManager import CacheManager
from utils.prometheus_exporter import PrometheusExporter
from utils.postgres_logger import PostgresLogger
from utils.performance_monitoring import PerformanceMonitor
from utils.disclaimer import DisclaimerManager

# Initialize utilities
cache_manager = CacheManager(redis_client)
prometheus = PrometheusExporter()
postgres_logger = PostgresLogger(db_url)
perf_monitor = PerformanceMonitor()
disclaimer_manager = DisclaimerManager()

# Use in request handler
@app.post("/query")
async def query(request: QueryRequest):
    with perf_monitor.track('full_request'):
        result = await rag.answer_question(...)
        
    # Add disclaimers
    result['response'] = disclaimer_manager.add_disclaimers(
        result['response'],
        language=request.target_language
    )
    
    # Log to PostgreSQL
    postgres_logger.log_request(...)
    
    # Track metrics
    prometheus.track_request(...)
    
    return result
```

### RAG Pipeline
```python
# In pipeline/rag.py

from utils.CacheManager import CacheManager
from utils.model_manager import ModelManager
from utils.disclaimer import DisclaimerManager

class EnhancedGeorgianRAG:
    def __init__(self, ...):
        self.cache_manager = CacheManager(redis)
        self.model_manager = ModelManager()
        self.disclaimer_manager = DisclaimerManager()
    
    async def answer_question(self, query, language):
        # Check cache
        cached = self.cache_manager.get('query', cache_key)
        if cached:
            return cached
        
        # Process query
        result = await self._process_query(query)
        
        # Add disclaimers
        result['response'] = self.disclaimer_manager.add_disclaimers(
            result['response'],
            language=language
        )
        
        # Cache result
        self.cache_manager.set('query', cache_key, result)
        
        return result
```

---

## Configuration

### Environment Variables
```bash
# Caching
REDIS_URL=redis://localhost:6379
CACHE_TTL=86400  # 24 hours

# Logging
LOG_LEVEL=INFO
POSTGRES_URL=postgresql://user:pass@localhost/db

# Monitoring
PROMETHEUS_PORT=9090
ENABLE_PERFORMANCE_MONITORING=true

# Models
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
DEVICE=cpu  # or 'cuda'
```

### Settings Integration
```python
from config.settings import settings

# All utilities use centralized config
cache = CacheManager(
    redis_client=redis,
    ttl=settings.redis.ttl
)

logger = PostgresLogger(
    connection_url=settings.postgres.url
)
```

---

## Performance Impact

### CacheManager
- **Hit time:** < 5ms (Redis) or < 0.1ms (memory)
- **Miss time:** + query time
- **Typical hit rate:** 70-90%
- **Speedup:** 100-1000x for cached queries

### Monitoring Overhead
- **Prometheus:** < 0.1ms per metric
- **PostgreSQL logging:** < 10ms (async)
- **Performance tracking:** < 0.5ms per component

### Total Overhead
- **Without monitoring:** 0ms
- **With full monitoring:** ~10-20ms (< 1% of total)

---

## Notes

- All utilities designed for production use
- Graceful degradation on failures
- Async-first where applicable
- Comprehensive error handling
- Thread-safe implementations
- Memory-efficient caching
- Minimal performance overhead
- Full test coverage available
