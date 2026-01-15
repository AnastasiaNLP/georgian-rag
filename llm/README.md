# LLM Response Generation

Claude-powered response generation with multilingual support.

## Files

### `generator.py`

**EnhancedResponseGenerator** - Async LLM response generation.

## Features

- **AsyncAnthropic** - Non-blocking Claude API calls
- **Direct multilingual generation** - 18 languages without final translation
- **Optimized prompts** - 70% shorter language instructions
- **LangSmith tracing** - Performance tracking
- **Four intent types** - Specialized prompts for different query types
- **Error handling** - Timeout and error messages in all languages
- **Disclaimer support** - Auto-translated disclaimers

## Usage
```python
from llm.generator import EnhancedResponseGenerator
from multilingual.multilingual_manager import MultilingualManager

# Initialize
multilingual = MultilingualManager(...)
generator = EnhancedResponseGenerator(
    anthropic_api_key="sk-ant-...",
    langsmith_api_key="lsv2_...",
    multilingual_manager=multilingual,
    disclaimer_manager=disclaimer_manager
)

# Generate response
context = {
    "query_info": {
        "original_query": "What to see in Tbilisi?",
        "target_language": "en",
        "intent": "info_request"
    },
    "search_results": [...],
    "enrichment": {...},
    "images": [...]
}

result = await generator.generate_response(context)
# Returns: {response, language, token_usage, generation_info}
```

## Response Strategy

**Three-stage optimization:**

1. **Documents stay in original language** (no translation)
   - Search results: RU/EN/KA as stored
   - Saves 1-2 seconds per request

2. **LLM generates directly in target language**
   - Optimized language instruction (70% shorter)
   - Allows proper nouns in any language
   - Model: `claude-sonnet-4-20250514`

3. **No final translation needed**
   - Response already in correct language
   - Only disclaimers translated if needed

**Performance:**
- Async API calls (non-blocking)
- 30 second timeout
- max_tokens=800 (faster generation)
- Streaming-ready structure

## Intent Types

Four specialized prompt templates:

### 1. **info_request** (default)
General information queries.

**Prompt style:**
- Comprehensive, engaging (200-300 words)
- Markdown formatting
- Cultural aspects highlighted
- Practical tips included

### 2. **recommendation**
Recommendation queries ("best places for...").

**Prompt style:**
- Top 3-5 suggestions
- WHY each fits user needs
- Practical details (location, access, timing)
- Persuasive language

### 3. **route_planning**
Itinerary and route queries.

**Prompt style:**
- Logical, efficient route
- Travel times and logistics
- Optimal visiting times
- Must-see vs optional stops
- Insider tips

### 4. **follow_up**
Multi-turn conversation continuation.

**Prompt style:**
- Additional details (150-200 words)
- Builds on previous context
- New information not mentioned before
- Maintains enthusiasm

## Multilingual Support

**18 languages** with native error/timeout messages:

- English (EN), Russian (RU), Georgian (KA)
- German (DE), French (FR), Spanish (ES), Italian (IT)
- Dutch (NL), Polish (PL), Czech (CS)
- Chinese (ZH), Japanese (JA), Korean (KO)
- Arabic (AR), Turkish (TR), Hindi (HI)
- Armenian (HY), Azerbaijani (AZ)

## Language Instructions

**Optimized prompts** from `MultilingualManager`:
```python
# Example for Russian
language_instruction = multilingual.get_optimized_language_instruction("ru")
# Returns: "Ответь на русском языке. Имена собственные можно оставлять на латинице."
# (70% shorter than previous version)
```

**Key optimization:**
- Allows proper nouns in Latin (e.g., "Tbilisi", "Narikala")
- Reduces prompt length
- Improves generation quality

## Context Processing

**Template filling with data:**
```python
context = {
    "query_info": {...},
    "search_results": [
        {
            "name": "Narikala Fortress",
            "description": "...",
            "category": "Historical Site",
            "location": "Tbilisi",
            "score": 0.95,
            "image_url": "https://..."
        }
    ],
    "enrichment": {
        "wikipedia_content": "..."
    },
    "images": [
        {"url": "...", "location": "...", "source": "database"}
    ]
}
```

**Processed into prompt:**
- Top 3 search results (descriptions trimmed to 300 chars)
- Wikipedia enrichment (first 200 chars)
- Available images (up to 5)
- Photo URLs when available

## Error Handling

**Timeout (30s):**
```python
try:
    response = await asyncio.wait_for(
        self._call_claude_api_async(prompt),
        timeout=30.0
    )
except asyncio.TimeoutError:
    return await self._get_timeout_message(language)
```

**Error messages:**
- Native language error messages
- Polite, user-friendly
- Suggests retry

## Token Usage

**Tracking:**
```python
result = {
    "token_usage": {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens
    }
}
```

**Optimization:**
- max_tokens=800 (balance quality/speed)
- Temperature=0.7 (creative but focused)
- Trimmed descriptions (300 char limit)
- Trimmed enrichment (200 char limit)

## LangSmith Integration

**Tracing enabled:**
```python
@traceable(name="generate_tourism_response")
async def generate_response(self, context: Dict):
    ...
```

**Tracks:**
- Prompt construction
- API latency
- Token usage
- Response quality

## Disclaimer Support

**Auto-adds and translates disclaimers:**
```python
if self.disclaimer_manager:
    response_text = self.disclaimer_manager.add_disclaimers(response_text)
    
    if target_language not in ["ru", "en"]:
        response_text = await self._translate_disclaimers(
            response_text, 
            target_language
        )
```

## Integration

Used in `pipeline/rag.py`:
```python
# RAG pipeline calls generator
result = await self.response_generator.generate_response({
    "query_info": analysis,
    "search_results": formatted_results,
    "enrichment": enrichment,
    "images": images
})
```

## Performance

**Typical timings:**
- API call: 2-5 seconds (async)
- Prompt building: < 0.1s
- Total generation: 2-6 seconds

**Optimization strategies:**
- Async/await (non-blocking)
- max_tokens=800 (shorter = faster)
- Trimmed context (fewer input tokens)
- No final translation (saves 1-2s)

## Model Configuration

**Claude Sonnet 4:**
- Model: `claude-sonnet-4-20250514`
- Max tokens: 800
- Temperature: 0.7
- Timeout: 30 seconds

**Why Sonnet 4:**
- Best quality/speed balance
- Excellent multilingual support
- Handles 18 languages well
- Reasonable pricing

## Notes

- Always use AsyncAnthropic (non-blocking)
- Language instruction prepended to all prompts
- Images referenced in prompts when available
- Disclaimers only for non-EN/RU languages
- Error messages native to target language
