# Conversation Management

Multi-turn conversation history with Redis-first storage.

## Files

### `manager.py`

**ConversationManager** - Manages conversation history for multi-turn dialogues.

## Features

- **Redis-first storage** with in-memory fallback (Upstash compatible)
- **Automatic conversation creation** with UUID generation
- **Token-aware context windows** (max 2000 tokens ≈ 8000 chars)
- **24-hour TTL** for conversations (auto-cleanup)
- **Metadata tracking** (languages used, sources, topics)
- **History trimming** (max 20 messages per conversation)
- **Statistics tracking** (Redis hits/misses, cache hit rate)

## Usage
```python
from conversation.manager import ConversationManager
from core.clients import get_redis_client

# Initialize
redis_client = get_redis_client()  # or None for in-memory
manager = ConversationManager(
    redis_client=redis_client,
    max_history=20,
    ttl=86400  # 24 hours
)

# Create conversation
conv = manager.create_conversation(
    conversation_id="conv_abc123",  # optional, auto-generates if None
    user_id="user_456"
)

# Add messages
manager.add_message(
    conversation_id="conv_abc123",
    role="user",
    content="What to see in Tbilisi?",
    metadata={"language": "en"}
)

manager.add_message(
    conversation_id="conv_abc123",
    role="assistant",
    content="Here are top attractions...",
    metadata={"language": "en", "sources": ["source_1", "source_2"]}
)

# Get history
history = manager.get_history("conv_abc123", limit=10)

# Get context for LLM
context = manager.get_context_window(
    conversation_id="conv_abc123",
    max_tokens=2000,
    format="string"  # or "list"
)

# Get metadata
metadata = manager.get_conversation_metadata("conv_abc123")
# Returns: {id, created_at, updated_at, user_id, metadata}

# Clear conversation
manager.clear_conversation("conv_abc123")

# Get statistics
stats = manager.get_stats()
# Returns: {total_conversations, total_messages, redis_hits, 
#           redis_misses, cache_hit_rate, in_memory_conversations}
```

## Configuration

- **max_history**: Maximum messages per conversation (default: 20)
  - Older messages automatically trimmed
  - Keeps conversation context manageable

- **ttl**: Time-to-live in seconds (default: 86400 = 24 hours)
  - Redis keys auto-expire after TTL
  - Prevents memory buildup

## Storage Strategy

**Two-level storage:**

1. **Redis** (primary, if available):
   - Key format: `conversation:{conversation_id}`
   - TTL: 24 hours
   - Automatic expiration

2. **In-memory** (fallback):
   - Dictionary storage
   - No TTL (persists until restart)
   - Used when Redis unavailable

## Context Window

**Token-aware formatting:**

- Approximate: 1 token ≈ 4 characters
- max_tokens=2000 → max_chars=8000
- Messages added from newest to oldest until limit
- Two formats:
  - `"string"`: Formatted text with roles
  - `"list"`: Array of message dicts

## Metadata Tracking

**Automatic tracking:**

- `languages_used`: Set of languages in conversation
- `sources_used`: Set of source IDs referenced
- `total_messages`: Message count
- `topics`: Manual topic tags (optional)

## Integration

Used in `pipeline/rag.py` (EnhancedGeorgianRAG):
```python
# RAG pipeline uses conversation context
if conversation_id and self.conversation_manager:
    context = self.conversation_manager.get_context_window(
        conversation_id,
        max_tokens=2000
    )
    # Include context in LLM prompt
```

## Redis Compatibility

**Supports:**
- Standard Redis
- **Upstash Redis** (REST API) 
  - Handles both `bytes` and `str` data
  - Auto-detects format

## Statistics

**Tracked metrics:**

- `total_conversations`: Conversations created
- `total_messages`: Messages added
- `redis_hits`: Successful Redis loads
- `redis_misses`: Redis misses (not found)
- `errors`: Redis/storage errors
- `cache_hit_rate`: Redis hit percentage
- `in_memory_conversations`: Fallback storage count

## Testing

Test file: `tests/test_conversation.py`
```bash
python tests/test_conversation.py
```

## Notes

- **Small memory footprint**: ~20KB per conversation
- **Auto-cleanup**: 24-hour TTL prevents buildup
- **Fallback safe**: Works without Redis
- **No cache pollution**: Separate from query cache
