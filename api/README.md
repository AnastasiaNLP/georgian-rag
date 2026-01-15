# API Models

Pydantic models for FastAPI requests and responses.

## Files

### `models.py`

Defines all API data models:

**Request Models:**

- `ChatRequest` - Main query request with language, conversation_id, top_k
- `SearchRequest` - Search-only request
- `ClearCacheRequest` - Cache management
- `EnrichmentRequest` - Content enrichment trigger

**Response Models:**

- `ChatResponse` - Complete response with sources and metadata
- `Source` - Individual source with id, name, location, score, category, image_url
- `SearchResponse` - Search results
- `HealthResponse` - System health status
- `StatsResponse` - System statistics
- `ErrorResponse` - Error information

**Supporting Models:**

- `LanguageCode` - Enum with 18 supported languages (EN, RU, KA, etc.)
- `WebSocketMessage` - WebSocket message format (for future use)
- `SystemInfo` - System information

## Usage
```python
from api.models import ChatRequest, ChatResponse, Source

# Create request
request = ChatRequest(
    query="What to see in Tbilisi?",
    target_language="en",
    top_k=5
)

# Parse response
response = ChatResponse(
    response="Here are the top attractions...",
    language="en",
    sources=[
        Source(
            id="123",
            name="Narikala Fortress",
            location="Tbilisi",
            score=0.95,
            category="Historical Site",
            image_url="https://..."
        )
    ]
)
```

## Supported Languages

18 languages supported via `LanguageCode` enum:

- English (EN), Russian (RU), Georgian (KA)
- German (DE), French (FR), Spanish (ES), Italian (IT)
- Dutch (NL), Polish (PL), Czech (CS)
- Chinese (ZH), Japanese (JA), Korean (KO)
- Arabic (AR), Turkish (TR), Hindi (HI)
- Armenian (HY), Azerbaijani (AZ)

## Notes

- `Source.image_url` - Links to Cloudinary-hosted images
- `Source.description` - Short description (optional)
- All timestamps use `datetime.now()`
- WebSocket models present but not currently used in production