# Core Components

Core infrastructure: client singletons, exceptions, and data types.

## Files

### `clients.py`

**Singleton clients** for external services.

**Functions:**

- `get_qdrant_client()` → QdrantClient
  - Singleton pattern (one instance)
  - Auto-connects to Qdrant Cloud
  - Validates collection exists
  - Logs connection details

- `initialize_cloudinary()` → None
  - Configures Cloudinary SDK
  - One-time initialization
  - Uses config from settings

- `is_cloudinary_ready()` → bool
  - Check if Cloudinary initialized

- `reset_clients()` → None
  - Reset singletons (for testing)

**Usage:**
```python
from core.clients import get_qdrant_client, initialize_cloudinary

# Get Qdrant client (auto-connects)
qdrant = get_qdrant_client()

# Initialize Cloudinary
initialize_cloudinary()
```

### `exceptions.py`

**Custom exception hierarchy** for Georgian RAG.

**Exception Tree:**
```
RAGException (base)
├── ConfigurationError    # Config/init issues
├── SearchError           # Search failures
├── EmbeddingError        # Embedding model issues
├── QdrantError           # Qdrant client issues
├── EnrichmentError       # Web enrichment failures
└── CacheError            # Cache operation failures
```

**Usage:**
```python
from core.exceptions import SearchError, QdrantError

try:
    results = search_engine.search(query)
except QdrantError as e:
    logger.error(f"Qdrant failed: {e}")
except SearchError as e:
    logger.error(f"Search failed: {e}")
```

### `types.py`

**Core data types** and constants.

**QueryType Enum:**

- `FACTUAL` - Specific facts (BM25-heavy: 70%)
- `EXPLORATORY` - Open exploration (Dense-heavy: 50%)
- `COMPARATIVE` - Comparing options (Balanced)
- `NAVIGATIONAL` - Finding specific places (BM25: 60%)
- `FILTERED` - Category/filter queries (Metadata: 30%)

**QueryAnalysis Dataclass:**

Analysis result from query analyzer:
```python
@dataclass
class QueryAnalysis:
    original_query: str           # User's query
    language: str                 # Detected language
    detected_language: str        # Language code
    intent_type: QueryType        # Query type
    entities: Dict[str, Any]      # Extracted entities
    query_complexity: str         # simple/medium/complex
    suggested_weights: Dict       # BM25/Dense weights
    enhanced_query: str           # Enhanced version
    implicit_filters: Dict        # Auto-detected filters
    semantic_query: str           # For dense search
    keywords: List[str]           # For BM25
    qdrant_filters: List          # Qdrant filter clauses
    filter_strategy: str          # strict/moderate/loose
    dense_query: str              # Dense search query
```

**SearchResult Dataclass:**

Individual search result:
```python
@dataclass
class SearchResult:
    doc_id: str                   # Document ID
    score: float                  # Relevance score
    source: str                   # Source component
    metadata: Dict[str, Any]      # Document metadata
    content: str                  # Content snippet
    
    # Properties
    id                            # Alias for doc_id
    payload                       # Alias for metadata
    
    # Methods
    get_payload_field(field, default)
    has_content() -> bool
    get_display_name() -> str
```

**WEIGHT_PROFILES:**

Query type → search component weights:
```python
WEIGHT_PROFILES = {
    QueryType.FACTUAL: {
        'bm25': 0.7,      # Strong keyword matching
        'dense': 0.2,     # Semantic understanding
        'metadata': 0.1   # Filters
    },
    QueryType.EXPLORATORY: {
        'bm25': 0.4,
        'dense': 0.5,     # Semantic emphasis
        'metadata': 0.1
    },
    # ... etc
}
```

**GEORGIAN_SYNONYMS:**

Georgian place name synonyms:
```python
GEORGIAN_SYNONYMS = {
    'тбилиси': ['tbilisi', 'тифлис', 'თბილისი'],
    'светицховели': ['svetitskhoveli', 'სვეტიცხოველი'],
    'церковь': ['храм', 'собор', 'монастырь', 'church'],
    'крепость': ['fortress', 'castle', 'ციხე'],
    # ... 10+ entries
}
```

## Design Patterns

### Singleton Pattern (clients.py)
```python
_qdrant_client = None  # Global singleton

def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(...)
    return _qdrant_client
```

Benefits:
- One connection for entire app
- Connection reuse
- Lazy initialization

### Dataclass Pattern (types.py)
```python
@dataclass
class SearchResult:
    doc_id: str
    score: float
    # ...
```

Benefits:
- Type hints
- Auto __init__, __repr__
- Immutable by default

### Exception Hierarchy (exceptions.py)
```python
class RAGException(Exception):
    pass

class SearchError(RAGException):
    pass
```

Benefits:
- Catch all RAG errors: `except RAGException`
- Catch specific: `except SearchError`
- Clear error types

## Integration

**Used throughout project:**

- `clients.py` → Everywhere (Qdrant, Cloudinary access)
- `exceptions.py` → Error handling in all modules
- `types.py` → Search, RAG, query analysis

## Configuration

All clients use `config.settings`:
```python
from config.settings import config

qdrant = QdrantClient(
    url=config.qdrant.url,
    api_key=config.qdrant.api_key,
    timeout=config.qdrant.timeout
)
```

## Notes

- **Thread-safe**: Singletons are thread-safe
- **Testing**: Use `reset_clients()` to reset state
- **Lazy init**: Clients created on first use
- **Error handling**: All operations can raise custom exceptions
