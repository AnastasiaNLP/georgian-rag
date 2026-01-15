# Multilingual Support

18-language support with auto-detection and Groq translation.

## Files

### `multilingual_manager.py`

**MultilingualManager** - Complete multilingual infrastructure.

## Features

- **18 supported languages**
- **Auto-detection** (langdetect)
- **Translation** (Groq LLM only)
- **Optimized language instructions** (70% shorter)
- **Proper noun preservation** (Latin allowed)
- **Caching** (Redis/in-memory)

## Supported Languages

**Core (3):**
- English (EN), Russian (RU), Georgian (KA)

**European (8):**
- German (DE), French (FR), Spanish (ES), Italian (IT)
- Dutch (NL), Polish (PL), Czech (CS), Portuguese (PT)

**Asian (3):**
- Chinese (ZH), Japanese (JA), Korean (KO)

**Middle Eastern (2):**
- Arabic (AR), Hebrew (HE)

**South Asian (2):**
- Hindi (HI), Bengali (BN)

**Other (3):**
- Turkish (TR), Armenian (HY), Azerbaijani (AZ)

## Usage
```python
from multilingual.multilingual_manager import MultilingualManager

# Initialize (Groq only)
manager = MultilingualManager(
    groq_api_key="gsk_...",
    groq_model="mixtral-8x7b-32768"
)

# Auto-detect language
detected = manager.detect_language("Привет мир")
# Returns: "ru"

# Get language instruction (optimized)
instruction = manager.get_optimized_language_instruction("ru")
# Returns: "Ответь на русском языке. Имена собственные можно оставлять на латинице."

# Translate via Groq
translated = await manager.translate_if_needed(
    text="Hello world",
    target_language="ru",
    source_language="en"
)
# Returns: "Привет мир"

# Get language name
name = manager.get_language_name("ru")
# Returns: "Russian"
```

## Language Detection

**Auto-detect with langdetect:**
```python
# Detect query language
query = "Что посмотреть в Тбилиси?"
detected = manager.detect_language(query)
# Returns: "ru"

# Fallback to English if detection fails
query = "?!@#"
detected = manager.detect_language(query)
# Returns: "en"
```

**Confidence threshold:** 0.8 (below = fallback to EN)

## Translation

**Groq LLM translation:**

- **Model:** `mixtral-8x7b-32768`
- **Strategy:** Prompt-based translation
- **Prompt:** "Translate the following text from {source} to {target}. Maintain tone and style. Text: {text}"
- **Cache:** Redis/in-memory (TTL: 7 days for permanent, 24h for temp)

**Features:**
- Context-aware translation
- Proper noun preservation
- Cultural adaptation
- Idiomatic expressions

**When used:**
- Disclaimers (non-EN/RU)
- Error messages
- Optional query translation

## Optimized Language Instructions

**70% shorter than original** - allows proper nouns in Latin.

**Examples:**
```python
# Russian
"Ответь на русском языке. Имена собственные можно оставлять на латинице."
# English: "Answer in Russian. Proper nouns can be left in Latin."

# Georgian
"უპასუხე ქართულად. საკუთარი სახელები შეიძლება დარჩეს ლათინურად."

# German
"Antworte auf Deutsch. Eigennamen können auf Latein bleiben."

# Chinese
"用中文回答。专有名词可以保留拉丁字母。"
```

**Why optimized:**
- Shorter prompts (fewer tokens)
- Better LLM understanding
- Allows "Tbilisi", "Narikala" in any language
- Improves generation quality

## Caching Strategy

**Two-level cache:**

1. **Permanent cache** (no TTL)
   - Language instructions
   - Common translations
   - System messages

2. **Temporary cache** (24h TTL)
   - Query translations
   - Dynamic content

**Storage:**
- Redis (preferred)
- In-memory (fallback)

## Language Metadata

**LANGUAGE_CONFIGS dictionary:**
```python
{
    "en": {
        "name": "English",
        "native_name": "English",
        "code": "en",
        "groq_supported": True,
        "direction": "ltr"
    },
    "ru": {
        "name": "Russian", 
        "native_name": "Русский",
        "code": "ru",
        "groq_supported": True,
        "direction": "ltr"
    },
    # ... 16 more
}
```

## Integration

**Used by:**

- `llm/generator.py` - Language instructions for Claude
- `pipeline/rag.py` - Query language detection
- `utils/disclaimer.py` - Disclaimer translation
- `fastapi_dashboard.py` - API language validation

## Configuration

**From `config/settings.py`:**
```python
MultilingualConfig:
    supported_languages: [en, ru, ka, de, fr, ...]  # 18 total
    default_language: "en"
    auto_detect: True
    translate_queries: True  # Optional
```

**Environment variables:**
```bash
GROQ_API_KEY=gsk_...
LLM_MODEL=mixtral-8x7b-32768  # Optional, default
```

## Performance

**Typical timings:**

- Language detection: < 0.01s
- Get instruction: < 0.001s (cached)
- Translation (Groq): 1-3s (first time)
- Translation (cached): < 0.05s

**Optimization:**
- Instructions pre-cached at startup
- Translations cached for 24h
- Batch processing where possible

## Error Handling

**Fallbacks:**

1. **Detection fails** → Default to English
2. **Translation fails** → Return original text
3. **Groq unavailable** → Skip translation
4. **Invalid language** → Use English

**Graceful degradation** - system works without translation.

## Language Instruction Format

**Template:**
```
{instruction}

{base_prompt}
```

**Example (Russian):**
```
Ответь на русском языке. Имена собственные можно оставлять на латинице.

You are an expert Georgian tourism guide. A user asked: "Что посмотреть в Тбилиси?"

RELEVANT INFORMATION:
...
```

## Groq Translation

**Prompt template:**
```
Translate the following text from {source_language} to {target_language}.

Instructions:
- Maintain the original tone and style
- Preserve proper nouns (place names, person names)
- Keep markdown formatting intact
- Be culturally appropriate

Text to translate:
{text}

Translation:
```

**Parameters:**
- Model: mixtral-8x7b-32768
- Temperature: 0.3 (consistent translations)
- Max tokens: 2000

## Statistics

**Language usage tracking:**
```python
stats = manager.get_stats()
# Returns:
{
    "total_detections": 150,
    "total_translations": 45,
    "cache_hits": 120,
    "cache_misses": 30,
    "languages_used": {
        "en": 80,
        "ru": 50,
        "de": 20
    }
}
```

## Testing

**Test language detection:**
```python
# English
assert manager.detect_language("Hello world") == "en"

# Russian
assert manager.detect_language("Привет мир") == "ru"

# Georgian
assert manager.detect_language("გამარჯობა") == "ka"
```

**Test translation:**
```python
result = await manager.translate_if_needed(
    "Hello", "ru", "en"
)
assert "Привет" in result or "Здравствуй" in result
```

## Notes

- Auto-detection confidence: 0.8 threshold
- Groq used for all translations (no Google Translate)
- Language instructions optimized for Claude Sonnet 4
- Proper nouns always preserved in Latin
- RTL languages (AR, HE) supported
- Cache saves ~90% of translation calls
- Fallback to English on any error
